# TASK-BE-02: Consolidated My Data API

## Context (from master)
Phase 02 — "My Data" is the Data Owner's workspace. Currently there are 3 separate owner APIs (`owner/summary/`, `owner/assets/`, `owner/activity/`) that the frontend calls individually. We need a single consolidated endpoint — same pattern as ConsoleAPIView from Phase 01 — that returns everything in one call.

## Before starting
- Read `plans/carbon-phase/SHARED-CONTEXT.md` completely
- Read `MASTER-WORKER-PROTOCOL.md` DO/DON'T sections
- Study the existing `ConsoleAPIView` (views.py line ~1093) — use the same pattern

## Scope — DO
1. Create **one** new `MyDataAPIView` in `backend/emissions/views.py`
2. Register it at `GET /api/v1/emissions/my-data/` in `urls.py`
3. Return consolidated response with ALL of: org_unit context, module summaries, stats, recent activity
4. Use Window functions for aggregates (same pattern as ConsoleAPIView)
5. RBAC-scope to user's visible org units via `get_visible_module_ids()`
6. Add `fetchMyData()` function to `carbon-frontend/src/api/emissions.js`
7. Add `emissionsMyData: "carbon/my-data/"` route to `carbon-frontend/src/config.js`

## Scope — DO NOT
- Do NOT modify the existing 4 owner APIs (OwnerDashboardAPIView, OwnerSummaryAPIView, etc.) — leave them untouched
- Do NOT touch models.py or serializers.py unless absolutely necessary
- Do NOT add new dependencies
- Do NOT touch any frontend pages

## API Contract

### GET /api/v1/emissions/my-data/

**Request**: None (RBAC inferred from JWT user)

**Response**:
```json
{
  "org_unit": {
    "id": 1,
    "name": "Factory A",
    "code": "FACT-A"
  },
  "stats": {
    "total_modules": 5,
    "modules_with_data": 3,
    "total_rows": 1420,
    "latest_submission": "2026-07-25T10:30:00Z",
    "data_quality": {
      "passing": 3,
      "warning": 1,
      "failing": 1
    }
  },
  "modules": [
    {
      "id": 1,
      "name": "Electricity Consumption",
      "scope": 2,
      "table_count": 1,
      "row_count": 350,
      "quality_status": "passing",
      "quality_score": 95.0,
      "last_entry": "2026-07-25T10:30:00Z"
    }
  ],
  "recent_activity": [
    {
      "module_name": "Electricity Consumption",
      "action": "data_entered",
      "timestamp": "2026-07-25T10:30:00Z",
      "rows": 12
    }
  ]
}
```

### Key implementation notes
- `stats.latest_submission` → `DataRow.objects.filter(data_table__module__org_unit__in=org_units).order_by('-created_at').first().created_at`
- `modules[].quality_status` → derived from AssetProfile quality if available, else "unknown"
- `modules[].quality_score` → passing% from AssetProfile
- `recent_activity` → last 10 DataRow creates, not calculations (data owners care about data entry, not calc results)
- Use `Window(Count('id'))` for total_counts followed by `.order_by('-calculated_at')[:10]` for activity (same as ConsoleAPIView pattern)

## Acceptance Criteria
- [ ] Single endpoint returns all 4 sections (org_unit, stats, modules, recent_activity)
- [ ] RBAC-scoped to user's org units
- [ ] Window functions used for aggregates
- [ ] `fetchMyData()` added to emissions.js
- [ ] Route added to config.js
- [ ] Test evidence: curl output showing full JSON response
- [ ] No modification to existing owner APIs
