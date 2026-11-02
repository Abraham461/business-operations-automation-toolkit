import csv
import os
import tempfile
from datetime import datetime, timezone

from modules.ai_processing.processor import process_document_text
from modules.document_automation.generator import generate_customer_pdfs
from modules.workflow_engine.http_action import run_http_action

ALLOWED_NODES = {
    "manual_trigger",
    "read_csv",
    "map_fields",
    "validate_rows",
    "filter_rows",
    "conditional_branch",
    "http_request",
    "ai_process",
    "generate_pdfs",
    "execution_report",
}
REQUIRED_COLUMNS = {"customer_name", "customer_id", "email", "plan"}
CONDITION_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "greater_than",
    "less_than",
    "is_empty",
    "is_not_empty",
}


def _node_type(node):
    return node.get("type") if isinstance(node, dict) else node


def _condition_config(node):
    if isinstance(node, dict):
        return node
    return {
        "field": "plan",
        "operator": "equals",
        "value": "VIP",
    }


def validate_workflow(nodes):
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Add at least one workflow action.")
    if len(nodes) > 20:
        raise ValueError("A workflow can contain at most 20 actions in this MVP.")

    types = [_node_type(node) for node in nodes]
    if any(node_type not in ALLOWED_NODES for node_type in types):
        raise ValueError("The workflow contains an unsupported action.")
    if types[0] != "manual_trigger" or types.count("manual_trigger") != 1:
        raise ValueError("A workflow must start with exactly one Manual trigger.")
    if types.count("read_csv") != 1:
        raise ValueError("Add exactly one Read CSV action.")
    if types.count("map_fields") > 1:
        raise ValueError("A workflow can contain only one Map fields action.")
    if "map_fields" in types:
        if types.index("map_fields") < types.index("read_csv"):
            raise ValueError("Map fields must follow Read CSV.")
        if types.index("map_fields") > types.index("validate_rows"):
            raise ValueError("Map fields must come before Validate rows.")
        config = nodes[types.index("map_fields")]
        mapping = config.get("mapping", {}) if isinstance(config, dict) else {}
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("Configure at least one field mapping.")
        allowed_targets = REQUIRED_COLUMNS
        for target, source in mapping.items():
            if target not in allowed_targets:
                raise ValueError(f"Unsupported target field: {target}.")
            if not isinstance(source, str) or not source.strip() or len(source) > 100:
                raise ValueError("Each mapping needs a valid source CSV column.")
    if "validate_rows" not in types or types.index("validate_rows") < types.index("read_csv"):
        raise ValueError("Add Validate rows after Read CSV.")
    if "map_fields" in types and types.index("validate_rows") < types.index("map_fields"):
        raise ValueError("Validate rows must follow Map fields.")
    if types.count("filter_rows") > 1:
        raise ValueError("A workflow can contain only one Filter rows action in this MVP.")
    if "filter_rows" in types:
        filter_index = types.index("filter_rows")
        if filter_index < types.index("validate_rows"):
            raise ValueError("Filter rows must follow Validate rows.")
        if "conditional_branch" in types and filter_index > types.index("conditional_branch"):
            raise ValueError("Filter rows must come before Conditional branch.")
        if "generate_pdfs" in types and filter_index > types.index("generate_pdfs"):
            raise ValueError("Filter rows must come before Generate PDFs.")
        config = nodes[filter_index] if isinstance(nodes[filter_index], dict) else {}
        field = str(config.get("field", "")).strip()
        operator = config.get("operator", "equals")
        value = str(config.get("value", ""))
        if not field or len(field) > 100:
            raise ValueError("Choose a valid CSV column for the row filter.")
        if operator not in CONDITION_OPERATORS:
            raise ValueError("Choose a supported row filter operator.")
        if len(value) > 200:
            raise ValueError("Filter values must be 200 characters or fewer.")
    if types.count("conditional_branch") > 1:
        raise ValueError("A workflow can contain only one Conditional branch in this MVP.")
    if "conditional_branch" in types:
        if types.index("conditional_branch") < types.index("validate_rows"):
            raise ValueError("Conditional branch must follow Validate rows.")
        config = _condition_config(nodes[types.index("conditional_branch")])
        field = str(config.get("field", "")).strip()
        operator = config.get("operator", "equals")
        value = str(config.get("value", ""))
        if not field or len(field) > 100:
            raise ValueError("Choose a valid CSV column for the condition.")
        if operator not in CONDITION_OPERATORS:
            raise ValueError("Choose a supported condition operator.")
        if len(value) > 200:
            raise ValueError("Condition values must be 200 characters or fewer.")
    if "generate_pdfs" in types and types.index("generate_pdfs") < types.index("validate_rows"):
        raise ValueError("Generate PDFs must follow Validate rows.")
    if "generate_pdfs" in types and "conditional_branch" in types:
        if types.index("generate_pdfs") < types.index("conditional_branch"):
            raise ValueError("Generate PDFs must follow Conditional branch.")
    if types.count("ai_process") > 1:
        raise ValueError("A workflow can contain only one AI text processing action in this MVP.")
    if "ai_process" in types:
        ai_index = types.index("ai_process")
        if ai_index < types.index("validate_rows"):
            raise ValueError("AI text processing must follow Validate rows.")
        config = nodes[ai_index] if isinstance(nodes[ai_index], dict) else {}
        field = str(config.get("field", "")).strip()
        output_variable = config.get("output_variable", "ai_summary")
        details_variable = config.get("details_variable", "ai_key_details")
        variable_pattern = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
        if not field or len(field) > 100:
            raise ValueError("Choose a valid CSV column for AI text processing.")
        if not isinstance(output_variable, str) or not variable_pattern.fullmatch(output_variable):
            raise ValueError("AI summary variable must use letters, numbers and underscores.")
        if not isinstance(details_variable, str) or not variable_pattern.fullmatch(details_variable):
            raise ValueError("AI details variable must use letters, numbers and underscores.")
        if output_variable == details_variable:
            raise ValueError("AI summary and details must use different variable names.")
    for node_type, node in zip(types, nodes):
        if node_type == "http_request":
            config = node if isinstance(node, dict) else {}
            method = str(config.get("method", "GET")).upper()
            url = str(config.get("url", "")).strip()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                raise ValueError("HTTP Request has an unsupported method.")
            if not url or len(url) > 2048:
                raise ValueError("HTTP Request needs a valid URL (maximum 2,048 characters).")
            headers = config.get("headers", {})
            if not isinstance(headers, dict) or len(headers) > 20:
                raise ValueError("HTTP Request headers must be an object with at most 20 entries.")
            body = config.get("body")
            if body is not None and len(str(body)) > 100000:
                raise ValueError("HTTP Request body is too large.")
            extract = config.get("extract", {})
            if not isinstance(extract, dict) or len(extract) > 20:
                raise ValueError("Response extraction must be an object with at most 20 variables.")
            for variable, path in extract.items():
                if not isinstance(variable, str) or not variable.replace("_", "a").isalnum() or not variable[0].isalpha():
                    raise ValueError("Response variable names must use letters, numbers and underscores.")
                if not isinstance(path, str) or not path.strip() or len(path) > 200:
                    raise ValueError("Each response variable needs a valid JSON path.")
    if types[-1] != "execution_report":
        raise ValueError("The final action must be Execution report.")
    if types.count("execution_report") != 1:
        raise ValueError("Add exactly one Execution report action.")
    return types


