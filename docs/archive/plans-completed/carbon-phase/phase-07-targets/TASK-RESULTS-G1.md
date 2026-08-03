# TASK-RESULTS-G1 — Phase 07 Backend: SBTiTarget URL Registration + Enrichment

## Status: ✅ COMPLETE

SBTiTarget endpoint now reachable via emissions app URLs + enriched with computed progress field.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/emissions/urls.py` | D1: Added `SBTiTargetViewSet` import, `targets_router`, `include(targets_router.urls)` in urlpatterns |
| `backend/emissions/serializers.py` | D2: Added `from django.db.models import Sum`, `progress` SerializerMethodField + `get_progress()` to `SBTiTargetSerializer` |

## Verification Results

| Gate | Result |
|------|--------|
| `python manage.py check` | ✅ exit 0 (pre-existing W005 only) |
| `makemigrations --check` | ✅ No changes detected |
| `verify.sh backend` | ✅ GATE PASSED |
| `verify.sh antipatterns` | ✅ GATE PASSED |
| `pytest emissions/tests/ -v` | ✅ 50/50 passed |

## HTTP Spot-Checks

| Operation | Path | Status | Detail |
|-----------|------|--------|--------|
| **GET** (LIST) | `/carbon-api/carbon/targets/` | ✅ 200 | `[]` initially |
| **POST** (CREATE) | `/carbon-api/carbon/targets/` | ✅ 201 | Created `FY30 Reduction` with `progress: {"current_year": 2026, "current_emissions_tco2e": 91221.6}` |
| **GET** (single) | `/carbon-api/carbon/targets/2/` | ✅ 200 | Returns full target with progress field |
| **DELETE** | `/carbon-api/carbon/targets/2/` | ✅ 204 | Removed; GET confirms empty `[]` |

## D2 — Progress Field

`SBTiTargetSerializer` now includes a computed `progress` field:
```json
{
  "progress": {
    "current_year": 2026,
    "current_emissions_tco2e": 91221.6
  }
}
```
- Aggregates `co2e_kg` from `Calculation` for matching scope(s) + org_unit in the current year
- Scope parsing handles `+`‑delimited strings (e.g. `"1+2"`)
- Uses `timezone.now().year` for the current year
