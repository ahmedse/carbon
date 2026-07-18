# Carbon Platform Completion Audit & Roadmap

**Date:** 2026-07-18  
**Status:** Planning  
**Context:** Post A0-A7 comprehensive review

---

## Executive Summary

This audit reviews the Carbon Data Trust Platform after completing RUNs A0-A7, mapping all studios, routes, and features to identify what's complete, what's missing, and what should be prioritized next.

### Current State Summary

**✅ Implemented & Working:**
- RBAC with global/org-scoped admin distinction
- Perspective-based UI (Data Entry/Dashboards/Admin)
- Data Hub with module browser, table navigation, scope filtering
- 5 executive dashboards with scoped data
- Schema management (Table Manager for admins)
- User/Org Unit/Access Control admin pages
- Settings page with profile/security/preferences
- Help & Feedback pages
- Emissions calculator (basic functionality)

**❌ Not Yet Implemented:**
- Data lineage visualization
- Evidence/attachment management UI
- Settings sub-pages (Profile/Preferences routes exist in sidebar but go to main settings)
- Advanced data quality rules UI
- Data catalog/governance UI
- Bulk data import/export UI
- Reports generation & export

**⚠️ Backend Exists, Frontend Missing:**
- Catalog app (Data Domains, Glossary, Tags, Asset Profiles, Governance Events)
- DQ app (Field Profiles, Table Profiles, Rules, Results) - only dashboard view exists
- MDM app (Reference Sets/Values, Org Units) - only org units admin exists

---

## Studio-by-Studio Audit

### 1. Home Studio (Dashboard) ✅ COMPLETE

**Activity Bar Icon:** DashboardIcon  
**Sidebar Items:**
- ✅ Executive Summary (`/dashboards/executive`) - **ExecutiveSummary.jsx**
- ✅ Analytics (`/dashboards/analytics`) - **AnalyticsDashboard.jsx**
- ✅ Targets (`/dashboards/targets`) - **TargetsDashboard.jsx**

**Additional Dashboard Routes:**
- ✅ Data Quality (`/dashboards/data-quality`) - **DataQualityDashboard.jsx**
- ✅ Reporting (`/dashboards/reporting`) - **ReportingDashboard.jsx**

**Status:** All dashboards implemented with real data visualization, scoped to user's context.

---

### 2. Emissions Studio (Emissions Calculator) ⚠️ PARTIAL

**Activity Bar Icon:** Co2Icon  
**Sidebar Items:**
- ✅ Dashboard (`/emissions/dashboard`) - **EmissionsDashboard.jsx**
- ✅ Report (`/emissions/report`) - **EmissionsReport.jsx**

**Backend APIs Available:**
- ✅ `/carbon-api/emissions/periods/` - ReportingPeriodViewSet
- ✅ `/carbon-api/emissions/factors/` - EmissionFactorViewSet
- ✅ `/carbon-api/emissions/gwp/` - GWPViewSet (read-only)
- ✅ `/carbon-api/emissions/calculations/` - CalculationViewSet
- ✅ `/carbon-api/emissions/rules/` - CalculationRuleViewSet

**Missing Frontend:**
- ❌ Emission factor management UI (CRUD for factors)
- ❌ Calculation rule builder UI
- ❌ GWP reference viewer
- ❌ Reporting period management
- ❌ Advanced calculation wizard

**Status:** Basic calculator works, but lacks admin/configuration UI for factors and rules.

---

### 3. Data Hub Studio (DataSchema) ✅ MOSTLY COMPLETE

**Activity Bar Icon:** StorageIcon  
**Sidebar Items:**
- ✅ Data Entry (`/dataschema`) - **DataHubHome.jsx** (module browser)
- ✅ Table Manager (`/schema-admin/table-manager`) - **TableManagerPage.jsx** (admin-only)
- ✅ Data Quality (`/dataschema/quality`) - **DataQualityView.jsx** (NEW in A7)

**Routes:**
- ✅ `/dataschema` - Module browser with scope filtering
- ✅ `/modules/:moduleId` - **ModuleLandingPage.jsx** (table grid for module)
- ✅ `/dataschema/entry/:moduleId/:tableId` - **DataEntryPage.jsx** → **TableDataPage.jsx**
- ✅ `/dataschema/quality` - Module-scoped data quality metrics
- ✅ `/schema-admin/table-manager` - Admin table/field CRUD

