# TASK-RESULTS-G4 — Calculation Audit Trail

## Summary
Implemented the Calculation Audit Trail (G4) for the Carbon Data Trust Platform. Every calculation trigger (single-rule and batch) now creates an immutable `CalculationAudit` record with who, what rule/table, which period, and what results. A read-only API endpoint exposes the trail with filtering.

## Deliverables

### ✅ D1 — CalculationAudit Model
Added `CalculationAudit` to `backend/emissions/models.py` with:
- `trigger_type`: `single | batch`
- `triggered_by`: FK to `accounts.User` (PROTECT)
- `calculation_rule`: FK to `CalculationRule` (SET_NULL, nullable for batch)
- `data_table`: FK to `DataTable` (SET_NULL, nullable)
- `reporting_period`: FK to `ReportingPeriod` (SET_NULL, nullable)
- `table_ids`: JSONField for batch table ID lists
- `recalculate`: BooleanField
- `created_count` / `skipped_count` / `error_count`: PositiveIntegerField
- `triggered_at`: auto_now_add DateTimeField
- Meta: ordering `-triggered_at`, indexed on `triggered_at`, `(triggered_by, triggered_at)`, and `reporting_period`

### ✅ D2 — CalculationAuditSerializer
Added to `backend/emissions/serializers.py`:
- Read-only fields: `triggered_by_name`, `rule_name`, `table_name`, `period_name` (resolved from FKs)
- `fields = '__all__'` with read-only `triggered_at`

### ✅ D3 — Hook into CalculateAPIView
Added audit record creation in `CalculateAPIView.post()` **after** `execute_rule` and **before** `return Response`. Records the single rule execution with all counts.

### ✅ D4 — Hook into BatchCalculateAPIView
Added audit record creation in `BatchCalculateAPIView.post()` **after** `batch_calculate` and **before** `return Response`. Records the batch run with aggregated counts and `table_ids`.

### ✅ D5 — CalculationAuditViewSet
Added `CalculationAuditViewSet` (ReadOnlyModelViewSet) with filters:
- `trigger_type` — filter by single/batch
- `period_id` — filter by reporting period
- `user_id` — filter by triggered_by user

### ✅ D6 — Router Registration
Registered `audit_router` in `backend/emissions/urls.py`:
- Route: `calculation-audits/` under the standard emissions prefix
- Pattern: `/api/v1/carbon/calculation-audits/`

### ✅ D7 — Migration
- Generated: `emissions/migrations/0007_calculationaudit.py`
- Applied successfully
- `makemigrations --check` → No changes detected

## Verification Gate Results

| Check | Status |
|-------|--------|
| Migration apply | ✅ `0007_calculationaudit... OK` |
| `makemigrations --check` | ✅ No changes detected |
| `python manage.py check` | ✅ Exit 0 (only pre-existing W005 warning) |
| `verify.sh backend` | ✅ GATE PASSED |
| GET calculation-audits (empty) | ✅ `[]` |
| Trigger single calculation | ✅ Returns `{"success":true,"total_created":0,...}` |
| GET calculation-audits (after trigger) | ✅ Returns audit record with all fields |
| Filter by `trigger_type=single` | ✅ Returns 1 record |
| Filter by `period_id=1` | ✅ Returns 1 record |
| Filter by `user_id=60` | ✅ Returns 1 record |

### Antipatterns Gate
`verify.sh antipatterns` → **GATE FAILED**. All violations are **pre-existing** (MUI v5 Grid syntax, raw fetch(), hardcoded hex colors, naive datetimes, 145 `print()` calls). None introduced by G4 changes.

## API Contract

```
GET /api/v1/carbon/calculation-audits/
  Query params: ?trigger_type=single|batch&period_id=N&user_id=N
  Response: [{
    "id": 1,
    "triggered_by_name": "admin",
    "rule_name": "Electricity → CO2e",
    "table_name": "monthly_electricity",
    "period_name": "FY 2026",
    "trigger_type": "single",
    "created_count": 0,
    "skipped_count": 27,
    "error_count": 0,
    "triggered_at": "2026-07-29T...",
    ...
  }]

POST /api/v1/carbon/calculate/  → creates audit record (D3)
POST /api/v1/carbon/batch-calculate/  → creates audit record (D4)
```

## Files Changed
| File | Action |
|------|--------|
| `backend/emissions/models.py` | Added `CalculationAudit` model |
| `backend/emissions/serializers.py` | Added `CalculationAuditSerializer` |
| `backend/emissions/views.py` | Added `CalculationAuditViewSet`, hooks in both CalculateAPIView and BatchCalculateAPIView |
| `backend/emissions/urls.py` | Registered `audit_router` with calculation-audits route |
| `backend/emissions/migrations/0007_calculationaudit.py` | New migration (auto-generated) |
