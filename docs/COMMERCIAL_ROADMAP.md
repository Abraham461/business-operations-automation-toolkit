# OpsPilot Commercial Product Strategy

**Status:** Proposed commercial direction  
**Target:** USD 2,000 in monthly recurring revenue (MRR)  
**Market:** International  
**Product direction:** General-purpose business operations automation platform  
**Initial go-to-market:** Focused workflows for operations-heavy small businesses

## 1. Product positioning

OpsPilot helps small businesses turn repetitive, file-driven operational processes into repeatable workflows without requiring a developer for every task.

**Core promise:** Bring business files and tools together, automate the process, and make every run visible and reviewable.

OpsPilot should evolve from a local automation toolkit into a hosted, multi-tenant SaaS platform. The current repository is an MVP and is not production-ready for public deployment.

## 2. Initial customer wedge

Keep the underlying platform general-purpose, but avoid marketing it as automation for absolutely everyone at launch. Start by validating repeatable workflows with operations-heavy small businesses, such as:

- Recruitment and staffing firms
- Accounting and bookkeeping practices
- Digital and professional services agencies
- Property management operators
- Small distributors and wholesalers

These are candidate segments, not validated demand. Customer interviews and paid pilots must determine which segment has the strongest pain and willingness to pay.

Prioritize workflows that are frequent, rule-based, file-heavy, costly to perform manually, and easy to measure.

## 3. Initial product use cases

1. **Document and spreadsheet processing:** extract structured data from PDFs and spreadsheets, validate it, transform it, and export clean results.
2. **Document generation:** generate customer-specific documents from configurable input schemas and templates.
3. **Operational workflow automation:** connect file intake, validation, transformation, API calls, document generation, and execution reports.
4. **AI-assisted processing:** extract or summarize unstructured text with human review for uncertain results.
5. **Monitoring:** retain execution history, surface failures, and make reruns understandable.

The first release should deliver a small number of complete, reliable workflows rather than a large catalogue of partially implemented integrations.

## 4. Proposed subscription packaging

Pricing below is a hypothesis for testing, not validated market pricing.

| Plan | Proposed price | Intended customer |
|---|---:|---|
| Starter | $49/month | Small team validating its first workflows |
| Growth | $149/month | Small business automating recurring operations |
| Business | $299/month | Team with multiple workflows and higher usage |

Differentiate plans using transparent limits for active workflows, monthly executions, team seats, storage, and support. Do not impose arbitrary limits until infrastructure costs and customer usage are understood.

Illustrative paths to $2,000 MRR:

- 14 Growth customers = $2,086 MRR
- 7 Business customers = $2,093 MRR
- 4 Business + 6 Growth customers = $2,090 MRR

MRR excludes one-time onboarding and implementation fees. Track churn, gross margin, payment fees, AI/API costs, and support time separately.

Offer optional paid onboarding or workflow implementation. Keep service revenue separate from subscription MRR.

## 5. Product roadmap and release gates

### Phase 1 - Complete the MVP workflows

- Finish and verify PDF table extraction and Excel export.
- Finish configurable workflow input schemas and dynamic field mapping.
- Redesign Workflow Builder for clarity and predictable operation.
- Provide useful workflow templates and sample datasets.
- Improve validation, row-level errors, execution reports, and safe reruns.
- Test supported file formats and document extraction edge cases.

**Exit gate:** A new user can complete at least two documented business workflows without developer intervention, and automated tests cover the critical processing paths.

### Phase 2 - SaaS foundation

- Authentication, password recovery, and secure sessions.
- Organization/workspace model and tenant isolation.
- Role-based access control.
- Database migrations and production database support.
- Secure object storage and file lifecycle management.
- Background job queue and worker processes.
- Scheduling, retries, idempotency, and execution status tracking.
- Credential/secret storage and redaction.
- CSRF protection, rate limits, audit logs, and security monitoring.
- Operational logging, backups, and restore procedures.

**Exit gate:** Tenant-isolation and security tests pass; workflows run reliably in a hosted environment; operational failures can be detected and recovered.

### Phase 3 - Billing and customer experience

- Subscription plans and entitlement enforcement.
- Payment provider integration and webhook verification.
- Customer billing portal and cancellation handling.
- Usage metering and transparent quota warnings.
- Guided onboarding and workflow templates.
- Product documentation, support process, and status communication.

**Exit gate:** A customer can register, subscribe, configure a workflow, see usage, manage billing, and cancel without manual database intervention.

### Phase 4 - Commercial validation and growth

- Interview prospective customers about actual workflows and costs.
- Select one beachhead segment based on evidence.
- Run paid pilots with clearly defined success metrics.
- Publish workflow-specific demonstrations and case studies.
- Convert successful pilots into recurring subscriptions.
- Track activation, time-to-first-value, conversion, retention, churn, and gross margin.

**Exit gate:** Repeatable acquisition and retention evidence, not merely sign-ups or demo interest.

## 6. Workflow Builder product principles

The Workflow Builder is strategically important, but it must not become a complex diagram editor that customers need training to operate.

- Use a clear step-by-step workflow layout with readable action cards.
- Make the trigger, input, actions, conditions, and outputs visually distinct.
- Provide a searchable action catalogue and sensible defaults.
- Configure each action in a focused side panel or editor.
- Show required inputs and validation before execution.
- Make variable mapping and data flow understandable.
- Provide sample data, dry-run/preview capability, and actionable errors.
- Show execution progress and step-level results.
- Support templates so users start from working examples.
- Preserve accessibility, keyboard navigation, and responsive layouts.

Prefer a reliable guided builder over advanced canvas features until customer evidence justifies more complexity.

## 7. Technical and security constraints

The current application is local-first and single-operator. It must not be exposed publicly in its current state.

Before public SaaS deployment, address at minimum:

- Authentication, authorization, tenant isolation, and CSRF protection.
- Secure upload validation, storage, download authorization, and retention.
- Server-side secret management and credential redaction.
- SSRF-safe outbound integrations with network-layer egress controls.
- Background execution, timeouts, retries, idempotency, and resource limits.
- Database migrations, backups, monitoring, and incident handling.
- Dependency and vulnerability scanning.

Never use real customer, banking, insurance, or other confidential data in demo workflows. AI output must be reviewable and must not be presented as guaranteed accurate.

## 8. Commercial metrics

Review these metrics during pilots and after launch:

- Qualified prospects interviewed
- Paid pilots started and completed
- Time from signup to first successful workflow
- Weekly active workspaces
- Successful versus failed workflow executions
- Workflow reuse and execution frequency
- Trial-to-paid conversion
- MRR and average revenue per account
- Monthly logo and revenue churn
- Gross margin after hosting, AI, and integration costs
- Support hours per customer

## 9. Immediate repository priorities

1. Review and merge the PDF-to-Excel feature after local end-to-end verification.
2. Retarget and complete the configurable workflow-schema PR after its dependency is merged.
3. Redesign Workflow Builder before expanding the action catalogue.
4. Add end-to-end tests for the core customer workflows.
5. Keep production SaaS infrastructure work behind the MVP reliability and security gates.

**Decision rule:** Build the smallest reliable workflow that saves a real business measurable time or money. Validate willingness to pay before expanding the platform.
