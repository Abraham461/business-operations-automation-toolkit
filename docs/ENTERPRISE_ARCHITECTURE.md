# OpsPilot Enterprise Architecture

**Operating model:** Hybrid SaaS + implementation + managed automation  
**Primary sales motion:** Enterprise-style discovery, paid pilot, onboarding, and recurring service agreement  
**Target contract:** USD $2,000 per customer per month, validated through paid pilots

## 1. Architecture principles

1. Start with a **modular monolith**, not microservices. The current Flask application is a local-first MVP; keep its Python domain logic reusable while separating web requests from long-running execution.
2. Separate the **control plane** (users, organizations, workflows, permissions, billing, configuration) from the **execution plane** (workers that process customer files and run workflows).
3. Enforce tenant ownership at every data-access boundary. A customer must never be able to read another customer's workflows, files, credentials, or execution logs.
4. Make workflow runs observable, replay-safe where possible, and auditable.
5. Keep customer-specific implementation in configuration, reusable connectors, and versioned workflow definitions. Avoid permanent customer-specific code forks.
6. Treat AI as an optional processing capability with human review and measurable accuracy, not as an autonomous source of truth.

## 2. Logical architecture

```text
Customer users / OpsPilot delivery team
                 |
          Web UI / API
                 |
        Flask application layer
                 |
   +-------------+-------------------+
   | Control plane                   |
   | - Identity / organizations      |
   | - Roles and permissions          |
   | - Workflow definitions/versions  |
   | - Connections and secrets refs   |
   | - Usage, plans, audit events     |
   +-------------+-------------------+
                 |
       PostgreSQL (production)
                 |
          Queue / scheduler
                 |
   +-------------+-------------------+
   | Execution plane                  |
   | - Isolated workflow workers      |
   | - Document processing            |
   | - API / connector actions        |
   | - AI extraction / transformation|
   | - Retry and exception handling  |
   +-------------+-------------------+
        |              |           |
   Object storage   External APIs  AI provider
   encrypted files  allowlisted    Gemini / others
        |
   Execution results, logs, metrics
```

This is a target logical design, not a claim that these components already exist in the repository.

## 3. Application modules

Keep a single deployable Flask application initially, with explicit domain boundaries:

- **Identity and tenancy:** users, organizations, memberships, roles, invitations, sessions.
- **Workflow catalogue:** definitions, drafts, published versions, templates, validation.
- **Workflow runtime:** trigger intake, execution state machine, action dispatch, variables, conditions.
- **Document intelligence:** file classification, extraction, schema mapping, validation, output generation.
- **Integration gateway:** allowlisted HTTP/API connectors, webhooks, OAuth/credential references, connection health.
- **Operations:** execution logs, alerts, exception queues, audit events, support access.
- **Commercial:** plans, entitlements, metering, invoices/subscriptions, contract metadata.
- **Administration:** tenant support tools with audited, time-limited access.

Keep business logic out of Flask route handlers. Route handlers should authenticate, validate request shape, authorize tenant access, and call application services.

## 4. Production data model

Use PostgreSQL for hosted production. SQLite remains suitable for the current single-user local MVP and automated tests, not concurrent multi-tenant production.

Core tables/entities:

| Entity | Purpose |
|---|---|
| organizations | Customer tenant and account configuration |
| users | User identity |
| memberships | User-to-organization relationship and role |
| workflows | Tenant-owned workflow identity and metadata |
| workflow_versions | Immutable published/draft definitions |
| workflow_runs | Tenant, workflow version, status, timestamps, correlation ID |
| step_runs | Per-step status, duration, safe output summary, error classification |
| files | Tenant-scoped object key, type, size, checksum, retention state |
| connections | Integration metadata and secret reference, never raw credentials |
| credentials | Encrypted secret material or external vault reference |
| usage_events | Meterable workflow executions, pages, storage and AI usage |
| subscriptions/contracts | Plan, contract dates, limits, status and billing references |
| audit_events | Security-sensitive actions and administrative access |

