# TASK — Leave Policy Registry (LPR)

**Owner:** Master Architect · **Domain:** People (Nibras HR) · **Status:** DONE (LPR-1A/LPR-1B/LPR-2A/LPR-2B/LPR-3A/LPR-3B)

## Problem

Today `LeavePolicy` is a flat, one-row-per-leave-type config table, surfaced as a
single "Leave Policy" tab inside `PeopleConfigPage`. It is not a registry:

- No human-readable **name** — identity is the leave-type code.
- No **lifecycle/status** (draft → active → deprecated) — only a boolean `is_active`.
- No **effective dates** — a change applies instantly, with no future-dated transitions.
- No **applicability rules** — cannot scope a policy to org units or contract types.
- No **employee visibility** — no count of who a policy covers; no propagation.

## Solution — three phases

### LPR-1 — Policy Registry + Detail 360

**1A (backend, `backend/people/*`)** — evolve the model into a registry and expose
the data the frontend needs:

| Add to `LeavePolicy` | Type | Notes |
|---|---|---|
| `name` | CharField(200, blank) | primary identity |
| `description` | TextField(blank) | |
| `status` | CharField(draft/active/deprecated, default active) | lifecycle source (supersedes `is_active`) |
| `effective_from` | DateField(null) | future-dated transitions |
| `effective_to` | DateField(null) | |
| `applies_to_org_units` | M2M(mdm.OrgUnit, blank) | empty = all |
| `applies_to_contract_types` | JSONField(list, blank) | contract_type codes; empty = all |

- Migration `0021_leave_policy_registry` (schema + data backfill:
  `name = leave_type.code`, `status = active/deprecated` from `is_active`).
- Serializer: new fields + read-only `employee_count` (distinct employees with a
  `LeaveEntitlement` matching the policy's `leave_type` in the current year).
- Action `POST /leave-policies/<id>/propagate/` (body `{ year }`, `?dry_run=true`).
- `__str__` → `f"{self.name} ({self.leave_type.code})"`.

**1B (frontend, `carbon-frontend/*`)** — replace the flat tab with a real registry:

- `PoliciesPage.jsx` (`/people/policies`) — FilterBar + PolicyGrid + New Policy CTA.
- `PolicyDetailPage.jsx` (`/people/policies/:id`) — 6 tabs (General / Entitlement /
  Carryover / Eligibility / Workflow / Employees), localStorage tab persistence.
- Remove LeavePolicy tab from `PeopleConfigPage`.
- `api/people.js` → `propagateLeavePolicy`.
- `manifest.js` → "Policies" nav item under Configuration.
- i18n keys (en + ar).

### LPR-2 — Smart propagation engine (LPR-2A backend, LPR-2B frontend)

**2A (backend, `backend/people/*`)** — auditable, reusable propagation:
- `LeaveEntitlement.policy` FK (nullable, `SET_NULL`, `related_name='+'`) → migration 0022.
- New DRF-free service `people/leave_policy_service.py`: `propagate_policy(policy, year, dry_run)` + `propagate_all_active(year, dry_run)`. On create, record `policy` provenance; never overwrite existing `entitled_days`/`policy`.
- `LeavePolicyPropagateView` becomes a thin wrapper over the service.
- Serializer exposes read-only `policy` + `policy_name`.
- Management command `propagate_leave_policies` (`--year`, `--policy-id`, `--dry-run`).

**2B (frontend, `carbon-frontend/*`)** — surface the engine:
- "Propagate All Active" batch action on `PoliciesPage`.
- Show `policy_name` provenance on per-employee entitlements (EmployeeLeaveTab).
- i18n keys.

### LPR-3 — Policy versioning (LPR-3A backend, LPR-3B frontend)

**3A (backend, `backend/people/*`)** — version ledger + fork semantics:
- New `LeavePolicyVersion` model (`policy` FK `related_name='versions'`, `version_number`,
  `effective_from`/`effective_to`, `snapshot` JSON, `change_summary`, `created_by`,
  `created_at`; `unique_together('policy','version_number')`) → migration 0023.
- `LeaveEntitlement.policy_version` FK (nullable, `SET_NULL`) — provenance at version
  granularity; backfill links legacy rows to version 1.
- Extend `leave_policy_service.py` (DRF-free): `snapshot_policy`, `fork_policy`
  (closes the prior open version, increments version_number), `get_version_history`,
  `latest_version`.
- `LeavePolicyVersionSerializer` + read-only `latest_version`/`version_count` on
  `LeavePolicySerializer` + read-only `policy_version`/`policy_version_number` on
  `LeaveEntitlementSerializer`.
- Views + URLs: `GET/POST /leave-policies/<id>/versions/` + `GET /leave-policies/<id>/versions/<vid>/`.
- Tests `test_leave_policy_versioning.py`.

**3B (frontend, `carbon-frontend/*`)** — version-history panel:
- `PolicyDetailPage.jsx` → 7th "Versions" tab (timeline + snapshot detail + "New Version"
  fork dialog).
- `api/people.js` → `fetchLeavePolicyVersions`, `forkLeavePolicy`.
- i18n keys (en + ar).

## Parallel-safety (vs. the other master's WIP)

The other master is working on the **correspondence engine** (`backend/correspondence/*`),
**AI answer envelope** (`backend/ai/*`, `shell/*`, `i18n/*/ai.json`), and
**accounts CBAC** (`backend/accounts/*`). LPR touches `backend/people/*` and
`carbon-frontend/src/apps/people/*` + `App.jsx` + `api/people.js` + `manifest.js` +
`Breadcrumbs.jsx` + `i18n/*/people.json`. **No file overlap** → LPR runs in parallel.

Shared-files to be careful about (both branches may eventually touch them, but not now):
`backend/config/settings.py`, `carbon-frontend/src/App.jsx`. Re-check `git status`
before each dispatch.

## Ordering

LPR-1A first (unblocks LPR-1B). LPR-2 after LPR-1A, LPR-3 after LPR-2.
