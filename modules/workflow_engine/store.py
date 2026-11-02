import json
import os
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4


def _now():
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    """Small SQLite persistence layer for workflow definitions and executions."""

    def __init__(self, database_path):
        self.database_path = database_path

    def _connect(self):
        parent = os.path.dirname(os.path.abspath(self.database_path))
        os.makedirs(parent, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        connection = self._connect()
        try:
            with connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS workflows (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS workflow_versions (
                        id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                        version_number INTEGER NOT NULL,
                        definition_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(workflow_id, version_number)
                    );
                    CREATE TABLE IF NOT EXISTS workflow_executions (
                        id TEXT PRIMARY KEY,
                        workflow_id TEXT REFERENCES workflows(id) ON DELETE SET NULL,
                        version_id TEXT REFERENCES workflow_versions(id) ON DELETE SET NULL,
                        status TEXT NOT NULL,
                        started_at TEXT,
                        finished_at TEXT,
                        summary TEXT,
                        result_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow
                    ON workflow_executions(workflow_id, created_at DESC);
                    """
                )
        finally:
            connection.close()

    def save_workflow(self, name, definition, workflow_id=None):
        name = (name or "").strip()
        if not name:
            raise ValueError("Enter a workflow name.")
        if len(name) > 100:
            raise ValueError("Workflow names must be 100 characters or fewer.")
        if not isinstance(definition, list):
            raise ValueError("Workflow definition must be a list of actions.")

        workflow_id = workflow_id or uuid4().hex
        now = _now()
        definition_json = json.dumps(definition, separators=(",", ":"), ensure_ascii=False)
        connection = self._connect()
        try:
            with connection:
                existing = connection.execute(
                    "SELECT id FROM workflows WHERE id = ?", (workflow_id,)
                ).fetchone()
                if workflow_id and existing is None and workflow_id != "":
                    if workflow_id and len(workflow_id) != 32:
                        raise KeyError("Workflow not found.")
                if existing is None:
                    connection.execute(
                        "INSERT INTO workflows (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (workflow_id, name, now, now),
                    )
                    version_number = 1
                else:
                    latest = connection.execute(
                        """SELECT version_number, definition_json FROM workflow_versions
                           WHERE workflow_id = ? ORDER BY version_number DESC LIMIT 1""",
                        (workflow_id,),
                    ).fetchone()
                    connection.execute(
                        "UPDATE workflows SET name = ?, updated_at = ? WHERE id = ?",
                        (name, now, workflow_id),
                    )
                    if latest and latest["definition_json"] == definition_json:
                        pass
                    else:
                        version_number = (latest["version_number"] if latest else 0) + 1
                        connection.execute(
                            """INSERT INTO workflow_versions
                               (id, workflow_id, version_number, definition_json, created_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (uuid4().hex, workflow_id, version_number, definition_json, now),
                        )
                if existing is None:
                    connection.execute(
                        """INSERT INTO workflow_versions
                           (id, workflow_id, version_number, definition_json, created_at)
                           VALUES (?, ?, 1, ?, ?)""",
                        (uuid4().hex, workflow_id, definition_json, now),
                    )
        finally:
            connection.close()
        return self.get_workflow(workflow_id)

    def list_workflows(self):
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT w.id, w.name, w.created_at, w.updated_at,
                       COALESCE(MAX(v.version_number), 0) AS latest_version
                FROM workflows w
                LEFT JOIN workflow_versions v ON v.workflow_id = w.id
                GROUP BY w.id
                ORDER BY w.updated_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def get_workflow(self, workflow_id):
        connection = self._connect()
        try:
            workflow = connection.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
            if workflow is None:
                return None
            versions = connection.execute(
                """SELECT id, version_number, definition_json, created_at
                   FROM workflow_versions WHERE workflow_id = ?
                   ORDER BY version_number DESC""",
                (workflow_id,),
            ).fetchall()
            version_items = [
                {
                    "id": row["id"],
                    "version_number": row["version_number"],
                    "definition": json.loads(row["definition_json"]),
                    "created_at": row["created_at"],
                }
                for row in versions
            ]
            result = dict(workflow)
            result["versions"] = version_items
            result["latest_version"] = version_items[0] if version_items else None
            return result
        finally:
            connection.close()

    def get_version(self, workflow_id, version_id):
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT id, workflow_id, version_number, definition_json, created_at
                   FROM workflow_versions WHERE workflow_id = ? AND id = ?""",
                (workflow_id, version_id),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "workflow_id": row["workflow_id"],
                "version_number": row["version_number"],
                "definition": json.loads(row["definition_json"]),
                "created_at": row["created_at"],
            }
        finally:
            connection.close()

    def create_execution(self, result, workflow_id=None, version_id=None):
        execution_id = uuid4().hex
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """INSERT INTO workflow_executions
                       (id, workflow_id, version_id, status, started_at, finished_at,
                        summary, result_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        execution_id,
                        workflow_id,
                        version_id,
                        result.get("status", "failed"),
                        result.get("started_at"),
                        result.get("finished_at"),
                        result.get("summary", result.get("error", "")),
                        json.dumps(result, ensure_ascii=False),
                        _now(),
                    ),
                )
        finally:
            connection.close()
        return execution_id

    def list_executions(self, workflow_id, limit=20):
        connection = self._connect()
        try:
            rows = connection.execute(
                """SELECT id, workflow_id, version_id, status, started_at,
                          finished_at, summary, created_at
                   FROM workflow_executions
                   WHERE workflow_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (workflow_id, max(1, min(int(limit), 100))),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
