import csv
import os
import tempfile
import unittest

from modules.workflow_engine.engine import run_workflow, validate_workflow
from unittest.mock import patch


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

    def test_maps_source_columns_before_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "mapped.csv")
            with open(source_path, "w", newline="", encoding="utf-8") as source:
                writer = csv.DictWriter(source, fieldnames=["full_name", "ref", "contact", "tier"])
                writer.writeheader()
                writer.writerow({
                    "full_name": "Mapped Customer",
                    "ref": "M001",
                    "contact": "mapped@example.com",
                    "tier": "VIP",
                })
            nodes = [
                "manual_trigger",
                "read_csv",
                {
                    "type": "map_fields",
                    "mapping": {
                        "customer_name": "full_name",
                        "customer_id": "ref",
                        "email": "contact",
                        "plan": "tier",
                    },
                },
                "validate_rows",
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Mapped 4 field(s)", result["steps"][2]["message"])

    def test_rejects_mapping_with_missing_source_column(self):
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
                {"type": "map_fields", "mapping": {"customer_name": "full_name"}},
                "validate_rows",
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["steps"][2]["status"], "failed")

    def test_rejects_mapping_after_validation(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger",
                "read_csv",
                "validate_rows",
                {"type": "map_fields", "mapping": {"customer_name": "name"}},
                "execution_report",
            ])

    def test_filter_rows_keeps_only_matching_valid_records(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [
                {"customer_name": "VIP One", "customer_id": "C001", "email": "one@example.com", "plan": "VIP"},
                {"customer_name": "Regular", "customer_id": "C002", "email": "two@example.com", "plan": "Standard"},
                {"customer_name": "VIP Two", "customer_id": "C003", "email": "three@example.com", "plan": "VIP"},
            ])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "filter_rows", "field": "plan", "operator": "equals", "value": "VIP"},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Kept 2 of 3 valid row(s)", result["steps"][3]["message"])

    def test_filter_rows_limits_records_sent_to_pdf_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [
                {"customer_name": "VIP One", "customer_id": "C001", "email": "one@example.com", "plan": "VIP"},
                {"customer_name": "Regular", "customer_id": "C002", "email": "two@example.com", "plan": "Standard"},
                {"customer_name": "VIP Two", "customer_id": "C003", "email": "three@example.com", "plan": "VIP"},
            ])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "filter_rows", "field": "plan", "operator": "equals", "value": "VIP"},
                "generate_pdfs", "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["pdf_count"], 2)
            self.assertEqual(result["steps"][4]["status"], "success")

    def test_filter_with_no_matches_skips_pdf_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Regular",
                "customer_id": "C001",
                "email": "regular@example.com",
                "plan": "Standard",
            }])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "filter_rows", "field": "plan", "operator": "equals", "value": "VIP"},
                "generate_pdfs", "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["steps"][4]["status"], "skipped")
            self.assertIsNone(result["archive"])

    def test_filter_rows_supports_contains_and_numeric_comparisons(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "amounts.csv")
            with open(source_path, "w", newline="", encoding="utf-8") as source:
                writer = csv.DictWriter(source, fieldnames=[
                    "customer_name", "customer_id", "email", "plan", "amount"
                ])
                writer.writeheader()
                writer.writerows([
                    {"customer_name": "A", "customer_id": "1", "email": "a@example.com", "plan": "VIP", "amount": "250"},
                    {"customer_name": "B", "customer_id": "2", "email": "b@example.com", "plan": "Standard", "amount": "80"},
                ])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "filter_rows", "field": "amount", "operator": "greater_than", "value": "100"},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Kept 1 of 2 valid row(s)", result["steps"][3]["message"])

    def test_rejects_filter_before_validation(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger", "read_csv",
                {"type": "filter_rows", "field": "plan", "operator": "equals", "value": "VIP"},
                "validate_rows", "execution_report",
            ])

    def test_rejects_filter_with_unsupported_operator(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "filter_rows", "field": "plan", "operator": "python", "value": "VIP"},
                "execution_report",
            ])


    def test_set_variables_resolves_prior_variables(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample", "customer_id": "C001",
                "email": "sample@example.com", "plan": "VIP",
            }])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "set_variables", "values": {
                    "api_base": "https://api.example.com",
                    "customer_ref": "C001",
                }},
                {"type": "set_variables", "values": {
                    "endpoint": "{{api_base}}/customers/{{customer_ref}}",
                }},
                {"type": "http_request", "method": "GET", "url": "https://api.example.com/check"},
                "execution_report",
            ]
            with patch(
                "modules.workflow_engine.engine.run_http_action",
                return_value={"method": "GET", "status_code": 200, "variables": {}},
            ) as http_mock:
                result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Set 1 workflow variable(s)", result["steps"][4]["message"])
            self.assertEqual(http_mock.call_args.args[1]["endpoint"], "https://api.example.com/customers/C001")

    def test_set_variables_rejects_missing_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample", "customer_id": "C001",
                "email": "sample@example.com", "plan": "VIP",
            }])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "set_variables", "values": {"copy": "{{unknown_value}}"}},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "failed")
            self.assertIn("has not been defined", result["steps"][3]["message"])

    def test_parse_json_extracts_nested_and_array_values(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample", "customer_id": "C001",
                "email": "sample@example.com", "plan": "VIP",
            }])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "set_variables", "values": {
                    "api_response": '{"data":{"customer":{"id":"C100"},"items":[{"code":"A1"}]}}'
                }},
                {"type": "parse_json", "source_variable": "api_response",
                 "extract": {"external_id": "data.customer.id", "item_code": "data.items.0.code"}},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Parsed JSON and created 2", result["steps"][4]["message"])


    def test_http_response_can_be_parsed_by_a_later_action(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample", "customer_id": "C001",
                "email": "sample@example.com", "plan": "VIP",
            }])
            response_payload = {"data": {"customer": {"id": "C900"}}}
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "http_request", "method": "GET",
                 "url": "https://api.example.com/customer",
                 "response_variable": "api_response"},
                {"type": "parse_json", "source_variable": "api_response",
                 "extract": {"external_customer_id": "data.customer.id"}},
                "execution_report",
            ]
            with patch(
                "modules.workflow_engine.engine.run_http_action",
                return_value={"method": "GET", "status_code": 200,
                              "variables": {}, "response": response_payload},
            ):
                result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("Parsed JSON and created 1", result["steps"][4]["message"])

    def test_parse_json_rejects_invalid_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample", "customer_id": "C001",
                "email": "sample@example.com", "plan": "VIP",
            }])
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "set_variables", "values": {"payload": "not-json"}},
                {"type": "parse_json", "source_variable": "payload", "extract": {"id": "data.id"}},
                "execution_report",
            ]
            result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "failed")
            self.assertIn("does not contain valid JSON", result["steps"][4]["message"])

    def test_variable_action_validates_names_and_types(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "set_variables", "values": {"bad-name": "value"}},
                "execution_report",
            ])

    def test_ai_action_sends_csv_column_text_and_chains_variables(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "ai_input.csv")
            with open(source_path, "w", newline="", encoding="utf-8") as source:
                writer = csv.DictWriter(source, fieldnames=[
                    "customer_name", "customer_id", "email", "plan", "description"
                ])
                writer.writeheader()
                writer.writerow({
                    "customer_name": "Sample", "customer_id": "C001",
                    "email": "sample@example.com", "plan": "VIP",
                    "description": "Customer requested an address update.",
                })
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "ai_process", "field": "description"},
                {"type": "http_request", "method": "POST", "url": "https://api.example.com/summary"},
                "execution_report",
            ]
            with patch("modules.workflow_engine.engine.process_document_text", return_value={
                "mode": "openrouter",
                "summary": "Customer requests an address update.",
                "key_details": ["Address update requested."],
            }) as ai_mock, patch(
                "modules.workflow_engine.engine.run_http_action",
                return_value={"method": "POST", "status_code": 200, "variables": {}},
            ) as http_mock:
                result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertIn("address update", ai_mock.call_args.args[0].lower())
            self.assertEqual(http_mock.call_args.args[1]["ai_summary"], "Customer requests an address update.")
            self.assertEqual(http_mock.call_args.args[1]["ai_key_details"], "Address update requested.")

    def test_ai_action_joins_multiple_rows_with_newlines(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "ai_rows.csv")
            with open(source_path, "w", newline="", encoding="utf-8") as source:
                writer = csv.DictWriter(source, fieldnames=[
                    "customer_name", "customer_id", "email", "plan", "description"
                ])
                writer.writeheader()
                for number, text_value in enumerate(["First note", "Second note"], start=1):
                    writer.writerow({
                        "customer_name": f"Customer {number}", "customer_id": f"C00{number}",
                        "email": f"customer{number}@example.com", "plan": "VIP",
                        "description": text_value,
                    })
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "ai_process", "field": "description"},
                "execution_report",
            ]
            with patch("modules.workflow_engine.engine.process_document_text", return_value={
                "mode": "demo", "summary": "Combined", "key_details": []
            }) as ai_mock:
                result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(ai_mock.call_args.args[0], "First note\nSecond note")

    def test_ai_action_rejects_invalid_variable_names(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "ai_process", "field": "description", "output_variable": "bad-name"},
                "execution_report",
            ])

    def test_http_request_action_chains_extracted_variables(self):
        with tempfile.TemporaryDirectory() as folder:
            source_path = self._make_csv(folder, [{
                "customer_name": "Sample",
                "customer_id": "C001",
                "email": "sample@example.com",
                "plan": "VIP",
            }])
            fake_result = {
                "method": "GET",
                "status_code": 200,
                "variables": {"access_token": "token-123"},
            }
            nodes = [
                "manual_trigger", "read_csv", "validate_rows",
                {
                    "type": "http_request",
                    "method": "GET",
                    "url": "https://api.example.com/auth",
                    "extract": {"access_token": "access_token"},
                },
                "execution_report",
            ]
            with patch("modules.workflow_engine.engine.run_http_action", return_value=fake_result) as mocked:
                result = run_workflow(nodes, source_path, folder)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["steps"][3]["status"], "success")
            self.assertEqual(mocked.call_args.args[1], {"access_token": "token-123"})

    def test_http_request_config_rejects_unsupported_method(self):
        with self.assertRaises(ValueError):
            validate_workflow([
                "manual_trigger", "read_csv", "validate_rows",
                {"type": "http_request", "method": "TRACE", "url": "https://api.example.com"},
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
