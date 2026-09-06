# DESIGN — e-Office Correspondence & Approval Platform (نظام المراسلات)

- **Status:** Design (approved for phased implementation)
- **Date:** 2026-09-06
- **Owner:** Master Architect
- **ADR:** [ADR-0030](../.ai-toolkit/decisions/0030-eoffice-correspondence-engine.md)
- **Builds on:** ADR-0025 (typed vs dataschema), ADR-0027 (governed FK),
  ADR-0015 (multi-instance), ADR-0016 (manifest contract), ADR-0018 (i18n/RTL),
  ADR-0029 (compensation ledger)

> **Read this first (30s):** We are building ONE shared engine — an e-Office
> Correspondence & Approval spine — not an HR feature. Every domain app (HR,
> Finance, Procurement) plugs into it. The routed thing is a **Correspondence**,
> shown to users as a **Request (طلب)** or a **Memo (مذكرة)**. It is trust-native:
> it reuses MDM reference sets, the DQ gate, and the governance audit trail that
> already exist. e-Signature is a **designed seam**, wired but not implemented in
> v1.

---

## 1. Vision & scope

### 1.1 What we are building
A paperless internal correspondence system: create → route → approve/reject/
send-back → track → edit → archive any internal document/request, with an
immutable trail, official reference numbers, Arabic RTL, delegation, and an
e-signature seam. Governed by the same Trust Platform core as all other data.

### 1.2 The three surfaces (one engine)
```
                    ┌───────────────────────────────────────────┐
                    │  correspondence engine  (trust-native BPF) │
                    │  Correspondence · WorkflowPolicy · Events  │
                    └───────────────────────────────────────────┘
                       ▲                ▲                  ▲
           ┌───────────┴────┐ ┌─────────┴────────┐ ┌───────┴──────────┐
           │  my  (ESS)     │ │  team  (MSS)     │ │ people / finance │
           │ "About me"     │ │ "About my reports"│ │ (domain admin)   │
           │ مكتبي / مراسلاتي │ │ الوارد والموافقات   │ │ HR/Finance office│
           │ my requests,   │ │ approvals inbox,  │ │ payroll runs,    │
           │ leave, payslip,│ │ team calendar,    │ │ policy config,   │
           │ profile        │ │ team attendance   │ │ correspondence   │
           │                │ │                   │ │ type/policy admin│
           └────────────────┘ └───────────────────┘ └──────────────────┘
           shows if:          shows if:              shows if:
           has employee_profile has direct_reports   has people:* caps
```

### 1.3 Terminology (bilingual — ADR-0018)
| Concept | English | Arabic | Notes |
|---------|---------|--------|-------|
| The system | e-Office / Correspondence | نظام المراسلات | Platform capability |
| The routed item (code) | `Correspondence` | مراسلة | One typed entity |
| Presented as (self-service) | Request | طلب (Talab) | leave/loan/profile-change |
| Presented as (official) | Memo / Circular / Decision | مذكرة / تعميم / قرار | correspondence types |
| Employee surface | My Desk / My Requests | مكتبي / طلباتي | frontend app `my` |
| Approver surface | Approvals Inbox | الوارد والموافقات | frontend app `team` |
| The approval trail | Process History | سجل الإجراءات | immutable, via governance events |
| For-action recipient | For Action | للتنفيذ | routing intent |
| For-info recipient | For Info / CC | للعلم | routing intent |
| Delegation | Delegation | تفويض | designed; UI in later phase |
| e-Signature | e-Signature | توقيع إلكتروني | **seam only in v1** |

### 1.4 In / out of scope for the first program
- **In:** correspondence engine; config-as-data policies; reference numbering;
  leave/loan/profile-change/generic-memo types; `my` + `team` surfaces;
  in-app notifications; DQ-gated submit; governance audit trail; EN/AR + RTL;
  reference-set migration for `leave_type`.
- **Seam only (wired, not implemented):** e-signature (PKI), delegation UI,
  memo reference-number stamping/QR, PDF via external reporting service.
- **Out (future domains):** Finance/Procurement correspondence types (they add
  their own `WorkflowPolicy` + form schema later — no engine change).

---

## 2. Architecture

