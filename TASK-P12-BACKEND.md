# TASK P12 — Backend: N+1 Audit + Profiling

**Role:** `backend-worker`
**Date:** 2026-08-02
**Depends on:** P12 spec (`TASK-CARBON-P12-PERFORMANCE.md`)
**Covers:** G1 (N+1 audit & fix) + G2 (silk profiling) + G5 (verification gates)

---

## Activation Protocol

1. Read `.ai-toolkit/project.config.md` — BACKEND_ACTIVATE, BACKEND_CHECK_CMD, HARD RULES
2. Read `.ai-toolkit/shared/base-rules.md` — verification loop, handoff format
3. Read `.ai-toolkit/shared/api-contract.md` + `shared/data-layer.md`
4. Run `./.ai-toolkit/scripts/scan.sh` to refresh registry
5. Read every file in "Files to Read First" below
6. Run `python manage.py check` to confirm clean baseline
7. Confirm: "Ready as Backend Worker. Baseline: [check output]"

---

## Files to Read First

- `backend/dq/views.py` — lines 65–280 (FieldProfileViewSet, TableProfileViewSet, DQRuleViewSet, DQResultViewSet)
- `backend/dq/serializers.py` — to see which FK fields each serializer traverses
- `backend/mdm/views.py` — lines 44–100 (ReferenceSetViewSet has select_related already), 307–330 (OrgUnitViewSet), 489+ (ReferenceValueViewSet)
- `backend/core/tests/test_performance.py` — 3 existing performance tests
- `backend/requirements.txt` — will add django-silk
- `backend/config/settings.py` — will add silk INSTALLED_APPS + MIDDLEWARE

---

## G1 — N+1 Query Audit & Fix

### Objective
Eliminate N+1 queries. Every `get_queryset()` that returns FK-traversing models must have `select_related`/`prefetch_related`.

### What's ALREADY optimized (DO NOT TOUCH)
- `DQResultViewSet.get_queryset()` — already has `select_related('rule__data_table', 'rule__created_by')` ✓
- `ReferenceSetViewSet.get_queryset()` — already has `select_related('domain', 'steward')` ✓
- `emissions/views.py` — CalculationViewSet, VerificationRecordViewSet, CalculationAuditViewSet all have select_related ✓

### What NEEDS fixing

#### DQ app (3 ViewSets to fix)

**1. FieldProfileViewSet** (`backend/dq/views.py`, line ~72)
```python
# CURRENT — no select_related
qs = FieldProfile.objects.all()

# FIX — add select_related for all FKs the serializer touches
qs = FieldProfile.objects.select_related(
    'data_field__data_table__module',
)
```
Serializer likely touches: `data_field.name`, `data_field.data_table.name`, `data_field.data_table.module.name`. Verify by reading `FieldProfileSerializer` in `dq/serializers.py`.

**2. TableProfileViewSet** (`backend/dq/views.py`, line ~99)
```python
# CURRENT
qs = TableProfile.objects.all()

# FIX
qs = TableProfile.objects.select_related(
    'data_table__module',
)
```

**3. DQRuleViewSet** (`backend/dq/views.py`, line ~127)
```python
# CURRENT
qs = DQRule.objects.filter(is_active=True)

# FIX
qs = DQRule.objects.select_related(
    'data_field__data_table__module',
    'data_table__module',
    'created_by',
).filter(is_active=True)
```

#### MDM app (2 places to audit + fix)

**4. OrgUnitViewSet** (`backend/mdm/views.py`, line ~307)
```python
# CURRENT — no select_related
qs = OrgUnit.objects.filter(is_active=True)

# AUDIT: does OrgUnitSerializer traverse `parent` FK?
# If yes, add: .select_related('parent')
qs = OrgUnit.objects.select_related('parent').filter(is_active=True)
```
Check `OrgUnitSerializer` in `mdm/serializers.py` — if it includes `parent` field, use `select_related('parent')`.

**5. ReferenceValueViewSet** (`backend/mdm/views.py`, line ~489)
```python
# CURRENT — no select_related
qs = ReferenceValue.objects.all()

# FIX — if serializer touches reference_set FK
qs = ReferenceValue.objects.select_related('reference_set').all()
```
Check `ReferenceValueSerializer` in `mdm/serializers.py`.

### Write N+1 tests

Add to `backend/core/tests/test_performance.py` (or create new test files):

```python
from django.test import override_settings
from django.db import connection, reset_queries
import json

class DQFieldProfileNPlusOneTest(TestCase):
    def test_field_profile_list_no_n_plus_one(self):
        """GET /dq/field-profiles/ should execute ≤ 3 queries."""
        with self.assertNumQueries(3):
            response = self.client.get('/carbon-api/dq/field-profiles/')
        self.assertEqual(response.status_code, 200)

    # Repeat for: table-profiles, rules, results
```

