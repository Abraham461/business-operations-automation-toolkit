# Tenant Isolation and Enterprise Security Design

**Status:** Architecture proposal for Issue #12  
**Applies to:** Hosted, multi-customer OpsPilot deployment  
**Current application status:** Local, single-operator MVP. This design is not evidence that the current application is production-ready.

## 1. Objective and security boundary

OpsPilot's hybrid enterprise model gives each customer organization a managed workspace. Customer A must never be able to read, change, execute, download, or infer Customer B's workflows, workflow versions, execution records, uploaded files, generated documents, credentials, usage metrics, or audit records.

The organization (tenant) is the primary data-ownership boundary. Authorization must be enforced by the server for every request. Hiding UI controls or filtering results in JavaScript is not a security control.

**Release gate:** Do not expose a shared hosted instance to real customer data until authentication, tenant scoping, authorization, CSRF, file isolation, credential handling, audit logging, backups, and cross-tenant tests are implemented and reviewed.

## 2. Current-state findings

The current MVP has the following constraints:

- `app.py` exposes workflow list, save, load, execution, history, and download routes without login or organization checks.
- `WorkflowStore` stores workflows, versions, and executions without an organization identifier.
- Uploads and generated files use shared application-level directories.
- The Flask secret has a development fallback.
- There is no user, membership, role, or audit-event model.
- Local SQLite is appropriate for the current single-operator development setup, not a shared multi-customer deployment.

The existing local workflow database and local-only behavior must remain usable during the transition.

## 3. Proposed logical data model

Use stable UUID identifiers. Every customer-owned record must have a non-null `organization_id` and a database relationship to the owning organization.

### Core identity tables

| Table | Important fields | Purpose |
|---|---|---|
| organizations | id, name, status, created_at, updated_at | Customer tenant |
| users | id, email_normalized, password_hash or identity_subject, status, created_at | Human identity |
| memberships | id, organization_id, user_id, role, status, created_at | User's organization access |
| invitations | id, organization_id, email_normalized, role, token_hash, expires_at, accepted_at | Controlled onboarding |
| audit_events | id, organization_id, actor_user_id, event_type, target_type, target_id, metadata_json, created_at | Security and operational history |

Enforce a unique membership per (organization_id, user_id), unique normalized user email, and hashed invitation tokens. Do not store raw invitation tokens or passwords.

### Customer-owned operational tables

Add `organization_id` to:

- workflows
- workflow_versions (directly, or enforce ownership through a composite foreign key to workflows)
- workflow_executions
- credentials / integration connections
- schedules and background jobs when introduced
- uploaded-file metadata and generated-artifact metadata
- customer baselines, usage aggregates, support cases, and reports when introduced

Use composite uniqueness and foreign keys where practical, such as `(organization_id, workflow_id)`, so the database helps prevent cross-tenant relationships. Application checks remain mandatory.

### File storage layout

Store files under an organization-scoped, opaque path, for example:

`storage/orgs/<organization_uuid>/uploads/<random_file_id>`

`storage/orgs/<organization_uuid>/artifacts/<random_file_id>`

Never use a user-supplied filename as a storage path. Resolve downloads through an authorized database record, verify its organization, then open the stored path. Do not expose filesystem paths or permanent public file URLs.

## 4. Roles and permissions

| Capability | Owner | Admin | Builder | Operator | Viewer |
|---|---:|---:|---:|---:|---:|
| View workspace and reports | Yes | Yes | Yes | Yes | Yes |
| Invite/remove members | Yes | Yes | No | No | No |
| Change roles and workspace settings | Yes | Limited | No | No | No |
| Create/edit workflows | Yes | Yes | Yes | No | No |
| Run workflows | Yes | Yes | Yes | Yes | No |
| View execution details and artifacts | Yes | Yes | Yes | Yes | Yes |
| Manage integration credentials | Yes | Yes | No by default | No | No |
| Delete organization | Yes, re-auth required | No | No | No | No |

Roles are organization-scoped. A user may have different roles in different organizations. Apply least privilege and deny by default. Do not rely on a role value submitted by the browser.

Internal OpsPilot support personnel are not automatically members of customer organizations. Support access must use a separate, explicit grant.

## 5. Authentication and session controls

Select and document the identity implementation before production coding. Prefer a mature, maintained authentication library or managed identity provider over custom password and token code.

Minimum requirements:

- Secure login, logout, account recovery, invitation acceptance, and email verification if password-based identity is selected.
- Password hashes using a modern password-hashing algorithm and library; never reversible encryption or plaintext.
- HTTPS-only, HttpOnly, SameSite cookies; secure cookie flag in hosted production.
- Session rotation after login and privilege changes; expiry and revocation.
- CSRF protection for every cookie-authenticated state-changing request.
- Rate limits for login, recovery, invitations, and other sensitive endpoints.
- Re-authentication for destructive or sensitive account actions.
- No secrets or session tokens in logs, URLs, analytics, or error responses.

The development secret-key fallback must not be accepted in hosted production. Production startup should fail closed if required secrets or secure settings are missing.

## 6. Tenant authorization pattern

Every request that touches customer data must resolve an authenticated user and an active organization membership on the server.

