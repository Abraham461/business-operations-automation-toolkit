import csv
import json
import os
import re
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
    "set_variables",
    "parse_json",
    "generate_pdfs",
    "execution_report",
}
LEGACY_REQUIRED_COLUMNS = {"customer_name", "customer_id", "email", "plan"}
FIELD_TYPES = {"text", "email", "number", "integer", "boolean", "date"}
FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
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


def _workflow_schema(nodes):
    """Return the schema configured on Validate rows, or None for legacy workflows."""
    for node in nodes:
        if _node_type(node) == "validate_rows" and isinstance(node, dict):
            schema = node.get("schema")
            if schema is not None:
                return schema
    return None


def _validate_schema(schema):
    if not isinstance(schema, list) or not schema or len(schema) > 50:
        raise ValueError("Configure between 1 and 50 input fields.")
    names = []
    for field in schema:
        if not isinstance(field, dict):
            raise ValueError("Each input field must be an object.")
        name = field.get("name")
        if not isinstance(name, str) or not FIELD_NAME_PATTERN.fullmatch(name):
            raise ValueError("Input field names must start with a letter and contain only letters, numbers and underscores.")
        if name.casefold() in {item.casefold() for item in names}:
            raise ValueError(f"Duplicate input field name: {name}.")
        names.append(name)
        if field.get("type", "text") not in FIELD_TYPES:
            raise ValueError(f"Unsupported data type for field '{name}'.")
        for text_key, limit in (("label", 100), ("default", 1000), ("error_message", 200)):
            text_value = field.get(text_key, "")
            if text_value is not None and (not isinstance(text_value, str) or len(text_value) > limit):
                raise ValueError(f"The {text_key} for '{name}' must be text with at most {limit} characters.")
        for flag in ("required", "unique"):
            if flag in field and not isinstance(field[flag], bool):
                raise ValueError(f"The {flag} rule for '{name}' must be true or false.")
        for limit in ("min", "max", "min_length", "max_length"):
            value = field.get(limit)
            if value is not None and value != "":
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"The {limit} rule for '{name}' must be numeric.") from exc
                if numeric < 0:
                    raise ValueError(f"The {limit} rule for '{name}' cannot be negative.")
                if limit in {"min_length", "max_length"} and not numeric.is_integer():
                    raise ValueError(f"The {limit} rule for '{name}' must be a whole number.")
        kind = field.get("type", "text")
        if kind not in {"number", "integer"} and (
            field.get("min") not in (None, "") or field.get("max") not in (None, "")
        ):
            raise ValueError(f"Numeric minimum/maximum rules require a number or integer field: '{name}'.")
        if kind != "text" and (
            field.get("min_length") not in (None, "") or field.get("max_length") not in (None, "")
        ):
            raise ValueError(f"Text length rules require a text field: '{name}'.")
        if field.get("min") not in (None, "") and field.get("max") not in (None, ""):
            if float(field["min"]) > float(field["max"]):
                raise ValueError(f"The minimum for '{name}' cannot exceed its maximum.")
        if field.get("min_length") not in (None, "") and field.get("max_length") not in (None, ""):
            if int(field["min_length"]) > int(field["max_length"]):
                raise ValueError(f"The minimum length for '{name}' cannot exceed its maximum length.")
    return names


