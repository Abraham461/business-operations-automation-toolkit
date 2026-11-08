import csv
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from modules.ai_processing.processor import process_document_text
from modules.api_testing.runner import run_api_test
from modules.document_automation.generator import generate_customer_pdfs


class DocumentAutomationTests(unittest.TestCase):
    def test_generates_one_pdf_per_valid_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "customers.csv")
            output = os.path.join(temp_dir, "output")
            with open(source, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["customer_name", "customer_id", "email", "plan"])
                writer.writeheader()
                writer.writerow({"customer_name": "Alex Demo", "customer_id": "C-001", "email": "alex@example.test", "plan": "Basic"})
                writer.writerow({"customer_name": "Sam Demo", "customer_id": "C/002", "email": "sam@example.test", "plan": "Plus"})
            zip_path, count = generate_customer_pdfs(source, output)
            self.assertEqual(count, 2)
            self.assertTrue(os.path.isfile(zip_path))

    def test_accepts_arbitrary_csv_columns_without_customer_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "sales.csv")
            output = os.path.join(temp_dir, "output")
            with open(source, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["product", "quantity", "unit_price"])
                writer.writeheader()
                writer.writerow({"product": "Notebook", "quantity": "12", "unit_price": "4.50"})
            zip_path, count = generate_customer_pdfs(source, output)
            self.assertEqual(count, 1)
            self.assertTrue(os.path.isfile(zip_path))

    def test_rejects_duplicate_headers_instead_of_losing_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "duplicate.csv")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("name,name\\nAlex,Sam\\n")
            with self.assertRaisesRegex(ValueError, "duplicate column names"):
                generate_customer_pdfs(source, temp_dir)


class ApiTestingTests(unittest.TestCase):
    @patch("modules.api_testing.runner.requests.request")
    def test_reports_expected_status(self, request_mock):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"id": 1}
        response.headers = {"Content-Type": "application/json"}
        response.elapsed.total_seconds.return_value = 0.025
        request_mock.return_value = response
        result = run_api_test("https://example.test/resource")
        self.assertTrue(result["success"])
        self.assertEqual(result["response_body"], {"id": 1})
        request_mock.assert_called_once()

    def test_rejects_invalid_scheme(self):
        with self.assertRaises(ValueError):
            run_api_test("file:///etc/passwd")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(ValueError):
            run_api_test("https://user:secret@example.test/path")


class AiProcessingTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_demo_mode_without_api_key(self):
        result = process_document_text("A fictional sample document.")
        self.assertEqual(result["mode"], "demo")
        self.assertTrue(result["summary"])


if __name__ == "__main__":
    unittest.main()
