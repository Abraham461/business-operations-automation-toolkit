"""Flask routes for general-purpose PDF table conversion."""
import os
from uuid import uuid4

from flask import Blueprint, current_app, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from modules.document_automation.excel_exporter import export_tables_to_excel
from modules.document_automation.pdf_extractor import PDFExtractionError, extract_pdf_tables

pdf_conversion_bp = Blueprint("pdf_conversion", __name__)


@pdf_conversion_bp.post("/documents/convert")
def convert_pdf():
    uploaded = request.files.get("pdf_file")
    if not uploaded or not uploaded.filename:
        return render_template(
            "pdf_conversion_result.html",
            error="Choose a PDF file to convert.",
        ), 400

    safe_name = secure_filename(uploaded.filename)
    if not safe_name.lower().endswith(".pdf"):
        return render_template(
            "pdf_conversion_result.html",
            error="Only PDF files are supported by this converter.",
        ), 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    output_dir = current_app.config["OUTPUT_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    token = uuid4().hex
    source_path = os.path.join(upload_dir, f"{token}_{safe_name}")
    output_name = f"{token}_converted.xlsx"
    output_path = os.path.join(output_dir, output_name)
    uploaded.save(source_path)

    try:
        tables = extract_pdf_tables(source_path)
        export_tables_to_excel(tables, output_path)
    except PDFExtractionError as exc:
        current_app.logger.info("PDF conversion could not extract tables: %s", exc)
        return render_template("pdf_conversion_result.html", error=str(exc)), 422
    except Exception:
        current_app.logger.exception("Unexpected PDF-to-Excel conversion failure")
        return render_template(
            "pdf_conversion_result.html",
            error="The PDF could not be converted due to an unexpected error.",
        ), 500
    finally:
        try:
            os.remove(source_path)
        except OSError:
            current_app.logger.warning("Could not remove temporary PDF upload: %s", source_path)

    preview = []
    for table_index, table in enumerate(tables, start=1):
        rows = table.get("rows") or []
        if rows:
            preview.append({
                "title": f"Page {table.get('page', table_index)} · Table {table_index}",
                "headers": rows[0],
                "rows": rows[1:11],
                "total_rows": max(len(rows) - 1, 0),
            })

    return render_template(
        "pdf_conversion_result.html",
        tables=preview,
        table_count=len(tables),
        download_url=url_for("pdf_conversion.download_excel", token=token),
        filename=f"{os.path.splitext(safe_name)[0]}_converted.xlsx",
    )


@pdf_conversion_bp.get("/documents/convert/download/<token>")
def download_excel(token):
    if not token.isalnum() or len(token) != 32:
        return {"error": "Invalid download reference."}, 400
    output_path = os.path.join(
        current_app.config["OUTPUT_FOLDER"], f"{token}_converted.xlsx"
    )
    if not os.path.isfile(output_path):
        return {"error": "This conversion file is no longer available. Convert the PDF again."}, 404
    return send_file(
        output_path,
        as_attachment=True,
        download_name="converted_tables.xlsx",
    )
