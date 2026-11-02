# OpsPilot Product Blueprint

**Status:** Product and technical blueprint  
**Product direction:** Workflow-first business automation platform  
**Ambition:** Advanced, developed in controlled phases  
**Initial implementation:** Local-first modular monolith

---

## 1. Product vision

OpsPilot is a configurable business process automation platform for small businesses, operations teams, business analysts, QA teams and automation consultants.

Users design, execute, monitor and improve repeatable business processes by connecting data inputs, business rules, document processing, AI-assisted tasks, API calls and notifications in reusable workflows.

OpsPilot should not remain a collection of unrelated utilities. Its defining capability is the workflow engine: existing document generation, AI processing and API testing become reusable actions inside complete business processes.

### Product promise

**Design a process once. Run it consistently. See exactly what happened.**

### Example end-to-end workflow

1. A user uploads a customer spreadsheet.
2. OpsPilot parses the rows and validates required fields.
3. Invalid rows are separated and reported.
4. Valid records are transformed into a standard format.
5. A document is generated for each valid record.
6. An optional AI action classifies or summarizes selected content.
7. An email or webhook notification reports completion.
8. OpsPilot stores the execution history and produces a downloadable report.

### Target users

- Operations teams automating repetitive administrative tasks.
- Small businesses processing spreadsheets, forms and customer documents.
- Business analysts designing and improving operational processes.
- QA and technical teams automating API checks and repeatable test sequences.
- Freelancers and consultants delivering automation solutions to clients.

### Product principles

1. Workflow-first: all major capabilities should be available as workflow actions.
2. Visual and understandable: users should understand what will run and in what order.
3. Configurable, not code-dependent: common automations should not require users to write Python.
4. Observable: every execution and step should have a clear status, duration and result.
5. Safe by default: credentials, files, network access and execution limits must be controlled.
6. Modular: new actions and integrations should not require rewriting the workflow engine.
7. Incremental: prove each layer before introducing infrastructure or complexity.

---

## 2. Product scope

### Core modules

| Module | Responsibility | Capabilities |
|---|---|---|
| Dashboard | Workspace overview | Workflow count, recent runs, success/failure summaries, quick actions |
| Workflow Studio | Design processes | Visual canvas, nodes, edges, configuration panels, validation, save and version |
| Workflow Engine | Execute definitions | Graph validation, step scheduling, context, branching, retries, error handling |
| Data and Documents | Process business files | CSV, Excel, PDF, DOCX, TXT and images; parsing, extraction, validation, transformation, PDF output |
| AI Processing | Optional intelligence | Summarization, classification, structured extraction and text generation |
| API and Integration Hub | Connect systems | HTTP requests, authentication, environment variables, response extraction, assertions |
| Logic | Control execution | If/else, switch, loops, filters, mapping, merge, stop and continue |
| Notifications | Communicate outcomes | Email and webhook notifications |
| Triggers and Scheduler | Start workflows | Manual run, file upload, scheduled execution and inbound webhook |
| Monitoring and Reports | Explain performance | Run history, node logs, durations, failures, downloadable execution reports |
| Administration | Manage access | Users, roles, credentials, settings and audit history |

### Initial action catalogue

| Category | Candidate actions |
|---|---|
| Triggers | Manual trigger, file upload trigger, scheduled trigger, webhook trigger |
| Files | Read file, detect type, extract text, parse CSV, parse Excel, generate PDF |
| Data | Map fields, filter rows, validate rows, transform values, merge datasets |
| Logic | If/else, switch, loop over records, stop, continue, delay |
| AI | Summarize text, classify text, extract structured fields, generate text |
| API | HTTP request, set authentication, extract JSON values, assert response |
| Communication | Send email, call webhook |
| Operations | Log message, create report, mark workflow complete |

The first workflow release should implement a dependable subset rather than every action. Suggested initial actions: manual trigger, CSV reader, row validator, field mapper, condition, PDF generator, HTTP request, log and end node.

### Product non-goals for the first release

- Replacement for enterprise RPA or full BPMN suites.
- Public marketplace of community workflow templates.
- Dozens of native SaaS connectors.
- Autonomous agents with unrestricted action permissions.
- Arbitrary Python or shell execution from workflow nodes.
- Distributed multi-region execution.
- Production handling of confidential banking, insurance or customer records before security, privacy and compliance review.

---

## 3. User journeys

### Journey A: Build and run a workflow