### 2.1 App/module layout
```
backend/
  correspondence/                 ← NEW: the shared engine
    models.py                     Correspondence, WorkflowPolicy, WorkflowPolicyStep,
                                  CorrespondenceEvent, CorrespondenceAttachment,
                                  CorrespondenceRegistry, Delegation, Notification
    fsm.py                        pure state-machine service (transitions)
    routing.py                    approver resolution (roles → users)
    registry.py                   reference-number allocation
    policies.py                   resolve active WorkflowPolicy for a type
    permissions.py                IsActiveEmployee, CanActOnCorrespondence
    serializers.py
    views.py                      generic correspondence + approvals + notifications API
    urls.py
    management/commands/
      seed_correspondence.py      seed reference sets + default policies
    tests/
  people/                         ← EXTEND
    self_views.py                 NEW: /me/ self-scoped reads (balance, payslip, ...)
    self_urls.py                  NEW
    models.py                     ADD Employee.user (OneToOne); leave_type → FK ReferenceValue
frontend/src/apps/
  my/                             ← NEW manifest surface (ESS)
  team/                           ← NEW manifest surface (MSS)
```

### 2.2 Why a new app (not inside `people`)
RULE_3 (hosted apps depend on core, never a sibling). `correspondence` is a
**core-level** capability: it imports only `mdm`, `dq`, `catalog`, `accounts`,
`core` — never `people`. `people` depends on `correspondence`, not the reverse.
This lets Finance/Procurement depend on `correspondence` too, with zero coupling
to HR.

### 2.3 Subject linkage (NO GenericForeignKey — ADR-0025)
A `Correspondence` points at its domain subject with a **string label + int id**,
exactly like `people.PersonnelEvent(entity_type, entity_id)`:
```python
subject_type = models.CharField(max_length=120)   # "people.LeaveRecord"
subject_id   = models.PositiveIntegerField(null=True, blank=True)
# resolved on demand:  apps.get_model(*subject_type.split(".")).objects.get(pk=subject_id)
```
Some correspondence (a plain internal memo) has **no** domain subject — then
`subject_type=""`, and the whole payload lives in `Correspondence.payload` (JSON).

---

## 3. Data model (typed — ADR-0025)

### 3.1 `CorrespondenceType` — governed, ReferenceSet-backed (ADR-0027)
Rather than a new table, correspondence types are a **reference set**
`correspondence_type` whose `ReferenceValue.metadata` carries policy pointers:
```
ReferenceSet(name="correspondence_type", domain="correspondence")
  values (ReferenceValue.code → metadata):
    leave_request     {category:"request", subject_model:"people.LeaveRecord",
                       default_policy:"leave-default", icon:"BeachAccess",
                       requires_attachment:false}
    loan_request      {category:"request", subject_model:"people.Loan", ...}
    profile_change    {category:"request", subject_model:"", form:"profile_change", ...}
    internal_memo     {category:"memo",    subject_model:"", numbering:"NIB-MEMO", ...}
    circular          {category:"memo",    numbering:"NIB-CIRC", broadcast:true, ...}
    decision          {category:"memo",    numbering:"NIB-DEC", ...}
```
Governed enums `leave_type`, `memo_type` are separate reference sets, each value
carrying policy metadata (paid?, max_days, requires_attachment, default_policy).

### 3.2 `Correspondence` — the routed item (typed)
| Field | Type | Notes |
|-------|------|-------|
| `corr_type` | FK `mdm.ReferenceValue` PROTECT | value in `correspondence_type` set |
| `reference_no` | CharField unique, blank until submit | e.g. `NIB-LEAVE-2026-000123` |
| `org_unit` | FK `mdm.OrgUnit` PROTECT | RULE_12 org scope |
| `subject_type` | CharField blank | `"people.LeaveRecord"` or `""` |
| `subject_id` | PositiveInt null | — |
| `payload` | JSONField | form fields (validated vs type schema + DQ) |
| `title` | CharField | human summary ("Annual leave 10–17 Sep") |
| `status` | CharField | draft·submitted·in_review·approved·rejected·cancelled·sent_back·expired·archived |
| `policy` | FK `WorkflowPolicy` PROTECT | snapshot pointer |
| `policy_version` | PositiveSmallInt | frozen at submit |
| `approver_chain` | JSONField | resolved `[{step,role,user_id,label,intent}]` |
| `current_step` | PositiveSmallInt default 1 | — |
| `requester` | FK `accounts.User` PROTECT | who initiated |
| `on_behalf_of` | FK `accounts.User` null | delegation stamp |
| `data_snapshot` | JSONField | immutable copy of subject at submit |
| `signature_ref` | JSONField null | **e-signature seam** — always null in v1 |
| `submitted_at` `resolved_at` `expires_at` | DateTime null | — |
| `created_at` `updated_at` | DateTime | — |

