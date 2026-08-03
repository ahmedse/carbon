# TASK-RESULTS-E2-B1.md — RBAC Reconciliation (Backend)

**Status**: ✅ COMPLETE  
**Date**: 2026-07-29  
**Phase**: E2-B1 (Deployment Blocker — Backend RBAC Reconciliation)  
**Tests**: 11 new regression tests, all passing  
**Full suite**: 343 passed / 15 failed (all pre-existing failures, no regressions)

---

## 5 Tasks Completed

### T1 — Single Source of Truth ✅
**File**: `backend/accounts/constants.py` (NEW)

Created canonical constant definitions for all RBAC group names, role sets, and protected groups:
- `ADMINS_GROUP`, `DATAOWNERS_GROUP`, `ANALYSTS_GROUP`, `VIEWERS_GROUP`, `AUDITORS_GROUP`
- `CARBON_DATA_OWNERS_GROUP`, `CARBON_ANALYSTS_GROUP`, `ADMIN_GROUP`
- `ADMIN_ROLES`, `VISIBILITY_ROLES`, `READ_ONLY_ROLES`
- `PROTECTED_GROUPS`, `ALL_CANONICAL_GROUPS`

### T2 — Fix Deploy Mismatch ✅
**Files**: `backend/deploy_aastmt_carbon.py`, `backend/accounts/rbac_utils.py`

- Deploy script: Ali's global admin role changed from `carbon_admin` → `admins_group`
- `rbac_utils.py`: removed hardcoded `ADMIN_ROLES` and `VISIBILITY_ROLES` lists, now imports from `.constants`

### T3 — Close Write Hole ✅
**File**: `backend/emissions/views.py`

Added `CalculationWritePermission(BasePermission)` class:
- Reads (SAFE_METHODS): any authenticated user
- Writes: requires superuser, global admin, OR `admins_group`/`analysts_group` role on target module
- Reads both `module_id` and `module` keys from request data and query params

`CalculationViewSet.permission_classes` changed from `[IsAuthenticated]` to `[IsAuthenticated, CalculationWritePermission]`.

### T4 — Fix verify()/reject() Hardcoded Checks ✅
**File**: `backend/emissions/views.py`

- `verify()`: `request.user.groups.filter(name='admins_group').exists()` → `user_is_global_admin(request.user)`
- `reject()`: Same change

### T5 — Alignment Note (Read-Only) ✅
**Files**: None modified (read-only analysis)

Manifest roles vs AdminRoute guard discrepancy identified and documented:
- Manifest: `carbon:data_owner` (scoped), `carbon:analyst` (global), `carbon:admin` (global)
- AdminRoute wraps ALL carbon pages with `isGlobalAdmin()` — contradiction for Calculations, Verification, Analytics, Reporting pages
- Feeds E2-F1 task 5

---

## Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `backend/accounts/constants.py` | NEW | Single source of truth for RBAC constants |
| `backend/accounts/rbac_utils.py` | MODIFIED | Imports from `.constants` instead of inline hardcoded lists |
| `backend/accounts/permissions.py` | MODIFIED | Imports `READ_ONLY_ROLES`, `ADMINS_GROUP`, `ADMIN_GROUP` from `.constants` |
| `backend/accounts/views.py` | MODIFIED | `destroy()` uses `PROTECTED_GROUPS` from constants |
| `backend/accounts/serializers.py` | MODIFIED | Role metadata helpers import from `.constants` |
| `backend/deploy_aastmt_carbon.py` | MODIFIED | `carbon_admin` → `admins_group` |
| `backend/emissions/views.py` | MODIFIED | Added `CalculationWritePermission`; fixed verify/reject checks |
| `backend/accounts/tests/test_e2_b1_rbac.py` | NEW | 11 regression tests |

---

## Test Results

### E2-B1 Tests (11/11 pass)
```
test_calc_create_denied_for_viewer
test_calc_create_denied_for_unauth
test_calc_create_allowed_for_analyst_with_module_role
test_calc_create_allowed_for_global_admin
test_calc_create_denied_for_analyst_without_module_id
test_calc_verify_denied_for_non_admin
test_calc_reject_denied_for_non_admin
test_calc_verify_allowed_for_scoped_role_admin
test_rbac_constants_consistency
test_protected_groups_from_constants
test_deployed_groups_resolve_to_canonical
```

### Full Suite: 343 passed / 15 failed
15 pre-existing failures (4 SBTi targets, 11 swagger docs) — zero regressions.

---

## Gate Status

| Gate | Requirement | Status |
|------|-------------|--------|
| pytest pass | ≥6 new RBAC regression tests | ✅ 11 pass |
| Full suite | No regressions | ✅ 343 pass (baseline: 332) |
| verify.sh backend | PASS | ℹ️ No verify.sh; pytest gates met |

---

## Bug Fixed During Implementation

**Problem**: `CalculationWritePermission` checked `request.data.get('module_id')` but DRF serializers use the FK field name `module` in POST data. Global admin tests passed because `user_is_global_admin()` returned True before reaching the module_id check; analyst tests failed because `module_id` resolved to None.

**Fix**: Added fallback to `request.data.get('module')` and `request.query_params.get('module')`.