Every tenant-owned record must include organization_id or have an enforced ownership path. Use database constraints and authorization tests, not only UI filtering. Consider PostgreSQL row-level security as defense in depth after the application authorization model is established.

## 5. Workflow execution lifecycle

1. User or trigger submits a run request.
2. API authenticates the actor and resolves the active organization.
3. Authorization verifies access to the workflow and its selected version.
4. Input files are validated and stored in tenant-scoped object storage.
5. A run record is created and a queue message is published transactionally (use an outbox pattern to avoid lost jobs).
6. A worker claims the run and executes versioned steps with timeouts and resource limits.
7. Each step records status, duration, retry count, and redacted output metadata.
8. Recoverable failures follow bounded retry policy; non-recoverable failures enter an exception state.
9. Customer and OpsPilot operators receive configured notifications.
10. Outputs are stored with tenant-scoped authorization and retention rules.

Use idempotency keys for trigger intake and external side effects where supported. Do not blindly retry non-idempotent API calls. Provide explicit rerun-from-start and, where safe, rerun-from-step semantics.

## 6. Execution isolation and reliability

- Move long-running work out of Flask request threads into a worker process.
- Use a durable queue such as Celery with Redis or another broker selected after deployment evaluation.
- Enforce per-tenant concurrency, file-size, execution-time, memory, and monthly usage limits.
- Keep workers isolated from the public web process and restrict their network egress.
- Validate file types by content as well as extension; scan uploads where feasible.
- Use temporary per-run working directories and deterministic cleanup.
- Store files in private object storage; use short-lived signed downloads after authorization.
- Add structured logs with run_id, organization_id, workflow_id, and step_id; never log secrets or full sensitive documents.
- Monitor queue age, execution latency, success/failure rates, worker health, and provider errors.
- Test backups and restore procedures.

## 7. Security and privacy baseline

Before production customer data:
- Authentication, MFA option, secure session handling, password reset, and rate limiting.
- Organization-scoped RBAC and authorization on every endpoint and background job.
- CSRF protection for browser sessions and secure CORS policy for APIs.
- Encryption in transit and at rest; secrets held in a managed secret store or envelope-encrypted store.
- SSRF defenses for HTTP actions: HTTPS, strict host allowlists, DNS/IP validation, redirect blocking, egress firewall, timeouts and response-size caps.
- Upload validation, malware scanning where appropriate, private storage, retention, and deletion controls.
- Audit events for login, role changes, credential changes, workflow publication, execution, exports, and support access.
- Data processing terms, subprocessor disclosure, incident process, and customer data export/deletion.
- Dependency scanning, patch process, vulnerability reporting, and security tests.

Do not claim compliance certifications or enterprise security guarantees until independently assessed and actually implemented.

## 8. Hybrid service delivery model

The product supports both customer self-service and OpsPilot-assisted delivery.

**Customer-facing experience**
- Customer workspace, workflow catalogue, run history, exception queue, usage, and reports.
- Customer admins manage users, approved connections, and workflow permissions.
- Customer operators can review exceptions and approve configured steps.

**OpsPilot delivery workspace**
- Separate internal operator identity and least-privilege access.
- Customer onboarding checklist and process discovery notes.
- Workflow configuration and version promotion.
- Deployment/connection health, run monitoring, and support cases.
- Time-limited, audited customer support access with customer authorization.
- Monthly outcome report and workflow optimization review.

Never share a universal admin login or give support staff unrestricted permanent access to customer data.

## 9. Commercial packaging and contract structure

### Target package: OpsPilot Managed Operations Automation

**Target recurring fee:** USD $2,000 per month per customer. This is a hypothesis to validate, not established market pricing.

