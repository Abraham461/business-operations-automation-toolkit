import csv
import os
import tempfile
import unittest

from modules.workflow_engine.engine import run_workflow, validate_workflow


class WorkflowEngineTests(unittest.TestCase):
    def test_rejects_workflow_without_manual_trigger(self):
        with self.assertRaises(ValueError):
            validate_workflow(["read_csv", "execution_report"])

    def test_rejects_missing_csv_reader(self):
        with self.assertRaises(ValueError):
            validate_workflow(["manual_trigger", "execution_report"])

    def test_runs_sequential_csv_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "sample.csv")
            with open(source_path, "w", newline="", encoding="utf-8") as source:
                writer = csv.DictWriter(
                    source,
                    fieldnames=["customer_name", "customer_id", "email", "plan"],
                )
                writer.writeheader()
                writer.writerow({
                    "customer_name": "Sample Customer",
                    "customer_id": "C001",
                    "email": "sample@example.com",
                    "plan": "Standard",
                })
            nodes = ["manual_trigger", "read_csv", "validate_rows", "execution_report"]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["steps"]), 4)
            self.assertTrue(all(step["status"] == "success" for step in result["steps"]))


if __name__ == "__main__":
    unittest.main()
