# TASKS — Carbon Phase 08: Production Hardening

**Date:** 2026-07-29
**Status:** IN PROGRESS

---

## Status Audit (Pre-Task)

Survey findings from `TASK-CARBON-P8-HARDENING.md` were partially addressed by earlier work:

| Deliverable | Status |
|---|---|
| D1 — RBAC lock write endpoints | ✅ DONE — all 4 endpoints already have `AdminOrSuperuserOnly` |
| D2 — DQ trigger in calculate_for_table | ✅ DONE — `profile_table()` + `run_dq()` already called |
| D3 — Policy engine + wiring | ✅ DONE — `catalog/policy_engine.py` exists, wired into `core/views.py` + `dataschema/views.py` |
| D6 — RBAC-aware UI (3 pages) | ✅ DONE — all 3 pages have `isAdmin` gating |
| D7 — Error handling consistency | ✅ DONE — all 3 pages use `notifyFromError` |
| D8 — Empty states | ✅ DONE — all 3 pages have `InboxIcon` + "No X found" messages |
| **D4 — Test expansion** | ⬜ REMAINING |
| **D5 — N+1 check** | ⬜ REMAINING |

---

## Phase G1 — Backend Tests + N+1

**Role:** Backend Worker
**Model:** DeepSeek (Medium)
**Domain:** Django backend only — zero frontend changes

### Files to Read First (before any edits)

| File | Why |
|---|---|
| `backend/emissions/views.py` | Check `permission_classes` on target viewsets |
| `backend/emissions/services.py` | N+1 check — DashboardService, ReportService |
| `backend/catalog/policy_engine.py` | Understand `check_policy()` signature for tests |
| `backend/catalog/models.py` lines 106-165 | `GovernancePolicy` model fields |
| `backend/catalog/permissions.py` | `AdminOrSuperuserOnly` to understand what admin means |
| `backend/accounts/models.py` | Custom User model, ScopedRole model |
| `backend/conftest.py` | Existing fixtures (users, org units, etc.) |

### Files to Edit/Create

**NEW FILE — `backend/emissions/tests/test_rbac_hardening.py`**

Write pytest tests using DRF `APIClient`. Use `--reuse-db`. Import fixtures from `conftest.py`.

Key test cases (7 total):
1. `test_admin_can_create_calculation_rule` — admin user POST `/carbon-api/emissions/rules/` → 201
2. `test_dataowner_cannot_create_rule` — transport_officer POST → 403
3. `test_dataowner_cannot_delete_rule` — transport_officer DELETE → 403
4. `test_dataowner_cannot_trigger_calculate` — transport_officer POST `/carbon-api/emissions/calculate/` → 403
5. `test_dataowner_cannot_batch_calculate` — transport_officer POST `/carbon-api/emissions/batch-calculate/` → 403
6. `test_dataowner_cannot_crud_target` — transport_officer POST/PUT/DELETE `/carbon-api/emissions/sbti-targets/` → 403 (combine into one parametrized or separate)
7. `test_calculate_triggers_dq` — execute a CalculationRule → verify `AssetProfile.objects.filter(data_table_id=...)` has `quality_status` updated (non-unknown)

**NEW FILE — `backend/catalog/tests/test_policy_engine.py`**

Test the policy engine's `check_policy()` function directly (unit tests, don't need API):

1. `test_policy_blocks_module_delete` — create enabled `module_delete` policy → `check_policy('module_delete')` → `(False, [policy.name])`
2. `test_policy_allows_when_disabled` — create disabled policy → `check_policy(...)` → `(True, [])`
3. `test_policy_allows_when_no_match` — create policy for different org → `check_policy('module_delete', org_unit_id=99999)` → `(True, [])`

**EDIT — N+1 check (D5)**

Read `backend/emissions/services.py`. Look at `DashboardService` and `ReportService` query patterns. If queries inside loops lack `select_related`/`prefetch_related`, add them. Acceptable if already optimized.

### DO NOT TOUCH
- `backend/emissions/views.py` (permissions already correct)
- `backend/emissions/models.py` (DQ trigger already wired)
- `backend/catalog/policy_engine.py` (already fully implemented)
- `backend/core/views.py` (policy engine already wired)
- `backend/dataschema/views.py` (policy engine already wired)
- Any frontend file

### Verification Gate

```bash
# 1. Django check
python manage.py check

# 2. No pending migrations
python manage.py makemigrations --check

# 3. Run the new tests
python -m pytest backend/emissions/tests/test_rbac_hardening.py backend/catalog/tests/test_policy_engine.py --reuse-db -v

# 4. Full suite still green
python -m pytest --reuse-db -q

# 5. Anti-pattern check
./.ai-toolkit/scripts/verify.sh antipatterns

# 6. Count: should be 83+ tests total (73 existing + 10 new)
```

### Acceptance Criteria
- [ ] All 10 new tests pass
- [ ] Full suite still green (283+ tests passing)
- [ ] `python manage.py check` clean
- [ ] `python manage.py makemigrations --check` clean (no model changes expected)
- [ ] `verify.sh antipatterns` passes

---

## Phase G2 — Frontend Hardening

**Status:** ✅ SKIPPED — all frontend deliverables (D6, D7, D8) already complete.

The 3 pages (`CalculationRulesPage.jsx`, `GWPReferencePage.jsx`, `SBTiTargetsPage.jsx`) already have:
- `isAdmin` check hiding Create/Edit/Delete buttons
- `notifyFromError()` in all catch blocks
- Empty state with `InboxIcon` + message

---

## Next After Completion

After G1 is done, run:
```bash
./.ai-toolkit/scripts/verify.sh full
```
to close out Phase 08.