`reflect`: `subject` resolved via `apps.get_model`. Money/date in `payload`
serialized JSON-safe (repo convention CB-13: `Decimal`→str, dates→isoformat).

### 3.3 `WorkflowPolicy` — config-as-data
| Field | Type | Notes |
|-------|------|-------|
| `key` | SlugField unique | `"leave-default"` |
| `name` / `name_ar` | CharField | bilingual |
| `document_type` | CharField | matches a `correspondence_type` code |
| `is_active` | Bool | one active per (document_type) |
| `version` | PositiveSmallInt | bumped on save |
| `initial_status` | CharField default `"submitted"` | draft optional |
| `terminal_statuses` | JSONField | `["approved","rejected","cancelled"]` |
| `employee_cancel_when` | JSONField | statuses where requester may cancel |
| `allow_send_back` | Bool | approver can return with comments |
| `visibility` | CharField | `private` \| `team` \| `org` (team-calendar policy) |
| `notify_on` | JSONField | events that create notifications |
| `numbering_format` | CharField | `"NIB-LEAVE-{year}-{seq:06d}"` |
| `sla_hours` | PositiveInt null | auto-escalate/expire seam |
| `render_template` | CharField blank | reporting-service template key (PDF) |

### 3.4 `WorkflowPolicyStep`
| Field | Type | Notes |
|-------|------|-------|
| `policy` | FK CASCADE | — |
| `step_order` | PositiveSmallInt | 1,2,3… |
| `label` / `label_ar` | CharField | "Manager Review" |
| `approver_role` | CharField | `manager` \| `hr` \| `role` \| `specific_user` |
| `approver_role_key` | CharField blank | ScopedRole group when `role` |
| `approver_user` | FK User null | when `specific_user` |
| `intent` | CharField | `action` (للتنفيذ) \| `info` (للعلم) |
| `is_required` | Bool default True | if False + unresolved → auto-skip |
| `skip_if_self` | Bool default True | approver==requester → auto-skip (no self-approval) |
| `condition` | JSONField null | data-driven skip/branch, e.g. `{"days_lte":1}` → auto-approve |

### 3.5 `CorrespondenceEvent` — append-only timeline (typed, like PersonnelEvent)
| Field | Type | Notes |
|-------|------|-------|
| `correspondence` | FK CASCADE | — |
| `actor` | FK User SET_NULL null | — |
| `on_behalf_of` | FK User null | delegation |
| `action` | CharField | submit·approve·reject·cancel·send_back·auto_approve·comment·edit·sign(seam) |
| `step_order` | PositiveSmallInt null | — |
| `comment` | TextField blank | reject requires it |
| `metadata` | JSONField | before/after diff for edits |
| `created_at` | DateTime auto_now_add | immutable |

Every event ALSO emits `catalog.emit_governance_event(entity_type="Correspondence",
entity_id=...)` — the platform Process History (ADR-0025 decoupled audit half).

### 3.6 `CorrespondenceAttachment` (typed; NOT `evidence.Evidence`)
`evidence.Evidence` is FK→`dataschema.DataRow` (coupled). Correspondence needs a
generic attachment, so a small typed table in this app: `correspondence` FK,
`file`, `original_filename`, `file_size`, `mime_type`, `uploaded_by`, soft-delete.
Mirrors `evidence.Evidence`'s shape/soft-delete for consistency.

### 3.7 `CorrespondenceRegistry` — reference-number sequences
One counter row per `(scope, year)` where scope = numbering prefix. Allocation is
`select_for_update()` + increment inside the submit transaction (no gaps race).
```
scope="NIB-LEAVE"  year=2026  last_seq=123  → next "NIB-LEAVE-2026-000124"
```

