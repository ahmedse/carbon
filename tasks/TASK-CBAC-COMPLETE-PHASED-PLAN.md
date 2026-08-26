# TASK — CBAC Complete Phased Plan
# Capability-Based Access Control: Close All Gaps
# Carbon Data Trust Platform — Enterprise Grade

**Date:** 2026-08-26  
**Role:** Product Designer → Master Architect  
**Status:** DESIGN — ready for MA decomposition into backend/frontend phases  
**Scope:** Data Trust Platform Core (all apps) + Domain Apps (CBAC is universal)  
**Benchmark:** Palantir Foundry (Marking + Gatekeeper), Databricks Unity Catalog (Column Masks + Row Filters), Collibra (Policy Workflows)

---

## Situation: What CBAC Already Has (Current State)

The foundation is **real and strong** — never re-build what exists.

| Component | Status | Evidence |
|-----------|--------|---------|
| **52 Capability definitions** | ✅ LIVE | `accounts/capabilities.py` — 14 domains, `Capability` dataclass |
| **IMPLIES inheritance** | ✅ LIVE | Transitive closure: `manage → view`, `_expand_capabilities()` |
| **GROUP_CAPABILITIES mapping** | ✅ LIVE | 8 built-in groups → capability sets |
| **Scoped resolution engine** | ✅ LIVE | Global vs. org-scoped distinction, read-only cap downgrade for scoped |
| **`has_capability()` API** | ✅ LIVE | `has_capability`, `has_any_capability`, `has_all_capabilities` |
| **`RequiresCapability` DRF class** | ✅ LIVE | Per-view `required_capability` declaration |
| **Frontend capability mirror** | ✅ LIVE | `src/capabilities.js` — identical keys, same domains |
| **`me_context` capability serialization** | ✅ LIVE | `get_capabilities_for_frontend()` → `{key, domain, label}` list |
| **`ScopedRole` model** | ✅ LIVE | User × Group × OrgUnit × Module scoping |
| **`RoleAssignmentAuditLog`** | ✅ LIVE | Actor, user, group, org, module, action, timestamp |
| **`GroupMetadata`** | ✅ LIVE | Category (platform/app), app_id, manifest_key, is_protected |
| **AI CBAC scoping** | ✅ LIVE | `ai_scoping.py` — app + visibility + org subtree |
| **AI guardrail redaction** | ✅ LIVE | `ai/engine/agent/guardrails.py` — after-tool redaction hooks |
| **Bootstrap command** | ✅ LIVE | `bootstrap_platform.py` — seeds all built-in groups + capabilities |

---

## What's Missing — The 8 Pillars That Remain (Gaps Map)

| Pillar | Gap | Severity |
|--------|-----|----------|
| **1. Field-Level Security** | No column/field visibility per capability — PII classification exists but triggers zero access control | P0 |
| **2. Data Masking Engine** | No automatic redaction of sensitive fields at serialization time | P0 |
| **3. Temporal / JIT Access** | `ScopedRole` has no `valid_from`/`valid_to` — no time-limited elevated permissions | P0 |
| **4. Self-Service Access Requests** | No `AccessRequest` model — users cannot request access, admins cannot approve/deny via UI | P0 |
| **5. Custom Role Builder** | Groups + capabilities are code-defined only — no DB-driven custom roles via UI | P1 |
| **6. Capability Use Audit** | `RoleAssignmentAuditLog` tracks assignments but not capability USE — no "who accessed what when" trail | P1 |
| **7. Access Reviews** | No periodic recertification workflow — admins cannot answer "who still needs this?" | P1 |
| **8. Negative Capabilities (Deny Rules)** | CBAC is allow-only — no explicit deny, no exception grants | P2 |

**Missing supplementary features (all attach to the 8 pillars above):**
- LDAP/AD group sync — manual user/group assignment
- Capability simulation — "what would user X see?" dry-run
- Notification preferences tied to capabilities
- Access review campaigns (scheduled/triggered)
- Capability matrix dashboard (what group has what)
- Column stats (null%, cardinality) gated behind masking
- Row-level security via capability-driven queryset filters
- ABAC (attribute-based) rules layered on top of CBAC groups

---

## Architecture Vision — The Full CBAC Stack

```
                   ┌─────────────────────────────────────┐
                   │  CBAC Request Pipeline               │
                   │                                      │
 Request           │  1. Authenticate (JWT / session)     │
    │              │  2. Build Scope (org + module)       │
    ▼              │  3. Resolve capabilities (CBAC)      │
 Middleware        │  4. Check Temporal validity           │
    │              │  5. Check resource capability         │
    ▼              │  6. Apply DENY rules                  │
 Permission        │  7. Filter queryset (row-level)       │
    │              │  8. Mask fields (column-level)        │
    ▼              │  9. Emit capability-use audit event   │
 Serializer        └─────────────────────────────────────┘
    │
    ▼
 Response (clean — PII fields either masked or absent)
```

