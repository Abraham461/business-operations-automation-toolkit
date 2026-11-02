import csv
from datetime import datetime, timezone

from modules.document_automation.generator import generate_customer_pdfs

ALLOWED_NODES = {"manual_trigger", "read_csv", "validate_rows", "generate_pdfs", "execution_report"}
REQUIRED_COLUMNS = {"customer_name", "customer_id", "email", "plan"}


def validate_workflow(nodes):
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Add at least one workflow action.")
    if len(nodes) > 20:
        raise ValueError("A workflow can contain at most 20 actions in this MVP.")
    types = [node.get("type") if isinstance(node, dict) else node for node in nodes]
    if any(node_type not in ALLOWED_NODES for node_type in types):
        raise ValueError("The workflow contains an unsupported action.")
    if types[0] != "manual_trigger" or types.count("manual_trigger") != 1:
        raise ValueError("A workflow must start with exactly one Manual trigger.")
    if types.count("read_csv") != 1:
        raise ValueError("Add exactly one Read CSV action.")
    if "validate_rows" in types and types.index("validate_rows") < types.index("read_csv"):
        raise ValueError("Validate rows must follow Read CSV.")
    if "generate_pdfs" in types and ("validate_rows" not in types or types.index("generate_pdfs") < types.index("validate_rows")):
        raise ValueError("Generate PDFs must follow Validate rows.")
    if types[-1] != "execution_report":
        raise ValueError("The final action must be Execution report.")
    return types


def run_workflow(nodes, csv_path, output_folder):
    types = validate_workflow(nodes)
    started = datetime.now(timezone.utc).isoformat()
    context = {"records": [], "pdf_count": 0}
    steps = []
    for index, action in enumerate(types, start=1):
        step = {"index": index, "type": action, "status": "running"}
        try:
            if action == "manual_trigger":
                step["message"] = "Workflow started manually."
            elif action == "read_csv":
                with open(csv_path, newline="", encoding="utf-8-sig") as source:
                    reader = csv.DictReader(source)
                    if not reader.fieldnames:
                        raise ValueError("The CSV file has no header row.")
                    context["headers"] = reader.fieldnames
                    context["records"] = list(reader)
                step["message"] = f"Read {len(context['records'])} row(s)."
            elif action == "validate_rows":
                missing = sorted(REQUIRED_COLUMNS - set(context.get("headers", [])))
                if missing:
                    raise ValueError("Missing required columns: " + ", ".join(missing))
                if not context["records"]:
                    raise ValueError("The CSV contains no records.")
                valid = [row for row in context["records"] if (row.get("customer_name") or "").strip() and (row.get("customer_id") or "").strip()]
                if not valid:
                    raise ValueError("No rows contain both customer_name and customer_id.")
                step["message"] = f"Validated {len(valid)} of {len(context['records'])} row(s)."
            elif action == "generate_pdfs":
                archive, count = generate_customer_pdfs(csv_path, output_folder)
                context["archive"] = archive
                context["pdf_count"] = count
                step["message"] = f"Generated {count} PDF document(s)."
            elif action == "execution_report":
                step["message"] = "Execution report created."
            step["status"] = "success"
            steps.append(step)
        except Exception as exc:
            step["status"] = "failed"
            step["message"] = str(exc)
            steps.append(step)
            break
    success = len(steps) == len(types) and all(step["status"] == "success" for step in steps)
    return {
        "status": "success" if success else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "summary": f"{len(steps)} of {len(types)} actions completed.",
        "archive": context.get("archive"),
        "pdf_count": context["pdf_count"],
    }
