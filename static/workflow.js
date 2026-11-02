(() => {
  const labels = {
    manual_trigger: ["Manual trigger", "Start the workflow", "bi-play-circle", "trigger-node"],
    read_csv: ["Read CSV", "Load uploaded records", "bi-filetype-csv", "data-node"],
    map_fields: ["Map fields", "Match source columns to customer fields", "bi-arrow-left-right", "map-node"],
    validate_rows: ["Validate rows", "Check required fields", "bi-check2-square", "validate-node"],
    filter_rows: ["Filter rows", "Keep records that match a rule", "bi-funnel", "filter-node"],
    conditional_branch: ["Conditional branch", "Route rows by a CSV condition", "bi-signpost-split", "condition-node"],
    generate_pdfs: ["Generate PDFs", "Create customer documents", "bi-file-earmark-pdf", "document-node"],
    execution_report: ["Execution report", "Summarize the run", "bi-clipboard-data", "report-node"]
  };
  const defaults = [
    "manual_trigger", "read_csv", "validate_rows",
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
    if (currentWorkflowData) {
      const draft = document.createElement("option");
      draft.value = "";
      draft.textContent = "Unsaved draft";
      versionSelect.replaceChildren(draft);
      versionSelect.disabled = true;
    }
  };

  const makeMappingEditor = (node, index) => {
    const config = configOf(node);
    const mapping = config.mapping || {};
    const editor = document.createElement("div");
    editor.className = "mapping-editor";
    const fields = [
      ["customer_name", "Customer name"],
      ["customer_id", "Customer ID"],
      ["email", "Email"],
      ["plan", "Plan"]
    ];
    fields.forEach(([target, label]) => {
      const wrap = document.createElement("label");
      wrap.className = "mapping-field";
      const caption = document.createElement("span");
      caption.textContent = target + " ← " + label;
      const input = document.createElement("input");
      input.className = "form-control form-control-sm";
      input.value = mapping[target] || "";
      input.placeholder = "Source CSV column";
      input.maxLength = 100;
      input.setAttribute("aria-label", "Source CSV column for " + label);
      input.addEventListener("change", () => {
        const next = { ...(config.mapping || {}) };
        if (input.value.trim()) next[target] = input.value.trim();
        else delete next[target];
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

  const render = () => {
    list.replaceChildren();
    nodes.forEach((nodeData, index) => {
      const type = typeOf(nodeData);
      const info = labels[type];
      const row = document.createElement("div");
      row.className = "workflow-node-row";
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
      row.append(node);
      if (index < nodes.length - 1) {
        const connector = document.createElement("div");
        connector.className = "workflow-connector";
        connector.innerHTML = "<span></span>";
        row.append(connector);
      }
      list.append(row);
    });
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
      if (nodes.some(node => typeOf(node) === type)) { result.textContent = "This action is already in the workflow."; return; }
      const reportIndex = nodes.findIndex(node => typeOf(node) === "execution_report");
      const mappingIndex = nodes.findIndex(node => typeOf(node) === "validate_rows");
      const conditionalIndex = nodes.findIndex(node => typeOf(node) === "conditional_branch");
      const pdfIndex = nodes.findIndex(node => typeOf(node) === "generate_pdfs");
      const newNode = type === "conditional_branch" || type === "filter_rows"
        ? { type, field: "plan", operator: "equals", value: "VIP" }
        : type === "map_fields"
          ? { type, mapping: { customer_name: "name", customer_id: "id", email: "email", plan: "plan" } }
          : type;
      let insertAt = reportIndex < 0 ? nodes.length : reportIndex;
      if (type === "map_fields" && mappingIndex >= 0) insertAt = mappingIndex;
      if (type === "filter_rows") insertAt = conditionalIndex >= 0 ? conditionalIndex : pdfIndex >= 0 ? pdfIndex : insertAt;
      if (type === "conditional_branch" && pdfIndex >= 0) insertAt = pdfIndex;
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
  savedSelect.addEventListener("change", loadWorkflow);

  document.getElementById("run-workflow").addEventListener("click", async () => {
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

  render();
  populateVersions({ versions: [] }, null);
  refreshLibrary();
})();
