# Project Overview

## Purpose

Business Operations Automation Toolkit is a local-first portfolio application that demonstrates three small workflow utilities in one Flask interface.

## Modules

| Module | Input | Output | Current scope |
|---|---|---|---|
| Document automation | CSV with customer fields | ZIP containing one sample PDF per valid row | Fixed sample layout; not a production document template engine |
| AI text processing | `.txt` file | Summary and key details | Demo response without a key; OpenRouter request when configured |
| API testing | HTTP method, URL, optional JSON body, expected status | Status, elapsed time, response headers and response body | One request at a time; expected-status check only |

## Architecture

- Flask handles routes, uploads and page rendering.
- Each module's processing logic lives under `modules/`.
- Jinja templates provide the web interface.
- Uploaded and generated files are stored locally in project folders.

## Data and privacy

The included CSV and text file contain fictional demo content. Do not upload employer, customer, banking, policyholder or other confidential information. The application is intended for local demonstration only.

## Known limitations

- No authentication, authorization or database.
- No PDF/image OCR or batch AI processing.
- No configurable PDF templates.
- API testing does not yet support collections, chained variables, JSONPath assertions or downloadable reports.
- The API testing module makes outbound requests. Do not expose this development app to the public internet; doing so without request allowlisting and additional SSRF protections could create a security risk.
- The application has not yet passed full end-to-end testing in a Windows environment.