1. User opens Workflow Studio and creates a workflow.
2. User adds a trigger and action nodes to the canvas.
3. User connects nodes and configures each action.
4. User maps output values from previous nodes into later inputs.
5. User validates the workflow and resolves configuration errors.
6. User saves a version and starts a manual test run.
7. User inspects node-level inputs, outputs, duration and errors.
8. User publishes or enables the workflow after successful testing.

### Journey B: Run an existing workflow

1. User selects a saved workflow.
2. User provides required input, such as a file.
3. OpsPilot validates the input and creates an execution record.
4. Engine executes the saved workflow version.
5. User sees live or refreshed progress.
6. User reviews the result and downloads generated files or a report.

### Journey C: Diagnose a failed run

1. User opens execution history.
2. User selects a failed execution.
3. OpsPilot identifies the failed node and error category.
4. User inspects sanitized input/output and execution logs.
5. User corrects the configuration or source data.
6. User retries safely, with duplicate side effects controlled where possible.

---

## 4. Architecture

### Architecture decision

Use a **modular monolith** initially. Flask remains the web application framework while domain logic is separated into services, engine components and action modules. Do not start with microservices.

The workflow editor creates and edits workflow definitions. The engine validates and executes those definitions independently of the editor.

### Logical layers

1. Presentation: dashboard, workflow canvas, configuration panels, execution history.
2. Application API: authentication, workflow CRUD, validation, run requests, file and credential endpoints.
3. Domain services: workflow management, versioning, execution management, file handling.
4. Workflow engine: graph validation, execution context, node scheduling, branching, retries and cancellation.
5. Action registry: maps a node type to a trusted action implementation and its schema.
6. Persistence: workflows, versions, executions, node executions, credentials, schedules and audit events.
7. Adapters: file formats, AI providers, HTTP APIs, SMTP and webhooks.

### Suggested stack

| Layer | Initial choice | Later option |
|---|---|---|
| Backend | Python + Flask | Keep unless scale justifies change |
| Frontend | HTML, CSS, JavaScript | Component framework only if UI complexity warrants it |
| Workflow canvas | JavaScript graph/canvas library | Custom nodes and interaction layer |
| Database | SQLite | PostgreSQL for hosted multi-user use |
| ORM/migrations | SQLAlchemy + Alembic | Retain |
| Background execution | Synchronous local runner | RQ + Redis worker |
| File processing | ReportLab, Pandas, OpenPyXL | Add format-specific libraries as needed |
| AI | Provider adapter around OpenRouter | Add provider adapters |
| HTTP | Requests | Controlled HTTP client adapter |
| Testing | Pytest | Add browser tests when UI stabilizes |

### Proposed repository structure

```text
opspilot/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── routes/
│   │   ├── dashboard.py
│   │   ├── workflows.py
│   │   ├── executions.py
│   │   ├── documents.py
│   │   ├── integrations.py
│   │   └── settings.py
│   ├── models/
│   │   ├── user.py
│   │   ├── workflow.py
│   │   ├── execution.py
│   │   └── credential.py
│   ├── services/
│   │   ├── workflow_service.py
│   │   ├── execution_service.py
│   │   └── file_service.py
│   ├── engine/
│   │   ├── validator.py
│   │   ├── executor.py
│   │   ├── context.py
│   │   └── registry.py
│   ├── actions/
│   │   ├── triggers/
│   │   ├── files/
│   │   ├── data/
│   │   ├── logic/
│   │   ├── ai/
│   │   ├── api/
│   │   └── notifications/
│   └── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── icons/
├── migrations/
├── tests/
├── instance/
├── storage/
├── docs/
├── app.py
├── requirements.txt
└── .env.example
```

This is a target structure, not a one-step migration. Refactor the existing app incrementally and preserve current working modules.

### Workflow definition format

A workflow is a directed graph of nodes and edges. Nodes contain a stable ID, registered action type, configuration and optional display metadata. Edges connect output ports to input ports. Definitions are stored as JSON and versioned.

Example:

```json
{
  "name": "Customer Document Automation",
  "nodes": [
    {"id": "start", "type": "trigger.manual", "config": {}},
    {"id": "read", "type": "file.read_csv", "config": {}},
    {
      "id": "validate",
      "type": "data.validate_rows",
      "config": {"required_fields": ["customer_name", "email"]}
    },
    {"id": "pdf", "type": "document.generate_pdf", "config": {}},
    {"id": "end", "type": "workflow.end", "config": {}}
  ],
  "edges": [
    {"source": "start", "target": "read"},
    {"source": "read", "target": "validate"},
    {"source": "validate", "target": "pdf"},
    {"source": "pdf", "target": "end"}
  ]
}
```

