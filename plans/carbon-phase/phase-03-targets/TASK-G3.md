# TASK.md — APP-CARBON-G3: Batch Calculation API
# Phase I, Group 3 | Parallel-safe with G1, G2
# Worker: backend-worker | Model: DeepSeek (medium cost)

## Summary
Add a `POST /carbon-api/emissions/batch-calculate/` endpoint that runs calculation rules across multiple tables at once. Thin APIView + service method. No models changed, no migration.

## Files to Read First (BEFORE writing anything)
1. `.ai-toolkit/project.config.md`
2. `.ai-toolkit/shared/base-rules.md`
3. `.ai-toolkit/roles/backend-worker.md`
4. `.ai-toolkit/shared/api-contract.md`
5. `backend/emissions/models.py` — understand Calculation, CalculationRule relationships
6. `backend/emissions/views.py` — find existing `CalculateAPIView` for pattern reference
7. `backend/emissions/services.py` — find `CalculationEngineService.calculate_for_table()` method signature
8. `backend/emissions/urls.py` — see how existing emission routes are wired
9. `backend/emissions/management/commands/setup_carbon_app.py` — see how calculate_for_table is called

## Registry Check
Run `./.ai-toolkit/scripts/scan.sh`. Grep `registry/api.md` for "batch-calculate" — confirm it doesn't exist yet. Grep `registry/services.md` for "calculate_for_table" — confirm the existing method.

## Files to Edit
| File | Action | What |
|------|--------|------|
| `backend/emissions/services.py` | EDIT | Add `batch_calculate()` method to `CalculationEngineService` |
| `backend/emissions/views.py` | ADD | `BatchCalculateAPIView` class |
| `backend/emissions/urls.py` | EDIT | Add route (NOT config/urls.py — the emissions app urls.py) |

## DO NOT TOUCH
- Any frontend file
- `catalog/`, `mdm/`, `dq/`, `dataschema/`, `accounts/`, `core/`
- `backend/emissions/models.py` — no model changes
- `backend/emissions/serializers.py` — no serializer changes
- `backend/config/urls.py` — route goes in emissions/urls.py
- `backend/emissions/management/` commands

## Deliverable 1 — Service Method
Open `backend/emissions/services.py`. Find the `CalculationEngineService` class. Add this method inside it:

```python
@staticmethod
def batch_calculate(table_ids, period_id):
    """Run calculation rules across multiple tables.

    Args:
        table_ids: list of DataTable IDs
        period_id: ReportingPeriod ID

    Returns:
        dict: {total_created, total_updated, total_skipped, per_table: {table_id: {created, updated, skipped}}}
    """
    result = {
        'total_created': 0,
        'total_updated': 0,
        'total_skipped': 0,
        'per_table': {},
    }
    for table_id in table_ids:
        rules = CalculationRule.objects.filter(
            data_table_id=table_id, is_active=True
        )
        if not rules.exists():
            result['per_table'][table_id] = {'created': 0, 'updated': 0, 'skipped': 0, 'note': 'no active rules'}
            continue

        t = {'created': 0, 'updated': 0, 'skipped': 0}
        for rule in rules:
            r = CalculationEngineService.calculate_for_table(
                table_id, rule.id, period_id
            )
            # calculate_for_table returns {created: N, updated: N, skipped: N} or similar
            t['created'] += r.get('created', 0)
            t['updated'] += r.get('updated', 0)
            t['skipped'] += r.get('skipped', 0)

        result['per_table'][str(table_id)] = t
        result['total_created'] += t['created']
        result['total_updated'] += t['updated']
        result['total_skipped'] += t['skipped']

    return result
```

IMPORTANT: First, read the actual `calculate_for_table` method in services.py to confirm its exact return shape. Adjust the keys (`created`/`updated`/`skipped`) to match the real return dict. If the method doesn't exist yet, look at `setup_carbon_app.py` for how calculations are currently done and wrap that logic.

## Deliverable 2 — API View
Add to `backend/emissions/views.py`:

```python
class BatchCalculateAPIView(APIView):
    """Run calculations across multiple tables at once."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Batch calculate emissions for multiple tables",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['table_ids', 'period_id'],
            properties={
                'table_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="DataTable IDs to calculate",
                ),
                'period_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="ReportingPeriod ID",
                ),
            },
        ),
    )
    def post(self, request):
        table_ids = request.data.get('table_ids')
        period_id = request.data.get('period_id')

        if not table_ids or not isinstance(table_ids, list):
            return Response(
                {'detail': 'table_ids is required and must be a list of integers.'},
                status=400,
            )
        if not period_id:
            return Response(
                {'detail': 'period_id is required.'},
                status=400,
            )

        try:
            result = CalculationEngineService.batch_calculate(table_ids, period_id)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

        return Response(result, status=200)
```

Imports needed: `from .services import CalculationEngineService`, `from drf_yasg import openapi`, `from drf_yasg.utils import swagger_auto_schema` (check if already imported).

## Deliverable 3 — Route
Edit `backend/emissions/urls.py`. Add:
```python
path('batch-calculate/', BatchCalculateAPIView.as_view(), name='batch-calculate'),
```

Add it inside the existing `urlpatterns` list, before any existing catch-all router includes. Import `BatchCalculateAPIView` from `.views`.

## Verification Gate

```bash
# 1. No migration needed — verify
./manage.sh manage makemigrations --check
# Must: "No changes detected"

# 2. Import + syntax check
./manage.sh manage check
# Must exit 0

# 3. Restart
./manage.sh restart backend

# 4. Get token
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# 5. Batch calculate for tables 7+8 (monthly_electricity + monthly_water) with period 1
curl -s -X POST http://localhost:8009/carbon-api/emissions/batch-calculate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_ids":[7,8],"period_id":1}' | python3 -m json.tool
# Expect 200 with: {total_created, total_updated, total_skipped, per_table: {"7":{...}, "8":{...}}}

# 6. Verify calculations exist
curl -s "http://localhost:8009/carbon-api/emissions/calculations/?period=1" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={d[\"count\"]}')"
# Expect: count > 0

# 7. Recalculate (should create 0 new, skip all existing)
curl -s -X POST http://localhost:8009/carbon-api/emissions/batch-calculate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"table_ids":[7,8],"period_id":1}' | python3 -m json.tool
# Expect: total_created=0, total_skipped > 0 (idempotent)
```

## Handoff
Write `plans/carbon-phase/phase-03-targets/TASK-RESULTS-G3.md`.
