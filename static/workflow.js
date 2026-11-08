(() => {
  const labels = {
    manual_trigger: ["Manual trigger", "Start the workflow", "bi-play-circle", "trigger-node"],
    read_csv: ["Read CSV", "Load uploaded records", "bi-filetype-csv", "data-node"],
    map_fields: ["Map fields", "Map source columns to your workflow fields", "bi-arrow-left-right", "map-node"],
    validate_rows: ["Validate rows", "Configure input fields and validation rules", "bi-check2-square", "validate-node"],
    filter_rows: ["Filter rows", "Keep records that match a rule", "bi-funnel", "filter-node"],
    conditional_branch: ["Conditional branch", "Route rows by a CSV condition", "bi-signpost-split", "condition-node"],
    http_request: ["HTTP Request", "Call an approved HTTPS endpoint", "bi-globe", "http-node"],
    ai_process: ["AI text processing", "Summarize text from a CSV column", "bi-stars", "ai-node"],
    set_variables: ["Set Variables", "Create or update workflow variables", "bi-braces", "variables-node"],
    parse_json: ["Parse JSON", "Extract values from a JSON variable", "bi-braces-asterisk", "json-node"],
    generate_pdfs: ["Generate PDFs", "Create customer documents", "bi-file-earmark-pdf", "document-node"],
    execution_report: ["Execution report", "Summarize the run", "bi-clipboard-data", "report-node"]
  };
  const defaults = [
    "manual_trigger", "read_csv",
    { type: "validate_rows", scope: { mode: "all" }, schema: [
      { name: "customer_name", type: "text", required: true, unique: false },
      { name: "customer_id", type: "text", required: true, unique: true },
      { name: "email", type: "email", required: true, unique: false },
      { name: "plan", type: "text", required: true, unique: false }
    ] },
    { type: "conditional_branch", field: "plan", operator: "equals", value: "VIP" },
    "generate_pdfs", "execution_report"
  ];
  let nodes = structuredClone(defaults);
  let currentWorkflowId = null;
  let currentVersionId = null;
  let currentWorkflowData = null;
  const list = document.getElementById("workflow-nodes");
  const result = document.getElementById("workflow-result");
  const libraryStatus = document.getElementById("workflow-library-status");
  const savedSelect = document.getElementById("saved-workflows");
  const versionSelect = document.getElementById("workflow-version");
  const history = document.getElementById("workflow-history");
  const typeOf = node => typeof node === "string" ? node : node.type;
  const configOf = node => typeof node === "string" ? { type: node } : node;
  let refreshValidationRowPicker = () => {};

  const parseCsvPreview = text => {
    const rows = [];
    let row = [], field = "", quoted = false;
    const source = text.replace(/^\\uFEFF/, "");
    for (let i = 0; i < source.length; i += 1) {
      const char = source[i];
      if (quoted) {
        if (char === '"' && source[i + 1] === '"') { field += '"'; i += 1; }
        else if (char === '"') quoted = false;
        else field += char;
      } else if (char === '"' && field.length === 0) quoted = true;
      else if (char === ",") { row.push(field); field = ""; }
      else if (char === "\\n" || char === "\\r") {
        if (char === "\\r" && source[i + 1] === "\\n") i += 1;
        row.push(field); field = "";
        if (row.some(value => value.trim())) rows.push(row);
        row = [];
      } else field += char;
    }
    row.push(field);
    if (row.some(value => value.trim())) rows.push(row);
    return rows;
  };

  const populateVersions = (workflow, selectedId) => {
    versionSelect.replaceChildren();
    (workflow.versions || []).forEach(version => {
      const option = document.createElement("option");
      option.value = version.id;
      option.textContent = "v" + version.version_number;
      versionSelect.append(option);
    });
    versionSelect.disabled = !(workflow.versions || []).length;
    versionSelect.value = selectedId || "";
  };

  const markDirty = () => {
    currentVersionId = null;
    const draftState = document.getElementById("workflow-draft-state");
    if (draftState) { draftState.classList.add("is-dirty"); draftState.innerHTML = "<span></span> Unsaved changes"; }
    if (currentWorkflowData) {
      const draft = document.createElement("option");
      draft.value = "";
      draft.textContent = "Unsaved draft";
      versionSelect.replaceChildren(draft);
      versionSelect.disabled = true;
    }
  };

  const defaultSchema = () => [
    { name: "customer_name", type: "text", required: true, unique: false },
    { name: "customer_id", type: "text", required: true, unique: true },
    { name: "email", type: "email", required: true, unique: false },
    { name: "plan", type: "text", required: true, unique: false }
  ];

  const schemaForWorkflow = () => {
    const validation = nodes.find(item => typeOf(item) === "validate_rows");
    const config = validation ? configOf(validation) : {};
    return Array.isArray(config.schema) && config.schema.length ? config.schema : defaultSchema();
  };

  const makeSchemaEditor = (node, index) => {
    const config = configOf(node);
    const schema = Array.isArray(config.schema) && config.schema.length
      ? structuredClone(config.schema) : defaultSchema();
    const editor = document.createElement("div");
    editor.className = "mapping-editor";
    const heading = document.createElement("strong");
    heading.textContent = "Input fields and validation rules";
    const help = document.createElement("small");
    help.textContent = "Define the columns this workflow expects. Required and unique rules are checked before later actions run.";
    editor.append(heading, help);
    const scopePanel = document.createElement("div");
    scopePanel.className = "validation-scope-editor";
    const scopeTitle = document.createElement("strong");
    scopeTitle.textContent = "Rows to validate";
    const scopeMode = document.createElement("select");
    scopeMode.className = "form-select form-select-sm";
    [["all", "All rows"], ["first_n", "First N rows"], ["range", "Specific row range"], ["selected", "Selected row numbers"]].forEach(([value, label]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = label; scopeMode.append(option);
    });
    scopeMode.value = scope.mode || "all";
    const scopeInputs = document.createElement("div");
    scopeInputs.className = "validation-scope-inputs";
    const countInput = document.createElement("input"); countInput.className = "form-control form-control-sm"; countInput.type = "number"; countInput.min = "1"; countInput.placeholder = "Number of rows"; countInput.value = scope.count || 100;
    const startInput = document.createElement("input"); startInput.className = "form-control form-control-sm"; startInput.type = "number"; startInput.min = "1"; startInput.placeholder = "Start row"; startInput.value = scope.start || 1;
    const endInput = document.createElement("input"); endInput.className = "form-control form-control-sm"; endInput.type = "number"; endInput.min = "1"; endInput.placeholder = "End row"; endInput.value = scope.end || 100;
    const rowsInput = document.createElement("input"); rowsInput.className = "form-control form-control-sm"; rowsInput.placeholder = "e.g. 1, 4, 8, 12"; rowsInput.value = Array.isArray(scope.rows) ? scope.rows.join(", ") : "";
    const scopeHint = document.createElement("small"); scopeHint.textContent = "Row numbers refer to data rows; the CSV header is not counted. Rows outside this selection are excluded from downstream actions and are reported as not validated.";
    const rowPicker = document.createElement("div");
    rowPicker.className = "validation-row-picker";
    const pickerHeading = document.createElement("div");
    pickerHeading.className = "validation-row-picker-heading";
    const pickerTitle = document.createElement("strong");
    pickerTitle.textContent = "Choose rows from your CSV";
    const pickerSummary = document.createElement("span");
    pickerSummary.textContent = "Upload a CSV to preview rows";
    const pickerActions = document.createElement("div");
    pickerActions.className = "validation-row-picker-actions";
    const selectVisible = document.createElement("button");
    selectVisible.type = "button";
    selectVisible.textContent = "Select visible";
    const clearSelected = document.createElement("button");
    clearSelected.type = "button";
    clearSelected.textContent = "Clear visible";
    pickerActions.append(selectVisible, clearSelected);
    pickerHeading.append(pickerTitle, pickerSummary, pickerActions);
    const pickerList = document.createElement("div");
    pickerList.className = "validation-row-picker-list";
    rowPicker.append(pickerHeading, pickerList);
    let previewRows = [];
    const applyVisibleSelection = selected => {
      const visibleRows = previewRows.slice(1, 51).map((_row, index) => index + 1);
      const hiddenRows = (scope.rows || []).filter(number => number > 50);
      scope.mode = "selected";
      scope.rows = selected ? [...new Set([...hiddenRows, ...visibleRows])].sort((a, b) => a - b) : hiddenRows;
      scopeMode.value = "selected";
      rowsInput.value = scope.rows.join(", ");
      rowsInput.setCustomValidity(scope.rows.length ? "" : "Select at least one row from the preview or enter row numbers.");
      showScopeInputs();
      update();
      renderRowPicker();
    };
    selectVisible.addEventListener("click", () => applyVisibleSelection(true));
    clearSelected.addEventListener("click", () => applyVisibleSelection(false));
    const renderRowPicker = () => {
      pickerList.replaceChildren();
      if (!previewRows.length) {
        const empty = document.createElement("small");
        empty.textContent = "Choose an input CSV below to see its rows here. You can also type row numbers above.";
        pickerList.append(empty);
        pickerSummary.textContent = "No CSV preview";
        return;
      }
      const dataRows = previewRows.slice(1);
      const selected = new Set(Array.isArray(scope.rows) ? scope.rows : []);
      pickerSummary.textContent = dataRows.length + " data row(s) in preview";
      dataRows.slice(0, 50).forEach((values, rowIndex) => {
        const rowNumber = rowIndex + 1;
        const label = document.createElement("label");
        label.className = "validation-row-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = selected.has(rowNumber);
        checkbox.addEventListener("change", () => {
          const visibleSelected = Array.from(pickerList.querySelectorAll("input:checked")).map(input => Number(input.value));
          const hiddenSelected = (scope.rows || []).filter(number => number > 50);
          scope.mode = "selected";
          scope.rows = [...new Set([...hiddenSelected, ...visibleSelected])].sort((a, b) => a - b);
          scopeMode.value = "selected";
          rowsInput.value = scope.rows.join(", ");
          rowsInput.setCustomValidity("");
          showScopeInputs();
          update();
          renderRowPicker();
        });
        checkbox.value = String(rowNumber);
        const number = document.createElement("span");
        number.className = "validation-row-number";
        number.textContent = "Row " + rowNumber;
        const preview = document.createElement("span");
        preview.className = "validation-row-preview";
        preview.textContent = values.slice(0, 3).map((value, columnIndex) => (previewRows[0][columnIndex] || "Column " + (columnIndex + 1)) + ": " + String(value).slice(0, 42)).join(" · ");
        label.append(checkbox, number, preview);
        pickerList.append(label);
      });
      if (dataRows.length > 50) {
        const note = document.createElement("small");
        note.textContent = "Showing the first 50 rows. Enter higher row numbers manually above.";
        pickerList.append(note);
      }
    };
    const updateScope = () => {
      const mode = scopeMode.value;
      if (mode === "selected") {
        const tokens = rowsInput.value.split(",").map(value => value.trim());
        if (tokens.length === 1 && tokens[0] === "") {
          Object.assign(scope, { mode, rows: [] });
          delete scope.count; delete scope.start; delete scope.end;
          rowsInput.setCustomValidity("Select at least one row from the preview or enter row numbers.");
          scopeHint.textContent = "Select rows from the CSV preview or enter row numbers separated by commas.";
          showScopeInputs();
          update();
          renderRowPicker();
          return;
        }
        const parsedRows = tokens.map(value => /^\\d+$/.test(value) ? Number(value) : NaN);
        const valid = tokens.length > 0 && tokens.every(Boolean)
          && parsedRows.every(value => Number.isSafeInteger(value) && value > 0)
          && new Set(parsedRows).size === parsedRows.length;
        rowsInput.setCustomValidity(valid ? "" : "Enter unique positive row numbers separated by commas, for example 1, 4, 8.");
        if (!valid) {
          scopeHint.textContent = "Enter unique positive row numbers separated by commas. Row 1 is the first data row after the CSV header.";
          showScopeInputs();
          return;
        }
        Object.assign(scope, { mode, rows: parsedRows });
        delete scope.count; delete scope.start; delete scope.end;
      } else if (mode === "first_n") {
        Object.assign(scope, { mode, count: Number(countInput.value) });
        delete scope.start; delete scope.end; delete scope.rows;
      } else if (mode === "range") {
        Object.assign(scope, { mode, start: Number(startInput.value), end: Number(endInput.value) });
        delete scope.count; delete scope.rows;
      } else {
        Object.assign(scope, { mode });
        delete scope.count; delete scope.start; delete scope.end; delete scope.rows;
      }
      rowsInput.setCustomValidity("");
      scopeHint.textContent = "Row numbers refer to data rows; the CSV header is not counted. Rows outside this selection are excluded from downstream actions and reported as not validated.";
      update();
      showScopeInputs();
      if (mode === "selected") renderRowPicker();
    };
    const showScopeInputs = () => {
      scopeInputs.replaceChildren();
      if (scopeMode.value === "first_n") scopeInputs.append(countInput);
      if (scopeMode.value === "range") scopeInputs.append(startInput, endInput);
      if (scopeMode.value === "selected") scopeInputs.append(rowsInput);
      rowPicker.hidden = scopeMode.value !== "selected";
    };
    scopeMode.addEventListener("change", updateScope);
    [countInput, startInput, endInput, rowsInput].forEach(control => {
      control.addEventListener("change", updateScope);
      if (control === rowsInput) control.addEventListener("input", () => {
        if (scopeMode.value === "selected") updateScope();
      });
    });
    showScopeInputs();
    scopePanel.append(scopeTitle, scopeMode, scopeInputs, rowPicker, scopeHint);
    editor.append(scopePanel);
    const scope = structuredClone(config.scope || { mode: "all" });
    const refreshPickerForFile = async () => {
      const file = document.getElementById("workflow-file").files[0];
      previewRows = [];
      if (!file) { renderRowPicker(); return; }
      try {
        previewRows = parseCsvPreview(await file.text());
        if (previewRows.length < 2) {
          pickerList.replaceChildren();
          const empty = document.createElement("small");
          empty.textContent = "This CSV does not contain any data rows.";
          pickerList.append(empty);
          pickerSummary.textContent = "No data rows";
          return;
        }
        renderRowPicker();
      } catch (_error) {
        pickerList.textContent = "Could not preview this CSV. You can still enter row numbers manually.";
        pickerSummary.textContent = "Preview unavailable";
      }
    };
    refreshValidationRowPicker = refreshPickerForFile;
    const update = () => {
      nodes[index] = { type: "validate_rows", schema, scope };
      markDirty();
    };
    schema.forEach((field, fieldIndex) => {
      const row = document.createElement("div");
      row.className = "schema-field-row";
      const name = document.createElement("input");
      name.className = "form-control form-control-sm";
      name.value = field.name || "";
      name.placeholder = "field_name";
      name.maxLength = 64;
      name.setAttribute("aria-label", "Input field name");
      const label = document.createElement("input");
      label.className = "form-control form-control-sm";
      label.value = field.label || "";
      label.placeholder = "Display label";
      label.maxLength = 100;
      label.setAttribute("aria-label", "Display label");
      const type = document.createElement("select");
      type.className = "form-select form-select-sm";
      ["text", "email", "number", "integer", "boolean", "date"].forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value.charAt(0).toUpperCase() + value.slice(1);
        type.append(option);
      });
      type.value = field.type || "text";
      const requiredLabel = document.createElement("label");
      const required = document.createElement("input");
      required.type = "checkbox";
      required.checked = Boolean(field.required);
      requiredLabel.append(required, document.createTextNode(" Required"));
      const uniqueLabel = document.createElement("label");
      const unique = document.createElement("input");
      unique.type = "checkbox";
      unique.checked = Boolean(field.unique);
      uniqueLabel.append(unique, document.createTextNode(" Unique"));
      const min = document.createElement("input");
      min.className = "form-control form-control-sm";
      min.placeholder = "Minimum";
      min.value = field.min ?? "";
      min.setAttribute("aria-label", "Minimum value");
      const max = document.createElement("input");
      max.className = "form-control form-control-sm";
      max.placeholder = "Maximum";
      max.value = field.max ?? "";
      max.setAttribute("aria-label", "Maximum value");
      const defaultValue = document.createElement("input");
      defaultValue.className = "form-control form-control-sm";
      defaultValue.placeholder = "Default value";
      defaultValue.value = field.default ?? "";
      defaultValue.maxLength = 1000;
      defaultValue.setAttribute("aria-label", "Default value");
      const errorMessage = document.createElement("input");
      errorMessage.className = "form-control form-control-sm";
      errorMessage.placeholder = "Custom error (optional)";
      errorMessage.value = field.error_message || "";
      errorMessage.maxLength = 200;
      errorMessage.setAttribute("aria-label", "Custom validation error message");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-sm btn-outline-secondary";
      remove.textContent = "Remove";
      remove.disabled = schema.length <= 1;
      remove.addEventListener("click", () => {
        schema.splice(fieldIndex, 1);
        update();
        render();
      });
      const updateField = () => {
        schema[fieldIndex] = {
          name: name.value.trim(),
          label: label.value.trim(),
          type: type.value,
          required: required.checked,
          unique: unique.checked,
          ...(min.value.trim() ? { min: min.value.trim() } : {}),
          ...(max.value.trim() ? { max: max.value.trim() } : {}),
          ...(defaultValue.value.trim() ? { default: defaultValue.value } : {}),
          ...(errorMessage.value.trim() ? { error_message: errorMessage.value.trim() } : {})
        };
        update();
      };
      [name, label, type, required, unique, min, max, defaultValue, errorMessage].forEach(control => control.addEventListener("change", updateField));
      row.append(name, label, type, requiredLabel, uniqueLabel, min, max, defaultValue, errorMessage, remove);
      editor.append(row);
    });
    const add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn-sm btn-outline-primary mt-2";
    add.textContent = "Add input field";
    add.disabled = schema.length >= 50;
    add.addEventListener("click", () => {
      schema.push({ name: "new_field_" + (schema.length + 1), type: "text", required: false, unique: false });
      update();
      render();
    });
    editor.append(add);
    return editor;
  };

  const makeMappingEditor = (node, index) => {
    const config = configOf(node);
    const mapping = config.mapping || {};
    const editor = document.createElement("div");
    editor.className = "mapping-editor";
    const heading = document.createElement("strong");
    heading.textContent = "Map source columns";
    editor.append(heading);
    schemaForWorkflow().forEach(field => {
      const wrap = document.createElement("label");
      wrap.className = "mapping-field";
      const caption = document.createElement("span");
      caption.textContent = field.name + " ← source CSV column";
      const input = document.createElement("input");
      input.className = "form-control form-control-sm";
      input.value = mapping[field.name] || "";
      input.placeholder = "Source CSV column";
      input.maxLength = 100;
      input.setAttribute("aria-label", "Source CSV column for " + field.name);
      input.addEventListener("change", () => {
        const next = { ...(config.mapping || {}) };
        if (input.value.trim()) next[field.name] = input.value.trim();
        else delete next[field.name];
        nodes[index] = { type: "map_fields", mapping: next };
        markDirty();
      });
      wrap.append(caption, input);
      editor.append(wrap);
    });
    return editor;
  };

  const makeConditionEditor = (node, index, nodeType = "conditional_branch") => {
    const config = configOf(node);
    const editor = document.createElement("div");
    editor.className = "condition-editor";
    const field = document.createElement("input");
    field.className = "form-control form-control-sm";
    field.value = config.field || "plan";
    field.placeholder = "CSV column (e.g. plan)";
    field.setAttribute("aria-label", "Condition CSV column");
    field.maxLength = 100;
    const operator = document.createElement("select");
    operator.className = "form-select form-select-sm";
    operator.setAttribute("aria-label", "Condition operator");
    [
      ["equals", "equals"], ["not_equals", "does not equal"], ["contains", "contains"],
      ["greater_than", "greater than"], ["less_than", "less than"],
      ["is_empty", "is empty"], ["is_not_empty", "is not empty"]
    ].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      operator.append(option);
    });
    operator.value = config.operator || "equals";
    const expected = document.createElement("input");
    expected.className = "form-control form-control-sm";
    expected.value = config.value || "";
    expected.placeholder = "Expected value";
    expected.setAttribute("aria-label", "Condition expected value");
    expected.maxLength = 200;
    const update = () => {
      nodes[index] = { type: nodeType, field: field.value.trim(), operator: operator.value, value: expected.value };
      markDirty();
    };
    field.addEventListener("change", update);
    operator.addEventListener("change", update);
    expected.addEventListener("change", update);
    editor.append(field, operator, expected);
    return editor;
  };


  const makeHttpEditor = (node, index) => {
    const config = configOf(node);
    const editor = document.createElement("div");
    editor.className = "http-editor";
    const makeLabel = (caption, control) => {
      const label = document.createElement("label");
      label.className = "http-field";
      const title = document.createElement("span");
      title.textContent = caption;
      label.append(title, control);
      return label;
    };
    const method = document.createElement("select");
    method.className = "form-select form-select-sm";
    ["GET", "POST", "PUT", "PATCH", "DELETE"].forEach(value => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      method.append(option);
    });
    method.value = config.method || "GET";
    const url = document.createElement("input");
    url.className = "form-control form-control-sm";
    url.type = "url";
    url.placeholder = "https://api.example.com/resource";
    url.value = config.url || "";
    url.maxLength = 2048;
    const headers = document.createElement("textarea");
    headers.className = "form-control form-control-sm";
    headers.rows = 2;
    headers.placeholder = '{"Accept":"application/json"}';
    headers.value = JSON.stringify(config.headers || {}, null, 2);
    const body = document.createElement("textarea");
    body.className = "form-control form-control-sm";
    body.rows = 3;
    body.placeholder = '{"customer_id":"{{customer_id}}"}';
    body.value = config.body ? JSON.stringify(config.body, null, 2) : "";
    const responseVariable = document.createElement("input");
    responseVariable.className = "form-control form-control-sm";
    responseVariable.value = config.response_variable || "";
    responseVariable.placeholder = "api_response";
    responseVariable.maxLength = 64;
    const extract = document.createElement("textarea");
    extract.className = "form-control form-control-sm";
    extract.rows = 2;
    extract.placeholder = '{"access_token":"access_token","customer_id":"data.id"}';
    extract.value = JSON.stringify(config.extract || {}, null, 2);
    const update = () => {
      let parsedHeaders = {};
      let parsedBody = null;
      let parsedExtract = {};
      try { parsedHeaders = headers.value.trim() ? JSON.parse(headers.value) : {}; } catch (_error) { parsedHeaders = config.headers || {}; }
      try { parsedBody = body.value.trim() ? JSON.parse(body.value) : null; } catch (_error) { parsedBody = config.body || null; }
      try { parsedExtract = extract.value.trim() ? JSON.parse(extract.value) : {}; } catch (_error) { parsedExtract = config.extract || {}; }
      nodes[index] = {
        type: "http_request",
        method: method.value,
        url: url.value.trim(),
        headers: parsedHeaders,
        body: parsedBody,
        response_variable: responseVariable.value.trim(),
        extract: parsedExtract
      };
      markDirty();
    };
    [method, url, headers, body, responseVariable, extract].forEach(control => control.addEventListener("change", update));
    editor.append(
      makeLabel("Method", method),
      makeLabel("HTTPS URL", url),
      makeLabel("Headers (JSON)", headers),
      makeLabel("JSON request body (optional)", body),
      makeLabel("Store full JSON response as variable (optional)", responseVariable),
      makeLabel("Response JSON paths → workflow variables", extract)
    );
    const hint = document.createElement("small");
    hint.className = "http-editor-hint";
    hint.textContent = "Use {{variable_name}} in later request fields. Optionally store the full JSON response for a Parse JSON action. Hosts must be listed in OPSPILOT_HTTP_ALLOWED_HOSTS.";
    editor.append(hint);
    return editor;
  };


  const makeAiEditor = (node, index) => {
    const config = configOf(node);
    const editor = document.createElement("div");
    editor.className = "ai-editor";
    const makeField = (caption, value, placeholder, maxLength) => {
      const label = document.createElement("label");
      label.className = "ai-field";
      const title = document.createElement("span");
      title.textContent = caption;
      const input = document.createElement("input");
      input.className = "form-control form-control-sm";
      input.value = value || "";
      input.placeholder = placeholder;
      input.maxLength = maxLength;
      label.append(title, input);
      return { label, input };
    };
    const source = makeField("CSV text column", config.field || "description", "e.g. description", 100);
    const summary = makeField("Summary variable", config.output_variable || "ai_summary", "ai_summary", 64);
    const details = makeField("Key details variable", config.details_variable || "ai_key_details", "ai_key_details", 64);
    const update = () => {
      nodes[index] = {
        type: "ai_process",
        field: source.input.value.trim(),
        output_variable: summary.input.value.trim(),
        details_variable: details.input.value.trim()
      };
      markDirty();
    };
    [source.input, summary.input, details.input].forEach(input => input.addEventListener("change", update));
    editor.append(source.label, summary.label, details.label);
    const hint = document.createElement("small");
    hint.className = "ai-editor-hint";
    hint.textContent = "Uses OPENROUTER_API_KEY when configured; otherwise returns a labelled demo result. Input is limited to 20,000 characters.";
    editor.append(hint);
    return editor;
  };


  const makeJsonConfigEditor = (node, index, nodeType) => {
    const config = configOf(node);
    const editor = document.createElement("div");
    editor.className = "workflow-config-editor";
    const makeField = (caption, value, placeholder) => {
      const label = document.createElement("label");
      label.className = "workflow-config-field";
      const title = document.createElement("span");
      title.textContent = caption;
      const input = document.createElement("textarea");
      input.className = "form-control form-control-sm";
      input.rows = 3;
      input.value = JSON.stringify(value || {}, null, 2);
      input.placeholder = placeholder;
      label.append(title, input);
      editor.append(label);
      return input;
    };
    let valuesInput;
    let sourceInput;
    let extractInput;
    if (nodeType === "set_variables") {
      valuesInput = makeField("Variable assignments (JSON)", config.values || { api_base: "https://api.example.com", request_id: "{{customer_id}}" }, '{"token":"{{access_token}}"}');
    } else {
      const sourceLabel = document.createElement("label");
      sourceLabel.className = "workflow-config-field";
      const sourceTitle = document.createElement("span");
      sourceTitle.textContent = "Source JSON variable";
      sourceInput = document.createElement("input");
      sourceInput.className = "form-control form-control-sm";
      sourceInput.value = config.source_variable || "api_response";
      sourceInput.maxLength = 64;
      sourceLabel.append(sourceTitle, sourceInput);
      editor.append(sourceLabel);
      extractInput = makeField("JSON paths → output variables", config.extract || { customer_id: "data.customer.id", first_item: "data.items.0" }, '{"status":"result.status"}');
    }
    const update = () => {
      try {
        if (nodeType === "set_variables") {
          const values = JSON.parse(valuesInput.value);
          nodes[index] = { type: nodeType, values };
        } else {
          const extract = JSON.parse(extractInput.value);
          nodes[index] = { type: nodeType, source_variable: sourceInput.value.trim(), extract };
        }
        markDirty();
      } catch (_error) {
        // Keep the last valid node configuration until the JSON editor is corrected.
      }
    };
    (nodeType === "set_variables" ? [valuesInput] : [sourceInput, extractInput]).forEach(control => {
      control.addEventListener("change", update);
    });
    const hint = document.createElement("small");
    hint.className = "workflow-config-hint";
    hint.textContent = nodeType === "set_variables"
      ? "Use {{variable_name}} to reuse an earlier value. Values are text only; no code or expressions are evaluated."
      : "Reads JSON from an existing workflow variable. Use dot paths and numeric array indexes, for example data.items.0.id.";
    editor.append(hint);
    return editor;
  };

  const render = () => {
    list.replaceChildren();
    nodes.forEach((nodeData, index) => {
      const type = typeOf(nodeData);
      const info = labels[type];
      const row = document.createElement("div");
      row.className = "workflow-node-row";
      const stepMeta = document.createElement("div");
      stepMeta.className = "workflow-step-meta";
      const stepNumber = document.createElement("span");
      stepNumber.className = "workflow-step-number";
      stepNumber.textContent = String(index + 1).padStart(2, "0");
      const stepLabel = document.createElement("span");
      stepLabel.textContent = index === 0 ? "TRIGGER" : index === nodes.length - 1 ? "RESULT" : "ACTION";
      stepMeta.append(stepNumber, stepLabel);
      row.append(stepMeta);
      const node = document.createElement("div");
      node.className = "workflow-node";
      const icon = document.createElement("span");
      icon.className = "workflow-node-icon " + info[3];
      const glyph = document.createElement("i");
      glyph.className = "bi " + info[2];
      icon.append(glyph);
      const copy = document.createElement("span");
      copy.className = "workflow-node-copy";
      const title = document.createElement("strong");
      title.textContent = info[0];
      const desc = document.createElement("small");
      desc.textContent = info[1];
      copy.append(title, desc);
      node.append(icon, copy);
      node.setAttribute("data-step-type", type);
      if (type === "validate_rows") {
        node.classList.add("workflow-node-mapping");
        node.append(makeSchemaEditor(nodeData, index));
      }
      if (type === "set_variables" || type === "parse_json") {
        node.classList.add("workflow-node-config");
        node.append(makeJsonConfigEditor(nodeData, index, type));
      }
      if (type === "ai_process") {
        node.classList.add("workflow-node-ai");
        node.append(makeAiEditor(nodeData, index));
      }
      if (type === "http_request") {
        node.classList.add("workflow-node-http");
        node.append(makeHttpEditor(nodeData, index));
      }
      if (type === "map_fields") {
        node.classList.add("workflow-node-mapping");
        node.append(makeMappingEditor(nodeData, index));
      }
      if (type === "conditional_branch" || type === "filter_rows") {
        node.classList.add("workflow-node-conditional");
        node.append(makeConditionEditor(nodeData, index, type));
      }
      if (index > 0 && index < nodes.length - 1 && type !== "conditional_branch" && type !== "filter_rows") {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "node-remove";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", "Remove " + info[0]);
        remove.addEventListener("click", () => { nodes.splice(index, 1); markDirty(); render(); });
        node.append(remove);
      }
      if (type === "conditional_branch" || type === "filter_rows") {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "node-remove";
        remove.textContent = "Remove";
        remove.setAttribute("aria-label", "Remove " + info[0]);
        remove.addEventListener("click", () => { nodes.splice(index, 1); markDirty(); render(); });
        node.append(remove);
      }
      if (index > 0 && index < nodes.length - 1) {
        const controls = document.createElement("div");
        controls.className = "workflow-node-controls";
        const moveButton = (label, iconName, offset, disabled) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "workflow-node-control";
          button.disabled = disabled;
          button.title = label;
          button.setAttribute("aria-label", label + " " + info[0]);
          const glyph = document.createElement("i");
          glyph.className = "bi " + iconName;
          button.append(glyph);
          button.addEventListener("click", () => {
            const target = index + offset;
            if (target <= 0 || target >= nodes.length - 1) return;
            const moved = nodes.splice(index, 1)[0];
            nodes.splice(target, 0, moved);
            markDirty();
            render();
          });
          return button;
        };
        const dragHandle = document.createElement("button");
        dragHandle.type = "button";
        dragHandle.className = "workflow-node-control workflow-drag-handle";
        dragHandle.draggable = true;
        dragHandle.title = "Drag to reorder";
        dragHandle.setAttribute("aria-label", "Drag to reorder " + info[0]);
        const grip = document.createElement("i");
        grip.className = "bi bi-grip-vertical";
        dragHandle.append(grip);
        dragHandle.addEventListener("dragstart", event => {
          event.stopPropagation();
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(index));
          row.classList.add("is-dragging");
        });
        dragHandle.addEventListener("dragend", () => {
          document.querySelectorAll(".workflow-node-row").forEach(item => item.classList.remove("is-dragging", "is-drop-target"));
        });
        row.addEventListener("dragover", event => {
          if (!document.querySelector(".workflow-node-row.is-dragging")) return;
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
          document.querySelectorAll(".workflow-node-row").forEach(item => item.classList.remove("is-drop-target"));
          row.classList.add("is-drop-target");
        });
        row.addEventListener("drop", event => {
          event.preventDefault();
          const sourceIndex = Number(event.dataTransfer.getData("text/plain"));
          if (!Number.isInteger(sourceIndex) || sourceIndex <= 0 || sourceIndex >= nodes.length - 1 || index <= 0 || index >= nodes.length - 1 || sourceIndex === index) return;
          const moved = nodes.splice(sourceIndex, 1)[0];
          nodes.splice(index, 0, moved);
          markDirty();
          render();
        });
        controls.append(
          dragHandle,
          moveButton("Move up", "bi-arrow-up", -1, index <= 1),
          moveButton("Move down", "bi-arrow-down", 1, index >= nodes.length - 2)
        );
        node.append(controls);
      }
      row.append(node);
      if (index < nodes.length - 1) {
        const connector = document.createElement("div");
        connector.className = "workflow-connector";
        connector.innerHTML = "<span></span>";
        row.append(connector);
      }
      list.append(row);
    });
    const count = document.getElementById("workflow-step-count");
    if (count) count.textContent = nodes.length + (nodes.length === 1 ? " step" : " steps");
  };

  const refreshLibrary = async (selectedId = currentWorkflowId) => {
    try {
      const response = await fetch("/api/workflows");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not load saved workflows.");
      savedSelect.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select workflow";
      savedSelect.append(placeholder);
      (payload.workflows || []).forEach(workflow => {
        const option = document.createElement("option");
        option.value = workflow.id;
        option.textContent = workflow.name + " · v" + workflow.latest_version;
        savedSelect.append(option);
      });
      savedSelect.value = selectedId || "";
    } catch (error) {
      libraryStatus.textContent = error.message;
    }
  };

  const refreshHistory = async () => {
    if (!currentWorkflowId) {
      history.textContent = "Save or load a workflow to view its execution history.";
      return;
    }
    try {
      const response = await fetch("/api/workflows/" + encodeURIComponent(currentWorkflowId) + "/executions");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not load execution history.");
      history.replaceChildren();
      if (!payload.executions.length) {
        history.textContent = "No executions recorded for this workflow yet.";
        return;
      }
      payload.executions.forEach(item => {
        const row = document.createElement("div");
        row.className = "d-flex flex-wrap justify-content-between gap-2 border-bottom py-2";
        const description = document.createElement("span");
        description.textContent = (item.started_at || item.created_at || "Unknown time") + " · " + (item.summary || "Execution");
        const status = document.createElement("strong");
        status.textContent = item.status.toUpperCase();
        status.className = item.status === "success" ? "text-success" : "text-danger";
        row.append(description, status);
        history.append(row);
      });
    } catch (error) {
      history.textContent = error.message;
    }
  };

  const saveWorkflow = async () => {
    const button = document.getElementById("save-workflow");
    button.disabled = true;
    libraryStatus.textContent = "Saving workflow…";
    try {
      const response = await fetch("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: currentWorkflowId,
          name: document.getElementById("workflow-name").value,
          nodes
        })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not save workflow.");
      currentWorkflowData = payload.workflow;
      currentWorkflowId = currentWorkflowData.id;
      currentVersionId = currentWorkflowData.latest_version.id;
      populateVersions(currentWorkflowData, currentVersionId);
      libraryStatus.textContent = "Saved as version " + currentWorkflowData.latest_version.version_number + ".";
      const draftState = document.getElementById("workflow-draft-state");
      if (draftState) { draftState.classList.remove("is-dirty"); draftState.innerHTML = "<span></span> Saved"; }
      await refreshLibrary(currentWorkflowId);
      await refreshHistory();
    } catch (error) {
      libraryStatus.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };

  const loadWorkflow = async () => {
    const id = savedSelect.value;
    if (!id) {
      currentWorkflowId = null;
      currentVersionId = null;
      currentWorkflowData = null;
      populateVersions({ versions: [] }, null);
      history.textContent = "Save or load a workflow to view its execution history.";
      return;
    }
    libraryStatus.textContent = "Loading workflow…";
    try {
      const response = await fetch("/api/workflows/" + encodeURIComponent(id));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Could not load workflow.");
      currentWorkflowData = payload.workflow;
      currentWorkflowId = currentWorkflowData.id;
      const latest = currentWorkflowData.latest_version;
      if (!latest) throw new Error("This workflow has no saved version.");
      currentVersionId = latest.id;
      nodes = structuredClone(latest.definition);
      document.getElementById("workflow-name").value = currentWorkflowData.name;
      populateVersions(currentWorkflowData, currentVersionId);
      render();
      libraryStatus.textContent = "Loaded version " + latest.version_number + ".";
      const draftState = document.getElementById("workflow-draft-state");
      if (draftState) { draftState.classList.remove("is-dirty"); draftState.innerHTML = "<span></span> Saved version " + latest.version_number; }
      await refreshHistory();
    } catch (error) {
      libraryStatus.textContent = error.message;
    }
  };

  versionSelect.addEventListener("change", () => {
    if (!currentWorkflowData || !versionSelect.value) return;
    const selected = currentWorkflowData.versions.find(item => item.id === versionSelect.value);
    if (!selected) return;
    currentVersionId = selected.id;
    nodes = structuredClone(selected.definition);
    render();
    libraryStatus.textContent = "Loaded version " + selected.version_number + ".";
  });

  document.querySelectorAll("[data-add-node]").forEach(button => {
    button.addEventListener("click", () => {
      const type = button.dataset.addNode;
      if (!["http_request", "set_variables", "parse_json"].includes(type) && nodes.some(node => typeOf(node) === type)) { result.textContent = "This action is already in the workflow."; return; }
      const reportIndex = nodes.findIndex(node => typeOf(node) === "execution_report");
      const mappingIndex = nodes.findIndex(node => typeOf(node) === "validate_rows");
      const conditionalIndex = nodes.findIndex(node => typeOf(node) === "conditional_branch");
      const pdfIndex = nodes.findIndex(node => typeOf(node) === "generate_pdfs");
      const newNode = type === "conditional_branch" || type === "filter_rows"
        ? { type, field: "plan", operator: "equals", value: "VIP" }
        : type === "http_request"
          ? { type, method: "GET", url: "https://api.example.com/resource", headers: { Accept: "application/json" }, body: null, extract: {} }
        : type === "set_variables"
          ? { type, values: { source_system: "OpsPilot", workflow_label: "Customer document run" } }
        : type === "parse_json"
          ? { type, source_variable: "api_response", extract: { customer_id: "data.customer.id" } }
        : type === "ai_process"
          ? { type, field: "description", output_variable: "ai_summary", details_variable: "ai_key_details" }
        : type === "map_fields"
          ? { type, mapping: Object.fromEntries(schemaForWorkflow().map(field => [field.name, field.name])) }
          : type;
      let insertAt = reportIndex < 0 ? nodes.length : reportIndex;
      if (type === "map_fields" && mappingIndex >= 0) insertAt = mappingIndex;
      const aiIndex = nodes.findIndex(node => typeOf(node) === "ai_process");
      const httpIndex = nodes.findIndex(node => typeOf(node) === "http_request");
      if (type === "filter_rows") insertAt = conditionalIndex >= 0 ? conditionalIndex : pdfIndex >= 0 ? pdfIndex : insertAt;
      if (type === "conditional_branch" && pdfIndex >= 0) insertAt = pdfIndex;
      if (type === "ai_process") {
        const validationIndex = nodes.findIndex(node => typeOf(node) === "validate_rows");
        const downstreamIndex = nodes.findIndex(node => ["filter_rows", "conditional_branch", "http_request", "generate_pdfs", "execution_report"].includes(typeOf(node)));
        insertAt = downstreamIndex >= 0 ? downstreamIndex : validationIndex + 1;
      }
      const variableProducerTypes = ["set_variables", "ai_process", "http_request", "parse_json"];
      if (type === "set_variables" || type === "parse_json" || type === "http_request") {
        const lastProducerIndex = nodes.reduce(
          (found, node, i) => variableProducerTypes.includes(typeOf(node)) ? i : found,
          -1
        );
        const validationPosition = nodes.findIndex(node => typeOf(node) === "validate_rows");
        const pdfPosition = nodes.findIndex(node => typeOf(node) === "generate_pdfs");
        const reportPosition = nodes.findIndex(node => typeOf(node) === "execution_report");
        if (lastProducerIndex >= 0) insertAt = lastProducerIndex + 1;
        else if (pdfPosition >= 0) insertAt = pdfPosition;
        else if (reportPosition >= 0) insertAt = reportPosition;
        else insertAt = validationPosition + 1;
      }
      nodes.splice(insertAt, 0, newNode);
      markDirty();
      result.textContent = "";
      render();
    });
  });

  document.getElementById("reset-workflow").addEventListener("click", () => {
    nodes = structuredClone(defaults);
    markDirty();
    result.textContent = "";
    render();
  });
  document.getElementById("save-workflow").addEventListener("click", saveWorkflow);
  document.getElementById("workflow-file").addEventListener("change", () => refreshValidationRowPicker());
  savedSelect.addEventListener("change", loadWorkflow);

  document.getElementById("run-workflow").addEventListener("click", async () => {
    const invalidScopeInput = list.querySelector(".validation-scope-inputs input:invalid");
    if (invalidScopeInput) {
      invalidScopeInput.reportValidity();
      result.textContent = "Correct the validation row selection before running the workflow.";
      return;
    }
    const file = document.getElementById("workflow-file").files[0];
    if (!file) { result.textContent = "Choose a CSV file before running the workflow."; return; }
    const button = document.getElementById("run-workflow");
    button.disabled = true;
    result.textContent = "Running workflow…";
    const data = new FormData();
    data.append("file", file);
    data.append("workflow", JSON.stringify(nodes));
    if (currentWorkflowId) data.append("workflow_id", currentWorkflowId);
    if (currentVersionId) data.append("version_id", currentVersionId);
    try {
      const response = await fetch("/workflows/run", { method: "POST", body: data });
      const payload = await response.json();
      result.replaceChildren();
      const heading = document.createElement("strong");
      heading.textContent = payload.status === "success" ? "Workflow completed" : "Workflow failed";
      result.append(heading);
      const summary = document.createElement("p");
      summary.textContent = payload.summary || payload.error || "No execution details returned.";
      result.append(summary);
      (payload.steps || []).forEach(step => {
        const line = document.createElement("p");
        line.className = "workflow-step-result " + step.status;
        line.textContent = step.index + ". " + labels[step.type][0] + " · " + step.status + " · " + step.message;
        result.append(line);
      });
      if (payload.download_url) {
        const link = document.createElement("a");
        link.href = payload.download_url;
        link.textContent = "Download generated PDF archive";
        link.className = "text-link";
        result.append(link);
      }
      if (payload.execution_id) {
        const saved = document.createElement("p");
        saved.className = "small text-muted";
        saved.textContent = "Execution saved to history.";
        result.append(saved);
        await refreshHistory();
      }
      if (!response.ok && payload.error) result.setAttribute("data-error", "true");
    } catch (_error) {
      result.textContent = "The workflow request failed. Check the application and try again.";
    } finally {
      button.disabled = false;
    }
  });

  const actionSearch = document.getElementById("action-search");
  if (actionSearch) {
    actionSearch.addEventListener("input", () => {
      const query = actionSearch.value.trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll(".action-option[data-action-name]").forEach(option => {
        const match = !query || (option.dataset.actionName + " " + option.textContent).toLowerCase().includes(query);
        option.hidden = !match;
        if (match) visible += 1;
      });
      document.querySelectorAll(".workflow-action-group").forEach(group => {
        const hasAction = Array.from(group.querySelectorAll(".action-option[data-action-name]")).some(option => !option.hidden);
        group.hidden = !hasAction && !group.querySelector(".action-option:not([data-action-name])");
      });
      const empty = document.getElementById("action-search-empty");
      if (empty) empty.hidden = visible > 0;
    });
    document.addEventListener("keydown", event => {
      if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
        event.preventDefault(); actionSearch.focus();
      }
      if (event.key === "Escape" && document.activeElement === actionSearch) {
        actionSearch.value = ""; actionSearch.dispatchEvent(new Event("input")); actionSearch.blur();
      }
    });
  }

  render();
  refreshValidationRowPicker();
  populateVersions({ versions: [] }, null);
  refreshLibrary();
})();