The engine must validate node types, node configuration, edge references, graph reachability, required inputs, cycles and workflow limits before execution. Begin with acyclic graphs and explicit condition branches. Add controlled loop nodes later; do not implement arbitrary graph cycles in the first engine.

### Execution context and data mapping

Each node receives:
- Its validated configuration.
- Explicit workflow input.
- Outputs from permitted upstream nodes.
- Execution metadata such as run ID and cancellation state.

Each action returns a structured result, for example:

```json
{
  "status": "success",
  "output": {
    "valid_rows": [],
    "invalid_rows": [],
    "valid_count": 12,
    "invalid_count": 2
  }
}
```

Use a safe interpolation mechanism such as `{{ steps.read.output.rows }}` with a parser that resolves approved paths. Never use Python `eval` to evaluate user expressions. Define how missing values, nulls, arrays and type mismatches behave.

### Execution statuses

Workflow: `queued`, `running`, `success`, `failed`, `cancelled`.

Node: `pending`, `running`, `success`, `failed`, `skipped`, `retrying`.

Persist execution and node status transitions so the user can inspect a run after a restart.

### Core data model

| Entity | Key fields | Purpose |
|---|---|---|
| User | id, email, password_hash, role, created_at | Account and access |
| Workflow | id, owner_id, name, description, status | Workflow identity |
| WorkflowVersion | id, workflow_id, version, definition_json, created_at | Immutable workflow definition |
| Execution | id, workflow_version_id, status, started_at, ended_at, trigger_type | Workflow run |
| NodeExecution | id, execution_id, node_id, status, input_json, output_json, error, duration_ms | Per-node result |
| Credential | id, owner_id, provider, encrypted_secret, created_at | External credentials |
| Schedule | id, workflow_id, cron_expression, enabled, next_run_at | Scheduled trigger |
| AuditEvent | id, actor_id, action, target_type, target_id, created_at | Security and change history |

Workflow versions should be immutable once used by an execution. This makes every historical run reproducible against the definition that produced it.

### Action plugin contract

Every action should declare:
- Unique type identifier and display name.
- Category and description.
- Configuration schema and validation.
- Input and output schema.
- Execution function.
- Timeout and retry policy.
- Whether it performs external side effects.
- Required permissions or credential types.

The registry should only load trusted built-in actions in the first releases. Do not dynamically import arbitrary user-supplied code.

---

## 5. Phased development roadmap

Estimates assume one developer working approximately 10–15 hours per week. They are planning estimates, not fixed delivery promises.

### Phase 0: Baseline and stabilization
**Estimate: 1 week**

- Pull and run the current OpsPilot code.
- Verify all existing routes and three modules on Windows.
- Add automated regression tests around current document generation, AI demo/live mode and API testing.
- Capture current behavior and document known limitations.
- Create a dedicated feature branch and establish a clean commit baseline.

**Exit criteria:** existing modules run locally; critical regressions are covered by tests; no secrets or user data are committed.

### Phase 1: Application foundation
**Estimate: 1–2 weeks**

- Refactor Flask application into a maintainable package structure.
- Introduce SQLAlchemy and SQLite.
- Add database migrations.
- Create workflow, workflow version, execution and node execution models.
- Add workflow CRUD endpoints and basic workflow list/detail pages.
- Preserve existing standalone module pages while preparing them for action reuse.

**Exit criteria:** workflows can be created, saved, listed, edited and versioned; data survives application restart.

### Phase 2: Workflow engine core
**Estimate: 2–3 weeks**

- Define workflow JSON schema.
- Build node registry and action contract.
- Implement graph validation and topological execution.
- Implement execution context and safe variable resolution.
- Persist workflow and node execution states.
- Implement structured logs, timeout handling and error propagation.
- Add cancellation support where practical.

**Exit criteria:** a workflow defined in JSON can execute several registered actions in order, persist each result and report a failure accurately.

### Phase 3: Visual Workflow Studio
**Estimate: 2–3 weeks**

- Build canvas with draggable nodes and connecting edges.
- Add node library and configuration side panel.
- Add save, load, delete and version selection.
- Add client-side validation feedback and server-side validation.
- Add manual test run and execution status display.
- Add a starter template gallery.

