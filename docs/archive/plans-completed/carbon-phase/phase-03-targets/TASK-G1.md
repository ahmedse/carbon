# TASK.md — APP-CARBON-G1: SBTi Target Model + API
# Phase I, Group 1 | Parallel-safe with G2, G3
# Worker: backend-worker | Model: DeepSeek (medium cost)

## Summary
Add an SBTi-compatible target model so org units can set emission reduction goals. Model + serializer + ViewSet + service. One migration.

## Files to Read First (BEFORE writing anything)
1. `.ai-toolkit/project.config.md`
2. `.ai-toolkit/shared/base-rules.md`
3. `.ai-toolkit/roles/backend-worker.md`
4. `.ai-toolkit/shared/data-layer.md`
5. `.ai-toolkit/shared/api-contract.md`
6. `backend/emissions/models.py`
7. `backend/emissions/views.py`
8. `backend/emissions/services.py`
9. `backend/emissions/serializers.py`
10. `backend/config/urls.py`

## Registry Check
Before creating anything: run `./.ai-toolkit/scripts/scan.sh`, then grep `registry/models.md` for "target" — confirm no existing SBTiTarget model.

## Files to Edit
| File | Action | What |
|------|--------|------|
| `backend/emissions/models.py` | ADD | `SBTiTarget` model class (appended before last line) |
| `backend/emissions/serializers.py` | ADD | `SBTiTargetSerializer` |
| `backend/emissions/views.py` | ADD | `SBTiTargetViewSet` class + import |
| `backend/emissions/services.py` | ADD | `TargetService` class |
| `backend/config/urls.py` | EDIT | Register targets router |

## DO NOT TOUCH
- **Any frontend file** (`carbon-frontend/`)
- `catalog/`, `mdm/`, `dq/`, `dataschema/`, `accounts/` apps
- `core/` — except you don't touch core here either
- `backend/emissions/management/` commands

## Deliverable 1 — SBTiTarget Model
Add to `backend/emissions/models.py` (at end, before the file ends):

```python
class SBTiTarget(models.Model):
    """Science-Based Target initiative target — emission reduction goal per org unit."""
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.CASCADE, related_name='sbti_targets'
    )
    name = models.CharField(max_length=200)
    base_year = models.IntegerField()
    target_year = models.IntegerField()
    target_type = models.CharField(
        max_length=20,
        choices=[('absolute', 'Absolute Reduction'), ('intensity', 'Intensity Reduction')]
    )
    scope = models.CharField(
        max_length=20,
        choices=[
            ('1', 'Scope 1'),
            ('2', 'Scope 2'),
            ('3', 'Scope 3'),
            ('1+2', 'Scope 1+2'),
            ('1+2+3', 'Scope 1+2+3'),
        ]
    )
    reduction_pct = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('committed', 'Committed'),
            ('approved', 'Approved'),
        ],
        default='draft',
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-base_year']

    def __str__(self):
        return f"{self.name} ({self.base_year}→{self.target_year}, -{self.reduction_pct}%)"
```

## Deliverable 2 — Serializer
Add to `backend/emissions/serializers.py`:

```python
class SBTiTargetSerializer(serializers.ModelSerializer):
    org_unit_name = serializers.CharField(source='org_unit.name', read_only=True)

    class Meta:
        model = SBTiTarget
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'org_unit_name']
```

Import at top: `from .models import SBTiTarget` (add `SBTiTarget` to existing import line).

## Deliverable 3 — ViewSet + Route
Add to `backend/emissions/views.py`:

```python
class SBTiTargetViewSet(viewsets.ModelViewSet):
    """CRUD for SBTi targets — org-scoped visibility."""
    serializer_class = SBTiTargetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from accounts.rbac_utils import get_visible_org_units
        allowed = get_visible_org_units(self.request.user)
        if allowed is None:
            return SBTiTarget.objects.all()
        return SBTiTarget.objects.filter(org_unit_id__in=allowed)
```

Import at top: `from .models import SBTiTarget` (add to existing import line).

Register in `backend/config/urls.py` — add a router for targets alongside the existing emissions routers. Pattern to follow (find the existing emissions router registration and add next to it):

```python
targets_router = DefaultRouter()
targets_router.register(r'targets', SBTiTargetViewSet, basename='targets')
```

Then add to emissions urlpatterns:
```python
path('', include(targets_router.urls)),
```

Import `SBTiTargetViewSet` from emissions.views.

## Deliverable 4 — Service
Add to `backend/emissions/services.py`:

```python
class TargetService:
    """Progress tracking for SBTi targets."""

    @staticmethod
    def get_progress(target_id, year):
        from .models import SBTiTarget, Calculation
        from decimal import Decimal

        target = SBTiTarget.objects.get(pk=target_id)
        scopes = target.scope.replace('+', ',').split(',')

        actual = Calculation.objects.filter(
            module__org_unit_id=target.org_unit_id,
            period__year=year,
            scope__in=scopes,
        ).aggregate(total=Sum('total_co2e'))['total'] or Decimal('0')

        # Progress = how much of the reduction achieved (simplified baseline model)
        return {
            'target_id': target.id,
            'name': target.name,
            'base_year': target.base_year,
            'target_year': target.target_year,
            'target_type': target.target_type,
            'reduction_pct': float(target.reduction_pct),
            'actual_tco2e': float(actual),
            'status': target.status,
        }
```

## Migration
```bash
./manage.sh manage makemigrations emissions
```
One migration file should be created: `backend/emissions/migrations/0006_sbti_target.py` (or next number). Verify it contains the SBTiTarget model.

## Verification Gate (copy-paste into terminal, paste ALL output in TASK-RESULTS.md)

```bash
# 1. Migration check
./manage.sh migrate
./manage.sh manage makemigrations --check
# Must output: "No changes detected"

# 2. Import check
./manage.sh manage check
# Must exit 0

# 3. Restart backend
./manage.sh restart backend

# 4. Get token
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# 5. List targets (empty)
curl -s http://localhost:8009/carbon-api/emissions/targets/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: []

# 6. Create a target
curl -s -X POST http://localhost:8009/carbon-api/emissions/targets/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_unit":5,"name":"Facilities 2030 Reduction","base_year":2023,"target_year":2030,"target_type":"absolute","scope":"1+2","reduction_pct":50.00,"status":"draft"}' \
  | python3 -m json.tool
# Expect: 201 with id, name, etc.

# 7. List again (should have 1)
curl -s http://localhost:8009/carbon-api/emissions/targets/ \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={d[\"count\"]}')"
# Expect: count=1
```

## Handoff
Write `plans/carbon-phase/phase-03-targets/TASK-RESULTS-G1.md` with:
- Files changed (paths)
- Verification output pasted
- Issues encountered
- Deviations from spec (if any)
