# Design — Mandatory Lock Reason + Generic Notes/Reflections (Enterprise Pattern)

> **Status:** Research + recommended design (deliverable for the "lock toggle with a note" request)
> **Date:** 2026-08-27 · **Author:** Debugger/Fixer (research-grounded, per user request "check research and top enterprise systems and avoid flaws")

---

## 1. The request, abstracted

> "Add a mechanism to lock toggle button + a small text area to write a note why such lock.
> Or tell me a solution that is enterprise and abstract to attach some kind of notes/reflections
> when admin/user do things in general on the system."

The two asks are the **same problem at two scopes**:

1. **Narrow:** a lock/unlock toggle must carry a mandatory human-written **reason**.
2. **Broad:** any consequential admin action (lock, delete, soft-delete, role change, policy enable,
   period status transition, DQ rule activate/deactivate…) should be able to carry a **note/reflection**,
   and users should be able to attach free-form **notes** to entities generally.

The enterprise answer is **not** a lock-specific hack — it is a **two-layer annotation + audit model**:
- **Layer A — mandatory `reason` on state-changing actions**, stored as part of the **immutable audit event**.
- **Layer B — a generic, entity-agnostic `Note`/`Annotation` model** for free-form reflections that is
  *separate* from the audit trail (comments ≠ audit).

This document: (2) what top enterprise systems do, (3) the recommended design for Carbon, (4) concrete
implementation sketch, (5) flaws to avoid (with citations to where the top systems got it right/wrong).

---

## 2. Research — how top enterprise systems handle reasons & notes

### 2.1 Mandatory reasons on state changes

| System | Mechanism | Why it matters for us |
|---|---|---|
| **Salesforce** | **Field History Tracking** (`<Object>History`): append-only per-field before/after + who/when. Approval processes require **comments at each step** (approve/reject mandates a note in many orgs). | History is **append-only, never edited/deleted in place**. Reasons travel with the event, not the row. |
| **ServiceNow** | **Audit History** (table-level before/after + user + timestamp) and **mandatory work notes / additional comments** on state transitions (e.g. Change Management requires a comment when moving Change Request states). | Mandatory-reason is enforced **server-side on the transition**, not just in the UI. |
| **Jira** | **Workflow validators** can make a comment/field **required before a transition** (e.g. "Resolution required"). Comments are separate from changelog (immutable issue history). | Separation of concerns: **changelog = machine audit; comments = human narrative**. |
| **GitHub** | PR merge requires a **commit message**; branch protection requires reviews. Releases require a **release note**. | Reason at the moment of a consequential action; stored with the event. |
| **SAP** | **Change Documents**: append-only before/after for master data; many transactions (e.g. material master lock) require a **reason code**. | Reason codes = structured (enum) + free text, kept in the change record. |
| **Palantir Foundry** | **Change notes** on datasets/branches: edits require a short human note; **ontology versioning** keeps every version with a description. | Every write is versioned + annotated; nothing is silently overwritten. |
| **Ataccama / Collibra** | Governance workflows require a **justification** to approve/deny a change request; stewardship notes attach to assets. | Notes attach to **entities** (asset level), not just actions. |

### 2.2 Generic notes/reflections (annotation layer)

| System | Mechanism | Key property |
|---|---|---|
| **Salesforce** | Chatter / `Note` object — notes attach to any record, author + timestamps, edit history. | Author-owned, editable, visible per sharing rules. |
| **Jira** | Issue comments — threadable, author + timestamps, edit history, delete restricted. | **Editable** but **audited** (comment edit history). |
| **Collibra** | Asset comments + stewardship notes — attach to any asset/term, author + timestamp. | Entity-agnostic (attach to anything). |
| **ServiceNow** | Journal entries (work notes vs comments) on any table. | Two visibility classes: **internal** vs **customer-facing**. |
| **Grafana** | Annotation events on dashboards (with text + tags). | Tagged, timestamped, authored. |