**Exit criteria:** a user can build, save, validate and run a simple workflow without editing JSON manually.

### Phase 4: Business automation actions
**Estimate: 2–3 weeks**

- Implement CSV and Excel parsing.
- Implement row validation, field mapping and filtering.
- Integrate existing PDF generator as an action.
- Add file output handling and downloadable results.
- Add conditional branching and controlled record iteration.
- Add execution summary report.

**Exit criteria:** a complete spreadsheet-to-validated-records-to-PDF workflow runs from the visual editor.

### Phase 5: API and AI action expansion
**Estimate: 2–3 weeks**

- Upgrade API action with methods, headers, query parameters and JSON body.
- Add credential references and environment variables.
- Add response extraction and assertions.
- Add AI summarize, classify and structured extraction actions.
- Add provider abstraction and structured-output validation.
- Add request timeouts, retry policy and cost/usage tracking where available.

**Exit criteria:** a workflow can call an API, map response data into a later action and use an AI action with validated output.

### Phase 6: Scheduling, notifications and monitoring
**Estimate: 2–3 weeks**

- Introduce background worker and queue.
- Add scheduled triggers.
- Add email and webhook notification actions.
- Add execution history filters and node-level logs.
- Add retry of eligible failed runs and safe duplicate prevention.
- Add dashboard metrics and downloadable run reports.

**Exit criteria:** workflows can run asynchronously or on a schedule, notify users and retain useful execution history.

### Phase 7: Security and hosted beta
**Estimate: 3–4 weeks, depending on deployment target**

- Add authentication, authorization and role checks.
- Add CSRF protection, secure session configuration and secret encryption.
- Harden upload storage and outbound HTTP controls.
- Add SSRF protection and egress restrictions.
- Add rate limits, execution quotas, retention settings and audit events.
- Move to PostgreSQL for hosted multi-user deployment.
- Add production configuration, backups, monitoring and deployment automation.
- Run security and end-to-end tests before inviting external users.

**Exit criteria:** security review and deployment checklist are passed for a limited beta. Do not describe the system as production-ready until the actual hosting environment, threat model and operational controls have been reviewed.

### Indicative total

Approximately 15–21 weeks at 10–15 hours per week, with uncertainty around visual editor complexity, integrations and deployment hardening. A narrower usable workflow MVP can be delivered much earlier by completing Phases 0–4.

---

## 6. Implementation plan and engineering standards

### First implementation milestone

Build the smallest complete vertical slice:

**Manual trigger → Read CSV → Validate rows → Generate PDF → Execution report**

This validates the entire product architecture:
- Workflow definition and persistence.
- Visual editor and node configuration.
- Action registry.
- Engine and execution context.
- File handling.
- Node-level logs.
- Downloadable output.

Do not start with a large library of disconnected nodes. Prove one end-to-end workflow first.

### Work breakdown

1. Stabilize current code and create a feature branch.
2. Design workflow definition schema and action interface.
3. Add database models and migrations.
4. Implement node registry and graph validator.
5. Implement sequential workflow executor.
6. Wrap the existing CSV/PDF code as registered actions.
7. Create workflow CRUD endpoints.
8. Build a basic canvas and configuration panel.
9. Implement manual execution and run details.
10. Add tests for success, failure, invalid graph, missing inputs and file errors.
11. Add conditional branching and data mapping.
12. Expand to API and AI actions.

