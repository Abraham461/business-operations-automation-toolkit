import os
import tempfile
import unittest

from modules.workflow_engine.store import WorkflowStore


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "opspilot.sqlite3")
        self.store = WorkflowStore(self.database_path)
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_workflow_definition(self):
        definition = ["manual_trigger", "read_csv", "validate_rows", "execution_report"]
        saved = self.store.save_workflow("Customer checks", definition)
        loaded = self.store.get_workflow(saved["id"])

        self.assertEqual(loaded["name"], "Customer checks")
        self.assertEqual(loaded["latest_version"]["definition"], definition)
        self.assertEqual(loaded["latest_version"]["version_number"], 1)

    def test_changed_definition_creates_new_version(self):
        first = self.store.save_workflow(
            "Customer checks",
            ["manual_trigger", "read_csv", "execution_report"],
        )
        second = self.store.save_workflow(
            "Customer checks",
            ["manual_trigger", "read_csv", "validate_rows", "execution_report"],
            first["id"],
        )

        self.assertEqual(second["latest_version"]["version_number"], 2)
        self.assertEqual(len(second["versions"]), 2)

    def test_unchanged_definition_does_not_create_duplicate_version(self):
        definition = ["manual_trigger", "read_csv", "execution_report"]
        first = self.store.save_workflow("Customer checks", definition)
        second = self.store.save_workflow("Renamed checks", definition, first["id"])

        self.assertEqual(second["name"], "Renamed checks")
        self.assertEqual(len(second["versions"]), 1)

    def test_execution_history_is_persisted(self):
        saved = self.store.save_workflow(
            "Customer checks",
            ["manual_trigger", "read_csv", "execution_report"],
        )
        execution_id = self.store.create_execution(
            {
                "status": "success",
                "started_at": "2026-11-02T10:00:00+00:00",
                "finished_at": "2026-11-02T10:00:01+00:00",
                "summary": "3 of 3 actions completed.",
                "steps": [],
            },
            saved["id"],
            saved["latest_version"]["id"],
        )
        executions = self.store.list_executions(saved["id"])

        self.assertEqual(executions[0]["id"], execution_id)
        self.assertEqual(executions[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
