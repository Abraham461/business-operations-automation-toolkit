import os
import re
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash


ROLES = {"owner", "admin", "builder", "operator", "viewer"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(email):
    normalized = (email or "").strip().casefold()
    if len(normalized) > 254 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


class IdentityStore:
    """SQLite identity and organization-membership foundation.

    This store deliberately does not implement HTTP sessions or route
    authorization. Callers must enforce membership checks on every request.
    """

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
                    CREATE TABLE IF NOT EXISTS organizations (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'suspended', 'closed')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email_normalized TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'disabled')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS memberships (
                        id TEXT PRIMARY KEY,
                        organization_id TEXT NOT NULL
                            REFERENCES organizations(id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL
                            REFERENCES users(id) ON DELETE CASCADE,
                        role TEXT NOT NULL
                            CHECK (role IN ('owner', 'admin', 'builder', 'operator', 'viewer')),
                        status TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'suspended', 'removed')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE (organization_id, user_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_memberships_user_status
                    ON memberships(user_id, status);
                    CREATE INDEX IF NOT EXISTS idx_memberships_org_status
                    ON memberships(organization_id, status);
                    """
                )
        finally:
            connection.close()

    def create_organization(self, name):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Organization name must be between 1 and 120 characters.")
        organization_id = uuid4().hex
        now = _now()
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """INSERT INTO organizations (id, name, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (organization_id, name, now, now),
                )
        finally:
            connection.close()
        return self.get_organization(organization_id)

    def get_organization(self, organization_id):
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT id, name, status, created_at, updated_at
                   FROM organizations WHERE id = ?""",
                (organization_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def create_user(self, email, password):
        email = _normalize_email(email)
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError("Password must contain at least 12 characters.")
        user_id = uuid4().hex
        now = _now()
        password_hash = generate_password_hash(password)
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """INSERT INTO users
                       (id, email_normalized, password_hash, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, email, password_hash, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc
        finally:
            connection.close()
        return self.get_user(user_id)

    def get_user(self, user_id):
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT id, email_normalized AS email, status, created_at, updated_at
                   FROM users WHERE id = ?""",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def authenticate(self, email, password):
        try:
            email = _normalize_email(email)
        except ValueError:
            return None
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT id, email_normalized, password_hash, status
                   FROM users WHERE email_normalized = ?""",
                (email,),
            ).fetchone()
            if (
                row is None
                or row["status"] != "active"
                or not isinstance(password, str)
                or not check_password_hash(row["password_hash"], password)
            ):
                return None
            return {"id": row["id"], "email": row["email_normalized"]}
        finally:
            connection.close()

    def add_membership(self, organization_id, user_id, role):
        role = (role or "").strip().lower()
        if role not in ROLES:
            raise ValueError("Choose a valid organization role.")
        membership_id = uuid4().hex
        now = _now()
        connection = self._connect()
        try:
            with connection:
                organization = connection.execute(
                    "SELECT status FROM organizations WHERE id = ?",
                    (organization_id,),
                ).fetchone()
                user = connection.execute(
                    "SELECT status FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                if organization is None or user is None:
                    raise ValueError("Organization or user was not found.")
                if organization["status"] != "active" or user["status"] != "active":
                    raise ValueError("Only active organizations and users can be members.")
                connection.execute(
                    """INSERT INTO memberships
                       (id, organization_id, user_id, role, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (membership_id, organization_id, user_id, role, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("This user already has a membership in the organization.") from exc
        finally:
            connection.close()
        return self.get_membership(organization_id, user_id)

    def get_membership(self, organization_id, user_id):
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT m.id, m.organization_id, m.user_id, m.role, m.status,
                          m.created_at, m.updated_at,
                          o.name AS organization_name, o.status AS organization_status,
                          u.email_normalized AS user_email, u.status AS user_status
                   FROM memberships m
                   JOIN organizations o ON o.id = m.organization_id
                   JOIN users u ON u.id = m.user_id
                   WHERE m.organization_id = ? AND m.user_id = ?""",
                (organization_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list_active_memberships(self, user_id):
        connection = self._connect()
        try:
            rows = connection.execute(
                """SELECT m.organization_id, m.role, o.name AS organization_name
                   FROM memberships m
                   JOIN organizations o ON o.id = m.organization_id
                   JOIN users u ON u.id = m.user_id
                   WHERE m.user_id = ?
                     AND m.status = 'active'
                     AND o.status = 'active'
                     AND u.status = 'active'
                   ORDER BY o.name COLLATE NOCASE""",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