def _validate_rows(records, headers, schema, row_numbers=None):
    """Validate records against a workflow-specific schema and return valid rows plus errors."""
    if schema is None:
        missing = sorted(LEGACY_REQUIRED_COLUMNS - set(headers))
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        valid = [
            row for row in records
            if (row.get("customer_name") or "").strip()
            and (row.get("customer_id") or "").strip()
        ]
        return valid, len(records) - len(valid), []

    field_names = _validate_schema(schema)
    missing = sorted(set(field_names) - set(headers))
    if missing:
        raise ValueError("Missing input columns: " + ", ".join(missing))

    seen = {name: set() for name in field_names if next(
        field for field in schema if field["name"] == name
    ).get("unique")}
    valid, errors = [], []
    for row_number, row in zip(row_numbers or range(2, len(records) + 2), records):
        row_errors = []
        normalized_row = dict(row)
        for field in schema:
            name = field["name"]
            label = field.get("label") or name
            value = str(row.get(name) or "").strip()
            if not value and field.get("default") not in (None, ""):
                value = str(field["default"]).strip()
                normalized_row[name] = value
            kind = field.get("type", "text")
            field_errors = []
            if field.get("required") and not value:
                field_errors.append(f"{label} is required")
            elif value:
                try:
                    if kind == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                        field_errors.append(f"{label} must be a valid email")
                    elif kind in {"number", "integer"}:
                        number = float(value)
                        if kind == "integer" and not number.is_integer():
                            field_errors.append(f"{label} must be a whole number")
                        if field.get("min") not in (None, "") and number < float(field["min"]):
                            field_errors.append(f"{label} must be at least {field['min']}")
                        if field.get("max") not in (None, "") and number > float(field["max"]):
                            field_errors.append(f"{label} must be no more than {field['max']}")
                    elif kind == "boolean" and value.casefold() not in {"true", "false", "1", "0", "yes", "no"}:
                        field_errors.append(f"{label} must be true or false")
                    elif kind == "date":
                        datetime.strptime(value, "%Y-%m-%d")
                    if kind == "text":
                        if field.get("min_length") not in (None, "") and len(value) < int(field["min_length"]):
                            field_errors.append(f"{label} is shorter than {field['min_length']} characters")
                        if field.get("max_length") not in (None, "") and len(value) > int(field["max_length"]):
                            field_errors.append(f"{label} exceeds {field['max_length']} characters")
                except (ValueError, TypeError):
                    field_errors.append(f"{label} has an invalid {kind} value")
            if field.get("unique") and value:
                normalized = value.casefold()
                if normalized in seen[name]:
                    field_errors.append(f"{label} must be unique")
                else:
                    seen[name].add(normalized)
            if field_errors:
                row_errors.append(field.get("error_message") or "; ".join(field_errors))
        if row_errors:
            errors.append({"row": row_number, "errors": row_errors})
        else:
            valid.append(normalized_row)
    return valid, len(records) - len(valid), errors


