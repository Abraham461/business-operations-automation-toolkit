import csv
import os
import tempfile
import unittest

from modules.workflow_engine.engine import run_workflow, validate_workflow


class WorkflowEngineTests(unittest.TestCase):
    def _make_csv(self, folder, rows):
        source_path = os.path.join(folder, "sample.csv")
        with open(source_path, "w", newline="", encoding="utf-8") as source:
            writer = csv.DictWriter(
                source,
                fieldnames=["customer_name", "customer_id", "email", "plan"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return source_path

    def test_rejects_workflow_without_manual_trigger(self):
        with self.assertRaises(ValueError):
            validate_workflow(["read_csv", "validate_rows", "execution_report"])

    def test_rejects_missing_csv_reader(self):
        with self.assertRaises(ValueError):
            validate_workflow(["manual_trigger", "validate_rows", "execution_report"])

    def test_rejects_condition_before_validation(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger",
                "read_csv",
                {"type": "conditional_branch", "field": "plan", "operator": "equals", "value": "VIP"},
                "validate_rows",
                "execution_report",
            ])

    def test_rejects_unsupported_condition_operator(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger",
                "read_csv",
                "validate_rows",
                {"type": "conditional_branch", "field": "plan", "operator": "exec", "value": "VIP"},
                "execution_report",
            ])

    def test_runs_sequential_csv_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample Customer",
                "customer_id": "C001",
                "email": "sample@example.com",
                "plan": "Standard",
            }])
            result = run_workflow(
                ["manual_trigger", "read_csv", "validate_rows", "execution_report"],
                source_path,
                folder,
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["steps"]), 4)

    def test_condition_matches_rows_case_insensitively(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [
                {"customer_name": "VIP One", "customer_id": "C001", "email": "one@example.com", "plan": "VIP"},
                {"customer_name": "Regular", "customer_id": "C002", "email": "two@example.com", "plan": "Standard"},
            ])
            nodes = [
                "manual_trigger",
                "read_csv",
                "validate_rows",
                {"type": "conditional_branch", "field": "plan", "operator": "equals", "value": "vip"},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["matched_rows"], 1)
            self.assertIn("TRUE branch", result["steps"][3]["message"])

    def test_false_branch_skips_pdf_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Regular",
                "customer_id": "C001",
                "email": "regular@example.com",
                "plan": "Standard",
            }])
            nodes = [
                "manual_trigger",
                "read_csv",
                "validate_rows",
                {"type": "conditional_branch", "field": "plan", "operator": "equals", "value": "VIP"},
                "generate_pdfs",
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["steps"][4]["status"], "skipped")
            self.assertIsNone(result["archive"])

    def test_condition_requires_existing_csv_column(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample",
                "customer_id": "C001",
                "email": "sample@example.com",
                "plan": "VIP",
            }])
            nodes = [
                "manual_trigger",
                "read_csv",
                "validate_rows",
                {"type": "conditional_branch", "field": "unknown_column", "operator": "equals", "value": "VIP"},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["steps"][3]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