```
                   ┌─────────────────────────────────────────────────────┐
                   │  CBAC Data Model — Complete Picture                  │
                   │                                                      │
  User             │  ScopedRole (existing: user × group × org × module)  │
    │              │    + valid_from (NEW)                                │
    │              │    + valid_to   (NEW)                                │
    │              │    + granted_by (NEW)                                │
    │              │    + reason     (NEW)                                │
    │              │                                                      │
    │              │  CapabilityDenyRule (NEW)                            │
    │              │    user / group × capability_key × reason            │
    │              │                                                      │
    │              │  AccessRequest (NEW)                                 │
    │              │    requester × capability_key × org × module         │
    │              │    status: pending / approved / denied               │
    │              │    reviewed_by / reviewed_at                         │
    │              │                                                      │
    │              │  FieldAccessPolicy (NEW)                             │
    │              │    data_field × required_capability                  │
    │              │    mask_strategy: hide / hash / partial / redact     │
    │              │                                                      │
    │              │  CapabilityUseLog (NEW)                              │
    │              │    user × capability_key × resource_type × resource_id│
    │              │    action × timestamp × ip × user_agent              │
    │              │                                                      │
    │              │  AccessReviewCampaign (NEW)                          │
    │              │    name × scope × reviewer × deadline × status       │
    │              │                                                      │
    │              │  CustomRole (NEW — wraps Group)                      │
    │              │    group (1:1) × capability_keys[] × is_template     │
    └──────────────└─────────────────────────────────────────────────────┘
```

---

## Phase Plan

### Phase C1 — Temporal Role Expiry + Capability Use Audit (BACKEND)
**Worker Role:** backend-worker  
**Model:** DeepSeek V4-Flash (RULE_24)  
**Status:** PLANNED  
**Depends on:** existing `ScopedRole` model, `RoleAssignmentAuditLog`  
**Effort:** Medium. 2 migrations, 1 new model, 1 new service, 4 tests.

#### Goal
`ScopedRole` gains `valid_from`/`valid_to`/`granted_by`/`reason`. Expired roles are excluded from capability resolution. Every capability USE is logged to a new `CapabilityUseLog` table, giving the platform a full "who accessed what when" trail.

#### User Story
**As a** platform admin, **I want** to grant time-limited elevated access to a user, **so that** the access automatically expires without requiring me to remember to revoke it.

**As an** auditor, **I want** to see which users exercised which capabilities and when, **so that** I can produce a compliance report without needing to reconstruct it from application logs.

#### Acceptance

**Scenario: Temporal role — auto-expiry**
```
Given a ScopedRole with valid_to = yesterday
When the capability resolution engine runs for that user
Then the role is excluded (as if it does not exist)
And the user loses the capabilities from that group
```

**Scenario: Temporal role — not-yet-active**
```
Given a ScopedRole with valid_from = tomorrow
When the capability resolution engine runs for that user today
Then the role is excluded
```

**Scenario: Capability use log — every protected action**
```
Given a user with has_capability("catalog:manage_metadata")
When they call a view protected by RequiresCapability("catalog:manage_metadata")
Then a CapabilityUseLog row is inserted with user / capability_key / resource_type / resource_id / action / timestamp / ip
And the log row is never mutated after insert (append-only)
```

**Scenario: Capability use log — denied action**
```
Given a user WITHOUT catalog:manage_metadata
When they attempt to call the protected view
Then a CapabilityUseLog row is inserted with status="denied"
And the user receives HTTP 403
```

**Scenario: Edge — valid_from=None means "active since creation"**
```
Given a ScopedRole with valid_from=None, valid_to=None
When capability resolution runs
Then it behaves exactly as today (no change to existing roles)
```

#### Models to Change
```
accounts/models.py — ScopedRole:
  + valid_from = models.DateTimeField(null=True, blank=True)
  + valid_to   = models.DateTimeField(null=True, blank=True)
  + granted_by = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL, related_name='granted_roles')
  + reason     = models.CharField(max_length=500, blank=True)
  
  # Manager: override default queryset to filter by temporal validity
  objects = ScopedRoleManager()   # ScopedRoleManager.get_queryset() filters active + in-window

accounts/models.py — new CapabilityUseLog:
  user         = models.ForeignKey(User, on_delete=SET_NULL, null=True)
  capability_key = models.CharField(max_length=120, db_index=True)
  resource_type = models.CharField(max_length=80, blank=True)  # "AssetProfile", "DQRule", etc.
  resource_id   = models.CharField(max_length=80, blank=True)  # str to cover int + uuid
  action        = models.CharField(max_length=20)               # "access" | "denied" | "manage"
  status        = models.CharField(max_length=10, default='allowed')  # "allowed" | "denied"
  timestamp     = models.DateTimeField(auto_now_add=True, db_index=True)
  ip_address    = models.GenericIPAddressField(null=True, blank=True)
  user_agent    = models.CharField(max_length=400, blank=True)
  
  class Meta:
    ordering = ['-timestamp']
    indexes = [
      Index(fields=['user', '-timestamp']),
      Index(fields=['capability_key', '-timestamp']),
    ]
```