### 2.3 Research takeaways (the "avoid flaws" core)

1. **Reasons belong to the audit event, not the mutable row.** If the reason lives on the row, editing the
   row later erases the reason for the *historical* lock. Salesforce/SAP/ServiceNow all store the reason in
   the history record.
2. **Mandatory must be enforced server-side.** UI-only required fields are trivially bypassed via API
   (exactly the class of bug just fixed on MDM — client/server contract drift). Jira validators and
   ServiceNow ACLs enforce at the transition, not the form.
3. **Audit is append-only.** No update/delete on history records; user FK is `SET_NULL` (not cascade).
4. **Comments and audit are different layers.** Audit = who/what/when (machine). Notes = why/narrative
   (human). Mixing them makes both useless: notes become formal (fear of audit), audit becomes noisy.
5. **Reason = structured + free text.** SAP reason codes: a required enum (e.g. `accidental_lock`,
   `freeze_for_review`) plus optional free text. Pure free text defeats reporting/analytics.
6. **Enforce reasons only on consequential actions.** Requiring a reason for *every* toggle creates
   `"as per standard"` noise (users type anything). Salesforce/SAP scope mandatory comments to
   **irreversible or high-impact transitions** (lock, delete, approve, reject, submit, role grant).
7. **Timezone-aware, author-captured, never silently dropped.** Africa/Cairo everywhere; actor must be
   captured even on background/system actions (`user=NULL` = system).
8. **Notes are entity-agnostic** (polymorphic `entity_type` + `entity_id`), not per-model — one model
   serves org units, modules, periods, DQ rules, users, etc. (Collibra/ServiceNow pattern).

---

## 3. Recommended design for Carbon

Carbon already has the perfect backbone:
- `GovernanceEvent` (`backend/catalog/models.py:104`) — append-only audit: `entity_type`, `entity_id`,
  `action`, `before`, `after`, `user` (SET_NULL), `timestamp` (auto_now_add). **Exactly** the Salesforce
  `<Object>History` pattern.
- `emit_governance_event(...)` (`backend/catalog/audit_utils.py`) — the emit helper.
- `is_locked` on `Module` (`core/models.py:30`) and `DataTable` (`dataschema/models.py:33`) — the toggles.
- Soft-delete `is_active=False` in MDM views (`mdm/views.py`).
- `note = TextField(blank=True)` precedent in `DatasetAccessPolicy` (per-policy note — narrow).

### Layer A — `GovernanceEvent.reason` (mandatory on consequential actions)

Add two fields to `GovernanceEvent` (append-only, never edited):

```python
class GovernanceEvent(models.Model):
    # ...existing fields...
    reason_code = models.CharField(max_length=40, blank=True, default='',
        help_text='Structured reason (enum) — e.g. freeze_for_review, accidental_lock, policy_required')
    reason = models.TextField(blank=True, default='',
        help_text='Human-readable justification. REQUIRED (server-enforced) for consequential actions: lock/unlock/delete/archive/approve/reject/role-grant.')
```

**Enforcement contract (server-side):**

```python
# backend/catalog/audit_utils.py
CONSEQUENTIAL_ACTIONS = {'lock', 'unlock', 'delete', 'archive', 'approve', 'reject', 'role_grant'}

def emit_governance_event(entity_type, entity_id, action, before, after, user, reason='', reason_code=''):
    if action in CONSEQUENTIAL_ACTIONS and not (reason.strip() or reason_code):
        raise ValueError(f"GovernanceEvent {action} requires a reason (reason or reason_code)")
    ...
```

Every lock/unlock/delete path already calls `emit_governance_event` (verified: MDM `perform_update`/
`perform_destroy` emit `create/update/delete` events) → one change propagates everywhere.

**API surface:** views that toggle locks/status accept an optional `reason`/`reason_code` in the request
body and pass it through. Serializer-level validation where the action is a dedicated endpoint.

### Layer B — generic `Note` model (reflections on anything)

