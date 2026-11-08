"""Extract tabular data from text-based PDF documents."""
import os

import pdfplumber


class PDFExtractionError(ValueError):
    """Raised when a PDF cannot be converted into tabular data."""


def extract_pdf_tables(pdf_path):
    """Return detected tables as page-numbered row collections.

    The first row of each detected table is treated as its header when exporting.
    Original cell values are preserved; this module does not use AI to invent data.
    """
    if not os.path.isfile(pdf_path):
        raise PDFExtractionError("The uploaded PDF could not be found.")

    if os.path.getsize(pdf_path) == 0:
        raise PDFExtractionError("The uploaded PDF is empty.")

    tables = []
    has_extractable_text = False

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise PDFExtractionError("The PDF does not contain any pages.")

            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    has_extractable_text = True

                for raw_table in page.extract_tables() or []:
                    rows = []
                    for raw_row in raw_table or []:
                        row = [
                            str(cell).strip() if cell is not None else ""
                            for cell in (raw_row or [])
                        ]
                        if any(cell for cell in row):
                            rows.append(row)

                    if rows:
                        tables.append({"page": page_number, "rows": rows})
    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError(
            "The PDF could not be read. Make sure it is a valid, unencrypted PDF."
        ) from exc

    if not tables:
        if not has_extractable_text:
            raise PDFExtractionError(
                "No selectable text was found. This appears to be a scanned PDF. "
                "OCR support is not included in this version."
            )
        raise PDFExtractionError(
            "No tables were detected in this PDF. Try a PDF with clearly structured "
            "rows and columns. OCR and free-form text conversion are not included yet."
        )

    return tables