#### Code Seams
1. `accounts/capabilities.py::get_user_capabilities()` — filter `ScopedRole.objects.filter(is_active=True)` → use `ScopedRoleManager` that adds `Q(valid_from__isnull=True | valid_from__lte=now) & Q(valid_to__isnull=True | valid_to__gte=now)`.
2. `accounts/permissions.py::RequiresCapability.has_permission()` — after capability check, `CapabilityUseLog.objects.create(...)` (non-blocking, fire-and-forget, never fail the request if log insert fails).
3. New API view `GET /carbon-api/accounts/capability-use-log/` — paginated, filterable by user/capability/date range. Requires `platform:view_audit`.

#### Verification Gate
```bash
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run
cd backend && ../.venv/bin/python -m pytest accounts/tests/ -q -k "capability or scoped_role or temporal"
```

---

### Phase C2 — Field-Level Access Policies + Data Masking Engine (BACKEND)
**Worker Role:** backend-worker  
**Model:** DeepSeek V4-Flash  
**Status:** PLANNED  
**Depends on:** C1 (capability use log for masking events)  
**Effort:** Large. 2 models, 1 serializer mixin, field-policy API, 6 tests.

#### Goal
A `FieldAccessPolicy` defines which capability is required to see a `DataField` in plain text, and what masking strategy to apply when the capability is absent. Masking is applied inside DRF serializers via a mixin — the model data never changes; only the API response is filtered.

#### Why This Matters
Today, `AssetProfile.classification = 'pii'` is a metadata tag. It has zero access-control effect — a user without PII clearance can still read full SSN values. This closes the gap that matters most for GDPR and SOC 2.

#### User Stories
**As a** data steward, **I want** to declare that the `email` field requires `dataschema:view_pii` to read in plain text, **so that** users without that capability see `"***@***.com"` instead.

**As an** analyst, **I want** to know which fields are masked in my context before I build a report, **so that** I'm not surprised by partial data.

#### Acceptance

**Scenario: Field hidden (mask_strategy=hide)**
```
Given DataField "ssn" with FieldAccessPolicy(required_capability="dataschema:view_pii", mask_strategy="hide")
And a user WITHOUT dataschema:view_pii
When the user calls GET /carbon-api/dataschema/fields/<id>/
Then the response does NOT include the "default_value" or "options" payload for that field
And the response includes a "masked": true, "mask_reason": "Requires dataschema:view_pii" envelope key
```

**Scenario: Field partially masked (mask_strategy=partial)**
```
Given DataField "email" with FieldAccessPolicy(required_capability="dataschema:view_pii", mask_strategy="partial")
And a user WITHOUT dataschema:view_pii
When the user fetches a DataRow containing email="ahmed@example.com"
Then the response contains email="a***@***.com"
```

**Scenario: Field hashed (mask_strategy=hash)**
```
Given DataField "national_id" with mask_strategy="hash"
And a user WITHOUT the required capability
When the user fetches a DataRow
Then the response contains national_id="<sha256-prefix-8-chars>"
```

**Scenario: Admin sees plain text**
```
Given the same DataField
And a superuser / user WITH the required capability
When the user fetches the same DataRow
Then the response contains national_id="123-45-6789" (unmasked)
```

**Scenario: Empty policy = no masking**
```
Given a DataField with NO FieldAccessPolicy
When any user fetches it
Then the response is identical to today (no change in behavior)
```

**Scenario: Mask event logged**
```
Given a masked field access
When the masking engine redacts the field
Then a CapabilityUseLog row is inserted with action="masked", status="masked"
```

#### Models
```python
# accounts/models.py or dataschema/models.py (lives closest to DataField)
class FieldAccessPolicy(models.Model):
    MASK_STRATEGIES = [
        ('hide',    'Hide field entirely'),
        ('hash',    'SHA-256 truncated to 8 chars'),
        ('partial', 'Partial: first char + *** + domain'),
        ('redact',  'Full redact — replace with [REDACTED]'),
    ]
    data_field          = models.OneToOneField('dataschema.DataField', on_delete=models.CASCADE, related_name='access_policy')
    required_capability = models.CharField(max_length=120)      # e.g. "dataschema:view_pii"
    mask_strategy       = models.CharField(max_length=10, choices=MASK_STRATEGIES, default='hide')
    is_active           = models.BooleanField(default=True)
    created_by          = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Field Access Policy"
```

#### Code Seams
1. New `dataschema/masking.py::MaskingEngine` — stateless service: `mask_value(value, strategy, user) -> str`
2. New `dataschema/serializer_mixin.py::FieldMaskingMixin` — plugs into DRF serializers; reads `FieldAccessPolicy` (cached per request), calls `MaskingEngine`.
3. `dataschema/serializers.py::DataRowSerializer` + `DataFieldSerializer` — inherit `FieldMaskingMixin`.
4. New `DATASCHEMA_VIEW_PII` capability in `capabilities.py` — `dataschema:view_pii`.
5. `GROUP_CAPABILITIES` update — `admins_group` gets `dataschema:view_pii`; `dataowners_group` gets it only when their `data_field` is in their module.
6. New management API: `GET/POST/PATCH /carbon-api/dataschema/field-policies/` — requires `dataschema:manage` (steward UI).