Test pattern for each endpoint:
1. Create test data (at least 3 objects with FK relationships)
2. Send GET request
3. Assert query count ≤ acceptable threshold
4. Assert 200 response

### Gates (G1)
- [ ] `python manage.py check` — 0 errors
- [ ] `python manage.py makemigrations --check` — "No changes detected"
- [ ] `pytest backend/core/tests/test_performance.py -v` — all pass
- [ ] `pytest backend/ -q --tb=short` — all 310+ tests pass
- [ ] Zero `select * from` patterns in the 5 fixed ViewSets (verified by test)

---

## G2 — Profiling & Slow Endpoint Identification

### Objective
Install django-silk, profile 15 endpoints, produce timing report.

### Install django-silk

```bash
cd backend && source ../.venv/bin/activate
pip install django-silk==5.3.2
```

Add to `backend/requirements.txt`:
```
django-silk==5.3.2
```

Add to `backend/config/settings.py` (DEV ONLY — wrap in `if DEBUG`):
```python
if DEBUG:
    INSTALLED_APPS += ['silk']
    MIDDLEWARE.insert(0, 'silk.middleware.SilkyMiddleware')
```

Add to `backend/config/urls.py`:
```python
if settings.DEBUG:
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
```

Run migrations:
```bash
python manage.py migrate
```

### Profile 15 endpoints

Hit each endpoint 5–10 times via script. Collect:
- Average response time (ms)
- p95 response time (ms)
- Query count

**Endpoints to profile:**
1. `GET /carbon-api/emissions/dashboard/`
2. `GET /carbon-api/emissions/calculations/`
3. `GET /carbon-api/catalog/assets/`
4. `GET /carbon-api/accounts/users/`
5. `GET /carbon-api/accounts/scoped-roles/`
6. `GET /carbon-api/accounts/me/context/`
7. `GET /carbon-api/dq/rules/`
8. `GET /carbon-api/dq/results/`
9. `GET /carbon-api/mdm/org-units/`
10. `GET /carbon-api/mdm/reference-sets/`
11. `GET /carbon-api/dataschema/tables/`
12. `GET /carbon-api/dataschema/fields/`
13. `GET /carbon-api/emissions/targets/`
14. `GET /carbon-api/catalog/governance-policies/`
15. `GET /carbon-api/accounts/audit-log/`

Write a profiling script (`backend/profile_endpoints.py`) or run from terminal:

```bash
# Get a JWT token first
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access'])")

# Profile each endpoint 5x
for endpoint in "emissions/dashboard/" "emissions/calculations/" ...; do
  for i in $(seq 1 5); do
    curl -s -o /dev/null -w "$endpoint: %{time_total}s\n" \
      -H "Authorization: Bearer $TOKEN" \
      "http://localhost:8009/carbon-api/$endpoint"
  done
done
```

### Gates (G2)
- [ ] django-silk installed and migrations applied
- [ ] Silk UI accessible at `http://localhost:8009/silk/`
- [ ] `TASK-RESULTS-P12-PROFILE.md` created with table: endpoint | avg ms | p95 ms | query count | notes
- [ ] django-silk wrapped in `if DEBUG` — not active in production config

---

## G5 — Final Verification

Run ALL of these before marking done:

```bash
# Backend checks
cd backend && source ../.venv/bin/activate
python manage.py check
python manage.py makemigrations --check
python -m pytest -q --tb=short

# Anti-pattern check
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns
```

---

## DO NOT
- ❌ Change serializer logic, add fields, or modify serializer classes
- ❌ Add migration files (optimization only, no schema changes)
- ❌ Touch `emissions/` app (already optimized)
- ❌ Change permission classes or business logic
- ❌ Enable django-silk outside `if DEBUG` block
- ❌ Touch any frontend files

---

## Success Criteria
1. **0 N+1 queries** in DQ FieldProfile, TableProfile, DQRule ViewSets
2. **select_related added** where OrgUnitSerializer and ReferenceValueSerializer traverse FKs
3. **django-silk running** at `/silk/` with profiling data
4. **`TASK-RESULTS-P12-PROFILE.md`** populated with p95 timings for 15 endpoints
5. **All gates pass** — check, makemigrations, 310+ tests

---

## Handoff

When done, write `TASK-RESULTS-P12-BACKEND.md` with:
- Files changed (with line ranges)
- Terminal output from gates
- Timing table from profiling
- Any issues or blockers
