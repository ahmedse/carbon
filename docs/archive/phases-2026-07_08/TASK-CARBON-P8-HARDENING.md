# TASK-CARBON-P8-HARDENING — Phase 08: Production Hardening

**Date:** 2026-07-29
**Status:** IN PROGRESS
**Depends on:** Phase 07 complete

---

## Survey Findings (Master Audit)

### Gap 1 — RBAC: Write endpoints too permissive

| Endpoint | Current Permission | Problem |
|---|---|---|
| `CalculationRuleViewSet` (ModelViewSet) | `IsAuthenticated` | Any dataowner can create/edit/delete rules |
| `CalculateAPIView` (POST) | `IsAuthenticated` | Any dataowner can trigger calculations |
| `BatchCalculateAPIView` (POST) | `IsAuthenticated` | Any dataowner can batch-calculate |
| `SBTiTargetViewSet` (ModelViewSet) | `IsAuthenticated` | Any dataowner can CRUD SBTi targets |

These 4 endpoints allow **write actions by any authenticated user** — including dataowners who should only view their org's data, not modify platform config. We already have `AdminOrSuperuserOnly` from `catalog/permissions.py` used by ReportingPeriodViewSet, EmissionFactorViewSet, GWPViewSet — the same pattern must apply here.

### Gap 2 — DQ not wired into calculation pipeline

When `CalculationRule.calculate_for_table()` runs, it creates `Calculation` records, but never triggers DQ profiling or validation. The source table's quality status in `AssetProfile` becomes stale. The DQ engine (`dq/services.py`) already has `profile_table()` and `run_dq()`, they just need to be called.

### Gap 3 — Governance policy enforcement not wired

`GovernancePolicy` model + CRUD exists. But enforcement is **hardcoded** in destroy() guards — not driven by the policy config engine. There's no `catalog/policy_engine.py` that reads enabled policies and evaluates them at runtime.

### Gap 4 — Test coverage at 50 tests, room for RBAC/DQ/policy tests

### Gap 5 — Frontend: admin actions visible to non-admins

Dataowners who visit `/carbon/admin/rules`, `/carbon/admin/gwp`, `/carbon/admin/targets` see Create/Edit/Delete buttons. They'll get 403 from the API, but the UI shouldn't show admin-only actions.

---

## Deliverables

### G1 — Backend Hardening (5 areas)

#### D1: RBAC — Lock write endpoints

| File | Change |
|---|---|
| `backend/emissions/views.py` | `CalculationRuleViewSet` → `AdminOrSuperuserOnly` (full CRUD restricted) |
| `backend/emissions/views.py` | `CalculateAPIView` → `AdminOrSuperuserOnly` |
| `backend/emissions/views.py` | `BatchCalculateAPIView` → `AdminOrSuperuserOnly` |
| `backend/emissions/views.py` | `SBTiTargetViewSet` → `AdminOrSuperuserOnly` (full CRUD restricted) |

Note: `CalculationViewSet`, Dashboard, Report, Verification, Owner endpoints, Console all stay `IsAuthenticated` — those are read/view/owner-scoped, fine for dataowners.

#### D2: DQ — Auto-trigger DQ after calculation

In `backend/emissions/models.py`, `CalculationRule.calculate_for_table()`:
- After the loop completes and `created > 0`, call `dq.services.profile_table(self.data_table_id)` then `dq.services.run_dq(self.data_table_id)`
- Only trigger when calculations were actually created (not on zero-change runs)
- Import inside method body (avoid circular imports)

#### D3: Governance — Policy enforcement engine

Create `backend/catalog/policy_engine.py`:

```python
def check_policy(action, *, org_unit=None, module=None, data_table=None):
    """Evaluate enabled governance policies for an action.
    Returns (allowed: bool, blocked_by: list[str])
    """
```

Logic:
1. Query `GovernancePolicy.objects.filter(enabled=True, policy_type=action)`
2. For each policy, check scope match (global always matches; org_unit must be in subtree; domain must match)
3. Return False + blocked policy names if any match

Wire it into:
- `core/views.py` `ModuleViewSet.destroy()` — replace hardcoded `is_locked` check with `check_policy('module_delete', module=instance)`
- `dataschema/views.py` `DataTableViewSet.destroy()` — replace hardcoded `is_locked` check with `check_policy('table_delete', data_table=instance)`

Keep existing `is_locked` as an additional hard block (superuser can override `is_locked` but NOT override an active governance policy — policies are the organizational rule, lock is the technical safeguard).

#### D4: Test expansion

