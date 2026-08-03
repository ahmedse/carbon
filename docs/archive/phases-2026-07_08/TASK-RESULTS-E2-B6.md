# TASK-RESULTS-E2-B6 — Recalculate endpoints

**Role:** backend-worker
**Date:** 2026-08-03
**Status:** ✅ COMPLETE

---

## Summary

Added two new custom actions on `CalculationViewSet`:
1. `POST /carbon-api/carbon/calculations/{id}/recalculate/` — re-runs a single calculation
2. `POST /carbon-api/carbon/calculations/batch-recalculate/` — re-runs multiple calculations

Service methods added to `CalculationEngineService` in `emissions/services.py`.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/emissions/services.py` | Added `CalculationEngineService.recalculate()` and `CalculationEngineService.batch_recalculate()` |
| `backend/emissions/views.py` | Added `recalculate` and `batch_recalculate` `@action` methods on `CalculationViewSet` |
| `backend/emissions/tests/test_recalculate.py` | **NEW** — 10 tests |

---

## Implementation Details

### Service layer (`emissions/services.py`)

**`CalculationEngineService.recalculate(calculation)`**
- Recomputes `co2e_kg = activity_value × factor_value`
- Recomputes individual gas components (`co2_kg`, `ch4_kg`, `n2o_kg`) if the factor provides them
- Updates `calculated_at` to current time
- Saves only changed fields via `update_fields=[...]`

**`CalculationEngineService.batch_recalculate(*, period_id, module_id, calculation_ids)`**
- Filters by `calculation_ids` (explicit list) OR `period_id`/`module_id`
- Iterates with `.iterator()` for memory efficiency on large sets
- Returns `{total, recalculated, failed}`

### View layer (`emissions/views.py`)

Both actions are thin — parsing → gating → service call → serialize → Response.

**Period gating (E2-B3 pattern):** If the calculation's `reporting_period.status` is `locked`, `verified`, or `closed`, returns `409 Conflict`.

### Tests (`emissions/tests/test_recalculate.py`) — 10 tests

| Test | What it verifies |
|------|-----------------|
| `test_recalculate_single_returns_200` | Single recalc updates values correctly |
| `test_recalculate_404_when_not_found` | Non-existent calc → 404 |
| `test_recalculate_409_when_period_locked` | Locked period blocks recalc → 409 |
| `test_recalculate_409_when_period_verified` | Verified period blocks recalc → 409 |
| `test_recalculate_409_when_period_closed` | Closed period blocks recalc → 409 |
| `test_batch_recalculate_returns_200_with_counts` | Batch by period with 2 calcs → correct counts |
| `test_batch_recalculate_by_module_id` | Batch by module → correct counts |
| `test_batch_recalculate_by_calculation_ids` | Batch by explicit IDs → correct counts |
| `test_batch_recalculate_400_no_params` | No params → 400 |
| `test_batch_recalculate_409_when_period_locked` | Locked period blocks batch → 409 |

---

## Gates

```bash
$ cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest --reuse-db -q
399 passed, 15 failed, 2 warnings in 76.39s
```

- **399 passed** (389 pre-existing + 10 new)
- **15 failed** — all pre-existing (SBTi targets + swagger docs), zero regressions
- `python manage.py check` — 0 issues

---

## Best Practice Notes

- **Thin views:** Both actions delegate to `CalculationEngineService` — no business logic in views
- **Iterator for batch:** Uses `.iterator()` to avoid loading all calculations into memory
- **Gating reuse:** Period status check matches the E2-B3 pattern in `PeriodLockService` — locked/verified/closed periods blocked at both view and batch service layers