### 3.8 `Delegation` — designed, minimal in v1
| Field | Type | Notes |
|-------|------|-------|
| `delegator` / `delegate` | FK User | — |
| `document_types` | JSONField | scope (`[]` = all) |
| `starts_at` / `ends_at` | DateTime | date-bound |
| `is_active` | Bool | — |
Routing consults active delegations; delegated actions stamp `on_behalf_of`. v1
ships the model + routing hook; management UI is a later phase.

### 3.9 `Notification` — in-app only (v1)
`recipient` FK, `correspondence` FK null, `event` CharField, `title`/`body`
(pre-rendered EN+AR), `link`, `is_read`, `read_at`, `created_at`. Polled; no
websocket in v1 (desktop-first).

### 3.10 e-Signature seam (explicit)
- `Correspondence.signature_ref` JSONField (null in v1).
- `CorrespondenceEvent.action` includes `"sign"` (never emitted in v1).
- Policy step `approver_role` reserves future `signature_required: bool`.
- API returns `signature: null` and UI shows a disabled **"Sign (coming soon)"**
  affordance on memo/decision types — so the capability is visibly planned.

---

## 4. State machine (FSM)

```
        submit()                approve@step<last            approve@last
 draft ─────────▶ submitted ───────────────────▶ in_review ─────────────▶ approved
   ▲                 │  │                            │   │
   │ send_back()     │  │ reject()                   │   │ reject()
   └─────────────────┘  ▼                            ▼   ▼
                     rejected                      rejected
        requester cancel() (if status ∈ policy.employee_cancel_when) ▶ cancelled
        expires_at reached (sla_hours) ▶ expired
        terminal + retention ▶ archived
```
- `condition` on a step may **auto_approve** (e.g. `days_lte:1`) or **skip**.
- `skip_if_self` auto-skips a step whose resolved approver == requester.
- `send_back` returns to the initiator (or a prior step) with a required comment;
  requester edits `payload` (logged as `edit` event) and re-submits.
- All transitions are **pure functions in `fsm.py`** (no view logic), unit-tested
  independently, returning the new status + events to persist.

---

## 5. Trust-native seams (reuse, never reinvent)

| Concern | Reused platform capability | Where |
|---------|---------------------------|-------|
| Governed enums | `mdm.ReferenceSet`/`ReferenceValue` (ADR-0027) | corr types, leave types, memo types |
| Org scope (RULE_12) | `mdm.OrgUnit` FK + `get_visible_org_units` | `Correspondence.org_unit` |
| Submit validation | `dq.typed_gate.check_instances` via `ModelRuleAssignment` | `fsm.submit()` pre-check |
| Immutable audit | `catalog.emit_governance_event` | every `CorrespondenceEvent` |
| AI assist (Nibras) | Pulse `nibras` instance (advisory, own data only) | future "draft my leave request" |
| Reporting/PDF | external reporting service (Gigacast) | `render_template` seam |

The DQ submit-gate is the "balance-before-submit / no-overlap" enforcement point:
a Leave request that exceeds entitlement or overlaps an existing one is **blocked
at submit** with a typed finding, not silently accepted.

---

## 6. API surface

Prefix `/carbon-api/correspondence/` (generic engine) and
`/carbon-api/people/me/` (self-scoped domain reads).

### 6.1 Generic engine (`correspondence` app)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/correspondence/` | my correspondence (requester=me), filter type/status |
| POST | `/correspondence/` | create + submit (atomic) for a given `corr_type` |
| GET | `/correspondence/:id/` | detail + full `CorrespondenceEvent` timeline |
| POST | `/correspondence/:id/cancel/` | requester cancel (policy-gated) |
| POST | `/correspondence/:id/edit/` | edit payload when `sent_back` |
| GET | `/correspondence/inbox/` | items awaiting MY action (approver) |
| POST | `/correspondence/:id/approve/` | approve current step |
| POST | `/correspondence/:id/reject/` | reject (comment required) |
| POST | `/correspondence/:id/send-back/` | return to initiator (comment required) |
| GET | `/correspondence/:id/attachments/` · POST | list / upload attachment |
| GET | `/notifications/` · POST `/:id/read/` · POST `/read-all/` | in-app notifications |
| GET/POST | `/policies/` · GET/PATCH `/policies/:id/` · steps | policy admin (people:manage) |
| GET/POST | `/delegations/` | my delegations (model live; UI later) |

