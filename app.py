import json
import os
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

load_dotenv()

from modules.ai_processing.processor import process_document_text
from modules.api_testing.runner import run_api_test
from modules.document_automation.generator import generate_customer_pdfs

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "generated_files"

for folder in (app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]):
    os.makedirs(folder, exist_ok=True)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/documents")
def documents():
    return render_template("documents.html")


@app.post("/documents/generate")
def documents_generate():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        flash("Choose a CSV file first.", "error")
        return redirect(url_for("documents"))
    if not uploaded_file.filename.lower().endswith(".csv"):
        flash("For this MVP, upload a CSV file.", "error")
        return redirect(url_for("documents"))

    safe_name = secure_filename(uploaded_file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid4().hex}_{safe_name}")
    uploaded_file.save(path)

    try:
        output_path, count = generate_customer_pdfs(path, app.config["OUTPUT_FOLDER"])
        flash(f"Generated {count} sample customer PDF(s).", "success")
        return send_file(output_path, as_attachment=True, download_name="customer_documents.zip")
    except (ValueError, OSError) as exc:
        app.logger.warning("Document generation rejected or failed: %s", exc)
        flash(f"Could not generate documents: {exc}", "error")
        return redirect(url_for("documents"))
    except Exception:
        app.logger.exception("Unexpected document generation failure")
        flash("An unexpected error occurred while generating documents.", "error")
        return redirect(url_for("documents"))


@app.get("/ai")
def ai():
    return render_template("ai.html")


@app.post("/ai/process")
def ai_process():
    uploaded_file = request.files.get("file")
    if (
        not uploaded_file
        or not uploaded_file.filename
        or not uploaded_file.filename.lower().endswith(".txt")
    ):
        flash("Upload a .txt sample document. PDF/image OCR is a planned extension.", "error")
        return redirect(url_for("ai"))

    text = uploaded_file.read().decode("utf-8", errors="replace")[:30000]
    try:
        result = process_document_text(text)
    except Exception:
        app.logger.exception("AI text processing failed")
        flash("AI processing failed. Check your configuration and try again.", "error")
        return redirect(url_for("ai"))
    return render_template("ai.html", result=result)


@app.get("/api-testing")
def api_testing():
    return render_template("api_testing.html")


@app.post("/api-testing/run")
def api_testing_run():
    url = request.form.get("url", "").strip()
    method = request.form.get("method", "GET").upper()
    body_text = request.form.get("body", "").strip()
    expected_status = request.form.get("expected_status", "200").strip()

    try:
        body = json.loads(body_text) if body_text else None
        result = run_api_test(url, method, body, int(expected_status))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        result = {"success": False, "error": str(exc)}
    except Exception:
        app.logger.exception("API test request failed")
        result = {"success": False, "error": "The API request failed. Check the URL and try again."}

    return render_template(
        "api_testing.html",
        result=result,
        previous={
            "url": url,
            "method": method,
            "body": body_text,
            "expected_status": expected_status,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "application": "Business Operations Automation Toolkit"}


@app.errorhandler(413)
def file_too_large(_error):
    flash("The upload exceeds the 12 MB limit.", "error")
    return redirect(url_for("index")), 413


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