**Backend APIs:**
- ✅ `/carbon-api/dataschema/tables/` - DataTableViewSet
- ✅ `/carbon-api/dataschema/fields/` - DataFieldViewSet
- ✅ `/carbon-api/dataschema/rows/` - DataRowViewSet
- ✅ `/carbon-api/dataschema/schema-logs/` - SchemaChangeLogViewSet (read-only)

**Missing Features:**
- ❌ **Evidence/Attachment Management** - No UI for uploading/viewing evidence files
- ❌ **Bulk Import/Export** - No CSV/Excel import/export UI
- ❌ **Data Lineage Visualization** - No lineage/provenance tracking UI
- ❌ **Field-level validation rules UI** - Schema logs are read-only, no UI for DQ rules
- ❌ **Row-level comments/notes** - No collaboration features

**Status:** Core data entry works perfectly. Missing: attachments, lineage, bulk operations.

---

### 4. Admin Studio ✅ COMPLETE

**Activity Bar Icon:** AdminPanelSettingsIcon  
**Sidebar Items:**
- ✅ Users (`/admin/users`) - **UsersPage.jsx**
- ✅ Org Units (`/admin/org-units`) - **OrgUnitsPage.jsx**
- ✅ Access Control (`/admin/access`) - **AccessControlPage.jsx**

**Backend APIs:**
- ✅ `/carbon-api/accounts/users/` - UserViewSet
- ✅ `/carbon-api/accounts/roles/` - GroupViewSet (read-only)
- ✅ `/carbon-api/accounts/scoped-roles/` - ScopedRoleViewSet
- ✅ `/carbon-api/accounts/role-audit-logs/` - RoleAssignmentAuditLogViewSet (read-only)
- ✅ `/carbon-api/mdm/org-units/` - OrgUnitViewSet

**Status:** Fully functional admin suite. All CRUD operations work with proper RBAC.

---

### 5. Settings Studio ⚠️ PARTIAL

**Activity Bar Icon:** SettingsIcon  
**Sidebar Items (Defined):**
- ⚠️ Profile (`/settings/profile`) - **Route exists but goes to main SettingsPage**
- ⚠️ Preferences (`/settings/preferences`) - **Route exists but goes to main SettingsPage**

**Actual Implementation:**
- ✅ `/settings` - **SettingsPage.jsx** (single page with tabs)
- ✅ Tab: Profile (user info)
- ✅ Tab: Security (password change)
- ✅ Tab: Preferences (language, theme)
- ✅ Tab: Pulse Integration
- ✅ Tab: Keyboard Shortcuts

**Issue:** Sidebar defines `/settings/profile` and `/settings/preferences` routes, but App.jsx only has `/settings`. When user clicks sidebar items, they go to generic settings page.

**Fix Options:**
1. **Remove sub-routes from sidebar** - Keep single `/settings` page with tabs
2. **Add sub-routes to App.jsx** - Create separate pages for Profile/Preferences
3. **Use hash navigation** - `/settings#profile`, `/settings#preferences`

**Recommendation:** Option 1 (remove sub-routes, keep tab-based UI). Settings page is already well-designed.

---

### 6. Help Studio ✅ COMPLETE

**Activity Bar Icon:** HelpIcon  
**Sidebar Items:**
- ✅ Documentation (`/help`) - **Help.jsx**
- ✅ Feedback (`/feedback`) - **Feedback.jsx**

**Backend API:**
- ✅ `/carbon-api/core/feedback/` - FeedbackViewSet

**Status:** Both pages fully functional with rich content.

---

## Backend Apps Without Frontend

### 1. Catalog App (Data Governance) ❌ NO FRONTEND

**Backend APIs Available:**
- `/carbon-api/catalog/domains/` - DataDomainViewSet
- `/carbon-api/catalog/glossary/` - GlossaryTermViewSet
- `/carbon-api/catalog/tags/` - TagViewSet
- `/carbon-api/catalog/assets/` - AssetProfileViewSet
- `/carbon-api/catalog/governance-events/` - GovernanceEventViewSet (read-only)

**Purpose:** Data catalog for organizing tables, glossary terms, tagging, and tracking governance events.

**Missing Frontend:**
- Data domain management UI
- Glossary term dictionary
- Tag management & assignment
- Asset profile viewer
- Governance event log

**Priority:** MEDIUM - Useful for data governance maturity, but not blocking data entry.

---

### 2. DQ App (Data Quality) ⚠️ PARTIAL FRONTEND

