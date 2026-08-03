# TASK-G1 — Phase 04 Backend: Calculations & Verification API Enrichment

## Summary
Enrich existing Calculation + Verification endpoints with traceability data needed for Phase 04 UI (calculation browser with factor provenance, verification dashboard). No new models, no new viewsets — only serializer enrichment + one computed summary endpoint.

---

## Deliverables

### D1 — Enriched CalculationSerializer (serializers.py)

Current `CalculationSerializer` uses `fields = '__all__'`. Enhance with read-only resolved FK names for traceability:

Add to `CalculationSerializer.Meta`:
- `fields` become explicit (keep all current)
- Add read-only fields:
  - `module_name` = `module.name` (StringRelatedField or SerializerMethodField)
  - `factor_name` = `emission_factor.name`
  - `factor_code` = `emission_factor.code`
  - `data_row_label` = `data_row` → format as `"Row #id"` or first field value (SerializerMethodField)
  - `data_table_id` = source data_table via emission_factor → rule → data_table (use `__` traversal or annotate in ViewSet)
  - `data_table_name` = resolved from data_table if reachable

### D2 — Enriched CalculationViewSet.list() (views.py)

Current `list()` returns only `['id', 'module_id', 'reporting_year', 'scope', 'co2e_kg']`.

**Enhance** to return richer results with traceability:
```python
.values('id', 'module_id', 'module__name', 'reporting_year', 'reporting_period_id',
        'scope', 'co2e_kg', 'category', 'emission_factor__name', 'emission_factor__code',
        'emission_factor_id', 'calculated_at', 'activity_date',
        'data_row_id')
```

Add optional query param `?detail=true` that returns full serialized objects (for drill-down).

### D3 — New endpoint: Calculation Summary (views.py)

Add `CalculationSummaryAPIView` with GET at `/emissions/calculations/summary/`:

**Query params**: `?reporting_period_id=N` (filter by period)

**Response**:
```json
{
  "period_id": 1,
  "total_calculations": 44,
  "by_scope": {"1": 0, "2": 34, "3": 10},
  "by_status": {"draft": 0, "submitted": 0, "verified": 44},
  "by_module": [{"module_id": 5, "module_name": "Monthly Electricity", "count": 34, "total_tco2e": 2663.6}],
  "latest_run_at": "2026-07-29T...",
  "last_audit": {"trigger_type": "single", "triggered_by_name": "ahmed", "triggered_at": "..."}
}
```

Implementation: aggregate from `Calculation.objects.filter(...)` with annotated groupings by scope, module, period status.

### D4 — Enriched VerificationRecordSerializer (serializers.py)

Add read-only resolved names:
- `period_name` = `reporting_period.name`
- `period_status` = `reporting_period.status`
- `period_start_date` = `reporting_period.start_date`
- `period_end_date` = `reporting_period.end_date`
- `verifier_name` = `verifier.username` (already present? verify)

Also add `?period_id=N` filter support in `VerificationRecordViewSet.get_queryset()` if not already present.

### D5 — Enriched CalculationRuleSerializer (serializers.py)

Add read-only:
- `data_table_name` = `data_table.name`
- `activity_field_name` = `activity_field.name`
- `factor_name` = `emission_factor.name`
- `last_executed_at` = from latest CalculationAudit for this rule (SerializerMethodField)

### D6 — URL Registration (urls.py)

Add one new path:
```python
path('calculations/summary/', CalculationSummaryAPIView.as_view(), name='calculation-summary'),
```
Place BEFORE the router include so it resolves correctly.

---

## Files to Change

| File | Action |
|------|--------|
| `backend/emissions/serializers.py` | D1: Enrich CalculationSerializer + D4: VerificationRecordSerializer + D5: CalculationRuleSerializer |
| `backend/emissions/views.py` | D2: Enhance CalculationViewSet.list() + D3: Add CalculationSummaryAPIView |
| `backend/emissions/urls.py` | D6: Add calculations/summary/ path |

---

## DO-NOT-TOUCH

- ❌ No new models (no migrations)
- ❌ No changes to services.py
- ❌ No changes to CalculateAPIView / BatchCalculateAPIView
- ❌ No changes to DashboardAPIView, ReportAPIView, or any other view
- ❌ Frontend files
- ❌ config/urls.py — only emissions/urls.py

---

## Verification

```bash
# 1. Django checks
cd backend && python manage.py check

# 2. No unexpected migrations
python manage.py makemigrations --check

# 3. Gateway
cd .. && bash .ai-toolkit/scripts/verify.sh backend

# 4. All tests pass
cd backend && python -m pytest emissions/tests/ -v

# 5. Manual HTTP spot-checks (restart backend first):
./manage.sh restart backend

# Token
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# D2: Enriched calculation list
curl -s http://localhost:8009/carbon-api/emissions/calculations/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -30

# D3: Calculation summary
curl -s http://localhost:8009/carbon-api/emissions/calculations/summary/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# D4: Verification records with period info
curl -s http://localhost:8009/carbon-api/emissions/verifications/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# D5: Calculation rules with table/factor names
curl -s http://localhost:8009/carbon-api/emissions/rules/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20
```

## Success Criteria

- [ ] `python manage.py check` — exit 0
- [ ] `makemigrations --check` — No changes detected
- [ ] `verify.sh backend` — GATE PASSED
- [ ] All 50 emissions tests pass
- [ ] `GET /calculations/?reporting_period_id=1` returns enriched data with `module__name`, `emission_factor__name`
- [ ] `GET /calculations/summary/` returns aggregated summary (by_scope, by_module, latest_run_at)
- [ ] `GET /verifications/` returns period_name + period_status
- [ ] `GET /rules/` returns data_table_name, factor_name
- [ ] No files outside the 3 listed files changed