```python
class Note(models.Model):                      # backend/catalog/models.py
    entity_type = models.CharField(max_length=40)      # 'org_unit' | 'module' | 'period' | 'dq_rule' | 'user' ...
    entity_id = models.PositiveIntegerField()          # polymorphic
    body = models.TextField()
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    visibility = models.CharField(max_length=10, choices=[('public', 'Public'), ('internal', 'Internal')],
                                  default='public')     # ServiceNow work-note pattern

    class Meta:
        indexes = [models.Index(fields=['entity_type', 'entity_id'])]
        ordering = ['-created_at']
```

- **Editable** by author (or admin) — but **audited**: editing emits `update` GovernanceEvent, so the
  reflection narrative stays human while the fact of the edit stays auditable (Jira comment-edit pattern).
- **Delete** restricted to admin, and deletion emits `delete` event (or soft-delete via `is_active=False`).
- **Never cascades**: `entity_id` is plain int (no FK) → deleting the entity keeps the notes (Collibra keeps
  comments when assets are archived; Salesforce keeps notes when records are deleted — important for
  post-mortem).

### Frontend

**Lock/unlock toggle + mandatory reason (Layer A):** any `Switch` that flips `is_locked`/`is_active`/
`status` toward a consequential state opens a small confirm dialog:

```
┌─ Lock Module "Scope 1 — Fuel Combustion" ────────────┐
│ Reason (required)                                     │
│ [ Freeze for FY26 verification                ▾ ]     │  ← reason_code dropdown (optional structured)
│ [ Freeze the module while the external auditor       ]│
│ [ reviews FY26 activity data.                 ]       │  ← reason textarea (required if no code)
│                                                     │
│        [ Cancel ]          [ Confirm Lock ]          │
└───────────────────────────────────────────────────────┘
```

- The confirm dialog is a small reusable `<ReasonDialog action entityType entityId onConfirm>`
  component (single implementation, reused by every toggle: MDM, DQ rules, periods, modules).
- **Round-trip safety:** the MDM lesson applies — the dialog must send the reason as part of the same
  request that performs the toggle (one atomic PUT/POST), **not** a second "attach note" call, or you get
  the same client/server contract drift class of bug.

**Notes/reflections (Layer B):** a "Notes" tab/section (Collibra-style) on entity detail pages — list,
add, edit, delete, `internal` badge. Reuses the existing `apiFetch` JWT wrapper, pagination unwrap
pattern (`Array.isArray(x) ? x : x?.results || []`).

---

## 4. Concrete implementation sketch (Carbon, minimal)

### Backend

**1. Migration** — `catalog/0008_governanceevent_reason_note.py`:
- `AddField` x2 to `GovernanceEvent` (`reason_code`, `reason`)
- `CreateModel` `Note`

**2. `audit_utils.py`** — extend `emit_governance_event` signature (`reason='', reason_code=''`),
enforce mandatory for `CONSEQUENTIAL_ACTIONS`. **All existing call sites keep working** (default `''`),
so non-consequential events are unaffected; only lock/unlock/delete paths must start passing reasons.

**3. Lock toggle endpoints** (example: module lock in `core/views.py`):
```python
class ModuleLockToggleView(APIView):
    def post(self, request, pk):
        reason = request.data.get('reason', '').strip()
        reason_code = request.data.get('reason_code', '').strip()
        if not (reason or reason_code):
            return Response({'detail': 'A reason is required to lock/unlock a module.',
                             'code': 'ERR_REASON_REQUIRED'}, status=400)
        ...
        emit_governance_event('module', pk, 'lock', before, after, request.user,
                              reason=reason, reason_code=reason_code)
```

**4. Note CRUD** — `catalog/views.py` `NoteViewSet` (list/create/update/delete) with
`permission_classes=[IsAuthenticated]`, update/delete restricted to author or
`platform:manage_*` admin. Route under `/carbon-api/catalog/notes/`.

