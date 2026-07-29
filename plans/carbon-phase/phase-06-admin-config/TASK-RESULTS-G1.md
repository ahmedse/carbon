# TASK-RESULTS-G1 — Phase 06 Admin Configuration: Backend GWP CRUD Enabler

## Status: ✅ COMPLETE

1-word change to upgrade GWP from read-only to full CRUD.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/emissions/views.py` (line 191) | `ReadOnlyModelViewSet` → `ModelViewSet`; docstring updated |

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
| **POST** (CREATE) | `/carbon-api/carbon/gwp/` | ✅ 201 | `{"id":1,"gas_name":"Test Gas","gas_formula":"TG","gwp_ar6_100yr":"1.00"}` |
| **GET** (LIST) | `/carbon-api/carbon/gwp/` | ✅ 200 | Returns list with all GWP fields |
| **DELETE** | `/carbon-api/carbon/gwp/1/` | ✅ 204 | Entry removed; GET confirms 0 items |

## D2 — Permission Check

`AdminOrSuperuserOnly` (in `catalog/permissions.py`) already permits write operations for superusers and global admins (ScopedRole with `org_unit=None, module=None`). No permission change needed. ✅

## D3 — Serializer Fields

`GWPSerializer` already declares all model fields. No changes needed. ✅

## Scope

Only 1 file changed — no new models, migrations, serializers, URLs, or permissions.