def validate_workflow(nodes):
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Add at least one workflow action.")
    if len(nodes) > 20:
        raise ValueError("A workflow can contain at most 20 actions in this MVP.")

    variable_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    types = [_node_type(node) for node in nodes]
    if any(node_type not in ALLOWED_NODES for node_type in types):
        raise ValueError("The workflow contains an unsupported action.")
    if types[0] != "manual_trigger" or types.count("manual_trigger") != 1:
        raise ValueError("A workflow must start with exactly one Manual trigger.")
    if types.count("read_csv") != 1:
        raise ValueError("Add exactly one Read CSV action.")
    schema = _workflow_schema(nodes)
    if schema is not None:
        _validate_schema(schema)
    validation_node = next((node for node in nodes if _node_type(node) == "validate_rows" and isinstance(node, dict)), {})
    scope = validation_node.get("scope", {"mode": "all"})
    if not isinstance(scope, dict) or scope.get("mode", "all") not in {"all", "first_n", "range", "selected"}:
        raise ValueError("Choose a supported validation row scope.")
    scope_mode = scope.get("mode", "all")
    if scope_mode == "first_n" and (not isinstance(scope.get("count"), int) or isinstance(scope.get("count"), bool) or scope["count"] < 1):
        raise ValueError("First N rows must be a positive whole number.")
    if scope_mode == "range":
        start, end = scope.get("start"), scope.get("end")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start:
            raise ValueError("Enter a valid validation row range. Row numbers start at 1, excluding the CSV header.")
    if scope_mode == "selected":
        selected_rows = scope.get("rows")
        if not isinstance(selected_rows, list) or not selected_rows or len(selected_rows) > 10000 or any(not isinstance(row, int) or isinstance(row, bool) or row < 1 for row in selected_rows) or len(set(selected_rows)) != len(selected_rows):
            raise ValueError("Enter one or more unique, positive row numbers to validate.")
    if scope_mode == "selected":
        selected_rows = scope.get("rows")
        if not isinstance(selected_rows, list) or not selected_rows or len(selected_rows) > 10000 or any(not isinstance(row, int) or isinstance(row, bool) or row < 1 for row in selected_rows) or len(set(selected_rows)) != len(selected_rows):
            raise ValueError("Enter one or more unique, positive row numbers to validate.")
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
        schema = _workflow_schema(nodes)
        allowed_targets = set(_validate_schema(schema)) if schema is not None else LEGACY_REQUIRED_COLUMNS
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
            response_variable = config.get("response_variable", "")
            if response_variable and (
                not isinstance(response_variable, str)
                or not variable_pattern.fullmatch(response_variable)
            ):
                raise ValueError("HTTP response variable must start with a letter and use only letters, numbers and underscores.")
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
                if not isinstance(variable, str) or not variable_pattern.fullmatch(variable):
                    raise ValueError("Response variable names must start with a letter and use only letters, numbers and underscores.")
                if (
                    not isinstance(path, str)
                    or not path
                    or path != path.strip()
                    or len(path) > 200
                    or any(not segment for segment in path.split("."))
                ):
                    raise ValueError("Each response variable needs a valid dot-separated JSON path.")
            if response_variable and response_variable in extract:
                raise ValueError("The full response variable must have a different name from extracted variables.")

    for node_type, node in zip(types, nodes):
        config = node if isinstance(node, dict) else {}
        if node_type == "set_variables":
            if types.index(node_type) < types.index("validate_rows"):
                raise ValueError("Set Variables must follow Validate rows.")
            values = config.get("values", {})
            if not isinstance(values, dict) or not values or len(values) > 20:
                raise ValueError("Set Variables needs 1 to 20 variable assignments.")
            for name, value in values.items():
                if not isinstance(name, str) or not variable_pattern.fullmatch(name):
                    raise ValueError("Variable names must start with a letter and use only letters, numbers and underscores.")
                if not isinstance(value, str) or len(value) > 2000:
                    raise ValueError("Set Variables values must be text with at most 2,000 characters.")
        elif node_type == "parse_json":
            if types.index(node_type) < types.index("validate_rows"):
                raise ValueError("Parse JSON must follow Validate rows.")
            source_variable = config.get("source_variable", "")
            extract = config.get("extract", {})
            if not isinstance(source_variable, str) or not variable_pattern.fullmatch(source_variable):
                raise ValueError("JSON Parse needs a valid source variable name.")
            if not isinstance(extract, dict) or not extract or len(extract) > 20:
                raise ValueError("JSON Parse needs 1 to 20 output mappings.")
            for name, path in extract.items():
                if not isinstance(name, str) or not variable_pattern.fullmatch(name):
                    raise ValueError("JSON output variable names must start with a letter and use only letters, numbers and underscores.")
                if (
                    not isinstance(path, str)
                    or not path
                    or path != path.strip()
                    or len(path) > 200
                    or any(not segment for segment in path.split("."))
                ):
                    raise ValueError("Each JSON output needs a valid dot-separated path.")
    if types[-1] != "execution_report":
        raise ValueError("The final action must be Execution report.")
    if types.count("execution_report") != 1:
        raise ValueError("Add exactly one Execution report action.")
    return types



def _resolve_variable_template(value, variables):
    pattern = re.compile(r"{{([A-Za-z][A-Za-z0-9_]{0,63})}}")

    def replace(match):
        name = match.group(1)
        if name not in variables:
            raise ValueError(f"Workflow variable '{name}' has not been defined.")
        resolved = variables[name]
        if isinstance(resolved, (dict, list)):
            return json.dumps(resolved, ensure_ascii=False)
        return str(resolved)

    return pattern.sub(replace, value)