### 6.2 Self-scoped domain reads (`people` app, `IsActiveEmployee`)
| Method | Path | Returns |
|--------|------|---------|
| GET | `/people/me/` | my employee summary (name, position, manager, org) |
| GET | `/people/me/leave-balance/` | per-type `{entitled,used,pending,remaining}` |
| GET | `/people/me/leave/` | my leave records + linked correspondence status |
| GET | `/people/me/payslips/` · `/:run_id/` | my payslip lines, grouped |
| GET | `/people/me/payslips/:run_id/render/` | reporting-service PDF seam |
| GET | `/people/me/attendance/?month=YYYY-MM` | my attendance grid |
| GET | `/people/me/loans/` · `/:id/installments/` | my loans + schedule |
| GET | `/people/me/certifications/` | my certs + expiry status |
| GET | `/people/me/team-calendar/?month=` | teammates' leave (policy.visibility gated) |

Leave submit is `POST /correspondence/` with `corr_type=leave_request`; the view
creates the `people.LeaveRecord` (draft) + `Correspondence` atomically.

---

## 7. Permissions (CBAC)

New capabilities in `accounts/capabilities.py` + mirror in `src/capabilities.js`:
```
correspondence:submit   — create/submit own correspondence   (auto-granted to active employees)
correspondence:act      — approve/reject/send-back as a routed approver
correspondence:admin    — manage WorkflowPolicy + CorrespondenceType (people:manage holders)
my:access               — see the My surface (auto if employee_profile active)
team:access             — see the Team surface (auto if has direct_reports OR is a routed approver)
```
**Auto-derivation (no manual role assignment):** in the me_context/claims builder —
```
if user.employee_profile active:            caps += {my:access, correspondence:submit}
if user.employee_profile.direct_reports:    caps += {team:access}
if user is a resolved approver anywhere:    caps += {team:access, correspondence:act}
if has_capability(people:manage):           caps += {correspondence:admin}
```
Self-scope is enforced in querysets (`requester=request.user` / `employee=me`),
never by capability alone. Approver actions verify the acting user is in the
current step's resolved approver set (or a valid delegate).

---

## 8. Frontend surfaces

### 8.1 `my` app (ESS) — `src/apps/my/`
Manifest `showIf: 'hasEmployeeProfile'`. Nav: My Desk (dashboard), My Requests,
My Leave, My Payslip, My Profile, My Attendance, My Loans, My Certifications.
- **Dashboard**: Action-Required strip, Leave Balance card, My Requests (status),
  Upcoming (leave + cert expiry), Quick Actions.
- **My Leave**: balance cards (entitled/used/pending/remaining) rendered **before**
  the Request button; team-calendar strip if `policy.visibility=team`; history.
- **Request Leave drawer**: type (with inline balance) → dates (disables taken
  days) → auto-days → notes → **shows resolved approver chain before submit** →
  confirm.
- **My Requests / detail**: unified list across all types; detail shows full
  Process-History timeline (not just a status chip).
- **My Payslip**: period selector, earnings/deductions/net, Download (reporting
  seam). **My Profile**: view + "Request Change" → profile_change correspondence.

### 8.2 `team` app (MSS) — `src/apps/team/`
Manifest `showIf: 'hasDirectReportsOrApprover'`. Nav: Approvals Inbox, Team
Calendar, Team Attendance, Team Directory.
- **Approvals Inbox**: items awaiting my action; approve/reject/send-back with
  comment; batch approve; delegation banner when acting on behalf.
- **Team Calendar**: who's on leave (dates; type per visibility policy).

### 8.3 Shell + notifications
- Sidebar shows `My` and `Team` sections per derived caps (ShellSidebar).
- Header bell badge from `GET /notifications/?is_read=false` count, polled 60s.
- EN/AR + RTL throughout (ADR-0018); Arabic labels from §1.3.

---

## 9. Anti-patterns explicitly avoided (from ESS research)

| Failure mode | Mitigation in this design |
|--------------|---------------------------|
| Balance hidden until after submit | Balance cards render above Request button; DQ gate blocks over-request |
| No team calendar | `WorkflowPolicy.visibility` → team-calendar strip |
| Can't cancel after submit | `employee_cancel_when` policy list + Cancel action |
| No status-change notification | `Notification` on every `notify_on` event |
| No PDF | reporting-service `render_template` seam |
| Audit invisible to employee | Full `CorrespondenceEvent` timeline in detail |
| Self-approval | `skip_if_self=True` auto-skip |
| Hardcoded approval chain | `WorkflowPolicy`/`Step` config-as-data |
| Overlapping leave accepted | DQ typed-gate finding at submit |
| Approver can't act off-desk | `Delegation` model + `on_behalf_of` stamp |