**Backend APIs Available:**
- `/carbon-api/dq/profiles/` - FieldProfileViewSet (read-only)
- `/carbon-api/dq/table-profiles/` - TableProfileViewSet (read-only)
- `/carbon-api/dq/rules/` - DQRuleViewSet
- `/carbon-api/dq/results/` - DQResultViewSet (read-only)

**Existing Frontend:**
- ✅ DataQualityDashboard (org-wide metrics)
- ✅ DataQualityView (module-scoped metrics)

**Missing Frontend:**
- ❌ DQ Rule builder UI (create validation rules per field/table)
- ❌ Field/Table profile viewer (stats, distribution, nulls, etc.)
- ❌ DQ Result detail viewer (drill into failures)
- ❌ Rule execution scheduler

**Priority:** HIGH - Needed for data quality enforcement and audit readiness.

---

### 3. MDM App (Master Data Management) ⚠️ PARTIAL FRONTEND

**Backend APIs Available:**
- `/carbon-api/mdm/reference-sets/` - ReferenceSetViewSet
- `/carbon-api/mdm/reference-values/` - ReferenceValueViewSet
- `/carbon-api/mdm/org-units/` - OrgUnitViewSet

**Existing Frontend:**
- ✅ OrgUnitsPage (admin studio)

**Missing Frontend:**
- ❌ Reference Set manager (e.g., "Fuel Types", "Vehicle Categories")
- ❌ Reference Value manager (e.g., values within a set)
- ❌ Dropdown integration (data entry should use reference sets for picklists)

**Priority:** MEDIUM - Useful for standardizing data entry, but workarounds exist (free text).

---

## Missing Features Analysis

### 1. Evidence/Attachment Management ❌ CRITICAL GAP

**Problem:** Users can enter data but cannot attach evidence files (invoices, receipts, photos).

**Backend Status:** Unknown - need to check if attachment model exists

**Frontend Needs:**
- File upload widget in DataEntryPage
- Evidence viewer (list of attachments per row)
- Download/preview capability
- Drag-and-drop support

**User Story:**
```
As a data owner,
I want to attach evidence files to data rows,
So that auditors can verify my entries.
```

**Priority:** **CRITICAL** - Required for audit readiness.

---

### 2. Data Lineage Visualization ❌ HIGH PRIORITY

**Problem:** No way to track data provenance, transformations, or dependencies.

**Backend Status:** No lineage tracking detected in models

**Frontend Needs:**
- Lineage graph viewer (D3.js, React Flow, or similar)
- Lineage metadata capture (source system, transformation logic)
- Lineage panel (resizable drawer on right side)

**User Story:**
```
As an auditor,
I want to see where data came from and how it was calculated,
So that I can validate its accuracy.
```

**Proposed Architecture:**
```
┌─────────────────────────────────────────┐
│  DataEntryPage (main content)           │
│  ┌─────────────────────────────────┐    │
│  │  Table grid                     │    │
│  │  [Edit] [Save] [Add Row]        │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
                                    ↑
                         [Lineage] button opens →
                                    ↓
┌────────────────────────────────────────┐
│  Right Drawer (resizable, dockable)    │
│  ┌────────────────────────────────┐    │
│  │ [Lineage] [History] [Comments] │    │  ← Tabs
│  ├────────────────────────────────┤    │
│  │  Lineage Graph:                │    │
│  │  [Source] → [Transform] → [Row]│    │
│  │                                │    │
│  │  Source: Excel import          │    │
│  │  Date: 2026-07-15              │    │
│  │  User: john.doe                │    │
│  └────────────────────────────────┘    │
└────────────────────────────────────────┘
```

**Priority:** **HIGH** - Needed for transparency and trust.

---

### 3. Bulk Import/Export ❌ HIGH PRIORITY

**Problem:** Users must enter data row-by-row. No bulk upload from Excel/CSV.

**Backend Status:** DataRowViewSet likely supports bulk operations via REST

**Frontend Needs:**
- Import wizard (upload CSV/Excel → map columns → validate → submit)
- Export button (download current table as CSV/Excel)
- Template generator (download blank template with correct headers)

**User Story:**
```
As a data owner,
I want to upload 500 rows from an Excel file,
So that I don't have to type each one manually.
```

**Priority:** **HIGH** - Huge time saver for users.

---

### 4. DQ Rule Builder UI ❌ MEDIUM PRIORITY

**Problem:** DQ rules exist in backend but can only be managed via API/admin.

**Frontend Needs:**
- Rule builder UI (field selection, operator, threshold)
- Rule testing (run rule on sample data, see results)
- Rule management (list, edit, delete rules per table)