#### Verification Gate
```bash
cd backend && ../.venv/bin/python -m pytest dataschema/tests/ accounts/tests/ -q -k "mask or field_policy or pii"
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run
```

---

### Phase C3 — Self-Service Access Requests + Approval Workflow (BACKEND + FRONTEND)
**Worker Role:** backend-worker (C3-A), frontend-worker (C3-B)  
**Model:** DeepSeek V4-Flash  
**Status:** PLANNED  
**Depends on:** C1 (temporal roles — approval grants time-limited ScopedRole)  
**Effort:** Large backend + medium frontend. 2 models, service, 5 API endpoints, 3 UI flows, 8 tests.

#### Goal
Any authenticated user can request a capability or role for an org scope. A designated reviewer (group admin / platform admin) approves or denies. Approval creates a `ScopedRole` (optionally temporal). The requester and reviewer are notified. Full audit trail.

#### Why This Matters
Today: access is manual — admins must proactively grant roles. This means the floor is "nobody has access until an admin acts," which creates friction and leads to over-granting to avoid the back-and-forth. Self-service with approval gives the platform a compliant, auditable access lifecycle.

#### User Stories
**As a** data analyst, **I want** to request access to the `catalog:manage_metadata` capability for a specific org unit, **so that** I can tag new assets without asking IT.

**As a** platform admin, **I want** to see a queue of pending access requests with the requester's justification, **so that** I can approve or deny them in one place.

**As a** user, **I want** to know the status of my access request, **so that** I'm not left guessing.

#### Acceptance

**Scenario: Happy path — request → approve → role granted**
```
Given user Ahmed requests "catalog:manage_metadata" for "College of Engineering" OrgUnit
When the platform admin opens the Access Requests panel
Then they see Ahmed's request with justification text
When they click "Approve" and optionally set an expiry date
Then a ScopedRole is created for Ahmed × catalog_lead-equivalent × "College of Engineering"
And Ahmed receives an in-app notification: "Your request for Manage Metadata was approved"
And the request status transitions to "approved"
```

**Scenario: Denial with reason**
```
Given a pending request
When the admin clicks "Deny" and enters a reason
Then the request status becomes "denied"
And the requester receives a notification with the reason
And no ScopedRole is created
```

**Scenario: Requester views own requests**
```
Given Ahmed has 2 pending and 1 approved request
When Ahmed opens "My Access Requests"
Then he sees all 3 with status chips (Pending / Approved / Denied)
And the approved one shows "Expires: 2026-12-31" if temporal was set
```

**Scenario: Duplicate prevention**
```
Given Ahmed already has an approved pending request for the same capability + scope
When he submits a new request for the same combination
Then the API returns 409 Conflict with "You already have a pending or active request for this access"
```

**Scenario: Empty state — admin sees no pending requests**
```
Given no pending requests
When the admin opens the Requests panel
Then they see "No pending access requests. You're all caught up." with no list
```

**Scenario: Permission boundary — only admins can approve**
```
Given a regular user attempts POST /access-requests/<id>/approve/
Then they receive HTTP 403
```

#### Models (backend C3-A)
```python
class AccessRequest(models.Model):
    STATUS = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('denied',   'Denied'),
        ('cancelled', 'Cancelled by requester'),
        ('expired',   'Expired — not actioned'),
    ]
    requester         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_requests')
    capability_key    = models.CharField(max_length=120)          # e.g. "catalog:manage_metadata"
    org_unit          = models.ForeignKey('mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL)
    module            = models.ForeignKey('core.Module', null=True, blank=True, on_delete=models.SET_NULL)
    justification     = models.TextField()
    requested_duration_days = models.PositiveIntegerField(null=True, blank=True)  # None = permanent
    status            = models.CharField(max_length=12, choices=STATUS, default='pending', db_index=True)
    reviewer          = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_requests')
    reviewed_at       = models.DateTimeField(null=True, blank=True)
    denial_reason     = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at        = models.DateTimeField(auto_now=True)
    resulting_role    = models.ForeignKey('ScopedRole', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-created_at']
        indexes = [Index(fields=['status', '-created_at'])]
        constraints = [
            UniqueConstraint(
                fields=['requester', 'capability_key', 'org_unit', 'module'],
                condition=Q(status='pending'),
                name='unique_pending_request_per_scope'
            )
        ]
```

#### API Endpoints (backend C3-A)
```
GET    /carbon-api/accounts/access-requests/         # list (admin: all; user: own)
POST   /carbon-api/accounts/access-requests/         # create (any authenticated)
GET    /carbon-api/accounts/access-requests/<id>/    # detail
DELETE /carbon-api/accounts/access-requests/<id>/    # cancel (requester only)
POST   /carbon-api/accounts/access-requests/<id>/approve/  # requires platform:manage_access
POST   /carbon-api/accounts/access-requests/<id>/deny/     # requires platform:manage_access
```