---

## 10. Phased plan (worker-executable)

> Each phase is scoped for one worker session, names exact files, states a
> contract, and gives a copy-pasteable verification gate. Phases are ordered by
> dependency. Do **one phase per session**. Always: `DJANGO_BRAND=nibras` for
> runtime checks, `DJANGO_BRAND=aastmt` for the pytest suite (pinned in
> conftest). Never run docker. Show live test output (no `tail` pipes).

### Legend
- **Role** = which `.ai-toolkit` role. **Gate** = must pass before phase is "done".

---

### P0 — Foundations: reference sets + ADR (role: backend-worker)
**Goal:** governed enums exist before anything references them.
**Files:**
- `backend/correspondence/` (new app skeleton: `apps.py`, `__init__.py`, empty
  `models.py`, register in `INSTALLED_APPS`).
- `backend/correspondence/management/commands/seed_correspondence.py` — seed
  reference sets: `correspondence_type`, `leave_type`, `memo_type` (values +
  metadata per §3.1).
**Contract:** idempotent seed (re-run safe); values carry `metadata` policy
pointers; no models beyond app registration yet.
**Gate:**
```bash
cd backend && DJANGO_BRAND=nibras ../.venv/bin/python manage.py seed_correspondence
DJANGO_BRAND=nibras ../.venv/bin/python manage.py shell -c "from mdm.models import ReferenceSet; print(ReferenceSet.objects.get(name='correspondence_type').values.count())"
# expect >= 6
```

---

### P1 — Employee ↔ User link (role: backend-worker)
**Goal:** an employee can be resolved from `request.user`.
**Files:** `backend/people/models.py` (add `Employee.user = OneToOneField(
'accounts.User', null=True, blank=True, on_delete=SET_NULL,
related_name='employee_profile')`); migration; `backend/people/permissions.py`
(add `IsActiveEmployee`).
**Contract:** nullable (existing rows survive); `user.employee_profile` reverse
accessor; permission returns True only for active linked employees.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest people/tests/ -q
DJANGO_BRAND=aastmt ../.venv/bin/python manage.py makemigrations --check --dry-run
```

---

### P2 — Engine models + migration (role: backend-worker)
**Goal:** all tables from §3 exist. **No API, no business logic yet.**
**Files:** `backend/correspondence/models.py` (Correspondence, WorkflowPolicy,
WorkflowPolicyStep, CorrespondenceEvent, CorrespondenceAttachment,
CorrespondenceRegistry, Delegation, Notification); `admin.py`; migration.
**Contract:** NO `GenericForeignKey` (use `subject_type`+`subject_id`); governed
enums are FK to `mdm.ReferenceValue`; `signature_ref` present + nullable; money/
date JSON-safe helpers. Emit-governance NOT wired yet.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python manage.py makemigrations correspondence
DJANGO_BRAND=aastmt ../.venv/bin/python manage.py migrate
DJANGO_BRAND=aastmt ../.venv/bin/python manage.py check
grep -rn "GenericForeignKey\|ContentType" backend/correspondence/ && echo "FAIL: generic FK present" || echo "OK: no generic FK"
```

---

