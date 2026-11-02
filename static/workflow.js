(() => {
  const labels = {
    manual_trigger: ["Manual trigger", "Start the workflow", "bi-play-circle", "trigger-node"],
    read_csv: ["Read CSV", "Load uploaded records", "bi-filetype-csv", "data-node"],
    validate_rows: ["Validate rows", "Check required fields", "bi-check2-square", "validate-node"],
    generate_pdfs: ["Generate PDFs", "Create customer documents", "bi-file-earmark-pdf", "document-node"],
    execution_report: ["Execution report", "Summarize the run", "bi-clipboard-data", "report-node"]
  };
  const defaults = ["manual_trigger", "read_csv", "validate_rows", "generate_pdfs", "execution_report"];
  let nodes = defaults.slice();
  let currentWorkflowId = null;
  let currentVersionId = null;
  let currentWorkflowData = null;
  const list = document.getElementById("workflow-nodes");
  const result = document.getElementById("workflow-result");
  const libraryStatus = document.getElementById("workflow-library-status");
  const savedSelect = document.getElementById("saved-workflows");
  const versionSelect = document.getElementById("workflow-version");
  const history = document.getElementById("workflow-history");

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

  const render = () => {
    list.replaceChildren();
    nodes.forEach((type, index) => {
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
      if (index > 0 && index < nodes.length - 1) {
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
      nodes = latest.definition;
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
    nodes = selected.definition;
    render();
    libraryStatus.textContent = "Loaded version " + selected.version_number + ".";
  });

  document.querySelectorAll("[data-add-node]").forEach(button => {
    button.addEventListener("click", () => {
      const type = button.dataset.addNode;
      if (nodes.includes(type)) { result.textContent = "This action is already in the workflow."; return; }
      const reportIndex = nodes.indexOf("execution_report");
      nodes.splice(reportIndex < 0 ? nodes.length : reportIndex, 0, type);
      markDirty();
      result.textContent = "";
      render();
    });
  });

  document.getElementById("reset-workflow").addEventListener("click", () => {
    nodes = defaults.slice();
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
