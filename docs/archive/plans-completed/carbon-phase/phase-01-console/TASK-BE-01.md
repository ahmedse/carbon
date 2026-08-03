# TASK-BE-01: Carbon Console — Aggregated API

## Context (from master)

Phase 01 of Carbon rebuild. The Console is the landing page that answers "What needs my attention?" Currently the frontend makes two separate API calls (`fetchActiveReportingPeriod` + `fetchOwnerSummary`). We need a single aggregated endpoint that returns everything the console needs in one request.

This task is **backend only**. You create the API; the frontend worker (FE-01) will consume it.

## Prerequisites

**Read before starting:**
1. `/home/ahmed/aast/carbon/plans/carbon-phase/SHARED-CONTEXT.md` — models, patterns, conventions
2. `/home/ahmed/aast/carbon/plans/carbon-phase/PROTOCOL.md` — do's and don'ts
3. `/home/ahmed/aast/carbon/backend/emissions/views.py` — existing views (read first 200 lines)
4. `/home/ahmed/aast/carbon/backend/emissions/urls.py` — existing routes
5. `/home/ahmed/aast/carbon/backend/emissions/serializers.py` — existing serializers

## Scope — DO

1. **Create `ConsoleAPIView`** in `backend/emissions/views.py`
   - Class-based view extending `APIView`
   - Permission: `IsAuthenticated`
   - GET handler that returns aggregated console data

2. **Add URL route** in `backend/emissions/urls.py`
   - `path('console/', ConsoleAPIView.as_view(), name='console')`

3. **Return this exact shape**:
```json
{
  "active_period": {
    "id": 1,
    "name": "FY 2026",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "status": "open",
    "days_remaining": 159
  },
  "stats": {
    "total_modules": 5,
    "total_tables": 12,
    "total_calculations": 44,
    "avg_quality_score": 87.5,
    "total_emissions_tonnes": 2669.9
  },
  "alerts": [
    {
      "type": "dq",
      "module_name": "Electricity S2",
      "score": 45,
      "threshold": 70,
      "message": "Data quality below 70% threshold"
    },
    {
      "type": "pending_submission",
      "module_name": "Water S3",
      "module_id": 3,
      "pending_rows": 12,
      "message": "12 rows pending submission"
    }
  ],
  "recent_activity": [
    {
      "id": 44,
      "action": "calculation_completed",
      "module_name": "Electricity S2",
      "timestamp": "2026-07-25T10:30:00Z",
      "detail": "12 rows calculated — 245.3 kg CO2e"
    }
  ]
}
```

4. **Query logic** (by section):
   - **active_period**: Get the first `ReportingPeriod` where `status IN ('open', 'locked', 'submitted')`, ordered by `-start_date`. Compute `days_remaining = (end_date - today).days`. If none, return `null`.
   - **stats.total_modules**: Count of `Module` objects visible to user (scope by `get_visible_org_unit_ids()` from core — check if such helper exists, otherwise count all non-archived modules).
   - **stats.total_tables**: Count of `DataTable` objects where `module__in=visible_modules`, `is_archived=False`.
   - **stats.total_calculations**: Count of `Calculation` objects scoped to user's org_units. Use existing `_scope_calcs()` pattern if it exists in views.py.
   - **stats.avg_quality_score**: `AssetProfile.objects.filter(...).aggregate(Avg('quality_score'))` across modules visible to user. Return 0 if none.
   - **stats.total_emissions_tonnes**: `Sum('co2e_kg')` from scoped calculations, divided by 1000. Return 0 if none.
   - **alerts.dq**: Query `AssetProfile` where `quality_score < 70` AND `quality_score IS NOT NULL`, joined to modules visible to user. Limit 5. Include `module_name` via `content_object.module.name`.
   - **alerts.pending_submission**: Find `DataRow` objects in visible modules that were recently created/updated but have no associated `Calculation`. This is a heuristic — count rows per module where `calculation__isnull=True`. Limit 5.
   - **recent_activity**: Last 10 `Calculation` objects scoped to user, ordered by `-calculated_at`. Map to action/detail format.

5. **Handle empty states**: If no active period, `active_period: null`. If no calculations, `total_emissions_tonnes: 0`. Always return the exact shape.

6. **Add serializer validation** — create a `ConsoleResponseSerializer(serializers.Serializer)` that defines the output shape (for DRF Browsable API documentation).

## Scope — DO NOT

- DON'T change existing API endpoints or their signatures
- DON'T modify existing models
- DON'T create new models
- DON'T add new dependencies to requirements.txt
- DON'T touch frontend code
- DON'T scope by tenant (tenant is removed)
- DON'T return more than 10 recent activities or 5 alerts
- DON'T make more than 5 database queries total (use `select_related`/`prefetch_related`)

## API Contract

| Method | Endpoint | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/emissions/console/` | IsAuthenticated | See shape above |

## Files to modify

1. `backend/emissions/views.py` — add `ConsoleAPIView`
2. `backend/emissions/urls.py` — add console route
3. `backend/emissions/serializers.py` — add `ConsoleResponseSerializer` (optional, for docs)

## Acceptance Criteria

- [ ] `GET /api/v1/emissions/console/` returns 200 for authenticated user
- [ ] Response shape matches contract exactly (all keys present, even if null/0)
- [ ] `active_period` is the most recent open/locked/submitted period
- [ ] `days_remaining` is correct (positive integer)
- [ ] `stats` computed correctly for the user's org scope
- [ ] `alerts` returns DQ issues and pending submissions
- [ ] `recent_activity` returns last 10 calculations
- [ ] No 500 errors on edge cases (no periods, no calculations, empty org)
- [ ] Query count ≤ 5 (add `print(len(connection.queries))` for evidence)

## Test Evidence Required

Run and paste output:
```bash
cd /home/ahmed/aast/carbon/backend
python -c "
import django; import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.test import RequestFactory
from emissions.views import ConsoleAPIView
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(username='ahmed')
factory = RequestFactory()
request = factory.get('/api/v1/emissions/console/')
request.user = user
view = ConsoleAPIView.as_view()
response = view(request)
import json
print(json.dumps(response.data, indent=2, default=str))
"
```

## Deliverables

Paste results into: `/home/ahmed/aast/carbon/plans/carbon-phase/phase-01-console/TASK-RESULTS-BE-01.md`