#### Frontend Flows (C3-B — 3 flows, all inside admin/access or user settings)

**Flow 1 — Admin: Pending Requests Queue**
- IA: `Admin → Access Control → Requests` (new tab in admin access panel)
- List: request date, requester name, requested capability (human label from CAPABILITY_REGISTRY), scope (org/module), justification (truncated, expand on row click), status chip
- Actions: Approve (opens inline form: expiry date optional) / Deny (opens inline form: reason required)
- Empty state: "No pending access requests."
- Loading/error states per design-system RULE 4

**Flow 2 — User: My Access Requests**
- IA: `Settings → Access Requests` tab
- Timeline list: status chip, capability label, scope, submitted at, reviewed at + reviewer if done
- "Request Access" CTA → opens `AccessRequestDialog` (capability autocomplete from user-accessible CAPABILITY_REGISTRY, org selector, justification text, optional duration)
- Cancellation: "Cancel" action on pending items (confirm dialog naming the consequence)

**Flow 3 — Inline: "Request Access" affordance on locked features**
- When a user tries to access a UI area they lack the capability for, the empty/403 state includes a "Request Access" CTA that pre-populates the dialog with the required capability
- Connects to: every `RequiresCapability` view that has a `locked_message` declared

---

### Phase C4 — Custom Role Builder (BACKEND + FRONTEND)
**Worker Role:** backend-worker (C4-A), frontend-worker (C4-B)  
**Model:** DeepSeek V4-Flash  
**Status:** PLANNED  
**Depends on:** C1 (temporal roles), C3 (access requests may create from custom roles)  
**Effort:** Medium backend + large frontend. 1 model, CRUD API, role-matrix UI.

#### Goal
Platform admins can create custom roles (Groups) by selecting capabilities from the registry, save them as templates, and assign them to users via ScopedRole — all without touching code. The capability matrix admin view shows every group's full capability set at a glance.

#### Why This Matters
Today: adding a new role requires editing `GROUP_CAPABILITIES` in `capabilities.py`, re-deploying, running `bootstrap_platform`. This is a code-deploy cycle for a config change. Enterprise platforms make role management a UI operation.

#### Design Constraints
- Custom roles must NOT bypass the IMPLIES inheritance — if a custom role has `catalog:manage_metadata`, it automatically implies `catalog:view`.
- System/built-in groups (`admins_group`, `viewers_group`, etc.) are `is_protected=True` (already in `GroupMetadata`) — UI must not allow editing/deleting them.
- Custom roles are stored as Django `Group` + `GroupMetadata(is_scoped=False)` + `CustomRole` (new model capturing selected capability keys).

#### User Story
**As a** platform admin, **I want** to create a "Data Steward" role that has `catalog:manage_metadata` + `dq:manage_rules` but not carbon management capabilities, **so that** I can assign it to users who govern data quality without giving them emissions data write access.

#### Acceptance

**Scenario: Create custom role**
```
Given admin opens the Custom Roles panel
When they click "New Role", enter name "Data Steward", select 2 capabilities
Then a Group + GroupMetadata + CustomRole row is created
And the new role appears in the role assignment UI immediately
And the IMPLIES expansion is auto-applied (selected caps imply view caps automatically)
```

**Scenario: Capability conflict prevention**
```
Given admin selects "platform:admin" for a new custom role
Then the UI warns: "This capability grants full platform access. Are you sure?"
And they must confirm explicitly
```

**Scenario: Edit custom role — capability added**
```
Given an existing custom role "Data Steward" assigned to 3 users
When admin adds "mdm:manage" to it
Then all 3 users immediately gain mdm:manage (cache invalidated)
And a RoleAssignmentAuditLog entry is written for each affected user
```

**Scenario: Capability matrix dashboard**
```
Given admin opens the CBAC Matrix view
Then they see a table: rows = capabilities, columns = groups
And each cell shows a checkmark (direct) or strikethrough (implied) or empty
And it is filterable by domain, category, group type
```

**Scenario: Protect built-in roles**
```
Given admin views "admins_group"
Then the Edit and Delete buttons are disabled with tooltip "System roles cannot be modified"
```

#### Models (backend C4-A)
```python
class CustomRole(models.Model):
    group             = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='custom_role')
    capability_keys   = models.JSONField(default=list)      # ["catalog:manage_metadata", "dq:manage_rules"]
    description       = models.TextField(blank=True)
    is_template       = models.BooleanField(default=False)  # can be cloned as starting point
    created_by        = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)
```

#### API Endpoints (C4-A)
```
GET    /carbon-api/accounts/custom-roles/               # list (platform:manage_groups)
POST   /carbon-api/accounts/custom-roles/               # create
GET    /carbon-api/accounts/custom-roles/<id>/          # detail (includes expanded_capabilities[])
PATCH  /carbon-api/accounts/custom-roles/<id>/          # update capability_keys
DELETE /carbon-api/accounts/custom-roles/<id>/          # soft-delete (fail if users assigned)
GET    /carbon-api/accounts/capability-matrix/          # full matrix view (platform:view_audit)
```