### P3 — FSM + routing + registry + policies (pure services) (role: backend-worker)
**Goal:** submit/approve/reject/send-back/cancel work as **pure functions**,
fully unit-tested, no HTTP.
**Files:** `backend/correspondence/fsm.py`, `routing.py`, `registry.py`,
`policies.py`; `backend/correspondence/tests/test_fsm.py`,
`test_routing.py`, `test_registry.py`.
**Contract:** transitions honor `terminal_statuses`, `employee_cancel_when`,
`skip_if_self`, `condition` (auto_approve/skip); reference numbers gap-free
(`select_for_update`); `submit()` calls the DQ typed gate and blocks on findings;
every transition returns events to persist AND calls `emit_governance_event`;
`policy_version` frozen at submit.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest correspondence/tests/ -q
# must include: submit blocked by DQ finding; skip_if_self; auto_approve condition;
# cancel allowed only in policy window; reference-number uniqueness under concurrency.
```

---

### P4 — Generic engine API (role: backend-worker)
**Goal:** the endpoints in §6.1 exist and enforce scope.
**Files:** `backend/correspondence/serializers.py`, `views.py`, `urls.py`,
`permissions.py` (CanActOnCorrespondence); wire into `config/urls.py`;
`accounts/capabilities.py` (new caps §7) + auto-derivation in me_context;
`tests/test_api.py`.
**Contract:** list is self-scoped (`requester=user`); inbox = items where user is
in current step's approver set (or delegate); approve/reject verify the acting
user; reject/send-back require a comment; policy admin gated by
`correspondence:admin`.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest correspondence/tests/test_api.py -q
# assert 403 when a non-approver approves; 400 when reject has no comment;
# assert another user's items never appear in my list.
```

---

### P5 — Leave type → governed FK (role: backend-worker) — ADR-0027
**Goal:** `people.LeaveRecord.leave_type` + `LeaveEntitlement.leave_type` become
FK to `ReferenceValue` (`leave_type` set); balance math uses it.
**Files:** `backend/people/models.py`, data migration (map existing strings →
seeded values), `serializers.py` (GovernedValueField shape), `tests/`.
**Contract:** no denormalized code mirror; `on_delete=PROTECT`; existing rows
migrated; balance endpoint (P6) reads FK.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest people/tests/ -q
DJANGO_BRAND=aastmt ../.venv/bin/python manage.py makemigrations --check --dry-run
```

---

### P6 — Self-scoped `people/me/` reads (role: backend-worker)
**Goal:** §6.2 endpoints, self-scoped, incl. leave-balance with `pending`.
**Files:** `backend/people/self_views.py`, `self_urls.py` (include under
`people/me/`); `tests/test_self_api.py`.
**Contract:** all queries filtered to `request.user.employee_profile`; balance
returns `{entitled,used,pending,remaining}` where `pending` = days in
submitted/in_review correspondence; team-calendar gated by `policy.visibility`;
leave submit delegates to `POST /correspondence/`.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest people/tests/test_self_api.py -q
# assert an employee cannot read another employee's payslip/balance (404/403).
```

---

### P7 — `my` frontend app (role: frontend-worker)
**Goal:** ESS surface per §8.1.
**Files:** `carbon-frontend/src/apps/my/` (manifest.js, MyDashboard.jsx,
MyRequests.jsx, MyLeave.jsx + RequestLeaveDrawer.jsx, MyPayslip.jsx,
MyProfile.jsx, MyAttendance.jsx, MyLoans.jsx, MyCertifications.jsx); register in
`apps/registry.js`; routes in `App.jsx`; `src/capabilities.js` (new caps);
`ShellSidebar.jsx` (My section, derived caps); i18n `locales/en/my.json` +
`ar/my.json`.
**Contract:** balance shown before submit; approver chain shown before submit;
full timeline in request detail; all via `apiFetch` (no raw fetch); MUI theme
tokens only (no inline hex); RTL-safe.
**Gate:**
```bash
cd carbon-frontend && VITE_BRAND=nibras npx vitest run src/apps/my 2>&1
VITE_BRAND=nibras npm run build   # must succeed; bundle title "Nibras..."
```

---

### P8 — `team` frontend app + Approvals Inbox (role: frontend-worker)
**Goal:** MSS surface per §8.2.
**Files:** `carbon-frontend/src/apps/team/` (manifest.js, ApprovalsInbox.jsx,
TeamCalendar.jsx, TeamAttendance.jsx, TeamDirectory.jsx); registry/App/sidebar
wiring; i18n `team.json` EN+AR.
**Contract:** inbox lists my pending approvals; approve/reject/send-back with
comment; team calendar respects visibility; batch approve; delegation banner.
**Gate:**
```bash
cd carbon-frontend && VITE_BRAND=nibras npx vitest run src/apps/team 2>&1
VITE_BRAND=nibras npm run build
```

---