def _matches(value, operator, expected):
    actual = (value or "").strip()
    target = (expected or "").strip()
    if operator == "equals":
        return actual.casefold() == target.casefold()
    if operator == "not_equals":
        return actual.casefold() != target.casefold()
    if operator == "contains":
        return target.casefold() in actual.casefold()
    if operator == "is_empty":
        return not actual
    if operator == "is_not_empty":
        return bool(actual)
    try:
        left_number = float(actual)
        right_number = float(target)
    except (TypeError, ValueError):
        return False
    if operator == "greater_than":
        return left_number > right_number
    if operator == "less_than":
        return left_number < right_number
    return False


def _write_filtered_csv(records, headers, folder):
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        suffix=".csv",
        prefix="opspilot_branch_",
        dir=folder,
        delete=False,
    )
    try:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
        return handle.name
    finally:
        handle.close()


def run_workflow(nodes, csv_path, output_folder):
    types = validate_workflow(nodes)
    started = datetime.now(timezone.utc).isoformat()
    context = {"records": [], "pdf_count": 0, "condition_evaluated": False, "filter_evaluated": False, "variables": {}}
    steps = []
    filtered_csv = None

    try:
        for index, (action, node) in enumerate(zip(types, nodes), start=1):
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
                elif action == "map_fields":
                    mapping = node.get("mapping", {}) if isinstance(node, dict) else {}
                    missing_sources = sorted({
                        source.strip() for source in mapping.values()
                        if source.strip() not in context.get("headers", [])
                    })
                    if missing_sources:
                        raise ValueError(
                            "Mapping source column(s) not found: " + ", ".join(missing_sources)
                        )
                    mapped_records = []
                    for row in context.get("records", []):
                        mapped = dict(row)
                        for target, source in mapping.items():
                            mapped[target] = row.get(source.strip(), "")
                        mapped_records.append(mapped)
                    context["records"] = mapped_records
                    context["headers"] = list(dict.fromkeys(
                        list(context.get("headers", [])) + list(mapping.keys())
                    ))
                    step["message"] = f"Mapped {len(mapping)} field(s) across {len(mapped_records)} row(s)."
                elif action == "validate_rows":
                    missing = sorted(REQUIRED_COLUMNS - set(context.get("headers", [])))
                    if missing:
                        raise ValueError("Missing required columns: " + ", ".join(missing))
                    if not context["records"]:
                        raise ValueError("The CSV contains no records.")
                    valid = [
                        row for row in context["records"]
                        if (row.get("customer_name") or "").strip()
                        and (row.get("customer_id") or "").strip()
                    ]
                    context["valid_records"] = valid
                    step["message"] = (
                        f"Validated {len(valid)} of {len(context['records'])} row(s)."
                    )
                elif action == "filter_rows":
                    config = _condition_config(node)
                    field = str(config.get("field", "")).strip()
                    if field not in context.get("headers", []):
                        raise ValueError(f"Filter column '{field}' is not present in the CSV.")
                    operator = config.get("operator", "equals")
                    expected = str(config.get("value", ""))
                    source_records = context.get("valid_records", [])
                    filtered = [
                        row for row in source_records
                        if _matches(row.get(field), operator, expected)
                    ]
                    context["valid_records"] = filtered
                    context["filter_evaluated"] = True
                    step["message"] = (
                        f"Kept {len(filtered)} of {len(source_records)} valid row(s) "
                        f"where {field} {operator.replace('_', ' ')} '{expected}'."
                    )
                elif action == "conditional_branch":
                    config = _condition_config(node)
                    field = str(config.get("field", "")).strip()
                    if field not in context.get("headers", []):
                        raise ValueError(f"Condition column '{field}' is not present in the CSV.")
                    operator = config.get("operator", "equals")
                    expected = str(config.get("value", ""))
                    source_records = context.get("valid_records", [])
                    matched = [
                        row for row in source_records
                        if _matches(row.get(field), operator, expected)
                    ]
                    context["branch_records"] = matched
                    context["condition_evaluated"] = True
                    context["branch_matched"] = bool(matched)
                    step["status"] = "success" if matched else "success"
                    step["message"] = (
                        f"TRUE branch: {len(matched)} row(s) matched."
                        if matched
                        else "FALSE branch: no rows matched. PDF generation will be skipped."
                    )
                elif action == "ai_process":
                    field = str(node.get("field", "")).strip()
                    if field not in context.get("headers", []):
                        raise ValueError(f"AI text column '{field}' is not present in the CSV.")
                    source_records = context.get("valid_records", context.get("records", []))
                    source_text = "\\n".join(
                        str(row.get(field, "")).strip()
                        for row in source_records
                        if str(row.get(field, "")).strip()
                    )[:20000]
                    if not source_text:
                        raise ValueError(f"AI text column '{field}' contains no usable text.")
                    ai_result = process_document_text(source_text)
                    summary_variable = node.get("output_variable", "ai_summary")
                    details_variable = node.get("details_variable", "ai_key_details")
                    context["variables"][summary_variable] = ai_result.get("summary", "")
                    context["variables"][details_variable] = "\\n".join(
                        str(item) for item in ai_result.get("key_details", [])
                    )
                    step["message"] = (
                        f"Processed {len(source_text)} characters in "
                        f"{ai_result.get('mode', 'unknown')} mode; saved summary and key details "
                        "as workflow variables."
                    )
                elif action == "http_request":
                    request_result = run_http_action(node, context["variables"])
                    context["variables"].update(request_result["variables"])
                    step["message"] = (
                        f"{request_result['method']} request completed with HTTP "
                        f"{request_result['status_code']}; extracted "
                        f"{len(request_result['variables'])} variable(s)."
                    )
                elif action == "generate_pdfs":
                    source_records = (
                        context.get("branch_records", [])
                        if context["condition_evaluated"]
                        else context.get("valid_records", [])
                    )
                    if context["condition_evaluated"] and not context.get("branch_matched"):
                        step["status"] = "skipped"
                        step["message"] = "Skipped because the condition evaluated to FALSE."
                    elif not source_records and context["filter_evaluated"]:
                        step["status"] = "skipped"
                        step["message"] = "Skipped because the row filter returned no matching records."
                    elif not source_records:
                        raise ValueError("No valid rows are available for PDF generation.")
                    else:
                        source_path = csv_path
                        if context["condition_evaluated"] or context["filter_evaluated"]:
                            filtered_csv = _write_filtered_csv(
                                source_records, context["headers"], output_folder
                            )
                            source_path = filtered_csv
                        archive, count = generate_customer_pdfs(source_path, output_folder)
                        context["archive"] = archive
                        context["pdf_count"] = count
                        step["message"] = f"Generated {count} PDF document(s)."
                elif action == "execution_report":
                    matched_count = len(context.get("branch_records", []))
                    if context["condition_evaluated"] and not context.get("branch_matched"):
                        step["message"] = "Execution report created. No rows matched the condition."
                    elif context["condition_evaluated"]:
                        step["message"] = f"Execution report created. {matched_count} row(s) followed the TRUE branch."
                    else:
                        step["message"] = "Execution report created."
                if step["status"] == "running":
                    step["status"] = "success"
                steps.append(step)
            except Exception as exc:
                step["status"] = "failed"
                step["message"] = str(exc)
                steps.append(step)
                break
    finally:
        if filtered_csv and os.path.isfile(filtered_csv):
            os.remove(filtered_csv)

    success = (
        len(steps) == len(types)
        and all(step["status"] in {"success", "skipped"} for step in steps)
    )
    return {
        "status": "success" if success else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "summary": f"{sum(step['status'] == 'success' for step in steps)} successful, "
                   f"{sum(step['status'] == 'skipped' for step in steps)} skipped "
                   f"of {len(types)} actions.",
        "archive": context.get("archive"),
        "pdf_count": context["pdf_count"],
        "matched_rows": len(context.get("branch_records", []))
        if context["condition_evaluated"] else None,
    }
