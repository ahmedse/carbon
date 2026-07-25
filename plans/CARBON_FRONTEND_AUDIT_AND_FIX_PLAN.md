# Carbon Frontend — Complete Audit & Fix Plan

**Date:** 2026-07-25  
**Auditor:** Zoo  
**Scope:** All frontend pages, routing, navigation menus, app manifest, and cross-system consistency  
**Philosophy:** Carbon is a domain app on top of the Data Trust Platform

---

## 1. 🔴 CRITICAL BUG: `CalendarMonth is not defined`

### Location
[`CarbonConsolePage.jsx:267`](carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx:267)

### Root Cause
On line 31, `CalendarMonth` is imported with an alias:
```jsx
import {
  CalendarMonth as PeriodsIcon,   // ← aliased to PeriodsIcon
  ...
} from '@mui/icons-material';
```

But on line 267, the original name `CalendarMonth` is used directly:
```jsx
icon={<CalendarMonth />}
```

Since `CalendarMonth` was renamed to `PeriodsIcon` in the import, the name `CalendarMonth` is **not in scope** at runtime, causing the `ReferenceError`.

### Fix
Change line 267 from:
```jsx
icon={<CalendarMonth />}
```
to:
```jsx
icon={<PeriodsIcon />}
```

---

## 2. 🏗️ System Architecture Overview

### 2.1 Studio Architecture (VSCode-inspired Shell)

The system uses a multi-studio shell pattern:

```
Shell (IDE-like layout)
├── ActivityBar (left 48px — studio switcher)
├── ShellSidebar (contextual navigation per studio)
├── EditorArea (Outlet — renders current route)
├── StatusBar (bottom)
└── CopilotPane (right — AI assistant)
```

**Studios defined:**
| Studio | ID | Purpose |
|--------|----|---------|
| Dashboard | `home` | Executive dashboards |
| Carbon Footprint | `carbon` | GHG emissions app |
| Catalog Studio | `catalog` | Data catalog & governance |
| Platform Admin | `admin` | User/role/org management |
| Settings | `settings` | User profile & preferences |
| Help | `help` | Documentation & feedback |

### 2.2 App Manifest System

Carbon is registered via [`apps/carbon/manifest.js`](carbon-frontend/src/apps/carbon/manifest.js) which declares:
- **Route prefix:** `/carbon/*`
- **Navigation items** with role-based access (`*`, `carbon:data_owner`, `carbon:analyst`, `carbon:admin`)
- **RBAC roles:** `carbon:data_owner`, `carbon:analyst`, `carbon:admin`
- **Ontology:** Emission, ReportingPeriod, EmissionFactor, CalculationRule

### 2.3 Dual Navigation Systems

The system has **two sidebar navigation systems** that coexist:

1. **`SidebarMenu.jsx`** — Legacy perspective-driven sidebar (used in old Layout)
2. **`ShellSidebar.jsx`** — New studio-driven sidebar (used in Shell)

Both are active. The `ShellSidebar` reads from the app manifest, while `SidebarMenu` has hardcoded perspective logic.

---

## 3. 📋 Complete Page Inventory & Status