**User Story:**
```
As an admin,
I want to create a rule "Fuel Consumption > 0",
So that data owners can't enter negative values.
```

**Priority:** **MEDIUM** - Data quality is important but validation can be done manually for now.

---

### 5. Reports Generation & Export ❌ MEDIUM PRIORITY

**Problem:** No way to generate/export formatted reports (PDF, Excel).

**Backend Status:** ReportingDashboard exists but no export functionality

**Frontend Needs:**
- Export button on dashboards (PDF, Excel, PNG)
- Report scheduler (email reports weekly)
- Custom report builder (select metrics, date range, filters)

**Priority:** **MEDIUM** - Nice to have, but screenshots work as workaround.

---

## Proposed Next Steps (RUN A8+)

### RUN A8: Evidence & Attachments ⭐ RECOMMENDED NEXT

**Objective:** Enable users to attach evidence files to data rows

**Tasks:**
1. Check if attachment model exists in backend (DataRow foreign key?)
2. If not, create Evidence model + API endpoints
3. Add file upload widget to TableDataPage
4. Add evidence list viewer (shows attachments for selected row)
5. Add download/preview capability
6. Test with real files (PDFs, images, Excel)

**Acceptance Criteria:**
- ✅ User can upload evidence file for a data row
- ✅ User can view list of evidence files for a row
- ✅ User can download/preview evidence files
- ✅ Admin can see all evidence files in admin panel
- ✅ Evidence properly scoped to user's org unit

**Effort:** Medium (2-3 days)

---

### RUN A9: Bulk Import/Export

**Objective:** Enable bulk data operations via CSV/Excel

**Tasks:**
1. Create import wizard component
2. Add CSV/Excel parsing (use papaparse or xlsx library)
3. Add column mapping UI (match CSV headers to table fields)
4. Add validation preview (show errors before submit)
5. Implement bulk upsert API call
6. Add export button (download current table as CSV)
7. Add template generator (blank CSV with correct headers)

**Acceptance Criteria:**
- ✅ User can upload CSV/Excel file
- ✅ User can map columns to fields
- ✅ User sees validation errors before submitting
- ✅ User can bulk insert/update rows
- ✅ User can export table data as CSV
- ✅ User can download blank template

**Effort:** Medium-High (3-4 days)

---

### RUN A10: Data Lineage Panel

**Objective:** Add resizable drawer on right side showing lineage, history, comments

**Tasks:**
1. Design drawer component (resizable, dockable, collapsible)
2. Add lineage tab (show data provenance graph)
3. Add history tab (show row edit history)
4. Add comments tab (row-level collaboration)
5. Integrate with DataEntryPage
6. Add lineage metadata capture (source, user, timestamp)
7. Store lineage in backend (new model or extend DataRow)

**Acceptance Criteria:**
- ✅ User can open/close right drawer
- ✅ User can resize drawer
- ✅ User can see lineage graph for selected row
- ✅ User can see edit history for selected row
- ✅ User can add comments to a row
- ✅ Drawer state persists (localStorage)

**Effort:** High (4-5 days)

---

### RUN A11: DQ Rule Builder

**Objective:** Create UI for managing data quality rules

**Tasks:**
1. Create DQRuleManagerPage (admin-only or power users)
2. Add rule list view (table of existing rules per module)
3. Add rule form (field, operator, threshold, error message)
4. Add rule test function (run rule on sample data)
5. Add rule execution results viewer (drill into failures)
6. Integrate with DataEntryPage (show validation errors on save)

**Acceptance Criteria:**
- ✅ Admin can create DQ rule for a field
- ✅ Admin can test rule before saving
- ✅ Data owner sees validation errors when entering data
- ✅ Admin can view DQ results (which rows failed)
- ✅ Rules properly scoped to modules

**Effort:** Medium-High (3-4 days)

---

### RUN A12: Settings Sub-Routes Fix

**Objective:** Clean up Settings studio sidebar navigation

**Tasks:**
1. Remove `/settings/profile` and `/settings/preferences` from ShellSidebar
2. Keep single `/settings` route
3. Update sidebar to show just "Settings" link
4. Document tab-based navigation in SettingsPage

**Acceptance Criteria:**
- ✅ Sidebar shows "Settings" (not Profile/Preferences)
- ✅ Clicking Settings loads SettingsPage with tabs
- ✅ No 404 errors
- ✅ User can navigate tabs within SettingsPage

**Effort:** Low (30 minutes)

---

