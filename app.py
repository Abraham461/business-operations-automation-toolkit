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
from modules.document_automation.routes import pdf_conversion_bp
from modules.workflow_engine.engine import run_workflow, validate_workflow
from modules.workflow_engine.store import WorkflowStore

app = Flask(__name__)
app.register_blueprint(pdf_conversion_bp)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "generated_files"
app.config["DATABASE_PATH"] = os.getenv(
    "OPSPILOT_DATABASE", os.path.join(app.instance_path, "opspilot.sqlite3")
)

for folder in (app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]):
    os.makedirs(folder, exist_ok=True)

workflow_store = WorkflowStore(app.config["DATABASE_PATH"])
workflow_store.initialize()


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
        flash("Please upload a valid CSV file.", "error")
        return redirect(url_for("documents"))

    safe_name = secure_filename(uploaded_file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid4().hex}_{safe_name}")
    uploaded_file.save(path)

    try:
        output_path, count = generate_customer_pdfs(path, app.config["OUTPUT_FOLDER"])
        flash(f"Generated {count} PDF record(s) from your CSV.", "success")
        return send_file(output_path, as_attachment=True, download_name="csv_records.zip")
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


@app.get("/workflows")
def workflows():
    return render_template("workflows.html")


@app.get("/api/workflows")
def api_workflows_list():
    return {"workflows": workflow_store.list_workflows()}


@app.post("/api/workflows")
def api_workflows_save():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "")
    nodes = payload.get("nodes")
    workflow_id = payload.get("id")
    try:
        validate_workflow(nodes)
        saved = workflow_store.save_workflow(name, nodes, workflow_id)
        return {"workflow": saved}, 200 if workflow_id else 201
    except KeyError:
        return {"error": "Workflow not found. Refresh the workflow list and try again."}, 404
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}, 400


@app.get("/api/workflows/<workflow_id>")
def api_workflows_get(workflow_id):
    saved = workflow_store.get_workflow(workflow_id)
    if saved is None:
        return {"error": "Workflow not found."}, 404
    return {"workflow": saved}


@app.get("/api/workflows/<workflow_id>/executions")
def api_workflow_executions(workflow_id):
    if workflow_store.get_workflow(workflow_id) is None:
        return {"error": "Workflow not found."}, 404
    return {"executions": workflow_store.list_executions(workflow_id)}


@app.post("/workflows/run")
def workflows_run():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".csv"):
        return {"status": "failed", "error": "Upload a CSV file to start the workflow.", "steps": []}, 400
    try:
        nodes = json.loads(request.form.get("workflow", "[]"))
        validate_workflow(nodes)
        workflow_id = request.form.get("workflow_id") or None
        version_id = request.form.get("version_id") or None
        if workflow_id:
            saved = workflow_store.get_workflow(workflow_id)
            if saved is None:
                return {"status": "failed", "error": "Saved workflow not found. Refresh and try again.", "steps": []}, 404
            if version_id:
                version = workflow_store.get_version(workflow_id, version_id)
                if version is None or version["definition"] != nodes:
                    return {"status": "failed", "error": "The selected saved version does not match the current canvas. Save or reload the workflow before running.", "steps": []}, 409
        elif version_id:
            return {"status": "failed", "error": "A workflow version requires a saved workflow.", "steps": []}, 400

        safe_name = secure_filename(uploaded_file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid4().hex}_{safe_name}")
        uploaded_file.save(path)
        result = run_workflow(nodes, path, app.config["OUTPUT_FOLDER"])
        result.pop("archive", None)
        execution_id = workflow_store.create_execution(result, workflow_id, version_id)
        result["execution_id"] = execution_id
        if result["status"] == "success":
            result["download_url"] = url_for("workflow_download")
        return result, (200 if result["status"] == "success" else 422)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "failed", "error": str(exc), "steps": []}, 400
    except Exception:
        app.logger.exception("Workflow execution failed")
        return {"status": "failed", "error": "The workflow failed unexpectedly.", "steps": []}, 500


@app.get("/workflows/download")
def workflow_download():
    archive = os.path.join(app.config["OUTPUT_FOLDER"], "customer_documents.zip")
    if not os.path.isfile(archive):
        return {"error": "Run a successful document workflow first."}, 404
    return send_file(archive, as_attachment=True, download_name="customer_documents.zip")


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
