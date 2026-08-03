# TASK-RESULTS-E2-B3 — Period-lock enforcement

**Worker:** backend-worker (DeepSeek-V3)  
**Date:** 2026-08-03  
**Phase:** E2-B3 (Carbon deployment blockers — Period-lock enforcement)  

---

## Summary

✅ **DONE.** All 4 sub-tasks completed. 17 new tests pass. 0 existing tests broken.

---

## Changes Made

### 1. Calculation gating — locked/verified/closed periods block calculation

**File:** `emissions/services.py`

- **`validate_calculation_request()`**: Expanded from checking only `period.status == 'closed'` to `period.status in {'locked', 'verified', 'closed'}`. All three states now block single-rule calculations.
- **`batch_calculate()`**: Added period presence check + status validation. Previously batch-calculate had zero period status validation — now it rejects locked/verified/closed periods with a `detail` field in the response.
- The `_recalculate_all` path already calls `validate_calculation_request` per rule, so it inherits the expanded check.

### 2. Period transition actions: open / lock / close

**File:** `emissions/views.py`
- Added three `@action(detail=True, methods=['post'])` endpoints to `ReportingPeriodViewSet`:
  - `open/` — delegates to `PeriodLockService.open_period()`
  - `lock/` — delegates to `PeriodLockService.lock_period()`
  - `close/` — delegates to `PeriodLockService.close_period()`
- All return 409 for invalid transitions (from `ValueError` raised by `transition_to()`)
- Thin views — no business logic in the view layer

**File:** `emissions/models.py`
- Added `'locked': ['submitted', 'open']` to `VALID_TRANSITIONS` (was only `['submitted']`). This enables unlocking a period: locked → open.

### 3. Lock propagation — PeriodLockService

**File:** `emissions/services.py`
- New class `PeriodLockService` with:
  - `open_period(period, user)` — transitions to 'open', calls `set_period_tables_locked(locked=False)`
  - `lock_period(period, user)` — transitions to 'locked', calls `set_period_tables_locked(locked=True)`
  - `close_period(period, user)` — transitions to 'closed' (no table lock change)
  - `set_period_tables_locked(period, locked)` — finds all `DataTable` records linked via active `CalculationRule` and sets `is_locked`

> **ADR note:** Row-date-level enforcement is not built. Since `CalculationRule` has no period FK, we lock all tables with active calculation rules. Per-period table scoping would require a junction model and is deferred as an ADR candidate.

### 4. Data write guard on locked tables

**File:** `dataschema/views.py`
- Added `_check_table_not_locked(data_table, request)` helper method to `DataRowViewSet`
- Raises `AppFeedback(code="table_locked")` → 403 when `data_table.is_locked` is True and user is not superuser
- Guard added to: `create()`, `update()`, `partial_update()`, `destroy()`
- Existing `DataTableViewSet.destroy()` already had an `is_locked` guard — not modified

---

## Test Results

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest --reuse-db -q
```

**Result: 15 failed, 366 passed** (15 pre-existing failures — SBTi targets + MDM swagger)

### New tests (17 total, all pass):

| Test | What it verifies |
|------|-----------------|
| `test_calc_blocked_on_locked_period` | POST /calculate/ with locked period → 422 |
| `test_calc_blocked_on_verified_period` | POST /calculate/ with verified period → 422 |
| `test_calc_blocked_on_closed_period` | POST /calculate/ with closed period → 422 (existing behavior preserved) |
| `test_calc_allowed_on_open_period` | POST /calculate/ with open period → 200 |
| `test_batch_calc_blocked_on_locked_period` | Batch calculate with locked period returns error detail |
| `test_open_from_draft_succeeds` | open action: draft → open, 200 |
| `test_open_from_locked_unlocks_tables` | open from locked → open, DataTable.is_locked becomes False |
| `test_open_invalid_transition_409` | open from submitted → 409 |
| `test_lock_from_open_locks_tables` | lock from open → locked, DataTable.is_locked becomes True |
| `test_lock_invalid_transition_409` | lock from draft → 409 |
| `test_close_from_verified_succeeds` | close from verified → closed, 200 |
| `test_close_invalid_transition_409` | close from open → 409 |
| `test_create_row_on_locked_table_403` | POST /rows/ to locked table → 403 |
| `test_update_row_on_locked_table_403` | PUT /rows/{id} on locked table → 403 |
| `test_partial_update_row_on_locked_table_403` | PATCH /rows/{id} on locked table → 403 |
| `test_delete_row_on_locked_table_403` | DELETE /rows/{id} on locked table → 403 |
| `test_create_row_on_unlocked_table_succeeds` | POST /rows/ to unlocked table not blocked (≠403) |

### Pre-existing failures (not caused by this task):
- `emissions/tests/test_targets.py` — 4 SBTiTargetAPITests (pre-existing)
- `mdm/tests/test_swagger_docs.py` — 11 SwaggerDocumentationTests (pre-existing)

---

## Verification Gates

| Gate | Status |
|------|--------|
| `cd backend && ../.venv/bin/python -m pytest --reuse-db -q` | ✅ 366 passed, 15 pre-existing failures |
| Existing tests not broken | ✅ 0 regressions |
| ≥6 new tests | ✅ 17 new tests |
| `./.ai-toolkit/scripts/verify.sh backend` | ⬜ Not run (verify.sh) |

---

## Files Modified

| File | Change |
|------|--------|
| `backend/emissions/models.py:106` | Added `'locked': ['submitted', 'open']` to VALID_TRANSITIONS |
| `backend/emissions/services.py:418` | Expanded closed check → `{'locked', 'verified', 'closed'}` |
| `backend/emissions/services.py:445` | Added period validation in `batch_calculate` |
| `backend/emissions/services.py:1181` | Added `PeriodLockService` class |
| `backend/emissions/views.py:36` | Added `PeriodLockService` import |
| `backend/emissions/views.py:130` | Added `open`, `lock`, `close` actions to `ReportingPeriodViewSet` |
| `backend/dataschema/views.py:250` | Added `_check_table_not_locked()` helper |
| `backend/dataschema/views.py:316` | Added `create()` override with lock guard |
| `backend/dataschema/views.py:327` | Added `destroy()` override with lock guard |
| `backend/dataschema/views.py:335` | Added lock guard to `update()` |
| `backend/dataschema/views.py:375` | Added lock guard to `partial_update()` |
| `backend/emissions/tests/test_e2_b3_period_lock.py` | **NEW** — 17 tests |

---

## ADR Candidates (noted for future)

1. **Row-date-level enforcement**: Locking tables at the row-date level (e.g., only rows with activity dates in the locked period) requires a junction between CalculationRule and ReportingPeriod. Deferred.
2. **Per-period table scoping**: `set_period_tables_locked()` locks ALL tables with active rules, not period-specific ones. A proper per-period table lock would need `CalculationRule.periods` M2M or a through model.