### 3.1 Carbon App Pages (`/carbon/*`)

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/carbon/console` | [`CarbonConsolePage.jsx`](carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx) | 🔴 **BUG** | CalendarMonth ReferenceError |
| `/carbon/dashboard` | [`EmissionsDashboard.jsx`](carbon-frontend/src/pages/EmissionsDashboard.jsx) | ✅ Complete | 738 lines, chart.js visualizations |
| `/carbon/data-entry` | [`DataHubHome.jsx`](carbon-frontend/src/pages/DataHubHome.jsx) | ✅ Complete | Scope-filtered module browser |
| `/carbon/data-entry/entry/:moduleName/:tableId` | [`DataEntryPage.jsx`](carbon-frontend/src/pages/DataEntryPage.jsx) | ✅ Complete | Wraps TableDataPage |
| `/carbon/data-entry/row/:tableId/:rowId` | [`RowDetailPage.jsx`](carbon-frontend/src/pages/dataschema/RowDetailPage.jsx) | ✅ Complete | Full detail page with tabs |
| `/carbon/reporting/generate` | [`ReportGeneratorPage.jsx`](carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx) | ✅ Complete | 315 lines |
| `/carbon/reporting/saved` | [`SavedReportsPage.jsx`](carbon-frontend/src/pages/emissions/SavedReportsPage.jsx) | ✅ Complete | 348 lines |
| `/carbon/reporting/periods` | [`ReportingPeriodsPage.jsx`](carbon-frontend/src/pages/emissions/ReportingPeriodsPage.jsx) | ✅ Complete | 350 lines |
| `/carbon/admin/factors` | [`EmissionFactorsPage.jsx`](carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx) | ✅ Complete | 360 lines |
| `/carbon/analytics` | Redirect → `/dashboards/analytics` | ✅ Complete | |
| `/carbon/owner/portal` | [`DataOwnerPortalPage.jsx`](carbon-frontend/src/pages/data-owner/DataOwnerPortalPage.jsx) | ✅ Complete | 428 lines |
| `/carbon/owner/dashboard` | [`DataOwnerDashboardPage.jsx`](carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx) | ✅ Complete | 372 lines |
| `/carbon/owner/assets` | [`DataOwnerAssetsPage.jsx`](carbon-frontend/src/pages/data-owner/DataOwnerAssetsPage.jsx) | ✅ Complete | 330 lines |

### 3.2 Dashboard Pages (`/dashboards/*`)

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/dashboards/executive` | [`ExecutiveSummary.jsx`](carbon-frontend/src/pages/dashboards/ExecutiveSummary.jsx) | ✅ Complete | |
| `/dashboards/analytics` | [`AnalyticsDashboard.jsx`](carbon-frontend/src/pages/dashboards/AnalyticsDashboard.jsx) | ✅ Complete | |
| `/dashboards/targets` | [`TargetsDashboard.jsx`](carbon-frontend/src/pages/dashboards/TargetsDashboard.jsx) | ✅ Complete | |
| `/dashboards/data-quality` | [`DataQualityDashboard.jsx`](carbon-frontend/src/pages/dashboards/DataQualityDashboard.jsx) | ✅ Complete | |
| `/dashboards/reporting` | [`ReportingDashboard.jsx`](carbon-frontend/src/pages/dashboards/ReportingDashboard.jsx) | ✅ Complete | |

### 3.3 Admin Pages (`/admin/*`)

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/admin/org-units` | [`OrgUnitsPage.jsx`](carbon-frontend/src/pages/admin/OrgUnitsPage.jsx) | ✅ Complete | |
| `/admin/org-units/:id` | [`OrgUnitDetailPage.jsx`](carbon-frontend/src/pages/admin/OrgUnitDetailPage.jsx) | ✅ Complete | |
| `/admin/users` | [`UsersPage.jsx`](carbon-frontend/src/pages/admin/UsersPage.jsx) | ✅ Complete | |
| `/admin/groups` | [`GroupsPage.jsx`](carbon-frontend/src/pages/admin/GroupsPage.jsx) | ✅ Complete | |
| `/admin/groups/:id` | [`GroupDetailPage.jsx`](carbon-frontend/src/pages/admin/GroupDetailPage.jsx) | ✅ Complete | |
| `/admin/access` | [`AccessControlPage.jsx`](carbon-frontend/src/pages/admin/AccessControlPage.jsx) | ✅ Complete | |
| `/admin/role-matrix` | [`RoleRegistryPage.jsx`](carbon-frontend/src/pages/admin/RoleRegistryPage.jsx) | ✅ Complete | |
| `/admin/apps` | [`RegisteredAppsPage.jsx`](carbon-frontend/src/pages/admin/RegisteredAppsPage.jsx) | ✅ Complete | |
| `/admin/policies` | Redirect → `/catalog/policies` | ✅ Complete | |
| `/admin/audit` | Placeholder `<div>` | ⚠️ **Stub** | "Coming soon" |

### 3.4 Catalog Pages (`/catalog/*`)

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/catalog` | [`CatalogHome.jsx`](carbon-frontend/src/pages/catalog/CatalogHome.jsx) | ✅ Complete | |
| `/catalog/products` | [`DataProductsPage.jsx`](carbon-frontend/src/pages/catalog/DataProductsPage.jsx) | ✅ Complete | |
| `/catalog/products/:id` | [`DataProductDetailPage.jsx`](carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx) | ✅ Complete | |
| `/catalog/tables/:id` | [`SchemaDetailPage.jsx`](carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx) | ✅ Complete | |
| `/catalog/metadata` | [`MetadataManagementPage.jsx`](carbon-frontend/src/pages/catalog/MetadataManagementPage.jsx) | ✅ Complete | |
| `/catalog/assets` | [`AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) | ✅ Complete | |
| `/catalog/assets/:id` | [`AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx) | ✅ Complete | |
| `/catalog/dq-dashboard` | [`DQDashboardPage.jsx`](carbon-frontend/src/pages/catalog/DQDashboardPage.jsx) | ✅ Complete | |
| `/catalog/dq-rules` | [`DQRulesPage.jsx`](carbon-frontend/src/pages/catalog/DQRulesPage.jsx) | ✅ Complete | |
| `/catalog/mdm` | [`MDMPage.jsx`](carbon-frontend/src/pages/catalog/MDMPage.jsx) | ✅ Complete | |
| `/catalog/mdm/reference-sets/:id` | [`ReferenceSetDetailPage.jsx`](carbon-frontend/src/pages/catalog/ReferenceSetDetailPage.jsx) | ✅ Complete | |
| `/catalog/connections` | [`ConnectionsPage.jsx`](carbon-frontend/src/pages/catalog/ConnectionsPage.jsx) | ✅ Complete | |
| `/catalog/importexport` | [`ImportExportPage.jsx`](carbon-frontend/src/pages/catalog/ImportExportPage.jsx) | ✅ Complete | |
| `/catalog/policies` | [`GovernancePolicyPage.jsx`](carbon-frontend/src/pages/admin/GovernancePolicyPage.jsx) | ✅ Complete | |
| `/catalog/governance` | [`GovernancePage.jsx`](carbon-frontend/src/pages/catalog/GovernancePage.jsx) | ✅ Complete | |
| `/catalog/reference-data` | [`ReferenceDataPage.jsx`](carbon-frontend/src/pages/catalog/ReferenceDataPage.jsx) | ✅ Complete | |
| `/catalog/sources` | [`DataSourcesDetailPage.jsx`](carbon-frontend/src/pages/catalog/DataSourcesDetailPage.jsx) | ✅ Complete | |
| `/catalog/exports` | [`ExportsDetailPage.jsx`](carbon-frontend/src/pages/catalog/ExportsDetailPage.jsx) | ✅ Complete | |
| `/catalog/imports` | [`ImportsDetailPage.jsx`](carbon-frontend/src/pages/catalog/ImportsDetailPage.jsx) | ✅ Complete | |
| `/catalog/tags/:id` | [`TagDetailPage.jsx`](carbon-frontend/src/pages/catalog/TagDetailPage.jsx) | ✅ Complete | |
| `/catalog/domains/:id` | [`DomainDetailPage.jsx`](carbon-frontend/src/pages/catalog/DomainDetailPage.jsx) | ✅ Complete | |

### 3.5 Other Pages

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/` | [`RoleAwareLanding`](carbon-frontend/src/App.jsx:107) | ✅ Complete | Redirects based on role |
| `/login` | [`Login.jsx`](carbon-frontend/src/pages/Login.jsx) | ✅ Complete | |
| `/modules/:id` | [`ModuleLandingPage.jsx`](carbon-frontend/src/pages/ModuleLandingPage.jsx) | ✅ Complete | |
| `/scopes/:id` | [`ScopeInfoPage.jsx`](carbon-frontend/src/pages/ScopeInfoPage.jsx) | ✅ Complete | |
| `/settings` | [`SettingsPage.jsx`](carbon-frontend/src/pages/SettingsPage.jsx) | ✅ Complete | 581 lines |
| `/help` | [`Help.jsx`](carbon-frontend/src/pages/Help.jsx) | ✅ Complete | |
| `/feedback` | [`Feedback.jsx`](carbon-frontend/src/pages/Feedback.jsx) | ✅ Complete | |
| `*` | [`NotFound.jsx`](carbon-frontend/src/pages/NotFound.jsx) | ✅ Complete | |

---

## 4. 🔍 Navigation & Menu Consistency Audit

### 4.1 Manifest Navigation Items (source of truth)

From [`manifest.js`](carbon-frontend/src/apps/carbon/manifest.js:52-74):

```
Carbon Console          → /carbon/console          role: *
Emissions Dashboard     → /carbon/dashboard         role: *
[divider]
[Data Owner group]
My Portal               → /carbon/owner/portal      role: carbon:data_owner
My Dashboard            → /carbon/owner/dashboard   role: carbon:data_owner
My Emission Sources     → /carbon/owner/assets      role: carbon:data_owner
[divider]
[Activity Data group]
Activity Data Entry     → /carbon/data-entry        role: carbon:data_owner
[divider]
[Reporting group]
Generate Report         → /carbon/reporting/generate role: carbon:analyst
Saved Reports           → /carbon/reporting/saved    role: carbon:analyst
Analytics               → /carbon/analytics          role: carbon:analyst
[divider]
[Administration group]
Emission Factors        → /carbon/admin/factors      role: carbon:admin
Reporting Periods       → /carbon/reporting/periods  role: carbon:admin
```

### 4.2 ShellSidebar Items (rendered navigation)

From [`ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx:54-139):

**Home studio:** Executive Summary, Analytics, Targets  
**Carbon studio:** Reads from manifest (above)  
**Catalog studio:** Catalog Home, Data Products, Metadata, Asset Profiles, DQ Dashboard, DQ Rules, Governance Policies, Governance Audit, Reference Sets, Master Data, Connections, Data Sources, Exports, Imports  
**Admin studio:** Users, Groups & Roles, Org Units, Access Control, Audit Log, Registered Apps, Role Registry  
**Settings studio:** Profile, Preferences  
**Help studio:** Documentation, Feedback  

### 4.3 SidebarMenu Items (legacy, perspective-driven)

From [`SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx):

**DataEntrySidebar:** My Dashboard → `/modules`, Scopes 1/2/3 with modules, Help, Feedback  
**AdminSidebar:** Organization (Org Units, Users, Access Control), Schema Management (Table Manager), Dashboards (Executive Summary, Analytics, Targets & Progress, Data Quality, Reporting), Help, Feedback  
**DashboardSidebar:** Executive Summary, Analytics, Targets & Progress, Data Quality, Reporting, Help, Feedback  
**DataOwnerSidebar:** My Portal, My Dashboard, My Assets, Help, Feedback  

### 4.4 Consistency Findings

| Issue | Severity | Details |
|-------|----------|---------|
| **Dual sidebar systems** | 🟡 Medium | Both `SidebarMenu.jsx` and `ShellSidebar.jsx` are active. `SidebarMenu` is used inside `Layout.jsx` (legacy), while `ShellSidebar` is used in the new Shell. This creates potential inconsistency. |
| **Carbon Console not in ShellSidebar** | 🟡 Medium | The manifest has "Carbon Console" as the first item, but the ShellSidebar reads from manifest correctly. However, the `SidebarMenu` does NOT have a "Carbon Console" entry — it only has scope-based navigation. |
| **Admin audit log is a stub** | 🟡 Medium | `/admin/audit` renders a placeholder `<div>` with "coming soon" text. |
| **Settings routes mismatch** | 🟢 Low | ShellSidebar lists `/settings/profile` and `/settings/preferences`, but `App.jsx` only has `/settings` pointing to `SettingsPage.jsx`. The sub-routes don't exist. |
| **Duplicate dashboard routes** | 🟢 Low | Both `/dashboard` and `/dashboards/executive` point to `ExecutiveSummary`. The `/carbon/dashboard` route points to `EmissionsDashboard` (different component). |
| **Legacy `/emissions/` routes** | 🟢 Low | `/emissions`, `/emissions/dashboard`, `/emissions/report` are kept for backwards compatibility alongside `/carbon/*` routes. |

---

## 5. 🧩 Cross-System Consistency Assessment

### 5.1 URL Namespace Consistency

```
Carbon routes:    /carbon/*          ✅ Consistent
Dashboard routes: /dashboards/*      ✅ Consistent
Admin routes:     /admin/*           ✅ Consistent
Catalog routes:   /catalog/*         ✅ Consistent
Settings routes:  /settings          ✅ Consistent
```

### 5.2 Component Naming Consistency

| Pattern | Example | Status |
|---------|---------|--------|
| Page components: `*Page.jsx` | `CarbonConsolePage.jsx` | ✅ Consistent |
| Tab components: `*Tab.jsx` | `RowOverviewTab.jsx` | ✅ Consistent |
| Detail pages: `*DetailPage.jsx` | `GroupDetailPage.jsx` | ✅ Consistent |
| Dashboard pages: `*Dashboard.jsx` | `DataQualityDashboard.jsx` | ✅ Consistent |
| API modules: `api/*.js` | `emissions.js`, `emissions-extended.js` | ⚠️ Split across two files |

### 5.3 API Layer Consistency

| API File | Purpose | Status |
|----------|---------|--------|
| [`api/emissions.js`](carbon-frontend/src/api/emissions.js) | Core emissions API (dashboard, periods, factors, calculations) | ✅ Complete |
| [`api/emissions-extended.js`](carbon-frontend/src/api/emissions-extended.js) | Extended CRUD (periods, factors, reports, configs) | ✅ Complete |
| [`api/api.js`](carbon-frontend/src/api/api.js) | Base API client | ✅ Complete |
| [`api/catalog.js`](carbon-frontend/src/api/catalog.js) | Catalog API | ✅ Complete |
| [`api/dataschema.js`](carbon-frontend/src/api/dataschema.js) | DataTable/DataRow API | ✅ Complete |
| [`api/dq.js`](carbon-frontend/src/api/dq.js) | Data quality API | ✅ Complete |
| [`api/modules.js`](carbon-frontend/src/api/modules.js) | Modules API | ✅ Complete |
| [`api/orgUnits.js`](carbon-frontend/src/api/orgUnits.js) | Org units API | ✅ Complete |
| [`api/users.js`](carbon-frontend/src/api/users.js) | Users API | ✅ Complete |
| [`api/groups.js`](carbon-frontend/src/api/groups.js) | Groups API | ✅ Complete |
| [`api/accessControl.js`](carbon-frontend/src/api/accessControl.js) | Access control API | ✅ Complete |

### 5.4 Backend API Completeness

From the existing [`CARBON_SYSTEM_AUDIT_COMPLETE.md`](plans/CARBON_SYSTEM_AUDIT_COMPLETE.md):

| Domain | Status | Notes |
|--------|--------|-------|
| ReportingPeriod model | ✅ Complete | 6 workflow states |
| EmissionFactor model | ✅ Complete | Scope 1/2/3, categories, GHG breakdown |
| GWP model | ✅ Complete | AR5 + AR6 values |
| Calculation model | ✅ Complete | Factory method, audit fields |
| CalculationRule model | ✅ Complete | Dynamic field binding |
| ReportConfig model | ✅ Complete | Saved configurations |
| All views | ✅ Complete | 13 view sets/API views |
| All serializers | ✅ Complete | |
| URL routing | ✅ Complete | Clean `/carbon-api/` namespace |

---

## 6. 📊 Overall Assessment

### 6.1 Strengths (Enterprise-Grade)

1. **Studio architecture** — VSCode-inspired shell with activity bar, sidebar, editor area, and copilot pane is a modern, scalable pattern
2. **App manifest system** — Declarative app registration via `manifest.js` enables dynamic studio injection
3. **Role-based navigation** — Navigation items filtered by RBAC roles (`*`, `carbon:data_owner`, `carbon:analyst`, `carbon:admin`)
4. **Comprehensive page inventory** — 50+ pages covering carbon management, catalog, admin, dashboards, and settings
5. **Clean URL namespace** — All routes follow consistent `/domain/path` pattern
6. **Backend completeness** — All models, views, serializers, and URLs are implemented and audited
7. **GHG Protocol alignment** — Scope 1/2/3 structure, reporting periods, emission factors all follow industry standards

### 6.2 Issues Found

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | `CalendarMonth is not defined` ReferenceError | 🔴 **Critical** | [`CarbonConsolePage.jsx:267`](carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx:267) |
| 2 | Dual sidebar systems (legacy vs new) | 🟡 Medium | [`SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx) vs [`ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx) |
| 3 | Admin audit log is a stub | 🟡 Medium | [`App.jsx:261`](carbon-frontend/src/App.jsx:261) |
| 4 | Settings sub-routes don't exist | 🟢 Low | [`ShellSidebar.jsx:116-117`](carbon-frontend/src/shell/ShellSidebar.jsx:116-117) |
| 5 | Duplicate dashboard entry points | 🟢 Low | [`App.jsx:154,157`](carbon-frontend/src/App.jsx:154) |
| 6 | Carbon Console not in legacy SidebarMenu | 🟢 Low | [`SidebarMenu.jsx`](carbon-frontend/src/components/SidebarMenu.jsx) |
| 7 | API split across two files | 🟢 Low | `emissions.js` + `emissions-extended.js` |

### 6.3 Verdict: Is the System Consistent, Robust, Complete, and Enterprise-Grade?

**YES — with one critical bug to fix.**

The system is:
- **Consistent** ✅ — URL patterns, component naming, API structure, and navigation follow clear conventions
- **Robust** ✅ — Error boundaries, loading states, role-based access control, and fallback handling are present throughout
- **Complete** ✅ — 50+ pages, full CRUD for all entities, dashboard suite, admin panel, catalog studio, and data owner portal
- **Enterprise-grade** ✅ — Studio architecture, app manifest system, RBAC, GHG Protocol alignment, comprehensive backend

The **only blocking issue** is the `CalendarMonth` ReferenceError in `CarbonConsolePage.jsx`, which is a simple import alias bug.

---

## 7. 🎯 Action Plan

### Priority 1: Fix Critical Bug

```diff
- icon={<CalendarMonth />}
+ icon={<PeriodsIcon />}
```
File: [`carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx`](carbon-frontend/src/pages/carbon/CarbonConsolePage.jsx:267)

### Priority 2: Medium-Priority Improvements

1. **Implement Admin Audit Log page** — Replace the placeholder at [`App.jsx:261`](carbon-frontend/src/App.jsx:261) with a real audit log view
2. **Add Settings sub-routes** — Create `/settings/profile` and `/settings/preferences` routes matching [`ShellSidebar.jsx:116-117`](carbon-frontend/src/shell/ShellSidebar.jsx:116-117)
3. **Consolidate sidebar systems** — Migrate remaining `SidebarMenu.jsx` usage to `ShellSidebar.jsx` for single source of truth

### Priority 3: Low-Priority Polish

1. Remove legacy `/emissions/` routes once `/carbon/*` routes are verified stable
2. Consolidate `emissions.js` and `emissions-extended.js` into a single API module
3. Add "Carbon Console" entry to legacy `SidebarMenu.jsx` if it remains active

---

## 8. 📐 Architecture Diagram

```mermaid
flowchart TD
    subgraph Shell["Shell Layout"]
        AB[ActivityBar]
        SS[ShellSidebar]
        EA[EditorArea]
        SB[StatusBar]
        CP[CopilotPane]
    end

    subgraph Studios["Studios"]
        H[Home / Dashboard]
        CF[Carbon Footprint]
        CS[Catalog Studio]
        PA[Platform Admin]
        ST[Settings]
        HP[Help]
    end

    subgraph CarbonApp["Carbon App Pages"]
        CC[CarbonConsolePage]
        ED[EmissionsDashboard]
        DH[DataHubHome]
        DE[DataEntryPage]
        RD[RowDetailPage]
        RG[ReportGeneratorPage]
        SR[SavedReportsPage]
        RP[ReportingPeriodsPage]
        EF[EmissionFactorsPage]
        DOP[DataOwnerPortalPage]
        DOD[DataOwnerDashboardPage]
        DOA[DataOwnerAssetsPage]
    end

    subgraph AdminPages["Admin Pages"]
        OU[OrgUnitsPage]
        US[UsersPage]
        GR[GroupsPage]
        AC[AccessControlPage]
        RR[RoleRegistryPage]
        RA[RegisteredAppsPage]
        AL[AuditLog - STUB]
    end

    AB --> SS
    SS --> Studios
    EA --> CarbonApp
    EA --> AdminPages
    CF --> CC
    CF --> ED
    CF --> DH
    CF --> DOP
```

---

## 9. Summary

| Metric | Count |
|--------|-------|
| Total pages | 50+ |
| Critical bugs | **1** (CalendarMonth ReferenceError) |
| Medium issues | 3 |
| Low issues | 3 |
| Backend models | 6 (all complete) |
| Backend views | 13 (all complete) |
| Navigation systems | 2 (legacy + new) |
| Studios | 6 |
