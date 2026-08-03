# TASK-G1 — Phase 07 Backend: SBTiTarget URL Registration + Enrichment

## Summary
`SBTiTargetViewSet` (ModelViewSet) exists in `views.py` but is **NOT registered in `urls.py`** — the endpoint is unreachable. Register it + add a computed progress field to the serializer.

---

## Deliverables

### D1 — Register SBTiTargetViewSet in urls.py

In `backend/emissions/urls.py`:

**Add import** (line ~9):
```python
from .views import (
    ...
    SBTiTargetViewSet,  # ADD this line
    ...
)
```

**Add router registration** (after report-configs router, line ~39):
```python
targets_router = DefaultRouter()
targets_router.register(r'targets', SBTiTargetViewSet, basename='sbti-target')
```

**Add include** (in urlpatterns, after audit_router):
```python
path('', include(targets_router.urls)),
```

This exposes:
- `GET /emissions/targets/` — list all (org-scoped)
- `POST /emissions/targets/` — create target
- `GET /emissions/targets/{id}/` — retrieve
- `PATCH /emissions/targets/{id}/` — update
- `DELETE /emissions/targets/{id}/` — delete

### D2 — Add computed progress to SBTiTargetSerializer (optional but recommended)

In `backend/emissions/serializers.py`, add to `SBTiTargetSerializer`:

```python
progress = serializers.SerializerMethodField()

def get_progress(self, obj):
    """Return current-year emissions for this target's scope + org_unit."""
    from django.db.models import Sum
    from decimal import Decimal
    
    scopes = obj.scope.replace('+', ',').split(',')
    year = obj.base_year  # or current year — use timezone.now().year
    
    from .models import Calculation
    actual = Calculation.objects.filter(
        module__org_unit_id=obj.org_unit_id,
        reporting_year=timezone.now().year,
        scope__in=scopes,
    ).aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')
    
    return {
        'current_year': timezone.now().year,
        'current_emissions_tco2e': float(actual),
    }
```

Add `progress` to `fields` or at minimum add it to `read_only_fields`.

Alternative: skip D2 if you want minimal change. D1 alone is sufficient for the frontend to work — progress can be computed client-side or via a future `/targets/{id}/progress/` @action.

---

## Files to Change

| File | Action |
|------|--------|
| `backend/emissions/urls.py` | D1: +2 imports, +3 lines router, +1 line include |
| `backend/emissions/serializers.py` | D2: +~15 lines (optional) |

---

## DO-NOT-TOUCH

- ❌ No new models, no migrations
- ❌ No views.py changes (SBTiTargetViewSet already exists and is correct)
- ❌ No services.py changes
- ❌ No frontend files

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

# 5. HTTP spot-checks:
./manage.sh restart backend

TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# LIST — should return empty [] or existing targets
curl -s http://localhost:8009/carbon-api/emissions/targets/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# CREATE
curl -s -X POST http://localhost:8009/carbon-api/emissions/targets/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_unit":5,"name":"FY30 Reduction","base_year":2023,"target_year":2030,"target_type":"absolute","scope":"1+2","reduction_pct":42.0,"status":"draft"}' | python3 -m json.tool

# GET single
curl -s http://localhost:8009/carbon-api/emissions/targets/1/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# DELETE
curl -s -X DELETE http://localhost:8009/carbon-api/emissions/targets/1/ \
  -H "Authorization: Bearer $TOKEN"
```

## Success Criteria

- [ ] `python manage.py check` — exit 0
- [ ] `makemigrations --check` — No changes detected
- [ ] `verify.sh backend` — GATE PASSED
- [ ] All 50 tests pass
- [ ] `GET /emissions/targets/` returns 200 (with data or empty [])
- [ ] `POST /emissions/targets/` creates a target (201)
- [ ] `GET /emissions/targets/{id}/` returns the target
- [ ] `DELETE /emissions/targets/{id}/` removes it (204)
- [ ] Only 1-2 files changed