#### Frontend (C4-B)
- IA: `Admin → Access Control → Roles` (existing tab, extend with custom role management)
- Custom Role list: name, description, capability count, user count, is_template badge
- Role detail panel (right-side drawer per design-system patterns): capability checklist organized by domain, user assignments count, edit mode
- Capability matrix view: toggle-able table with filter bar (domain, group, "show implied only")
- All protected by `PLATFORM_MANAGE_GROUPS` capability check on every action button

---

### Phase C5 — Access Review Campaigns (BACKEND + FRONTEND)
**Worker Role:** backend-worker (C5-A), frontend-worker (C5-B)  
**Model:** DeepSeek V4-Flash  
**Status:** PLANNED  
**Depends on:** C1 (temporal roles — review can revoke/extend), C3 (access requests — review can spawn a re-request)  
**Effort:** Medium. 2 models, campaign service, review UI, 6 tests.

#### Goal
Platform admins create periodic "access review campaigns" that send reviewers a list of their direct reports' role assignments for recertification. Reviewers confirm (keep access) or revoke (remove ScopedRole). The platform tracks campaign completion, overdue items, and generates a compliance summary.

#### Why This Matters
SOC 2 Type II and ISO 27001 require periodic access reviews (typically quarterly). Today, Carbon has no mechanism for this — admins must manually audit who has what. This closes a hard compliance requirement.

#### User Stories
**As a** CISO, **I want** to launch a quarterly access review campaign, **so that** all org-unit managers confirm which users should retain their current access.

**As an** org-unit manager (reviewer), **I want** to see a list of my team's role assignments and confirm or revoke each one, **so that** I can complete my review obligation without needing technical knowledge.

#### Acceptance

**Scenario: Launch campaign**
```
Given platform admin opens "Access Reviews"
When they create a new campaign with name, scope (org units), reviewer group, deadline
Then the platform generates ReviewItem rows for every ScopedRole in the scope
And sends an in-app notification to each reviewer with their item count and deadline
```

**Scenario: Reviewer completes items**
```
Given reviewer Alice has 12 ReviewItems assigned
When she opens the campaign and clicks "Keep" on 10 and "Revoke" on 2
Then the 2 revoked ScopedRoles are deactivated (is_active=False + audit log entry)
And the 10 kept items are marked confirmed with Alice's timestamp
And the campaign tracks 12/12 reviewed
```

**Scenario: Overdue campaign**
```
Given a campaign with deadline = 3 days ago and 5 unreviewed items
When the system checks campaigns
Then those 5 items are marked "overdue"
And the admin dashboard shows the campaign in "Needs Attention" state
```

**Scenario: Compliance summary**
```
Given a completed campaign
When admin views the campaign report
Then they see: total items, kept%, revoked%, overdue count, reviewer completion %
And can export it as CSV
```

#### Models (C5-A)
```python
class AccessReviewCampaign(models.Model):
    STATUS = [('draft','Draft'),('active','Active'),('completed','Completed'),('cancelled','Cancelled')]
    name        = models.CharField(max_length=200)
    scope_org_units = models.ManyToManyField('mdm.OrgUnit', blank=True)
    reviewer_group  = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    deadline        = models.DateTimeField()
    status          = models.CharField(max_length=12, choices=STATUS, default='draft')
    created_by      = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at      = models.DateTimeField(auto_now_add=True)
    completed_at    = models.DateTimeField(null=True, blank=True)

class ReviewItem(models.Model):
    DECISION = [('pending','Pending'),('keep','Keep'),('revoke','Revoke')]
    campaign    = models.ForeignKey(AccessReviewCampaign, on_delete=models.CASCADE, related_name='items')
    scoped_role = models.ForeignKey(ScopedRole, on_delete=models.CASCADE, related_name='review_items')
    reviewer    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_items')
    decision    = models.CharField(max_length=10, choices=DECISION, default='pending')
    decision_at = models.DateTimeField(null=True, blank=True)
    note        = models.TextField(blank=True)
    is_overdue  = models.BooleanField(default=False)
```

---

### Phase C6 — Deny Rules + ABAC Layer + Capability Simulation (BACKEND + FRONTEND)
**Worker Role:** backend-worker (C6-A), frontend-worker (C6-B)  
**Model:** DeepSeek V4-Flash  
**Status:** PLANNED  
**Depends on:** C1–C5  
**Effort:** Large. Most architecturally complex phase — touches capability resolution engine.

#### Goal
Three features in one phase because they all extend the capability resolution engine:

1. **Deny rules** — explicit denials override any group-granted capability (deny wins). Enables "everyone in analysts_group has catalog:view EXCEPT user X" without creating a special group.
2. **ABAC layer** — attribute-based rules evaluated at resolution time: `if resource.classification == 'pii' AND NOT has_capability('dataschema:view_pii') → deny`. Rules are configured in DB, not code.
3. **Capability simulation** — "what would user X see?" dry-run: given a user + optional org context, return their full expanded capability set. Admins use it to verify access before granting/revoking.

