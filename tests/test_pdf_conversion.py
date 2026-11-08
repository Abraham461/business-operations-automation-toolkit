import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from openpyxl import load_workbook

from modules.document_automation.excel_exporter import export_tables_to_excel
from modules.document_automation.pdf_extractor import (
    PDFExtractionError,
    extract_pdf_tables,
)


class PDFTableExtractionTests(unittest.TestCase):
    def _make_pdf_placeholder(self, folder):
        path = os.path.join(folder, "sample.pdf")
        with open(path, "wb") as handle:
            handle.write(b"%PDF-1.4 test fixture")
        return path

    @patch("modules.document_automation.pdf_extractor.pdfplumber.open")
    def test_extracts_tables_from_multiple_pages(self, open_mock):
        page_one = MagicMock()
        page_one.extract_text.return_value = "Customer table"
        page_one.extract_tables.return_value = [
            [["Name", "Amount"], ["Alex", "100"]]
        ]
        page_two = MagicMock()
        page_two.extract_text.return_value = "Invoice table"
        page_two.extract_tables.return_value = [
            [["Invoice", "Status"], ["INV-1", "Paid"]]
        ]
        document = MagicMock()
        document.pages = [page_one, page_two]
        open_mock.return_value.__enter__.return_value = document

        with tempfile.TemporaryDirectory() as folder:
            result = extract_pdf_tables(self._make_pdf_placeholder(folder))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["page"], 2)
        self.assertEqual(result[1]["rows"][1], ["INV-1", "Paid"])

    @patch("modules.document_automation.pdf_extractor.pdfplumber.open")
    def test_reports_scanned_pdf_when_no_text_exists(self, open_mock):
        page = MagicMock()
        page.extract_text.return_value = None
        page.extract_tables.return_value = []
        document = MagicMock()
        document.pages = [page]
        open_mock.return_value.__enter__.return_value = document

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(PDFExtractionError, "scanned PDF"):
                extract_pdf_tables(self._make_pdf_placeholder(folder))

    @patch("modules.document_automation.pdf_extractor.pdfplumber.open")
    def test_reports_text_pdf_without_detectable_tables(self, open_mock):
        page = MagicMock()
        page.extract_text.return_value = "This PDF contains paragraphs."
        page.extract_tables.return_value = []
        document = MagicMock()
        document.pages = [page]
        open_mock.return_value.__enter__.return_value = document

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(PDFExtractionError, "No tables were detected"):
                extract_pdf_tables(self._make_pdf_placeholder(folder))

    def test_rejects_empty_pdf_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "empty.pdf")
            open(path, "wb").close()
            with self.assertRaisesRegex(PDFExtractionError, "empty"):
                extract_pdf_tables(path)


class ExcelExportTests(unittest.TestCase):
    def test_exports_each_table_to_a_separate_sheet(self):
        tables = [
            {"page": 1, "rows": [["Name", "Amount"], ["Alex", "100"]]},
            {"page": 2, "rows": [["Invoice", "Status"], ["INV-1", "Paid"]]},
        ]
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, "result.xlsx")
            export_tables_to_excel(tables, output)
            workbook = load_workbook(output, data_only=True)

        self.assertEqual(len(workbook.sheetnames), 2)
        first = workbook[workbook.sheetnames[0]]
        self.assertEqual(first["A1"].value, "Name")
        self.assertEqual(first["B2"].value, "100")
        self.assertEqual(first.freeze_panes, "A2")

    def test_generates_unique_headers_for_blank_and_duplicate_names(self):
        tables = [{"page": 1, "rows": [["Name", "Name", ""], ["Alex", "A.", "x"]]}]
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, "result.xlsx")
            export_tables_to_excel(tables, output)
            workbook = load_workbook(output, data_only=True)

        headers = [cell.value for cell in workbook.active[1]]
        self.assertEqual(headers, ["Name", "Name (2)", "Column 3"])


if __name__ == "__main__":
    unittest.main()
