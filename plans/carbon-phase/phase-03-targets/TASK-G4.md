# TASK.md — APP-CARBON-G4: Calculation Audit Trail
# Phase I, Group 4 | Blocks G5 (tests cover this)
# Worker: backend-worker | Model: DeepSeek (medium cost)

## Summary
Every calculation trigger (single + batch) must create an audit record: who ran what rule, on which table, for which period, with what results. New model `CalculationAudit`, hook into existing `CalculateAPIView` and `BatchCalculateAPIView`, add read-only list endpoint.

## Files to Read First (BEFORE writing anything)
1. `.ai-toolkit/project.config.md`
2. `.ai-toolkit/shared/base-rules.md`
3. `.ai-toolkit/roles/backend-worker.md`
4. `.ai-toolkit/shared/api-contract.md`
5. `.ai-toolkit/shared/data-layer.md`
6. `backend/emissions/models.py` — read `Calculation` (line 316), `CalculationRule` (line 505), `calculate_for_table` (line 713)
7. `backend/emissions/views.py` — read `CalculateAPIView` (line 404) and `BatchCalculateAPIView` (line 456)
8. `backend/emissions/services.py` — read `CalculationEngineService` (line 330)
9. `backend/emissions/serializers.py`
10. `backend/emissions/urls.py`

## Registry Check
Run `./.ai-toolkit/scripts/scan.sh`. Grep registry for "CalculationAudit" — confirm it doesn't exist.

## Files to Edit
| File | Action | What |
|------|--------|------|
| `backend/emissions/models.py` | ADD | `CalculationAudit` model |
| `backend/emissions/serializers.py` | ADD | `CalculationAuditSerializer` |
| `backend/emissions/views.py` | EDIT | `CalculateAPIView` — create audit record on success |
| `backend/emissions/views.py` | EDIT | `BatchCalculateAPIView` — create audit record on success |
| `backend/emissions/views.py` | ADD | `CalculationAuditViewSet` (ReadOnly) |
| `backend/emissions/urls.py` | EDIT | Register audit router |

## DO NOT TOUCH
- Any frontend file
- `catalog/`, `mdm/`, `dq/`, `dataschema/`, `accounts/`, `core/`
- `backend/emissions/services.py` — NO changes to services
- `backend/config/urls.py` — route goes in `emissions/urls.py`
- `backend/emissions/models.py` — DO NOT modify existing models, only ADD CalculationAudit

## Deliverable 1 — CalculationAudit Model
Add to `backend/emissions/models.py`:

```python
class CalculationAudit(models.Model):
    """Immutable audit trail for every calculation trigger event."""
    TRIGGER_TYPE_CHOICES = [
        ('single', 'Single Rule'),
        ('batch', 'Batch'),
    ]

    trigger_type = models.CharField(max_length=10, choices=TRIGGER_TYPE_CHOICES)
    triggered_by = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT,
        help_text="User who triggered this calculation run"
    )
    calculation_rule = models.ForeignKey(
        CalculationRule, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Rule executed (null for batch)"
    )
    data_table = models.ForeignKey(
        'dataschema.DataTable', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="DataTable targeted"
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Reporting period for this run"
    )
    table_ids = models.JSONField(
        null=True, blank=True,
        help_text="List of table IDs for batch runs"
    )
    recalculate = models.BooleanField(default=False)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    triggered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['-triggered_at']),
            models.Index(fields=['triggered_by', '-triggered_at']),
            models.Index(fields=['reporting_period']),
        ]

    def __str__(self):
        return f"Audit #{self.id} — {self.get_trigger_type_display()} by {self.triggered_by} ({self.created_count}c/{self.skipped_count}s/{self.error_count}e)"
```

## Deliverable 2 — Serializer
Add to `backend/emissions/serializers.py`:

```python
class CalculationAuditSerializer(serializers.ModelSerializer):
    triggered_by_name = serializers.CharField(source='triggered_by.username', read_only=True)
    rule_name = serializers.CharField(source='calculation_rule.name', read_only=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    period_name = serializers.CharField(source='reporting_period.name', read_only=True)

    class Meta:
        model = CalculationAudit
        fields = '__all__'
        read_only_fields = ['triggered_at', 'triggered_by_name', 'rule_name', 'table_name', 'period_name']
```

## Deliverable 3 — Hook into CalculateAPIView
In `backend/emissions/views.py`, in `CalculateAPIView.post()`, AFTER the `execute_rule` call and BEFORE the `return Response`, add:

```python
        CalculationAudit.objects.create(
            trigger_type='single',
            triggered_by=request.user,
            calculation_rule=rule,
            data_table=rule.data_table,
            reporting_period=period,
            recalculate=recalculate,
            created_count=created,
            skipped_count=skipped,
            error_count=err_count,
        )
```

Import `CalculationAudit` at the top of views.py.

## Deliverable 4 — Hook into BatchCalculateAPIView
In `backend/emissions/views.py`, in `BatchCalculateAPIView.post()`, AFTER the `batch_calculate` call and BEFORE the `return Response`, add:

```python
        CalculationAudit.objects.create(
            trigger_type='batch',
            triggered_by=request.user,
            reporting_period_id=period_id,
            table_ids=table_ids,
            created_count=result.get('total_created', 0),
            skipped_count=result.get('total_skipped', 0),
            error_count=result.get('total_errors', 0),
        )
```

## Deliverable 5 — Read-Only ViewSet
Add to `backend/emissions/views.py`:

```python
class CalculationAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail for calculation triggers."""
    serializer_class = CalculationAuditSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CalculationAudit.objects.select_related(
            'triggered_by', 'calculation_rule', 'data_table', 'reporting_period'
        )
        trigger_type = self.request.query_params.get('trigger_type')
        if trigger_type:
            qs = qs.filter(trigger_type=trigger_type)
        period_id = self.request.query_params.get('period_id')
        if period_id:
            qs = qs.filter(reporting_period_id=period_id)
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(triggered_by_id=user_id)
        return qs
```

## Deliverable 6 — Router
In `backend/emissions/urls.py`, add a third router (same pattern as `verification_router`):

```python
audit_router = DefaultRouter()
audit_router.register(r'calculation-audits', CalculationAuditViewSet, basename='calculation-audit')
```

Add `path('', include(audit_router.urls)),` to urlpatterns.

Import `CalculationAuditViewSet` in urls.py.

## Migration
```bash
cd backend && source ../.venv/bin/activate && python manage.py makemigrations emissions
```
One migration: `0007_calculationaudit.py` (or next number).

## Verification Gate

```bash
# 1. Migration
./manage.sh migrate
./manage.sh manage makemigrations --check  # actually: python manage.py makemigrations --check
# Must: "No changes detected"

# 2. Import check
python manage.py check
# Must exit 0

# 3. Restart
./manage.sh restart

# 4. Get token
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# 5. Trigger a single calculation (creates an audit record)
curl -s -X POST http://localhost:8009/carbon-api/emissions/calculate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rule_id":1,"reporting_period_id":1}' | python3 -m json.tool

# 6. Trigger a batch calculation (creates an audit record)
curl -s -X POST http://localhost:8009/carbon-api/emissions/batch-calculate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_ids":[7,8],"period_id":1}' | python3 -m json.tool

# 7. List audit records
curl -s "http://localhost:8009/carbon-api/emissions/calculation-audits/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: list with at least 2 records (one single, one batch)

# 8. Filter by trigger_type
curl -s "http://localhost:8009/carbon-api/emissions/calculation-audits/?trigger_type=batch" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'batch audits: {len(d)}')"

# 9. Filter by period
curl -s "http://localhost:8009/carbon-api/emissions/calculation-audits/?period_id=1" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'period 1 audits: {len(d)}')"
```

## Handoff
Write `plans/carbon-phase/phase-03-targets/TASK-RESULTS-G4.md`.