#### User Stories
**As a** platform admin, **I want** to deny `carbon:enter_data` to a specific user even though they're in `dataowners_group`, **so that** I can suspend one user's write access during an investigation without removing them from the group.

**As a** data steward, **I want** to define a rule that automatically denies access to PII fields for any user not in the `pii_approved` group, **so that** I don't have to manually set a `FieldAccessPolicy` on every single PII field.

**As a** platform admin, **I want** to simulate what User X can see under current access settings, **so that** I can verify a new custom role is correct before assigning it.

#### Acceptance

**Scenario: Deny rule overrides group capability**
```
Given user is in analysts_group (has carbon:view_analytics)
And a CapabilityDenyRule exists for that user × carbon:view_analytics
When capability resolution runs
Then carbon:view_analytics is NOT in the user's resolved capabilities
Even though the group grants it
```

**Scenario: ABAC rule — PII auto-deny**
```
Given an ABACRule: capability="dataschema:view_pii" AND user NOT IN group "pii_approved" → deny
When any user NOT in pii_approved accesses a PII field
Then the deny rule fires before the FieldAccessPolicy check
And the field is masked/hidden regardless of any other permission
```

**Scenario: Simulation — correct capability set**
```
Given admin opens "Simulate Access" for user Ahmed
When admin clicks "Run Simulation"
Then they see a table of all capabilities Ahmed currently has, why (which group), and any deny rules
And the simulation panel shows: "Ahmed would see X / not see Y"
```

**Scenario: Deny rule audit**
```
Given a deny rule fires for a user
When the platform logs the event
Then a CapabilityUseLog row is inserted with status="denied_by_rule", capability_key, rule_id
```

#### Models (C6-A)
```python
class CapabilityDenyRule(models.Model):
    """Explicit deny — overrides group-granted capabilities. Deny always wins."""
    SCOPE = [('user','Per-user'),('group','Per-group')]
    scope_type      = models.CharField(max_length=10, choices=SCOPE)
    target_user     = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    target_group    = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    capability_key  = models.CharField(max_length=120, db_index=True)
    reason          = models.TextField()
    is_active       = models.BooleanField(default=True)
    valid_until     = models.DateTimeField(null=True, blank=True)   # temporal deny
    created_by      = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='created_deny_rules')
    created_at      = models.DateTimeField(auto_now_add=True)

class ABACRule(models.Model):
    """Attribute-based rule evaluated at resolution time."""
    OPERATORS = [('eq','Equals'),('neq','Not Equals'),('in_group','User In Group'),('not_in_group','User Not In Group'),('has_cap','Has Capability'),('not_has_cap','Does Not Have Capability')]
    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    resource_classification = models.CharField(max_length=20, blank=True)   # "pii" | "confidential" | ""
    operator        = models.CharField(max_length=20, choices=OPERATORS)
    operand         = models.CharField(max_length=200)   # group name or capability key
    effect_capability = models.CharField(max_length=120) # capability to deny when rule fires
    is_active       = models.BooleanField(default=True)
    priority        = models.PositiveIntegerField(default=100)  # lower = evaluated first
    created_by      = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at      = models.DateTimeField(auto_now_add=True)
```

#### Resolution Engine Changes (C6-A)
The new resolution order in `get_user_capabilities()`:
```
1. Gather group capabilities (existing IMPLIES expansion)
2. Apply CapabilityDenyRule for user + user's groups (subtract from set)
3. Apply ABACRules (context-dependent — resource attr + user state → subtract)
4. Cache result on request (existing _cached_capabilities)
5. Log via CapabilityUseLog if RequiresCapability fires
```

ABAC evaluation is context-lazy: step 3 only fires when a resource object is available (serializer or view passes it in). Stateless `has_capability(user, cap)` calls skip ABAC (safe — ABAC is a narrowing rule, not a grant).

---

## Supplementary Tasks (Attach to Above Phases)

### S1 — LDAP/SSO Group Sync (Phase C1 prerequisite or parallel)
- `django-allauth` or `python-ldap` integration
- `LDAPGroupSync` management command: pull groups → map to `GROUP_CAPABILITIES` names → bulk-create `ScopedRole` rows
- Conflict resolution: LDAP-managed roles marked `source='ldap'`; manual roles stay `source='manual'`; LDAP wins on sync
- Frontend: `Admin → Users → LDAP Sync` tab showing last sync time, error count, diff preview

### S2 — Capability Use Log Dashboard (builds on C1)
- `GET /carbon-api/accounts/capability-use-log/?date_from=&date_to=&capability=&user=`
- Frontend: `Admin → Access Control → Audit Log` tab — filterable table with export (CSV)
- Charts: top-N capabilities accessed, top-N users by access events, denied events over time

