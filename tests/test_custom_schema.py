import csv
import os
import tempfile
import unittest

from modules.workflow_engine.engine import run_workflow, validate_workflow


class CustomWorkflowSchemaTests(unittest.TestCase):
    def _csv(self, folder, headers, rows):
        path = os.path.join(folder, "input.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_accepts_business_specific_schema_without_customer_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._csv(folder, ["product", "quantity", "unit_price"], [
                {"product": "Notebook", "quantity": "12", "unit_price": "4.50"},
                {"product": "", "quantity": "0", "unit_price": "2.00"},
            ])
            nodes = [
                "manual_trigger", "read_csv",
                {"type": "validate_rows", "schema": [
                    {"name": "product", "type": "text", "required": True},
                    {"name": "quantity", "type": "integer", "required": True, "min": 1},
                    {"name": "unit_price", "type": "number", "required": True, "min": 0},
                ]},
                "generate_pdfs", "execution_report",
            ]
            result = run_workflow(nodes, source, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Validated 1 of 2", result["steps"][2]["message"])
            self.assertEqual(result["pdf_count"], 1)

    def test_rejects_invalid_and_duplicate_unique_values(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._csv(folder, ["employee_id", "email", "age"], [
                {"employee_id": "E001", "email": "one@example.com", "age": "25"},
                {"employee_id": "E001", "email": "bad-email", "age": "not-a-number"},
            ])
            nodes = [
                "manual_trigger", "read_csv",
                {"type": "validate_rows", "schema": [
                    {"name": "employee_id", "type": "text", "required": True, "unique": True},
                    {"name": "email", "type": "email", "required": True},
                    {"name": "age", "type": "integer", "min": 18, "max": 65},
                ]},
                "execution_report",
            ]
            result = run_workflow(nodes, source, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Validated 1 of 2", result["steps"][2]["message"])
            errors = result["steps"][2]["invalid_rows"][0]["errors"]
            self.assertTrue(any("unique" in error for error in errors))
            self.assertTrue(any("valid email" in error for error in errors))
            self.assertTrue(any("invalid integer" in error for error in errors))

    def test_custom_mapping_targets_schema_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._csv(folder, ["item", "units"], [
                {"item": "Desk", "units": "3"},
            ])
            nodes = [
                "manual_trigger", "read_csv",
                {"type": "map_fields", "mapping": {"product_name": "item", "quantity": "units"}},
                {"type": "validate_rows", "schema": [
                    {"name": "product_name", "type": "text", "required": True},
                    {"name": "quantity", "type": "integer", "required": True, "min": 1},
                ]},
                "execution_report",
            ]
            result = run_workflow(nodes, source, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Mapped 2 field(s)", result["steps"][2]["message"])

    def test_applies_defaults_and_custom_field_error_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self._csv(folder, ["department", "employee_code"], [
                {"department": "", "employee_code": ""},
                {"department": "Finance", "employee_code": "EMP-01"},
            ])
            nodes = [
                "manual_trigger", "read_csv",
                {"type": "validate_rows", "schema": [
                    {"name": "department", "label": "Department", "type": "text",
                     "required": True, "default": "Operations"},
                    {"name": "employee_code", "label": "Employee code", "type": "text",
                     "required": True, "error_message": "Enter a valid employee code."},
                ]},
                "execution_report",
            ]
            result = run_workflow(nodes, source, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Validated 1 of 2", result["steps"][2]["message"])
            self.assertEqual(
                result["steps"][2]["invalid_rows"][0]["errors"],
                ["Enter a valid employee code."],
            )

    def test_rejects_duplicate_or_invalid_schema_fields(self):
        with self.assertRaisesRegex(ValueError, "Duplicate input field"):
            validate_workflow([
                "manual_trigger", "read_csv",
                {"type": "validate_rows", "schema": [
                    {"name": "product", "type": "text"},
                    {"name": "Product", "type": "text"},
                ]},
                "execution_report",
            ])
        with self.assertRaisesRegex(ValueError, "Unsupported data type"):
            validate_workflow([
                "manual_trigger", "read_csv",
                {"type": "validate_rows", "schema": [{"name": "price", "type": "currency"}]},
                "execution_report",
            ])


if __name__ == "__main__":
    unittest.main()
