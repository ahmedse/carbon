# TASKS-P8: Cross-Role Browser Integration Testing & RBAC Gap Remediation

**Date**: 2026-07-31
**Status**: ✅ Complete
**Predecessor**: P7 (Fix RBAC bugs, expand dataschema visibility)
**Successor**: P9 (TBD)

---

## Objective

Comprehensive browser-based integration testing across all principal roles
(viewer, data owner, analyst, transport officer, admin) to validate that every
carbon domain flow works end-to-end.  During testing, remediate any RBAC gaps
discovered in real time.

---

## Summary of Changes

### 5 files · 32 insertions · 29 deletions

| File | Change | Category |
|---|---|---|
| `backend/accounts/rbac_utils.py` | Added global visibility-role check to `get_visible_org_units()` | RBAC fix |
| `backend/dataschema/views.py` | Expanded `required_role` tuples to include `viewers_group` & `analysts_group`; switched to `get_visible_module_ids()` | RBAC fix |
| `backend/emissions/services.py` | Added global visibility-role check to `OwnerService.get_org_units()` | RBAC fix |
| `backend/emissions/views.py` | `ReportingPeriodViewSet`: `AdminOrSuperuserOnly` → `ReadAnyWriteAdmin` | Perm fix |
| `carbon-frontend/src/App.jsx` | `RoleAwareLanding`: redirect non-admin users to `/carbon/console` (rich landing with icons, stats, actions) instead of flat `/modules/:id` page | UX fix |

---

## Bugs Found & Fixed

### 1. Dataschema 403 for viewer/analyst roles (P8-G1)
**Symptom**: `GET /carbon-api/dataschema/tables/` returned 403 for viewer1.
**Root cause**: `DataTableViewSet`, `DataFieldViewSet`, `DataRowViewSet` had
`required_role` tuples that excluded `viewers_group` and `analysts_group`.
Same class of bug as P7.
**Fix**: Expanded all three viewsets' required_role to include all visibility
roles.  Switched `get_queryset()` from hardcoded `get_allowed_module_ids(user, [...])`
to `get_visible_module_ids(user)` — the same universal helper already used
by emissions views.

### 2. MyData / Owner API 403 for global visibility roles (P8-G2)
**Symptom**: `GET /carbon-api/carbon/my-data/` returned 403 "No accessible org units".
Also affected `carbon/owner/activity/`, `carbon/owner/dashboard/`, etc.
**Root cause**: `get_visible_org_units()` and `OwnerService.get_org_units()`
only checked for global **admin** roles, not global **visibility** roles.
A user with `viewers_group` (org_unit=None, module=None) got zero org units.
**Fix**: Both functions now check for global visibility roles
(`ScopedRole.objects.filter(org_unit=None, module=None, group__name__in=VISIBILITY_ROLES)`)
and return unrestricted access, matching the pattern already established in
`get_visible_module_ids()`.

### 3. Reporting Periods 403 for non-admin users (P8-G3)
**Symptom**: `GET /carbon-api/carbon/periods/` returned 403 for viewer1, breaking
the Report Generator page's period dropdown.
**Root cause**: `ReportingPeriodViewSet` used `AdminOrSuperuserOnly` — a
permission class designed for sensitive catalog/configuration management.
Periods are reference data needed by all users for report generation.
**Fix**: Switched to `ReadAnyWriteAdmin`, the standard permission class for
reference-data views that any authenticated user may read.

### 4. Flat landing page — no app icons or submenus (P8-G4)
**Symptom**: Non-admin users (viewer1, dataowner1, analyst1) landed on
`/modules/:id` — a flat grid of tables with no app icons, navigation cards,
stat banners, or sub-menu structure.
**Root cause**: `RoleAwareLanding` in `App.jsx` redirected non-admin users to
their first module (`/modules/${firstModule.id}`) which renders the flat
`ModuleLandingPage` instead of the rich `CarbonConsolePage`.
**Fix**: Unified both the "data-only" and "generic non-admin" redirect paths
to `/carbon/console`.  The `CarbonConsolePage` provides: PageHeader,
PeriodBanner (2026), StatCards (7926.73t CO₂e, 6 modules, 6 tables, 189 calcs),
Quick Actions (Dashboard, My Data, Reports), Recent Activity feed.

---

## Test Results: Role-by-Role

### viewer1 (viewers_group, global)
| Page | Result | Details |
|---|---|---|
| Login → `/carbon/console` | ✅ | Rich landing: stats, period banner, Quick Actions |
| Dashboard | ✅ | 7,926.73t CO₂e, scope breakdown, monthly trend, category table |
| My Data | ✅ | AASTMT, 1 module, 6 tables, 130 rows, DQ 100% |
| Reports → Generate | ✅ | Period dropdown populates, scope checkboxes, Generate button |
| Sidebar | ✅ | Overview, Emissions Dashboard, My Data, Reporting, Configuration |

### admin (superuser)
| Page | Result | Details |
|---|---|---|
| Login → `/` (PlatformHome) | ✅ | App cards with role chips |
| Carbon Console | ✅ | Full admin sidebar: Data Entry, Calculations, Verification, Emission Factors, SBTi Targets + Admin badge |
| Dashboard | ✅ | All stats, charts, category breakdown |

### dataowner1 (dataowners_group, global)
| Page | Result | Details |
|---|---|---|
| Login → `/carbon/console` | ✅ | Data owner sidebar: Data Entry, Calculations, Verification |
| My Data | ✅ | Buildings org unit, 6 tables, 130 rows, 100% DQ, Passing |

### analyst1 (analysts_group, global)
| Page | Result | Details |
|---|---|---|
| Login → `/carbon/console` | ✅ | Analyst sidebar: Analytics & Trends, Reporting, Configuration |
| Dashboard | ✅ | Full stats and charts |

### transport_officer (transport scope)
| Page | Result | Details |
|---|---|---|
| Module page | ✅ | 6 tables visible (Electricity, Water, Chilled Water, Fuel, Refrigerant, Commute) |

---

## RBAC Pattern (Universal)

The platform defines a single constant for visibility:

```python
VISIBILITY_ROLES = ["admins_group", "dataowners_group", "auditors_group", "viewers_group", "analysts_group"]
```

The **universal pattern** for any visibility-check function:

```python
def get_visible_X(user):
    if user_is_global_admin(user):
        return None  # unrestricted
    # Global visibility role → unrestricted
    if ScopedRole.objects.filter(
        user=user, is_active=True, org_unit=None, module=None,
        group__name__in=VISIBILITY_ROLES,
    ).exists():
        return None  # unrestricted
    return get_allowed_X(user, VISIBILITY_ROLES)
```

This pattern is now consistently applied across:
- `get_visible_module_ids()` (P7 + earlier)
- `get_visible_org_units()` (P8)
- `OwnerService.get_org_units()` (P8)

---

## Commit

```
commit: P8 RBAC gap remediation + landing page UX fix
  - dataschema: expand required_role to include viewers/analysts
  - rbac_utils: global visibility check in get_visible_org_units
  - services: OwnerService global visibility check
  - views: ReportingPeriodViewSet → ReadAnyWriteAdmin
  - App.jsx: RoleAwareLanding → /carbon/console (rich landing)
```