### S3 — Notification Preferences per Capability (builds on C3)
- Extend unified notification system: per-user preference: "notify me when my access request is approved/denied"
- Platform admin: "notify me when new access requests arrive"
- Tied to Phase C3 `AccessRequest` model

### S4 — Column Statistics Gating (builds on C2 masking)
- DQ profiling results (null%, cardinality, distribution) for PII fields are themselves sensitive
- `ColumnStats` serializer respects `FieldAccessPolicy` — masked fields show aggregated stats only, not sample values
- Admin can see full stats; analyst sees "N rows, X% null" but not the value distribution

### S5 — Frontend CBAC Audit Panel (`Admin → Access Control`)
- 4-tab panel: Users | Roles | Requests | Audit Log
- **Users tab**: user search → click user → side panel shows their full capability set (expanded + reason: which group), active ScopedRoles with temporal info, deny rules, request history
- **Roles tab**: custom roles + built-in roles; capability matrix toggle
- **Requests tab**: pending queue (C3) + campaign list (C5)
- **Audit Log tab**: CapabilityUseLog viewer (S2)

---

## Phasing Summary

| Phase | Components | Depends On | Backend | Frontend |
|-------|-----------|------------|---------|----------|
| **C1** | Temporal roles + Capability use log | None (extends existing) | backend-worker | — |
| **C2** | Field-level policies + Data masking | C1 (use log for mask events) | backend-worker | Admin field-policy UI (small) |
| **C3** | Self-service access requests + Workflow | C1 (temporal grant on approve) | backend-worker | frontend-worker |
| **C4** | Custom role builder | C1, C3 | backend-worker | frontend-worker |
| **C5** | Access review campaigns | C1, C3 | backend-worker | frontend-worker |
| **C6** | Deny rules + ABAC + Simulation | C1–C5 | backend-worker | frontend-worker |
| **S1** | LDAP/SSO sync | C1 | backend-worker | minimal UI |
| **S2** | Capability use log dashboard | C1 | — | frontend-worker |
| **S3** | Notification preferences | C3 + notification system | backend-worker | frontend-worker |
| **S4** | Column stats gating | C2 | backend-worker | — |
| **S5** | Full CBAC Admin Panel | C1–C5 | — | frontend-worker |

**Parallel execution possible:** C1 → C2 and C3 in parallel (C2 depends only on C1; C3 depends only on C1). C4, C5, C6 can follow in parallel once C1+C3 are done.

---

## Frontend IA — Where Everything Lives

```
/admin/access-control/           (new route — needs RULE_15 studioFromPath entry)
  ├── Users tab         (existing user management + capability overlay — S5)
  ├── Roles tab         (custom role builder — C4)
  ├── Requests tab      (access request queue — C3, campaign list — C5)
  └── Audit Log tab     (capability use log — S2)

/settings/access-requests/       (new route — self-service request history for current user — C3)

/admin/data-governance/
  └── Field Policies tab   (field access policy management — C2)

Inline "Request Access" affordance:
  Every 403/empty state for a locked feature → pre-populated AccessRequestDialog (C3)
```

All routes are **inside existing namespaces** — no new top-level sidebar entries per project rules (RULE_15, RULE_22).

---

## Verification Gates (per phase)

All phases share these gates in addition to their own:

```bash
# After every phase:
cd backend && ../.venv/bin/python manage.py check
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run
cd backend && ../.venv/bin/python -m pytest accounts/tests/ -q
./.ai-toolkit/scripts/verify.sh
cd carbon-frontend && npm run lint && npm run build
```

---

## Hand-off Notes for Master Architect

1. **C1 is the enabler** — dispatch first, independently. Unblocks everything else.
2. **C2 (field masking) is the highest enterprise value** — closes the P0 PII gap. Dispatch in parallel with C3.
3. **C3 + C4 are a UX pair** — self-service access requests and custom roles both live in the same admin panel (S5). Consider dispatching C4-B and C3-B to the same frontend-worker to build the unified panel.
4. **C6 (deny + ABAC)** is architecturally the heaviest — touches `get_user_capabilities()` core. Run last; write a regression test suite (capability-matrix snapshot before/after) as part of the gate.
5. **S1 (LDAP)** — only needed if the AASTMT deployment requires AD sync. Not a blocker for core enterprise platform.
6. **No schema changes to `ai/` models** — CBAC scoping for AI is already handled by `ai_scoping.py` and the `AppScopeMixin`. The AI read layer gets temporal role support automatically once C1 is shipped (it reads from `ScopedRole` which will filter expired rows via the new manager).
7. **Capability cache invalidation** — today capabilities are cached on `user._cached_capabilities` (per-request). When C4 (custom role edit) or C6 (deny rule create) changes a group, the next request will auto-rebuild — no additional cache invalidation needed for per-request caches. If a Redis capability cache is ever added (S-future), C4/C6 must emit an invalidation event.

---

*Produced by: Product/UX Designer*  
*Next step: Master Architect decomposes C1 into TASKS.md spec, dispatches backend-worker.*
