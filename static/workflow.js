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
  const list = document.getElementById("workflow-nodes");
  const result = document.getElementById("workflow-result");
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
        remove.addEventListener("click", () => { nodes.splice(index, 1); render(); });
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
  document.querySelectorAll("[data-add-node]").forEach(button => {
    button.addEventListener("click", () => {
      const type = button.dataset.addNode;
      if (nodes.includes(type)) { result.textContent = "This action is already in the workflow."; return; }
      const reportIndex = nodes.indexOf("execution_report");
      nodes.splice(reportIndex < 0 ? nodes.length : reportIndex, 0, type);
      result.textContent = "";
      render();
    });
  });
  document.getElementById("reset-workflow").addEventListener("click", () => {
    nodes = defaults.slice();
    result.textContent = "";
    render();
  });
  document.getElementById("run-workflow").addEventListener("click", async () => {
    const file = document.getElementById("workflow-file").files[0];
    if (!file) { result.textContent = "Choose a CSV file before running the workflow."; return; }
    const button = document.getElementById("run-workflow");
    button.disabled = true;
    result.textContent = "Running workflow…";
    const data = new FormData();
    data.append("file", file);
    data.append("workflow", JSON.stringify(nodes));
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
      if (!response.ok && payload.error) result.setAttribute("data-error", "true");
    } catch (_error) {
      result.textContent = "The workflow request failed. Check the application and try again.";
    } finally {
      button.disabled = false;
    }
  });
  render();
})();