### P9 — In-app notifications + i18n/RTL polish (role: frontend-worker)
**Goal:** bell badge + notification center; full EN/AR parity + RTL.
**Files:** `src/shell/` (NotificationBell.jsx, poll hook), `NotificationCenter`;
i18n key audit EN↔AR; RTL visual pass.
**Contract:** badge = unread count (poll 60s); mark-read/read-all; no missing AR
keys; RTL mirrors layout.
**Gate:**
```bash
cd carbon-frontend && VITE_BRAND=nibras npx vitest run src/shell 2>&1
node scripts/i18n-parity-check.mjs   # or grep: no EN key missing in ar/*.json
```

---

### P10 — Reporting-service PDF seam (role: backend-worker + devops-worker)
**Goal:** `render_template` wired to the external reporting service; NO WeasyPrint
in this repo.
**Files:** `backend/correspondence/render.py` (thin client to reporting API),
`people/self_views.py` payslip `/render/` endpoint; config env for reporting URL.
**Contract:** endpoint returns a signed URL or streamed PDF from the reporting
service; letterhead/logo/signature blocks are the reporting service's templates;
graceful error if service down.
**Gate:**
```bash
cd backend && DJANGO_BRAND=aastmt ../.venv/bin/python -m pytest correspondence/tests/test_render.py -q
# mock the reporting client; assert seam contract, not a real PDF.
```

---

### Seam phases (future — designed, not scheduled)
- **S1 e-Signature (PKI):** implement `signature_ref` + `sign` action + national
  PKI integration; enable the disabled "Sign" affordance.
- **S2 Delegation UI:** management screen for `Delegation`; already enforced in
  routing.
- **S3 Memo/Correspondence official types:** reference-number stamping + QR;
  for-action/for-info recipient lists; circular broadcast.
- **S4 Finance/Procurement types:** new `WorkflowPolicy` + form schema only —
  zero engine change (proves the abstraction).

---

## 11. Open decisions to confirm before P2
1. **Program shape:** run P0–P10 as one program, or ship a thin vertical slice
   (P0–P4 + P6 + P7, Leave only) to production first, then fan out? (Recommend:
   vertical slice first — proves the spine end-to-end.)
   → **RESOLVED (2025 dispatch): ship the thin vertical slice first** — P0–P4 +
   P6 + P7, Leave only. Defer P5 (leave_type→FK), P8 (team app), P9
   (notifications UI/i18n), P10 (PDF). Master task IDs `OF-0`…`OF-12` in
   `TASKS.md` map to this slice.
2. **Profile-change subject:** `profile_change` has no domain subject table —
   confirm payload-only (`subject_type=""`) is acceptable, applied to the
   Employee record on approval via a small applier in `people`.
3. **Numbering scope:** per-instance (`NIB-*`) confirmed for Nibras; each brand
   gets its own prefix from `WorkflowPolicy.numbering_format`.

## 12. Locked refinements (applied at dispatch — supersede §3–§6 where they differ)
These tighten the design to keep `correspondence` layering-safe and the slice
queryable. They override any conflicting wording above.

1. **Subject creation lives in the domain app, not the engine.** The generic
   `POST /correspondence/` create is **out of scope** for the slice. Leave
   submit is `POST /people/me/leave/`: the `people` self-service view creates the
   draft `LeaveRecord`, runs the balance/overlap pre-check, then calls the
   correspondence engine service `submit_correspondence(...)` with
   `subject_type="people.LeaveRecord"`, `subject_id=<pk>`. `correspondence` never
   imports `people` (it receives the subject instance + `model_label` string).
2. **`current_approver_ids` denormalization.** `Correspondence` carries a
   `current_approver_ids JSONField` (mirror of the current step in
   `approver_chain`), maintained on every step transition. This makes the inbox
   query and the `correspondence:act` derivation a single `__contains` lookup —
   no brittle JSON-object scanning.
3. **`submitted` vs `in_review` semantics.** `submitted` = waiting on the FIRST
   approver step (`current_step=0`); `in_review` = waiting on a later step
   (`current_step>=1`). Both are actionable. `ACTIONABLE = ('submitted','in_review')`.
4. **DQ submit-gate is two-part.** (a) generic field-level gate via
   `dq.typed_gate.check_instances(model_label, [subject], mode='block')` inside
   the engine submit; (b) domain overlap/balance enforcement in the `people`
   submit pre-check (cross-record rules are not expressible as single-field DQ
   rules).