New test file `backend/emissions/tests/test_rbac_hardening.py`:
- `DataownerCannotCreateRule` → POST /emissions/rules/ as transport.officer → 403
- `DataownerCannotDeleteRule` → DELETE as transport.officer → 403
- `DataownerCannotTriggerCalculate` → POST /emissions/calculate/ as transport.officer → 403
- `DataownerCannotBatchCalculate` → POST /emissions/batch-calculate/ as transport.officer → 403
- `DataownerCannotCRUDTarget` → POST/PUT/DELETE /emissions/targets/ as transport.officer → 403
- `AdminCanStillCRUD` → admin can do all the above → 200/201/204
- `CalculateTriggersDQ` → execute a rule → verify AssetProfile quality_status updated

New test file `backend/catalog/tests/test_policy_engine.py`:
- `PolicyBlocksModuleDelete` → create enabled module_delete policy → try delete → blocked
- `PolicyAllowsWhenDisabled` → disabled policy → delete succeeds
- `PolicyAllowsWhenNoMatch` → policy for different org → delete succeeds

#### D5: Performance — N+1 check

Verify no N+1 queries in hot paths:
- `CalculationViewSet.list()` → already has `select_related`
- `DashboardAPIView.get()` → verify `DashboardService` uses appropriate prefetch
- `ReportAPIView.get()` → verify `ReportService` uses appropriate prefetch

If gaps found, add `select_related`/`prefetch_related` and note them.

### G2 — Frontend Hardening (3 areas)

#### D6: RBAC-aware UI — Hide admin actions from non-admins

Modify 3 pages to check user role before showing Create/Edit/Delete buttons:

| File | Change |
|---|---|
| `src/pages/emissions/CalculationRulesPage.jsx` | Hide New Rule / Edit / Delete if not admin |
| `src/pages/emissions/GWPReferencePage.jsx` | Hide New GWP / Edit / Delete if not admin |
| `src/pages/carbon/SBTiTargetsPage.jsx` | Hide New Target / Edit / Delete if not admin |

Pattern: `const isAdmin = user?.is_superuser || user?.groups?.includes('admins_group')` via `useAuth()` context.

#### D7: Error handling consistency

Audit catch blocks in the 3 admin pages + CalculationRulesPage. Ensure all use `notifyFromError(err, 'fallback message')` instead of raw `console.error` or `alert()`.

#### D8: Empty states

Add proper empty-state UI (Typography + Icon + "No X found" message) to pages that currently render empty tables without explanation:
- `CalculationRulesPage.jsx` when rules array is empty
- `GWPReferencePage.jsx` when GWP array is empty  
- `SBTiTargetsPage.jsx` when targets array is empty

---

## Acceptance Criteria (Master Audit)

### Backend gates
- [ ] `python manage.py check` — clean (W005 exempt)
- [ ] `makemigrations --check` — no changes
- [ ] `verify.sh backend` — GATE PASSED
- [ ] `verify.sh antipatterns` — GATE PASSED
- [ ] `pytest emissions/ catalog/ -v` — all tests pass, 65+ total
- [ ] POST /emissions/rules/ as transport.officer → 403
- [ ] POST /emissions/calculate/ as transport.officer → 403
- [ ] POST /emissions/targets/ as transport.officer → 403
- [ ] After calculate → AssetProfile.quality_status updated for source table
- [ ] Policy blocks module/table delete when enabled matching policy exists

### Frontend gates
- [ ] `npm run build` — passes
- [ ] `verify.sh antipatterns` — GATE PASSED
- [ ] Admin buttons hidden when logged in as dataowner
- [ ] Empty states render for all 3 admin pages

### Files in scope

**Backend (~7 files changed, ~2 new):**
- `backend/emissions/views.py` (D1: 4 permission changes)
- `backend/emissions/models.py` (D2: DQ trigger in calculate_for_table)
- `backend/catalog/policy_engine.py` (D3: NEW file)
- `backend/core/views.py` (D3: wire policy engine into ModuleViewSet.destroy)
- `backend/dataschema/views.py` (D3: wire policy engine into DataTableViewSet.destroy)
- `backend/emissions/tests/test_rbac_hardening.py` (D4: NEW file)
- `backend/catalog/tests/test_policy_engine.py` (D4: NEW file)
- `backend/emissions/services.py` (D5: N+1 check, optional prefetch)

**Frontend (~3 files changed):**
- `src/pages/emissions/CalculationRulesPage.jsx` (D6+D7+D8)
- `src/pages/emissions/GWPReferencePage.jsx` (D6+D7+D8)
- `src/pages/carbon/SBTiTargetsPage.jsx` (D6+D7+D8)

---

## Execution

Split into G1 (backend) and G2 (frontend). The two groups have no hard dependency — they can run in parallel.

### Worker assignments

1. **Backend worker**: `activate.sh backend-worker` — implement D1-D5
2. **Frontend worker**: `activate.sh frontend-worker` — implement D6-D8