Use a shared authorization/service boundary rather than adding ad-hoc filters independently to route handlers. Repository methods should require an organization identifier for tenant-owned data access.

Examples of required behavior:

- List workflows only for the active organization.
- Load a workflow using both its ID and organization ID.
- Save a workflow only when the requested workflow belongs to the active organization.
- Verify workflow, version, execution, and organization ownership as one consistent chain before running.
- List execution history only after verifying workflow ownership.
- Authorize artifact download against the owning execution and organization before reading the file.
- Scope credentials, usage, audit events, reports, and background jobs to the organization.
- Return a consistent not-found response for cross-tenant object IDs to reduce resource enumeration.

Do not accept `organization_id`, role, or owner identity from an untrusted request body as proof of access. Derive the active organization from the authenticated session and validated membership.

## 7. Managed-service support access

For OpsPilot's hybrid service model, support access must be explicit and auditable:

1. Customer Owner/Admin requests or approves support access.
2. Grant specifies organization, permitted actions, reason, and expiry.
3. Access is time-limited and revocable.
4. Sensitive actions require additional approval or customer participation.
5. Every access and action is written to the audit log.
6. Access expires automatically; no shared customer passwords or permanent unrestricted support account.

Do not create a hidden universal admin bypass.

## 8. Database and migration strategy

- Keep SQLite for local single-user development and tests.
- Use PostgreSQL for a hosted multi-tenant deployment.
- Introduce versioned migrations before changing production schemas.
- Back up the local database before migration.
- For existing local data, create one explicitly named local organization and associate existing workflows, versions, and executions with it through a one-time migration.
- Never silently assign real customer records to an arbitrary tenant.
- Validate row counts, foreign keys, ownership links, and artifact references after migration.
- Make migrations repeatable or safely fail when preconditions are not met.
- Do not introduce distributed services until actual load requires them.

## 9. Audit and data protection

Record at minimum:

- Authentication and session security events.
- Invitation, membership, and role changes.
- Workflow creation, updates, version publication, deletion, and execution.
- Credential create/update/delete and integration use metadata.
- File upload, download, export, and deletion.
- Support-access grants, use, expiry, and revocation.
- Organization settings and retention changes.

Audit metadata must be structured and sanitized. Do not log passwords, access tokens, API keys, full uploaded documents, or unnecessary personal data. Define retention and deletion behavior before onboarding customers.

Credentials must be encrypted at rest using a managed key or a properly configured application encryption service. Never put secrets in workflow JSON, source control, URLs, or plain-text logs.

## 10. Required security test matrix

Use at least two organizations, two users per organization, and synthetic records. Tests must exercise both route/API behavior and service/repository boundaries.

| Test | Expected result |
|---|---|
| Org A lists workflows | Only Org A workflows returned |
| Org A requests Org B workflow ID | Not found; no data disclosed |
| Org A updates Org B workflow | Rejected; no mutation |
| Org A runs Org B workflow/version | Rejected before execution |
| Org A requests Org B execution history | Not found |
| Org A downloads Org B artifact | Rejected before filesystem access |
| Org A references Org B credential | Rejected |
| User removed from organization | Access revoked on next authorized request |
| Viewer attempts edit or run | Forbidden |
| Builder attempts role change | Forbidden |
| Missing/expired support grant | Support access denied |
| Expired session or CSRF token | Request rejected |
| Cross-tenant background job payload | Worker rejects mismatched organization |
| Organization deletion | Retention and artifact cleanup policy enforced |

Also test malformed IDs, missing organization context, inactive memberships, concurrent membership revocation, and error paths. A test that merely checks the UI hides a button is insufficient.

## 11. Delivery phases and exit criteria

### Phase A - Foundation
- Choose authentication approach and deployment assumptions.
- Add migrations and identity/organization/membership models.
- Add login, logout, session controls, CSRF, and invitation flow.
- Define organization-scoped authorization services.
- Add two-tenant isolation tests.

**Exit:** All existing local tests pass, and the new authorization tests demonstrate isolation.

### Phase B - Operational data isolation
- Add organization ownership to workflows, versions, executions, credentials, and file metadata.
- Scope all routes, store methods, downloads, and execution requests.
- Move file storage to organization-scoped opaque paths.
- Add audit events and retention behavior.

**Exit:** Every customer-data route and service has positive and negative authorization tests.

### Phase C - Customer operations console
- Add organization onboarding and membership management.
- Add customer workflow and execution health views.
- Add support case and exception handling.
- Add time-limited support grants and complete audit visibility.

**Exit:** An operator can manage multiple customer accounts without bypassing tenant boundaries.

### Phase D - Hosted production readiness
- PostgreSQL deployment and tested migrations.
- Managed secrets, HTTPS, secure cookies, backups and restore drills.
- Monitoring, alerting, incident response and data-retention procedures.
- Independent security review before real customer data.

**Exit:** Documented operational controls and successful restore/security exercises. No compliance certification is implied by completing this checklist.

## 12. Explicit non-goals

- No claim of SOC 2, ISO 27001, GDPR certification, or other compliance certification without independent evidence.
- No arbitrary shell/Python execution in workflows.
- No hidden support superuser.
- No public deployment of the current unauthenticated MVP.
- No microservices split without a measured operational need.
