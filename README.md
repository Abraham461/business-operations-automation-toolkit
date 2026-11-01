# Business Operations Automation Toolkit

A local-first Python/Flask portfolio project demonstrating practical automation and QA utilities in one lightweight web application.

> **Project status:** early MVP. The document-generation module has been exercised with fictional sample data. The full Flask application and all three workflows still require end-to-end testing on Windows. This repository does not claim production readiness.

## What it demonstrates

| Module | What it does | Current MVP scope |
|---|---|---|
| **CSV-to-PDF automation** | Converts customer rows from a CSV file into individual PDF summaries and packages them into a ZIP | Fixed sample layout; validates required columns and skips incomplete records |
| **AI text processing** | Produces a concise summary and key details from a text file | Demo mode without a key; optional OpenRouter integration |
| **REST API testing** | Sends one HTTP request and checks its status against an expected status | GET, POST, PUT, PATCH and DELETE; displays response details |

## Technology

- Python 3.10+
- Flask and Jinja templates
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

These tests cover document generation, basic API runner behavior and AI demo mode. They do **not** replace a full browser-based test of the Flask application.

## Project structure

```text
.
├── app.py
├── modules/
│   ├── ai_processing/
│   ├── api_testing/
│   └── document_automation/
├── templates/
├── static/
├── tests/
├── docs/
├── uploads/
├── generated_files/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Security and responsible use

- Fictional sample data only. Never use customer, policyholder, banking or employer-confidential information.
- `.env`, virtual environments, uploaded files and generated outputs are excluded from Git by `.gitignore`.
- Keep the Flask app bound to localhost for this MVP.
- Do not test third-party APIs without authorization.
- AI-generated summaries may be incomplete or inaccurate. Review all output before relying on it.

## Roadmap

1. Complete Windows end-to-end testing and add screenshots.
2. Improve API testing with configurable response extraction, variable chaining and assertions.
3. Add PDF/image OCR with upload validation.
4. Add configurable document templates and downloadable reports.
5. Add authentication, request allowlists, rate limits and deployment hardening before considering public hosting.

## Portfolio note

This project demonstrates Python automation, document generation, API testing and AI-assisted text processing. It is not a production banking, insurance or customer-management system.
