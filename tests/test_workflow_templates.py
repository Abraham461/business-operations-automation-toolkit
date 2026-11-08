import csv
import os
import tempfile
import unittest

from modules.workflow_engine.engine import run_workflow, validate_workflow


class WorkflowTemplateTests(unittest.TestCase):
    def _run(self, headers, rows, nodes):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "input.csv")
            with open(source, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(validate_workflow(nodes)[0], "manual_trigger")
            result = run_workflow(nodes, source, folder)
            self.assertEqual(result["status"], "success", result)
            self.assertEqual(result["steps"][-1]["type"], "execution_report")
            return result

    def test_customer_record_template_validates_and_selects_active_records(self):
        nodes = [
            "manual_trigger",
            "read_csv",
            {"type": "validate_rows", "schema": [
                {"name": "customer_id", "label": "Customer ID", "type": "text", "required": True, "unique": True},
                {"name": "customer_name", "label": "Customer name", "type": "text", "required": True},
                {"name": "email", "label": "Email address", "type": "email", "required": True},
                {"name": "service_type", "label": "Service type", "type": "text", "required": False},
                {"name": "status", "label": "Account status", "type": "text", "required": True},
            ]},
            {"type": "conditional_branch", "field": "status", "operator": "equals", "value": "Active"},
            "generate_pdfs",
            "execution_report",
        ]
        result = self._run(
            ["customer_id", "customer_name", "email", "service_type", "status"],
            [
                {"customer_id": "C001", "customer_name": "A. Customer", "email": "a@example.com", "service_type": "Payroll", "status": "Active"},
                {"customer_id": "C002", "customer_name": "B. Customer", "email": "b@example.com", "service_type": "HR", "status": "Inactive"},
            ],
            nodes,
        )
        self.assertEqual(result["matched_rows"], 1)
        self.assertEqual(result["pdf_count"], 1)

    def test_invoice_template_validates_and_filters_positive_amounts(self):
        nodes = [
            "manual_trigger",
            "read_csv",
            {"type": "validate_rows", "schema": [
                {"name": "invoice_number", "label": "Invoice number", "type": "text", "required": True, "unique": True},
                {"name": "supplier_name", "label": "Supplier name", "type": "text", "required": True},
                {"name": "invoice_date", "label": "Invoice date (YYYY-MM-DD)", "type": "date", "required": True},
                {"name": "amount", "label": "Invoice amount", "type": "number", "required": True, "min": 0.01},
                {"name": "currency", "label": "Currency", "type": "text", "required": True},
            ]},
            {"type": "filter_rows", "field": "amount", "operator": "greater_than", "value": "0"},
            "generate_pdfs",
            "execution_report",
        ]
        result = self._run(
            ["invoice_number", "supplier_name", "invoice_date", "amount", "currency"],
            [
                {"invoice_number": "INV-001", "supplier_name": "Northwind", "invoice_date": "2026-10-01", "amount": "125.50", "currency": "USD"},
                {"invoice_number": "INV-002", "supplier_name": "Contoso", "invoice_date": "2026-10-02", "amount": "0", "currency": "USD"},
            ],
            nodes,
        )
        self.assertEqual(result["pdf_count"], 1)
        self.assertIn("Validated 1 of 2", result["steps"][2]["message"])

    def test_employee_onboarding_template_validates_and_generates_records(self):
        nodes = [
            "manual_trigger",
            "read_csv",
            {"type": "validate_rows", "schema": [
                {"name": "employee_id", "label": "Employee ID", "type": "text", "required": True, "unique": True},
                {"name": "full_name", "label": "Full name", "type": "text", "required": True},
                {"name": "department", "label": "Department", "type": "text", "required": True},
                {"name": "start_date", "label": "Start date (YYYY-MM-DD)", "type": "date", "required": True},
                {"name": "manager_email", "label": "Manager email", "type": "email", "required": True},
            ]},
            "generate_pdfs",
            "execution_report",
        ]
        result = self._run(
            ["employee_id", "full_name", "department", "start_date", "manager_email"],
            [
                {"employee_id": "E001", "full_name": "Alex Employee", "department": "Operations", "start_date": "2026-12-01", "manager_email": "manager@example.com"},
            ],
            nodes,
        )
        self.assertEqual(result["pdf_count"], 1)


if __name__ == "__main__":
    unittest.main()
