# TASK-RESULTS-G3.md — Batch Calculation API

**Worker:** backend-worker  
**Date:** 2026-07-29  
**Status:** ✅ COMPLETE

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/emissions/services.py` | EDIT | Added `CalculationEngineService.batch_calculate()` static method |
| `backend/emissions/views.py` | EDIT | Added `BatchCalculateAPIView` class |
| `backend/emissions/urls.py` | EDIT | Added import + route for `batch-calculate/` |
| `backend/dq/migrations/0003_add_performance_indices.py` | EDIT | Fixed pre-existing bug: `executed_at` → `run_at` (blocker resolution) |

---

## Verification Gate Results

### 1. No migration needed (model check)
```
$ python manage.py makemigrations --check
→ Pre-existing conflict (0004_add_performance_indices ↔ 0004_assetprofile_is_active in catalog)
→ Merged as 0005_merge_20260729_0810
→ Applied merge + dormant dq migration (pre-existing bug fix)
→ Result: No changes detected (clean)
```

### 2. Django system check
```
$ python manage.py check
System check identified 1 issue (0 silenced):
  WARNING: urls.W005 — URL namespace 'carbon' isn't unique (pre-existing)
→ Exit 0 ✅
```

### 3. Restart backend
```
$ bash manage.sh restart backend
Backend started (PID: 985796, Port: 8009) ✅
```

### 4. Auth token obtained
```
$ curl -X POST /carbon-api/token/ → access token obtained ✅
```

### 5. Batch calculate — first run
```
POST /carbon-api/carbon/batch-calculate/
Body: {"table_ids":[7,8],"period_id":1}

Response (200):
{
    "total_created": 1,
    "total_updated": 0,
    "total_skipped": 44,
    "total_errors": 0,
    "per_table": {
        "7": {"created": 1, "updated": 0, "skipped": 26, "errors": 0},
        "8": {"created": 0, "updated": 0, "skipped": 18, "errors": 0}
    }
} ✅
```

### 6. Verify calculations exist
```
GET /carbon-api/carbon/calculations/?period=1
→ count=48 ✅
```

### 7. Batch calculate — idempotency (second run)
```
POST /carbon-api/carbon/batch-calculate/ (same payload)

Response (200):
{
    "total_created": 0,      ← 0 new
    "total_updated": 0,
    "total_skipped": 45,     ← all skipped
    ...
} ✅
```

### Backend verification gate
```
$ ./.ai-toolkit/scripts/verify.sh backend
✓ django check
✓ no missing migrations
→ GATE PASSED ✅
```

### Existing tests — no regressions
```
emissions/tests/test_calculation_validation.py — 3/3 PASSED ✅
emissions/tests/test_owner_endpoints.py — 4/4 PASSED ✅
```

---

## Issues Found (Pre-existing)

1. **Migration conflict:** `catalog` app had two divergent `0004` migration branches that needed a merge migration.
2. **Migration bug:** `dq/migrations/0003_add_performance_indices.py` referenced field `executed_at` which doesn't exist on `DQResult` model — correct field is `run_at`. Fixed as blocker to proceed with verification gate.
3. **Test infrastructure:** `emissions/tests.py` (legacy flat file) conflicts with `emissions/tests/` (package directory), preventing `./manage.sh test emissions` from working. Individual test modules run fine via direct pytest path.
4. **Antipatterns:** Pre-existing `print()`, naive `datetime.now()`, and frontend antipatterns flagged by `verify.sh antipatterns` — none introduced by this task.

---

## Summary

The `POST /carbon-api/carbon/batch-calculate/` endpoint is operational:
- Accepts `table_ids` (list of int) and `period_id` (int)
- Runs all active calculation rules for each table
- Returns aggregate `total_created`, `total_updated`, `total_skipped`, `total_errors` plus per-table breakdown
- Idempotent on re-run (skips existing calculations)
- Thin view + service layer, no model changes, no migration needed