def _read_json_path(payload, path):
    current = payload
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise ValueError(f"JSON path '{path}' could not be found in the source value.")
    if isinstance(current, (dict, list)) or current is None:
        raise ValueError(f"JSON path '{path}' must resolve to a non-null scalar value.")
    return current


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
                    if not context["records"]:
                        raise ValueError("The CSV contains no records.")
                    schema = node.get("schema") if isinstance(node, dict) else None
                    scope = node.get("scope", {"mode": "all"}) if isinstance(node, dict) else {"mode": "all"}
                    mode = scope.get("mode", "all")
                    total_rows = len(context["records"])
                    if mode == "all":
                        selected_indexes = list(range(total_rows))
                    elif mode == "first_n":
                        selected_indexes = list(range(min(scope["count"], total_rows)))
                    elif mode == "range":
                        if scope["end"] > total_rows:
                            raise ValueError(f"Validation range ends at row {scope['end']}, but the CSV contains only {total_rows} data row(s).")
                        selected_indexes = list(range(scope["start"] - 1, scope["end"]))
                    else:
                        if max(scope["rows"]) > total_rows:
                            raise ValueError(f"Selected validation row {max(scope['rows'])} exceeds the {total_rows} data row(s) in this CSV.")
                        selected_indexes = sorted(row_number - 1 for row_number in scope["rows"])
                    selected_records = [context["records"][index] for index in selected_indexes]
                    csv_line_numbers = [index + 2 for index in selected_indexes]
                    valid, invalid_count, row_errors = _validate_rows(
                        selected_records, context.get("headers", []), schema, csv_line_numbers
                    )
                    context["valid_records"] = valid
                    context["invalid_rows"] = row_errors
                    unselected_count = total_rows - len(selected_indexes)
                    context["validation_scope"] = scope
                    step["message"] = (
                        f"Validated {len(valid)} of {len(selected_records)} selected row(s); "
                        f"{invalid_count} invalid row(s) excluded; "
                        f"{unselected_count} row(s) outside the scope were not validated."
                    )
                    step["validated_rows"] = len(selected_records)
                    step["unvalidated_rows"] = unselected_count
                    if row_errors:
                        step["invalid_rows"] = row_errors[:100]
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
                elif action == "set_variables":
                    config = node if isinstance(node, dict) else {}
                    assignments = config.get("values", {})
                    prior_variables = dict(context["variables"])
                    resolved_assignments = {
                        name: _resolve_variable_template(template, prior_variables)
                        for name, template in assignments.items()
                    }
                    context["variables"].update(resolved_assignments)
                    step["message"] = f"Set {len(assignments)} workflow variable(s)."
                elif action == "parse_json":
                    config = node if isinstance(node, dict) else {}
                    source_name = config.get("source_variable", "")
                    if source_name not in context["variables"]:
                        raise ValueError(f"Source variable '{source_name}' has not been defined.")
                    source_value = context["variables"][source_name]
                    try:
                        payload = source_value if isinstance(source_value, (dict, list)) else json.loads(str(source_value))
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise ValueError(f"Variable '{source_name}' does not contain valid JSON.") from exc
                    extracted = {
                        name: _read_json_path(payload, path)
                        for name, path in config.get("extract", {}).items()
                    }
                    context["variables"].update(extracted)
                    step["message"] = f"Parsed JSON and created {len(extracted)} workflow variable(s)."
                elif action == "ai_process":
                    config = node if isinstance(node, dict) else {}
                    field = str(config.get("field", "")).strip()
                    if field not in context.get("headers", []):
                        raise ValueError(f"AI text column '{field}' is not present in the CSV.")
                    source_records = context.get("valid_records", context.get("records", []))
                    source_text = "\n".join(
                        str(row.get(field, "")).strip()
                        for row in source_records
                        if str(row.get(field, "")).strip()
                    )[:20000]
                    if not source_text:
                        raise ValueError(f"AI text column '{field}' contains no usable text.")
                    ai_result = process_document_text(source_text)
                    summary_variable = config.get("output_variable", "ai_summary")
                    details_variable = config.get("details_variable", "ai_key_details")
                    context["variables"][summary_variable] = ai_result.get("summary", "")
                    context["variables"][details_variable] = "\n".join(
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
                    response_variable = node.get("response_variable", "") if isinstance(node, dict) else ""
                    if response_variable:
                        if request_result.get("response") is None:
                            raise ValueError("The HTTP response variable requires a valid JSON response.")
                        context["variables"][response_variable] = json.dumps(
                            request_result["response"], ensure_ascii=False
                        )
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
                        # Always generate from the validated/transformed record set.
                        # This prevents invalid rows or unmapped source data leaking into output.
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
