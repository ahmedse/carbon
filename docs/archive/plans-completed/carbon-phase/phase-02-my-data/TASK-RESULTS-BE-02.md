# TASK-RESULTS-BE-02: Consolidated My Data API

## Status
- [x] COMPLETE — built & tested by Master

## Summary
Created `MyDataAPIView` — a single consolidated endpoint that returns org unit context, stats, module summaries, and recent activity in one response. Same Window-function pattern as ConsoleAPIView from Phase 01.

## Files Changed
| File | Action | Lines Added |
|---|---|---|
| `backend/emissions/views.py` | ADDED `MyDataAPIView` class (before ConsoleAPIView) | ~120 |
| `backend/emissions/urls.py` | ADDED import + `path('my-data/', ...)` route | 2 |
| `carbon-frontend/src/api/emissions.js` | ADDED `fetchMyData()` function | 6 |
| `carbon-frontend/src/config.js` | ADDED `emissionsMyData` route | 1 |

## API Contract Verified

### GET /api/v1/emissions/my-data/ (via /carbon-api/carbon/my-data/)

```json
{
  "org_unit": { "id": 1, "name": "AAST", "code": "AAST" },
  "stats": {
    "total_modules": 10,
    "modules_with_data": 9,
    "total_rows": 71,
    "latest_submission": "2026-07-25T08:29:06.111307+00:00",
    "data_quality": { "passing": 11, "warning": 0, "failing": 0, "unknown": 14, "total_assets": 25 }
  },
  "modules": [
    { "id": 25, "name": "AASTMT Scope 1 Emissions", "scope": 1, "table_count": 2, "row_count": 1, "quality_status": "unknown", "quality_score": null, "last_entry": "..." }
  ],
  "recent_activity": [
    { "module_name": "AASTMT Scope 3 Emissions", "action": "data_entered", "timestamp": "...", "rows": 1, "user": "ahmed" }
  ]
}
```

## Test Evidence
```
$ TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ -H 'Content-Type: application/json' -d '{"username":"ahmed","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access'])")

$ curl -s http://localhost:8009/carbon-api/carbon/my-data/ -H "Authorization: Bearer $TOKEN" | python -m json.tool

HTTP 200 — full JSON response with all 4 sections.
```

## Issues / Decisions
1. **Existing owner APIs left untouched**: `OwnerSummaryAPIView`, `OwnerAssetsAPIView`, etc. remain active. MyDataAPIView is additive.
2. **Quality per module**: Uses AssetProfile quality_status aggregation (worst-of logic: failing beats warning beats passing beats unknown).
3. **Recent activity**: Uses DataRow.created_at (data entry timestamps), not Calculation.calculated_at. Data owners care about data entry, not calculation results.
4. **403 for users without org units**: Returns clear error instead of crashing.
5. **Syntax verified**: `py_compile` passes.

## Checklist
- [x] Single endpoint returns all 4 sections
- [x] RBAC-scoped to user's org units (via get_visible_org_units)
- [x] Aggregate queries used (Count, Max)
- [x] fetchMyData() added to emissions.js
- [x] Route added to config.js
- [x] Test evidence: curl output showing full JSON
- [x] No modification to existing owner APIs