Include only a clearly defined service envelope:
- Agreed number and scope of production workflows.
- Agreed execution volume, document/page allowance, storage, and concurrency.
- Initial workflow discovery and implementation plan.
- Hosted platform access for named customer users.
- Monitoring, failure notifications, and exception triage.
- Monthly usage and business-outcome review.
- Defined support hours and response targets.
- Defined change-request process for new workflows or material scope changes.

**Implementation/onboarding:** quote separately after discovery. A paid pilot can be scoped and priced separately, with a portion credited toward onboarding or the first contract if commercially sensible. Do not promise free custom development.

**Contract terms to define:** initial term, renewal, cancellation, data processing, confidentiality, subprocessors, service boundaries, support hours, response targets, usage overages, retention/deletion, ownership of customer data and workflow configuration, and change requests. Obtain appropriate legal review before using a standard agreement internationally.

### Qualification gate

Do not quote $2,000/month merely because a prospect likes the demo. First establish:
- Process volume and frequency.
- Current labor and error/rework costs.
- Decision-maker and budget ownership.
- Data/system access and integration feasibility.
- Expected measurable value and payback.
- Security/privacy requirements.
- Delivery effort and ongoing support cost.

A target account should have a credible path to recurring value materially above the fee and a delivery model that preserves healthy gross margin.

## 10. Implementation lifecycle

1. **Discovery:** map the current process, systems, volumes, owners, exceptions, and baseline metrics.
2. **Solution design:** agree the future workflow, human checkpoints, integrations, data boundaries, and acceptance criteria.
3. **Paid pilot:** implement one high-value workflow with synthetic or approved limited data and explicit success measures.
4. **Acceptance:** validate accuracy, throughput, exception handling, security, and user sign-off.
5. **Production onboarding:** configure tenant, users, roles, connections, limits, retention, and monitoring.
6. **Managed operation:** monitor runs, resolve agreed exceptions, report outcomes, and review improvements.
7. **Expansion:** add workflows only after value, support load, and commercial scope are agreed.

## 11. Build sequence

### Priority 0 - Current MVP reliability
- Finish the current PDF-to-Excel and configurable workflow-schema work.
- Redesign Workflow Builder into a clear guided step editor with templates and step-level preview.
- Add robust end-to-end tests and execution reporting.
- Deliver one complete sample workflow with synthetic data.

### Priority 1 - First paid pilot
- Choose one beachhead customer segment after interviews.
- Build one repeatable workflow with reusable configuration.
- Add manual operator monitoring and clear exception handling.
- Document onboarding, acceptance criteria, and outcome measurement.
- Do not build broad multi-tenant infrastructure before the pilot workflow is understood.

### Priority 2 - Hosted SaaS foundation
- Refactor route handlers into service/domain modules.
- Introduce PostgreSQL migrations and organization-scoped data model.
- Add authentication, RBAC, tenant authorization, and audit events.
- Add private object storage and retention controls.
- Add durable queue, worker service, idempotency and bounded retries.
- Add observability, backups, restore tests and deployment automation.

### Priority 3 - Hybrid enterprise operations
- Build internal operator workspace and audited support access.
- Add customer notifications, exception queues and monthly reporting.
- Add integration connection management and secret vault.
- Add usage metering and contract entitlements.
- Add customer onboarding and support workflows.

### Priority 4 - Billing and scale
- Add invoice/contract management for enterprise customers first.
- Add automated subscription billing when self-service plans are justified.
- Add integration catalogue expansion based on repeated customer demand.
- Evaluate service separation only when scaling or team ownership requires it.

## 12. Explicit non-goals for the first enterprise pilot

- Microservices architecture.
- Unlimited workflow executions.
- A large public integrations marketplace.
- Unsupervised AI decisions on critical business records.
- Fully self-serve onboarding for complex enterprise processes.
- Compliance certification claims without assessment.
- Customer-specific code forks.

**Architecture decision:** A modular Flask/Python monolith with PostgreSQL, durable background workers, private object storage, strict tenant authorization, and a separately controlled internal operations workspace is the lowest-complexity credible path from this repository to a hybrid enterprise service.