### RUN A13: Emissions Factor Management

**Objective:** Add UI for managing emission factors and calculation rules

**Tasks:**
1. Create EmissionFactorManagerPage (admin-only)
2. Add CRUD for emission factors (fuel type, EF value, unit, source)
3. Add CRUD for calculation rules (formula builder)
4. Add GWP reference viewer (read-only table)
5. Add reporting period manager (fiscal year, baseline year)

**Acceptance Criteria:**
- ✅ Admin can create/edit emission factors
- ✅ Admin can create/edit calculation rules
- ✅ Admin can view GWP reference data
- ✅ Admin can manage reporting periods
- ✅ Changes reflected in emissions calculator

**Effort:** Medium-High (3-4 days)

---

### RUN A14: Data Catalog UI (Optional)

**Objective:** Build frontend for catalog app (domains, glossary, tags, assets)

**Tasks:**
1. Create CatalogPage with tabs (Domains, Glossary, Tags, Assets)
2. Add CRUD for data domains
3. Add glossary term dictionary (search, view, add)
4. Add tag management (create tags, assign to tables)
5. Add asset profile viewer (table metadata, owner, quality score)
6. Add governance event log viewer

**Acceptance Criteria:**
- ✅ Admin can manage data domains
- ✅ Users can search glossary terms
- ✅ Admin can create/assign tags
- ✅ Users can view asset profiles
- ✅ Admin can view governance events

**Effort:** High (4-5 days)

**Priority:** MEDIUM - Nice to have for data governance maturity

---

## Summary & Recommendations

### Immediate Priorities (Must Have)

1. **RUN A8: Evidence & Attachments** ⭐⭐⭐
   - **Why:** Required for audit readiness
   - **Impact:** Critical - users can't prove data without evidence
   - **Effort:** Medium

2. **RUN A9: Bulk Import/Export** ⭐⭐⭐
   - **Why:** Massive time saver for users (500 rows = 500 manual entries vs 1 upload)
   - **Impact:** High - improves UX dramatically
   - **Effort:** Medium-High

3. **RUN A12: Settings Sub-Routes Fix** ⭐
   - **Why:** Quick win, removes navigation confusion
   - **Impact:** Low - cosmetic improvement
   - **Effort:** Low (30 min)

### Short-Term Priorities (Should Have)

4. **RUN A10: Data Lineage Panel** ⭐⭐
   - **Why:** Transparency and trust, auditor requirement
   - **Impact:** High - builds confidence in data
   - **Effort:** High

5. **RUN A11: DQ Rule Builder** ⭐⭐
   - **Why:** Enforces data quality at entry time (prevent bad data)
   - **Impact:** Medium-High - reduces errors
   - **Effort:** Medium-High

### Long-Term Priorities (Nice to Have)

6. **RUN A13: Emissions Factor Management** ⭐
   - **Why:** Makes emissions calculator fully self-service
   - **Impact:** Medium - admins can update factors without code changes
   - **Effort:** Medium-High

7. **RUN A14: Data Catalog UI** ⭐
   - **Why:** Data governance maturity, compliance
   - **Impact:** Medium - better organization and discoverability
   - **Effort:** High

---

## Recommended Sequence

```
A7 ✅ (DONE)
  ↓
A12 (Quick fix - 30 min)
  ↓
A8 (Evidence - Critical)
  ↓
A9 (Bulk Import - High UX impact)
  ↓
A10 (Lineage Panel - Auditor requirement)
  ↓
A11 (DQ Rules - Quality enforcement)
  ↓
A13 (Emissions factors - Nice to have)
  ↓
A14 (Catalog - Long-term governance)
```

---

## Architecture Recommendation: Right Panel Pattern

For lineage, history, comments, and other contextual features, implement a **resizable right panel** similar to VS Code's side panel:

**Features:**
- ✅ Resizable (drag divider left/right)
- ✅ Collapsible (hide when not needed)
- ✅ Dockable (persist state in localStorage)
- ✅ Multi-tab (Lineage | History | Comments | Evidence)
- ✅ Context-aware (shows data for selected row)

**Benefits:**
- Keeps main data grid prominent
- Provides rich context without modal dialogs
- Familiar UX pattern (developers know VS Code)
- Scalable (add more tabs as needed)

**Implementation:**
- Use Allotment (already in project) for resizable split
- Store panel state in localStorage
- Integrate with TableDataPage (pass selected row ID)

---

**Status:** Analysis complete. Ready for prioritization and RUN A8 planning.