**5. GovernanceEvent serializer** — expose `reason`/`reason_code` in the audit read API so the
Governance Audit page can show "why".

### Frontend

1. `carbon-frontend/src/components/ReasonDialog.jsx` — reusable required-reason confirm dialog
   (reason_code dropdown optional + reason textarea; validates non-empty before enabling Confirm).
2. Swap each consequential toggle to use `<ReasonDialog>`: `MDMPage.jsx` (soft-delete), DQ rule
   activate/deactivate, `ReportingPeriodsPage.jsx` lock, module lock.
3. `NoteList` component (list + add + edit + delete, `internal` badge) — mount on entity detail pages
   (start with MDM org unit + module detail; the polymorphic model means no per-page backend work).
4. Governance Audit page shows `reason` column for events that carry one.

---

## 5. Flaws to avoid (mapped to research)

| # | Flaw | Why it's a flaw (evidence) | Avoid by |
|---|---|---|---|
| F1 | Reason stored on the mutable row (`Module.lock_reason`) | Editing the row later erases the historical why; Salesforce/SAP keep reasons in history records | Reason lives on **`GovernanceEvent`** (append-only) |
| F2 | UI-only required reason | Same class of bug as the MDM 400: client/server contract drift; API bypass | **Server-side validation** in serializer/view/`emit_governance_event` |
| F3 | Editable/deletable audit events | Destroy the evidence trail; regulatory failure | `GovernanceEvent` stays append-only; **never** expose update/delete |
| F4 | `user` FK `CASCADE` | Deleting a user wipes who did what | Keep `SET_NULL` (already correct) |
| F5 | Notes cascade-deleted with entity | Loses post-mortem context (Collibra keeps comments on archived assets) | `Note.entity_id` is a plain int, no FK cascade |
| F6 | Free-text-only reason | Unreportable; users type anything; SAP uses reason codes for a reason | Optional `reason_code` enum + free text |
| F7 | Reason required on *every* toggle | Noise (`"as per standard"`), measurement destroyed; Salesforce scopes mandatory comments | Enforce only on `CONSEQUENTIAL_ACTIONS` |
| F8 | Notes and audit merged into one table | Notes become formal, audit becomes noisy | Two layers: `GovernanceEvent` (machine) vs `Note` (human) |
| F9 | Naive datetimes | Africa/Cairo timezone bugs (PB-06 family) | `auto_now_add`/`auto_now` (Django timezone-aware; settings already `USE_TZ`) |
| F10 | Toggle + reason in two requests | Non-atomic → the exact contract-drift bug class just fixed | One request does the toggle AND carries the reason |
| F11 | Notes unmasked with PII | Reflections may contain sensitive data | `visibility` (public/internal); internal hidden from non-admin reads |
| F12 | No actor on system actions | Background jobs would blank out who | `user=NULL` is explicitly "system"; add `system=True` flag if needed |

---

## 6. Recommendation summary

**Do Layer A now, Layer B next.**

1. **Layer A (small, high-value):** add `reason_code` + `reason` to `GovernanceEvent`; enforce mandatory
   in `emit_governance_event` for `lock/unlock/delete/archive/approve/reject/role_grant`; one
   `ReasonDialog` on the frontend toggles. This directly answers "lock toggle + note why" with the
   enterprise pattern (reason travels with the immutable audit event).
2. **Layer B (medium):** generic polymorphic `Note` model + `NoteViewSet` + Notes section on detail pages
   for free-form reflections — Collibra/Jira-style, entity-agnostic, zero per-entity backend work.
3. **Guardrails:** server-side mandatory enforcement (never UI-only), append-only audit, no cascade deletes,
   timezone-aware, one atomic request per action, `visibility` for internal notes.

**Estimated footprint:** Layer A ≈ 1 migration + ~30 lines in `audit_utils.py` + 1 component + call-site
updates. Layer B ≈ 1 migration + 1 viewset + 1 component.
