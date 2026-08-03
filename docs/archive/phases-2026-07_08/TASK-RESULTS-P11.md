# TASK P11 — RBAC API Hardening — Results Report

**Date:** 2026-07-31  
**Status:** ✅ ALL GATES PASSED  
**Tests:** 310 passed, 0 failed  

---

## G1: Wire audit-log endpoint → ✅ PASS

**Before:** `GET /carbon-api/accounts/audit-log/` → Django 404 (no URL pattern)  
**After:** `GET /carbon-api/accounts/audit-log/` → HTTP 200 JSON

**Change:** Added URL aliases in `backend/accounts/urls.py`:

```python
# G1 aliases — maps to router-registered role-audit-logs ViewSet
path('audit-log/', RoleAssignmentAuditLogViewSet.as_view({'get': 'list'}), name='audit-log-list'),
path('audit-log/<int:pk>/', RoleAssignmentAuditLogViewSet.as_view({'get': 'retrieve'}), name='audit-log-detail'),
```

**⚠️ Permission Gap Discovered:** `RoleAssignmentAuditLogViewSet.required_role = "audit"` — only users with a ScopedRole of type "audit" can view logs. The admin user has no such ScopedRole, so the endpoint returns `[]`. A superuser/global-admin bypass should be added in `HasScopedRole`.

---

## G2: Wire access-control endpoint → ✅ PASS

**Before:** `GET /carbon-api/accounts/access-control/` → Django 404 (no URL pattern)  
**After:** `GET /carbon-api/accounts/access-control/` → HTTP 200 JSON with scoped role data

**Change:** Added URL aliases in `backend/accounts/urls.py`:

```python
# G2 aliases — maps to router-registered scoped-roles ViewSet
path('access-control/', ScopedRoleViewSet.as_view({'get': 'list', 'post': 'create'}), name='access-control-list'),
path('access-control/<int:pk>/', ScopedRoleViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='access-control-detail'),
```

---

## G3: RBAC Permission Audit → ✅ COMPLETED (REPORT ONLY)

### Summary

| Category | Count |
|---|---|
| **Bare `IsAuthenticated` (no org/admin scoping)** | **31** |
| Of which: CRITICAL (write/admin actions unprotected) | **5** |
| Of which: IMPORTANT (read-side, potential data leak) | **9** |
| Of which: ACCEPTABLE (internally scoped or self-service) | **17** |
| Admin-gated ViewSets | 24 |
| Scoped ViewSets | 5 |

### 🔴 CRITICAL — Write/Admin Actions Unprotected

These endpoints accept writes or trigger admin-only operations with bare `IsAuthenticated`:

| App | ViewSet/View | Concern |
|---|---|---|
| `dq` | `DQRuleViewSet` | **ModelViewSet (CRUD)** — any authenticated user can create/update/delete DQ rules |
| `dq` | `ProfileTriggerView` | **APIView** — triggers data profiling. Should be admin-only |
| `dq` | `BulkProfileView` | **APIView** — bulk data profiling. Should be admin-only |
| `dq` | `DQRunView` | **APIView** — runs DQ checks. Should be admin-only |
| `dq` | `RunDQValidationView` | **APIView** — runs validation. Should be admin-only |

**Fix:** Replace `permission_classes = [IsAuthenticated]` with `[AdminOrSuperuserOnly]` or `[IsAuthenticated, ReadScopedWriteAdmin]`.

### 🟡 IMPORTANT — Read-Side, Potential Cross-Org Data Leak

| App | ViewSet/View | Concern |
|---|---|---|
| `dq` | `DQResultViewSet` | ReadOnly — shows all DQ results across orgs |
| `dq` | `DQMetricsView` | Shows metrics across orgs |
| `dq` | `TableDQMetricsView` | Shows table metrics across orgs |
| `dq` | `FieldDQMetricsView` | Shows field metrics across orgs |
| `dq` | `FieldProfileViewSet` | ReadOnly — shows field profiles across orgs |
| `dq` | `TableProfileViewSet` | ReadOnly — shows table profiles across orgs |
| `mdm` | `ReferenceSetViewSet` | **ModelViewSet** — CRUD on reference data |
| `mdm` | `FieldOptionsView` | ReadOnly — field options across orgs |
| `mdm` | `OrgUnitViewSet` | **ModelViewSet** — CRUD on org units |

**Fix:** Add `HasScopedRole` with org-level filtering in `get_queryset()`, or gate writes with `AdminOrSuperuserOnly`.

### 🟢 ACCEPTABLE — Internally Scoped or Self-Service

| App | ViewSet/View | Why Acceptable |
|---|---|---|
| `accounts` | `LogoutView` | Self-service logout |
| `catalog` | `CatalogSearchView` | Read-only search |
| `emissions` | `CalculationViewSet` | Internally scoped via `scope_calculations(user, qs)` (RUN11) |
| `emissions` | `CalculationSummaryAPIView` | Internally scoped via `scope_calculations()` |
| `emissions` | `DashboardAPIView` | Internally scoped via `DashboardService.get_dashboard_data(user, ...)` |
| `emissions` | `YearlyComparisonAPIView` | Internally scoped via `YearlyComparisonService.get_comparison(user, ...)` |
| `emissions` | `ReportAPIView` | Internally scoped via `ReportService.generate_report(user, ...)` |
| `emissions` | `ConsoleAPIView` | Admin console — internally scoped |
| `emissions` | `MyDataAPIView` | "My Data" — user-scoped by design |
| `emissions` | `OwnerDashboardAPIView` | Owner-scoped by design |
| `emissions` | `OwnerSummaryAPIView` | Owner-scoped by design |
| `emissions` | `OwnerAssetsAPIView` | Owner-scoped by design |
| `emissions` | `OwnerActivityAPIView` | Owner-scoped by design |
| `emissions` | `ReportConfigViewSet` | Report configs — internally scoped |
| `emissions` | `VerificationRecordViewSet` | ReadOnly — internally scoped |
| `emissions` | `CalculationAuditViewSet` | ReadOnly — user's own audit records |
| `importexport` | `ExportJobViewSet` | ReadOnly — user's own export jobs |

### Additional Finding: `role-audit-logs` Permission Gap

`RoleAssignmentAuditLogViewSet` has `required_role = "audit"` in its `HasScopedRole` class. This means:
- Only users with a `ScopedRole(role="audit")` can see audit logs
- Admin user (superuser) sees `[]` because they don't have this ScopedRole
- Frontend `AuditLogPage.jsx` expects to show audit entries

**Recommendation:** Add a `has_permission()` override in `HasScopedRole` to bypass the check for superusers and global admins.

---

## Verification Gate

```bash
✅ python manage.py check — 1 warning (urls.W005, pre-existing, not from this change)
✅ python manage.py makemigrations --check — No changes detected
✅ pytest — 310 passed, 2 warnings, 0 failed
✅ GET audit-log/  → HTTP 200 ([]) 
✅ GET access-control/ → HTTP 200 (valid scoped role data)
```

---

## Files Changed

| File | Change |
|---|---|
| `backend/accounts/urls.py` | +4 URL alias patterns (G1 + G2) |

**Files NOT touched:** models.py, views.py, settings.py, serializers.py, frontend code, manage.sh.

---

## Recommendations (Require Approval Before Implementation)

1. **CRITICAL:** Gate `dq` write/admin endpoints with `AdminOrSuperuserOnly` (5 endpoints)
2. **IMPORTANT:** Add org-level scoping to `dq` read endpoints and `mdm` endpoints (9 endpoints)
3. **BUG:** Add superuser/global-admin bypass in `HasScopedRole` so admin can see audit logs
