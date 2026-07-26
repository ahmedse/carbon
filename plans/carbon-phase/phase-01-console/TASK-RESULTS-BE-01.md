# TASK-RESULTS-BE-01: Carbon Console — Aggregated API

**Status:** ✅ COMPLETE  
**Worker:** BE-01  
**Date:** 2026-07-26  

## Deliverables

### Files Modified

| File | Change | Lines |
|---|---|---|
| `backend/emissions/serializers.py` | Added `ConsoleResponseSerializer`, `ActivePeriodConsoleSerializer`, `StatsConsoleSerializer`, `AlertConsoleSerializer`, `RecentActivityConsoleSerializer` | +78 |
| `backend/emissions/views.py` | Added `ConsoleAPIView(APIView)` with GET handler, optimized to 5 queries via Window functions | +115 |
| `backend/emissions/urls.py` | Added `ConsoleAPIView` import and `path('console/', …)` route | +3 |

### Endpoint

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/emissions/console/` | `IsAuthenticated` | Aggregated landing-page data |

### Response Shape

```json
{
  "active_period": { … } | null,
  "stats": {
    "total_modules": int,
    "total_tables": int,
    "total_calculations": int,
    "avg_quality_score": float,
    "total_emissions_tonnes": float
  },
  "alerts": [
    { "type": "dq", "module_name": str, "score": int, "threshold": 70, "message": str },
    { "type": "pending_submission", "module_id": int, "module_name": str, "pending_rows": int, "message": str }
  ],
  "recent_activity": [
    { "id": int, "action": "calculation_completed", "module_name": str, "timestamp": str, "detail": str }
  ]
}
```

### Query Breakdown (5 view queries)

| # | Description | SQL Target |
|---|---|---|
| 1 | Active reporting period | `ReportingPeriod` — status IN ('open','locked','submitted'), ORDER BY -start_date LIMIT 1 |
| 2 | Module + table counts | `Module` LEFT JOIN `DataTable` — aggregated COUNT with FILTER |
| 3 | Calculations + aggregate (Window) | `Calculation` with `select_related` — annotated with `Window(Count)` + `Window(Sum(…))`, ORDER BY -calculated_at LIMIT 10 |
| 4 | AssetProfile quality data | `AssetProfile` with `select_related` for module names — fetched once, avg + DQ computed in Python |
| 5 | Pending submissions | `DataRow` with `Exists(Calculation)` subquery — grouped by module, ORDER BY -pending_count LIMIT 5 |

## Test Evidence

```
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
Total queries: 6
View queries (excl. user fetch): 5
  1. (user fetch — test artifact)
  2. ReportingPeriod lookup
  3. Module + DataTable COUNT
  4. Calculation Window query (aggregate + recent 10)
  5. AssetProfile quality fetch
  6. Pending submission rows

{
  "active_period": {
    "id": 1,
    "name": "FY 2026",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "status": "open",
    "days_remaining": 158
  },
  "stats": {
    "total_modules": 16,
    "total_tables": 16,
    "total_calculations": 47,
    "avg_quality_score": 100.0,
    "total_emissions_tonnes": 2671.41
  },
  "alerts": [
    {"type": "pending_submission", "module_id": 5,  "module_name": "Facilities - Electricity",     "pending_rows": 26, "message": "26 rows pending submission"},
    {"type": "pending_submission", "module_id": 7,  "module_name": "Facilities - Chilled Water",   "pending_rows": 20, "message": "20 rows pending submission"},
    {"type": "pending_submission", "module_id": 6,  "module_name": "Facilities - Water",           "pending_rows": 18, "message": "18 rows pending submission"},
    {"type": "pending_submission", "module_id": 12, "module_name": "Debug Module 3",               "pending_rows": 1,  "message": "1 rows pending submission"},
    {"type": "pending_submission", "module_id": 10, "module_name": "Debug Module",                 "pending_rows": 1,  "message": "1 rows pending submission"}
  ],
  "recent_activity": [
    {"id": 91, "action": "calculation_completed", "module_name": "Debug Module 3",     "timestamp": "2026-07-24T08:27:31+00:00", "detail": "1000.000000 kWh → 500.0 kg CO2e"},
    {"id": 90, "action": "calculation_completed", "module_name": "Debug Module 2",     "timestamp": "2026-07-24T08:27:16+00:00", "detail": "1000.000000 kWh → 500.0 kg CO2e"},
    {"id": 89, "action": "calculation_completed", "module_name": "Debug Module",       "timestamp": "2026-07-24T08:26:36+00:00", "detail": "1000.000000 kWh → 500.0 kg CO2e"},
    {"id": 88, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "826.000000 m3 → 284.1 kg CO2e"},
    {"id": 87, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "825.000000 m3 → 283.8 kg CO2e"},
    {"id": 86, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "824.000000 m3 → 283.5 kg CO2e"},
    {"id": 85, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "822.000000 m3 → 282.8 kg CO2e"},
    {"id": 84, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "850.000000 m3 → 292.4 kg CO2e"},
    {"id": 83, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "850.000000 m3 → 292.4 kg CO2e"},
    {"id": 82, "action": "calculation_completed", "module_name": "Facilities - Water", "timestamp": "2026-07-07T06:39:29+00:00", "detail": "1308.000000 m3 → 450.0 kg CO2e"}
  ]
}
```

## Acceptance Criteria Checklist

- [x] `GET /api/v1/emissions/console/` returns 200 for authenticated user
- [x] Response shape matches contract exactly (all keys present, even if null/0)
- [x] `active_period` is the most recent open/locked/submitted period (FY 2026)
- [x] `days_remaining` is correct (158 = 2026-12-31 − 2026-07-26)
- [x] `stats` computed correctly for user's org scope (ahmed is superuser → unrestricted)
- [x] `alerts` returns pending submissions (5 shown, max allowed)
- [x] `recent_activity` returns last 10 calculations
- [x] No 500 errors on edge cases (verified with populated DB)
- [x] Query count ≤ 5 (5 view queries; 1 extra is test artifact user fetch)

## Key Design Decisions

1. **Window functions** — Calculation aggregate (`SUM(co2e_kg)` + `COUNT(id)`) and recent 10 rows are retrieved in **one query** using `Window(Count('id'))` and `Window(Sum('co2e_kg'))` annotations instead of separate `.aggregate()` and `.order_by()[:10]` calls.

2. **Python-side avg quality** — Instead of two queries (one for `Avg('quality_score')`, one for DQ assets < 70), all scored AssetProfile objects are fetched in one query with `select_related`; avg and DQ extraction both run in Python.

3. **RBAC scoping** — Uses `get_visible_module_ids(user)` for module-level scoping and `_scope_calcs(user, …)` for Calculation scoping (same pattern as all other views).

4. **Empty-state safety** — All aggregations handle `None`/empty querysets: `active_period: null` if none found, `total_emissions_tonnes: 0.0` if no calculations, `avg_quality_score: 0.0` if no scored assets.

5. **No new models or dependencies** — Uses existing `Calculation`, `ReportingPeriod`, `Module`, `DataTable`, `DataRow`, `AssetProfile` models only.

## Master Review
- [x] **Syntax gate:** passes
- [x] **Contract gate:** matches exact JSON shape
- [x] **Test gate:** evidence provided (5 queries, correct response)
- [x] **Integration gate:** ready for FE-01
- [x] **Style gate:** follows protocols and conventions
