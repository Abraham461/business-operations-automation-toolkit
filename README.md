# Business Operations Automation Toolkit

A local-first Python/Flask portfolio project demonstrating practical automation and QA utilities in one lightweight web application.

> **Project status:** early MVP. The document-generation module has been exercised with fictional sample data. The full Flask application and all workflows still require end-to-end testing on Windows. This repository does not claim production readiness.

## What it demonstrates

| Workspace | What it does | Current MVP scope |
|---|---|---|
| **Workflow Builder** | Connect actions into a controlled sequential process | Manual trigger → CSV reader → optional field mapping → row validation → optional row filter → optional conditional row routing → PDF generation → execution report; saveable definitions, versions and execution history |
| **CSV-to-PDF automation** | Converts customer rows from a CSV file into individual PDF summaries and packages them into a ZIP | Fixed sample layout; validates required columns and skips incomplete records |
| **AI text processing** | Produces a concise summary and key details from a text file | Demo mode without a key; optional OpenRouter integration |
| **REST API testing** | Sends one HTTP request and checks its status against an expected status | GET, POST, PUT, PATCH and DELETE; displays response details |

## Technology

- Python 3.10+
- Flask and Jinja templates
- SQLite (built into Python) for local workflow persistence
- Requests
- ReportLab
- python-dotenv
- HTML and CSS

## Run locally on Windows

1. Install Python 3.10 or newer.
2. Clone or download this repository.
3. Open PowerShell in the project folder.
4. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

5. Open http://127.0.0.1:5000.

If PowerShell blocks virtual-environment activation, run this in the same PowerShell window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Workflow Builder

Open **Workflow Builder** to assemble the customer-document pipeline. Actions execute sequentially and the runner validates the workflow structure before processing the uploaded CSV.

You can now:
- Save a workflow with a name.
- Load saved workflows from the local SQLite database.
- Create a new version when a saved workflow's action sequence or condition changes.
- Review recent execution history for each saved workflow.
- Map differently named source CSV columns to the required customer fields before validation.
- Filter valid records using a configurable CSV column and operator before downstream actions.
- Add HTTPS API calls with JSON headers/body, response extraction and variable chaining, restricted to explicitly allowlisted hosts.
- Optionally configure one conditional row branch using a CSV column and an operator.
- Route matching rows to PDF generation. When no rows match, PDF generation is marked **skipped** and the workflow report explains the false branch.
- Run either a saved version or an unsaved draft.

Filter and condition operators: equals, does not equal, contains, greater than, less than, is empty and is not empty. Text comparisons are case-insensitive. Numeric comparisons require numeric cell values. PDF generation receives only the rows that pass the filter. If a filter returns no records, downstream PDF generation is marked **skipped** rather than failed.

HTTP Request actions support GET, POST, PUT, PATCH and DELETE. They require an exact hostname in `OPSPILOT_HTTP_ALLOWED_HOSTS`, use HTTPS only, reject redirects and private/reserved DNS addresses, enforce timeouts and cap response bodies at 1 MB. Configure response extraction as variable-name-to-JSON-path mappings; later request fields can reference values with `{{variable_name}}`. Do not store API secrets directly in workflow definitions. Full public deployment still requires authentication, CSRF protection and stronger network-layer egress controls.

The database is created automatically at `instance/opspilot.sqlite3` on first launch. Set `OPSPILOT_DATABASE` in `.env` to use another local database path. Existing workflow files are not migrated because the earlier MVP did not persist them.

The field mapper can map the customer name, customer ID, email and plan fields. It preserves original source columns and adds mapped canonical fields. The current MVP supports one row filter and one conditional branch per workflow. Nested branches, arbitrary expressions and loops are not supported.

## Try the sample workflows

### 1. CSV-to-PDF automation

Open **Documents** and upload `static/sample_customers.csv`.

Required CSV headers: `customer_name`, `customer_id`, `email`, `plan`.

The app returns a ZIP containing one generated PDF per valid row.

### 2. AI text processing

Open **AI Processing** and upload `static/sample_document.txt`. Without an API key, the app returns a clearly labelled demo response.

To enable live processing, add your OpenRouter key to `.env`:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Restart the app after changing `.env`. Never commit `.env` or share API keys.

**Current limitation:** only `.txt` uploads are supported. PDF/image OCR and structured extraction are future enhancements.

### 3. REST API testing

Open **API Testing** and try this public placeholder endpoint:

```text
https://jsonplaceholder.typicode.com/posts/1
```

Use only APIs you own or are explicitly authorized to test. The runner sends requests from your local machine. Do not expose this app publicly; outbound request functionality requires stronger SSRF controls and request allowlisting before deployment.

## Run the module tests

After installing dependencies:

```powershell
python -m unittest discover -s tests -v
```

These tests cover document generation, basic API runner behavior, AI demo mode, workflow persistence, field mapping, row filtering, conditional row routing and HTTP action configuration/variable chaining. They do **not** replace a full browser-based test of the Flask application.

## Project structure

```text
.
├── app.py
├── modules/
│   ├── ai_processing/
│   ├── api_testing/
│   ├── document_automation/
│   └── workflow_engine/
├── templates/
├── static/
├── tests/
├── docs/
├── uploads/
├── generated_files/
├── instance/                 # local SQLite database; ignored by Git
├── .env.example
├── .gitignore
└── requirements.txt
```

## Security and responsible use

- Fictional sample data only. Never use customer, policyholder, banking or employer-confidential information.
- `.env`, virtual environments, the SQLite database, uploaded files and generated outputs are excluded from Git.
- Keep the Flask app bound to localhost for this MVP.
- Do not test third-party APIs without authorization.
- AI-generated summaries may be incomplete or inaccurate. Review all output before relying on it.
- The workflow database has no user authentication or per-user authorization. It is intended for a single local operator only.

## Roadmap

1. **Completed:** persist workflow definitions, versions and execution history locally.
2. **Completed in this branch:** configurable field mapping, row filtering and one conditional row branch.
3. **Added in this branch:** configurable HTTPS requests with host allowlisting, response extraction and variable chaining. Add AI processing actions to the workflow catalogue.
4. Improve API testing with configurable response extraction, variable chaining and assertions.
5. Add scheduling, background execution, retries and monitoring.
6. Add authentication, CSRF protection, request allowlists, rate limits and deployment hardening before considering public hosting.

## Portfolio note

This project demonstrates Python automation, document generation, API testing and AI-assisted text processing. It is not a production banking, insurance or customer-management system.