### API surface proposal

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/workflows` | List workflows |
| POST | `/api/workflows` | Create workflow |
| GET | `/api/workflows/{id}` | Get workflow and latest version |
| PUT | `/api/workflows/{id}` | Update workflow metadata |
| POST | `/api/workflows/{id}/versions` | Save a new workflow version |
| POST | `/api/workflows/{id}/validate` | Validate definition |
| POST | `/api/workflows/{id}/run` | Start execution |
| GET | `/api/executions` | List execution history |
| GET | `/api/executions/{id}` | Get run summary |
| GET | `/api/executions/{id}/nodes` | Get node-level execution details |
| POST | `/api/executions/{id}/cancel` | Request cancellation |
| POST | `/api/executions/{id}/retry` | Retry an eligible execution |

These are proposed routes. Authentication and authorization must protect all user-owned resources before multi-user deployment.

### Testing strategy

- Unit tests: each action, schema validator, data mapper and status transition.
- Engine tests: sequential flow, branch selection, missing dependency, invalid graph, node failure, timeout and cancellation.
- Integration tests: database persistence, file lifecycle, API adapter and AI adapter using mocks.
- End-to-end tests: create workflow, run it, inspect output and download artifacts.
- Security tests: malicious filenames, oversized uploads, invalid content types, SSRF targets, redirect handling, secret leakage and unauthorized resource access.
- Regression tests: existing standalone document, AI and API pages remain functional during migration.

### Definition of done for every feature

A feature is complete only when:
- Inputs and outputs are defined.
- Invalid input is rejected with a useful error.
- Sensitive values are not exposed in logs or responses.
- Unit and relevant integration tests pass.
- UI loading, empty, success and failure states are handled.
- Documentation is updated.
- The feature does not break existing modules.

---

## 7. Security, privacy and operational requirements

The current application is a local-first MVP. It has no authentication or authorization and its API testing capability makes outbound requests. Do not expose it publicly until the controls below have been implemented and tested.

### Required controls

- Authentication and server-side authorization for every user-owned resource.
- CSRF protection for state-changing browser requests.
- Secure cookies, session expiry and production secret management.
- Encrypted credential storage; never store provider secrets in workflow JSON.
- Upload extension, MIME and content validation; generated internal filenames; per-user storage isolation; size limits and retention controls.
- SSRF protection for HTTP actions: block loopback, private, link-local and reserved IP ranges; validate DNS resolution and redirects; restrict ports and protocols; apply timeouts, response-size limits and egress policy.
- No arbitrary shell commands, Python evaluation or unrestricted file-system paths.
- Workflow quotas: maximum nodes, execution duration, retries, file size, API request count and concurrent runs.
- Sanitized logs and careful handling of personal or confidential data.
- AI output schema validation and human review for consequential decisions.
- Audit history for workflow edits, credential changes and administrative actions.
- Backups, restore tests, dependency updates and operational monitoring before hosted beta.

### Reliability requirements

- Persist execution and node status transitions.
- Use bounded retries only for eligible transient failures.
- Do not automatically retry non-idempotent side effects without a deduplication strategy.
- Record the workflow version used by every run.
- Provide useful failure messages and correlation IDs.
- Apply retention policies to uploaded files, generated outputs and logs.

---

## 8. Product success measures

Track operational outcomes rather than vanity metrics.

| Measure | What it indicates |
|---|---|
| Workflow completion rate | Reliability of workflow execution |
| Failed run rate by action | Weak or unstable actions and integrations |
| Median and p95 execution duration | Performance and bottlenecks |
| Manual steps removed | Practical automation value |
| Estimated time saved | Business value, with assumptions documented |
| Workflow reuse frequency | Whether users find workflows reusable |
| Recovery rate after failure | Quality of diagnosis and retry experience |
| Active workflows per workspace | Adoption of the core product |

For time-saved calculations, record the user's baseline estimate and the automated duration separately. Do not present estimates as measured savings unless the measurement method supports the claim.

---

## 9. Release definition

### Advanced local MVP

The first meaningful product release should include:
- Premium dashboard and navigation.
- Persistent workflow definitions and versions.
- Visual workflow canvas.
- Validated sequential workflow engine.
- Manual trigger.
- CSV reader, data validation and mapping.
- PDF generation action.
- Conditional branch.
- Execution history and node-level logs.
- Downloadable output and execution report.
- Local configuration and documented setup.

### Hosted beta

A hosted beta additionally requires:
- Authentication and authorization.
- PostgreSQL.
- Background workers and scheduling.
- Encrypted credentials.
- Email/webhook integrations.
- SSRF and upload security controls.
- Rate limits, quotas, audit logs and retention.
- Monitoring, backups and restore procedure.
- Security review and end-to-end deployment tests.

---

## 10. Immediate next steps

1. Verify the current OpsPilot UI and all three existing modules on Windows.
2. Create a feature branch before the architectural refactor.
3. Agree on the first workflow definition schema and action contract.
4. Add SQLite persistence and workflow version models.
5. Implement the engine independently of the UI.
6. Wrap the current CSV-to-PDF process as the first end-to-end workflow.
7. Build the first usable visual canvas around that workflow.

**Recommended first milestone:** deliver the CSV-to-PDF vertical slice through the workflow builder. It gives OpsPilot a real workflow product foundation while reusing existing work and avoiding premature infrastructure.
