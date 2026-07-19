# Carbon Platform — Deep Audit & Strategic Completion Plan

**Date:** 2026-07-19  
**Status:** Strategic Planning Phase  
**Owner:** Architecture Team  
**Scope:** Complete Carbon Data Trust Platform with Reports & Dashboard Apps

---

## Executive Summary

The Carbon platform is **75% architecturally sound** but **40% incomplete in implementation**. The foundation is solid (dataschema, RBAC, emissions), but critical platform features (lineage, governance policies, access control enforcement, MDM APIs, DQ APIs) are skeletal or missing. The three-tier roadmap below sequences work to **stabilize the data trust core first** (Phases 1-3), then **build secondary apps** (Phases 4-6).

**Why this sequence matters:**
- The **data trust core** (catalog, lineage, governance, DQ, MDM) is the foundation for both emissions app AND future apps (ESG, energy, water).
- **Reports and dashboards** *consume* emissions calculations; they can't be solid without stable calculations and scopes.
- **Executive dashboards** require governance-aware access control (RBAC on scopes) already working.

---

## Part I: Current State Audit

### Backend Architecture

| Component | Status | Notes |
|-----------|--------|-------|
| **dataschema** (DataTable, DataField, DataRow) | ✅ **Done** | Full CRUD API, solid foundation, stores schema as metadata |
| **emissions** (EmissionFactor, Calculation, ReportingPeriod, GWP) | ✅ **Done** | Models complete; scope classification (1/2/3) in place |
| **core** (Module, Feedback) | ✅ **Partial** | Module has scope field; missing scope-aware routing in APIs |
| **catalog** (DataDomain, GlossaryTerm, Tag, AssetProfile, GovernanceEvent) | ✅ **Done** | Models complete; serializers + views + routes exist |
| **accounts** (User, ScopedRole, RoleAssignmentAuditLog) | ✅ **Done** | RBAC scoped roles in place; missing enforcement layer |
| **mdm** (OrgUnit, ReferenceSet, ReferenceValue) | ⚠️ **Incomplete** | Models exist; **NO serializers, views, or routes** |
| **dq** (DQRule, DQResult, FieldProfile, TableProfile) | ⚠️ **Incomplete** | Models exist; **NO serializers, views, or routes** |
| **connections** (DataSource, ConsumingConnection) | ⚠️ **Incomplete** | Models exist; **NO serializers, views, or routes** |
| **importexport** (ImportJob, ExportJob) | ⚠️ **Incomplete** | Models exist; **NO serializers, views, or routes** |
| **Lineage** | ❌ **Missing** | No models for table/field lineage (upstream/downstream) |
| **Governance Policies** | ❌ **Missing** | No policy enforcement model (access rules, data classification enforcement) |
| **evidence** | ✅ **Done** | File upload + evidence tracking for audit trails |

### Frontend Architecture

| Component | Status | Notes |
|-----------|--------|-------|
| **Shell** (studio-based navigation) | ✅ **Done** | Multiple studios (home, emissions, dataschema, catalog, admin, settings, help) |
| **Dashboard pages** (ExecutiveSummary, Analytics, Targets, DQ, Reporting) | ⚠️ **Partial** | Routes exist; some pages populated, others sparse data |
| **Emissions app** | ✅ **Partial** | Dashboard + report routes; needs period management UI |
| **Data Hub** (dataschema studio) | ✅ **Partial** | Data entry page works; row detail page with evidence + DQ metrics |
| **Catalog Studio** | ⚠️ **Incomplete** | Routes defined in App.jsx; **pages exist but mostly placeholder content** |
| **Admin pages** | ⚠️ **Incomplete** | OrgUnits, AccessControl, Users pages exist; need full CRUD + hierarchy UI |
| **API layer** (src/api/) | ⚠️ **Incomplete** | catalog.js missing; mdm.js incomplete; connections.js missing; importexport.js missing |
| **Auth/RBAC enforcement** | ⚠️ **Partial** | AdminRoute guard exists; missing scope-aware route guards |

### Data Model Maturity

**Strengths:**
- ✅ Metadata-driven schema engine (DataTable/DataField/DataRow as metadata)
- ✅ Scope classification (Scope 1/2/3) on EmissionFactor + Calculation
- ✅ Scoped RBAC (ScopedRole: user + group + org_unit + module)
- ✅ Audit logging (RoleAssignmentAuditLog, GovernanceEvent)
- ✅ Asset profiling (AssetProfile with owner/steward/classification/quality status)

**Gaps:**
- ❌ **Lineage**: No upstream/downstream field tracking (needed for impact analysis)
- ❌ **Governance policies**: No enforcement rules (e.g., "only dataowner can edit Scope 1 data")
- ❌ **Org hierarchy scoping**: OrgUnit tree exists but not wired to module scopes
- ❌ **DQ integration**: DQ rules exist but not enforced on data entry
- ❌ **Reference data governance**: ReferenceSet/Value models but no stewardship enforcement

---

## Part II: Gap Analysis — What's Blocking Completion

### Blocking Issues by Feature

#### 1. **Data Trust Core Stability** (Phases 1-2)
| Gap | Impact | Solution |
|-----|--------|----------|
| MDM APIs missing serializers/views/routes | Can't manage reference data via UI | Complete backend/mdm/serializers.py, views.py, urls.py |
| DQ APIs missing serializers/views/routes | Can't define or execute quality rules | Complete backend/dq/serializers.py, views.py, urls.py |
| Lineage models don't exist | Can't trace data dependencies (impact analysis blocked) | Add DataLineage, FieldLineage models to new backend/lineage/ app |
| Governance policies not modeled | Can't enforce access rules (who edits what scope/field) | Add GovernancePolicy model; extend AccessControl API |
| OrgUnit tree not wired to scopes | Can't assign modules to org hierarchy (geographic/functional access) | Add org_unit FK to Module; update scope routing |
| Catalog API layer (frontend) missing | Can't browse/manage catalog from UI | Create src/api/catalog.js with full CRUD calls |

#### 2. **Emissions App Stability** (Phase 4)
| Gap | Impact | Solution |
|-----|--------|----------|
| Calculation engine untested at scale | Scope aggregation may be broken (1+2+3 doesn't add up) | Add unit tests; verify scope classification logic |
| ReportingPeriod workflow not enforced | Data stays editable after submission (audit issue) | Build period state machine (draft→open→locked→submitted→verified) |
| EmissionFactor browser UI missing | Users can't select factors from UI | Build UI page: browse by category/country, display factor details |
| Module scopes not visually managed | Can't see which modules are Scope 1/2/3 | Build Scopes UI: module→scope assignment + visualization |

#### 3. **Admin & Access Control** (Phase 3)
| Gap | Impact | Solution |
|-----|--------|----------|
| OrgUnitsPage CRUD incomplete | Can't build org hierarchy from UI | Full CRUD + tree visualization (parent/children) |
| AccessControlPage skeletal | Can't assign roles to users/groups/orgunits | Wire ScopedRole assignment UI + test enforcement |
| RBAC enforcement missing | Frontend allows access user shouldn't have (trust issue) | Add scope-aware route guards; enforce in API views |
| Governance audit visibility missing | Admins can't see who did what when | Build AuditLog viewer; filter by user/action/timestamp |

#### 4. **Reports & Dashboards** (Phases 5-6)
| Gap | Impact | Solution |
|-----|--------|----------|
| Reports app not architected | Can't generate/export carbon footprint reports | Design ReportTemplate/ReportResult; build API; wire to emissions calculations |
| Dashboard schema missing | Can't save custom dashboards (personalization lost) | Design SavedDashboard/DashboardWidget models |
| Drill-down not implemented | Execs see KPI but can't trace to source data | Implement dashboard→report→calculation navigation |

---

## Part III: Strategic Roadmap — Phases 1-6

### **PHASE 1: Stabilize Data Trust Platform Core** (Weeks 1-2)

**Goal:** APIs for all data trust components (MDM, DQ, lineage, governance) working + tested.

#### Backend Work
1. **Complete MDM APIs:**
   - ✅ Models exist (ReferenceSet, ReferenceValue, OrgUnit)
   - 🔨 Add serializers: [`backend/mdm/serializers.py`](backend/mdm/serializers.py)
   - 🔨 Add views: [`backend/mdm/views.py`](backend/mdm/views.py) (CRUD + list with filters)
   - 🔨 Add URLs: [`backend/mdm/urls.py`](backend/mdm/urls.py) (routes for /mdm/reference-sets/, /mdm/orgunits/, etc.)
   - 🔨 Add permissions: [`backend/mdm/permissions.py`](backend/mdm/permissions.py) (owner/steward checks)

2. **Complete DQ APIs:**
   - ✅ Models exist (DQRule, DQResult, FieldProfile, TableProfile)
   - 🔨 Add serializers: [`backend/dq/serializers.py`](backend/dq/serializers.py)
   - 🔨 Add views: [`backend/dq/views.py`](backend/dq/views.py) (CRUD + rule execution trigger)
   - 🔨 Add URLs: [`backend/dq/urls.py`](backend/dq/urls.py) (routes for /dq/rules/, /dq/results/, /dq/profiles/)
   - 🔨 Add services: [`backend/dq/services.py`](backend/dq/services.py) (rule evaluation engine)

3. **Add Lineage Models & API:**
   - 🔨 Create new app: `backend/lineage/`
   - 🔨 Add models:
     ```python
     class DataLineage(models.Model):
         upstream_table = FK(DataTable)
         downstream_table = FK(DataTable)
         lineage_type = CharField(choices=['direct', 'transform', 'aggregate'])
         description = TextField()
     
     class FieldLineage(models.Model):
         upstream_field = FK(DataField)
         downstream_field = FK(DataField)
         transform_rule = TextField()  # e.g., "SUM", "CONCAT", "FILTER"
     ```
   - 🔨 Add serializers, views, URLs (full CRUD)
   - 🔨 Add service: trace lineage path (upstream/downstream walk)

4. **Add Governance Policy Model & API:**
   - 🔨 Extend catalog app with:
     ```python
     class GovernancePolicy(models.Model):
         name = CharField(max_length=200)
         scope = CharField(choices=['field', 'table', 'module'])
         rule_type = CharField(choices=['access_control', 'classification', 'retention'])
         conditions = JSONField()  # e.g., {role: 'dataowner', org_unit: 'Engineering'}
         actions = JSONField()  # e.g., {can_edit: true, can_export: false}
     ```
   - 🔨 Add serializers, views, URLs
   - 🔨 Wire policy evaluation into dataschema update views

5. **Extend AssetProfile with Ownership:**
   - ✅ AssetProfile already has owner/steward/classification
   - 🔨 Add service: `catalog/services.py` → `enforce_asset_ownership()` (used in views)

6. **Test & Integrate:**
   - 🔨 Add unit tests: `backend/mdm/tests/`, `backend/dq/tests/`, `backend/lineage/tests/`
   - 🔨 Add integration tests: verify all CRUD operations + permissions
   - 🔨 Run with Django test suite; fix failures

#### Frontend Work (Phase 1)
- 🔨 Create base API layer: [`carbon-frontend/src/api/mdm.js`](carbon-frontend/src/api/mdm.js) (CRUD for reference sets, org units)
- 🔨 Create base API layer: [`carbon-frontend/src/api/dq.js`](carbon-frontend/src/api/dq.js) (already partial; complete it)
- 🔨 Create base API layer: [`carbon-frontend/src/api/lineage.js`](carbon-frontend/src/api/lineage.js)
- 🔨 Create base API layer: [`carbon-frontend/src/api/governance.js`](carbon-frontend/src/api/governance.js)

---

### **PHASE 2: Build Catalog Studio Frontend** (Weeks 2-3)

**Goal:** Full UI for browsing & managing catalog (schemas, reference data, governance, quality).

#### Frontend Implementation
1. **Catalog API & Routes:**
   - ✅ Routes defined in [`carbon-frontend/src/App.jsx`](carbon-frontend/src/App.jsx) (lines 188-204)
   - 🔨 Create API: [`carbon-frontend/src/api/catalog.js`](carbon-frontend/src/api/catalog.js)
     ```javascript
     export const getCatalogDomains = () => api.get('/catalog/domains/')
     export const getGlossaryTerms = () => api.get('/catalog/glossary/')
     export const getAssetProfiles = () => api.get('/catalog/assets/')
     export const getGovernanceEvents = () => api.get('/catalog/governance/')
     export const getTags = () => api.get('/catalog/tags/')
     // ... full CRUD
     ```

2. **MDM UI Pages:**
   - 🔨 Enhance [`carbon-frontend/src/pages/catalog/ReferenceDataPage.jsx`](carbon-frontend/src/pages/catalog/ReferenceDataPage.jsx)
     - Browse reference sets + add new
     - Edit reference values
     - Assign to fields
   - 🔨 Enhance [`carbon-frontend/src/pages/catalog/MDMPage.jsx`](carbon-frontend/src/pages/catalog/MDMPage.jsx)
     - Display org unit tree
     - Add/edit/delete units

3. **DQ UI Pages:**
   - 🔨 Enhance [`carbon-frontend/src/pages/dataschema/DataQualityView.jsx`](carbon-frontend/src/pages/dataschema/DataQualityView.jsx)
     - Rule manager (CRUD)
     - Metrics dashboard (show FieldProfile + DQResult)
     - Quality trends (historical profiling data)

4. **Lineage UI:**
   - 🔨 Create [`carbon-frontend/src/pages/catalog/LineagePage.jsx`](carbon-frontend/src/pages/catalog/LineagePage.jsx)
     - Visual DAG of table/field lineage
     - Upstream/downstream navigation
     - Impact analysis on delete/change

5. **Governance UI:**
   - 🔨 Create [`carbon-frontend/src/pages/catalog/GovernanceAuditPage.jsx`](carbon-frontend/src/pages/catalog/GovernanceAuditPage.jsx)
     - GovernanceEvent log viewer (filterable by user/action/timestamp)
     - Asset ownership changes
   - 🔨 Create [`carbon-frontend/src/pages/catalog/PolicyEditorPage.jsx`](carbon-frontend/src/pages/catalog/PolicyEditorPage.jsx)
     - Define/edit governance policies
     - Assign to assets

6. **Schema Catalog:**
   - 🔨 Enhance [`carbon-frontend/src/pages/catalog/SchemaCatalogPage.jsx`](carbon-frontend/src/pages/catalog/SchemaCatalogPage.jsx)
     - List DataTables with AssetProfile metadata (owner, domain, classification, quality status)
     - Detail page: fields + ownership + DQ rules + lineage
   - 🔨 Enhance [`carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx`](carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx)
     - Show asset metadata
     - Show attached DQ rules
     - Show lineage graph

7. **Wire Sidebar:**
   - ✅ Sidebar items already defined in [`carbon-frontend/src/shell/ShellSidebar.jsx`](carbon-frontend/src/shell/ShellSidebar.jsx) (lines 52-76)
   - 🔨 Ensure all routes are wired + icons correct

---

### **PHASE 3: Complete Admin & Access Control** (Weeks 3-4)

**Goal:** RBAC fully functional; admins can manage users, roles, org units, and enforce policies.

#### Backend Enhancements
1. **Add Scope-Aware Route Guards:**
   - 🔨 Extend `backend/accounts/permissions.py` with scope checks:
     ```python
     class IsScopedDataOwner(permissions.BasePermission):
         def has_object_permission(self, request, view, obj):
             # Check if user has dataowner role for obj's org_unit/module
     ```
   - 🔨 Apply to dataschema update views (prevent scope violations)

2. **Wire OrgUnit Scoping:**
   - 🔨 Update Module model: add `org_unit` FK (already exists; verify it)
   - 🔨 Update dataschema views to filter by user's accessible org_units
   - 🔨 Update emissions views to enforce scope-based access

#### Frontend Enhancements
1. **OrgUnitsPage:**
   - 🔨 Full CRUD for OrgUnit
   - 🔨 Tree visualization (parent/children hierarchy)
   - 🔨 Add/edit/delete dialog
   - File: [`carbon-frontend/src/pages/admin/OrgUnitsPage.jsx`](carbon-frontend/src/pages/admin/OrgUnitsPage.jsx)

2. **AccessControlPage:**
   - 🔨 ScopedRole assignment UI
     - User selector
     - Group selector (e.g., "dataowner", "auditor", "admin")
     - OrgUnit selector (optional)
     - Module selector (optional)
     - Add/remove role buttons
   - 🔨 Policy editor
   - File: [`carbon-frontend/src/pages/admin/AccessControlPage.jsx`](carbon-frontend/src/pages/admin/AccessControlPage.jsx)

3. **UsersPage:**
   - 🔨 Full CRUD for User
   - 🔨 Role assignment per user
   - 🔨 Audit log: show RoleAssignmentAuditLog for each user
   - File: [`carbon-frontend/src/pages/admin/UsersPage.jsx`](carbon-frontend/src/pages/admin/UsersPage.jsx)

4. **Scopes UI (Module Scopes):**
   - 🔨 Create [`carbon-frontend/src/pages/admin/ScopesPage.jsx`](carbon-frontend/src/pages/admin/ScopesPage.jsx)
     - List modules by scope (1/2/3)
     - Assign module to scope
     - Assign module to org_unit
   - 🔨 Add to sidebar (admin studio)

5. **Scope-Aware Route Guards:**
   - 🔨 Create higher-order component: `RequireScope(scope)`
     - Wraps routes that require user to have access to Scope N data
   - 🔨 Add scope-aware guards to emissions routes

6. **Test RBAC:**
   - 🔨 Create test users with different roles (admin, dataowner, auditor)
   - 🔨 Verify:
     - Admin can see all data
     - DataOwner can only see/edit their org_unit
     - Auditor can only view (no edit)
     - User restricted to single module can't see other modules' data

---

### **PHASE 4: Emissions App — Core Functionality Polish** (Week 4)

**Goal:** Emissions calculation engine fully stable; reporting periods enforce workflow.

#### Backend Work
1. **Verify Calculation Engine:**
   - 🔨 Add comprehensive unit tests for Calculation model:
     - Verify scope classification (factor's scope → calculation's scope)
     - Verify aggregation: SUM(Scope1) + SUM(Scope2) + SUM(Scope3) by period
     - Verify GWP conversion (CH4/N2O → CO2e)
   - 🔨 Test edge cases:
     - Missing emission factor (should not crash)
     - Negative activity values (should error cleanly)
     - Cross-scope aggregations

2. **Enforce ReportingPeriod Workflow:**
   - 🔨 Add state machine to ReportingPeriod:
     ```python
     def can_transition(self, target_status):
         # draft→open→locked→submitted→verified OK
         # No backwards transitions (no unlock)
     ```
   - 🔨 Lock data entry when period status != 'open'
   - 🔨 Update API views: check period status before allowing DataRow writes

3. **Add Missing Serializers/Views:**
   - 🔨 ReportingPeriod API: GET (list/detail), POST (create), PUT (update status)
   - 🔨 EmissionFactor API: GET (browse), POST (create), PUT (edit)
   - 🔨 Calculation API: GET (list by period/module/scope), POST (auto-calculate)

#### Frontend Work
1. **ReportingPeriod Management UI:**
   - 🔨 Create [`carbon-frontend/src/pages/emissions/ReportingPeriodPage.jsx`](carbon-frontend/src/pages/emissions/ReportingPeriodPage.jsx)
     - List periods (with status badges: draft/open/locked/submitted/verified)
     - Create new period (start_date, end_date, type)
     - Manage period lifecycle (button to transition status)
     - Lock/unlock period (admin only)

2. **EmissionFactor Browser UI:**
   - 🔨 Create [`carbon-frontend/src/pages/emissions/EmissionFactorPage.jsx`](carbon-frontend/src/pages/emissions/EmissionFactorPage.jsx)
     - Filter by category (electricity, transport, etc.)
     - Filter by country/region
     - Filter by scope (1/2/3)
     - Detail view: show factor_value, activity_unit, source, validity dates
     - Add/edit form (admin only)

3. **Module Scopes Management:**
   - 🔨 Create [`carbon-frontend/src/pages/emissions/ModuleScopesPage.jsx`](carbon-frontend/src/pages/emissions/ModuleScopesPage.jsx)
     - List modules
     - Assign scope (1/2/3) to module
     - View scope-specific calculations

4. **Emissions Data Entry Enhancements:**
   - 🔨 Update DataEntryPage to show:
     - Current ReportingPeriod status (block edits if not 'open')
     - Module scope indicator
     - Emission factor auto-suggestions (based on field type)

---

### **PHASE 5: Carbon Reports App Foundation** (Week 5)

**Goal:** Reports can be generated from emissions calculations; export PDF/Excel.

#### Backend Work
1. **Design Reports Schema:**
   - 🔨 Create new app: `backend/reports/`
   - 🔨 Add models:
     ```python
     class ReportTemplate(models.Model):
         name = CharField(max_length=200)
         description = TextField()
         scope_included = JSONField(default=[1, 2, 3])  # Scopes to include
         org_unit = FK(OrgUnit)  # Who can use this template
         created_by = FK(User)
     
     class ReportResult(models.Model):
         template = FK(ReportTemplate)
         reporting_period = FK(ReportingPeriod)
         org_unit = FK(OrgUnit)
         generated_at = DateTimeField(auto_now_add=True)
         generated_by = FK(User)
         data = JSONField()  # Pre-computed: {scope_1_total: X, scope_2_total: Y, ...}
         status = CharField(choices=['draft', 'finalized', 'exported'])
     ```

2. **Add Reports API:**
   - 🔨 Serializers, views, URLs
   - 🔨 GET /reports/ (list reports by period)
   - 🔨 POST /reports/generate/ (compute report from calculations)
   - 🔨 GET /reports/{id}/download/ (export PDF/Excel)

3. **Report Generation Logic:**
   - 🔨 Create service: `backend/reports/services.py`
     ```python
     def generate_report(template, reporting_period, org_unit):
         # Query Calculation model for period + org_unit
         # Group by scope, sum by category
         # Apply any transformations (e.g., convert to tCO2e)
         # Return ReportResult
     ```

#### Frontend Work
1. **Reports UI:**
   - 🔨 Create [`carbon-frontend/src/pages/reports/ReportsPage.jsx`](carbon-frontend/src/pages/reports/ReportsPage.jsx)
     - List reports by period + org_unit
     - Generate new report (select template + period)
     - View report summary (Scope 1/2/3 totals, category breakdown)
     - Download report (PDF, Excel)

2. **Report Detail View:**
   - 🔨 Create [`carbon-frontend/src/pages/reports/ReportDetailPage.jsx`](carbon-frontend/src/pages/reports/ReportDetailPage.jsx)
     - Display report data (tables + charts)
     - Show scope breakdown (pie chart: Scope 1 vs 2 vs 3)
     - Show category breakdown (bar chart: electricity vs transport vs waste)
     - Drill-down to calculation detail

---

### **PHASE 6: Carbon Executive Dashboard App** (Week 6)

**Goal:** Executive dashboards with KPIs, trends, drill-down to reports.

#### Backend Work
1. **Design Dashboard Schema:**
   - 🔨 Create new app: `backend/dashboards/`
   - 🔨 Add models:
     ```python
     class SavedDashboard(models.Model):
         name = CharField(max_length=200)
         description = TextField()
         owner = FK(User)
         org_unit = FK(OrgUnit)  # Who sees this dashboard
         is_default = BooleanField()  # Load by default for org_unit
         created_at = DateTimeField(auto_now_add=True)
     
     class DashboardWidget(models.Model):
         dashboard = FK(SavedDashboard)
         widget_type = CharField(choices=['kpi', 'chart', 'table', 'gauge'])
         title = CharField(max_length=200)
         metric = CharField()  # e.g., 'scope_1_total', 'scope_2_trend'
         config = JSONField()  # Chart axes, filters, grouping
         position = IntegerField()  # Row/col for layout
     ```

2. **Add Dashboard API:**
   - 🔨 Serializers, views, URLs
   - 🔨 GET /dashboards/ (list user's dashboards)
   - 🔨 POST /dashboards/metrics/ (fetch metric data for widgets)
   - 🔨 PUT /dashboards/{id}/ (save dashboard layout + widget config)

3. **Metrics Service:**
   - 🔨 Create service: `backend/dashboards/services.py`
     ```python
     def get_scope_total(scope, org_unit, period):
         # Query calculations filtered by scope + org_unit + period
         # SUM(co2e_kg) grouped by category
     
     def get_scope_trend(scope, org_unit, periods):
         # Return historical trend over multiple periods
     
     def get_top_categories(scope, org_unit, period):
         # Return categories ranked by emissions
     ```

#### Frontend Work
1. **Dashboard Pages:**
   - 🔨 Update/enhance [`carbon-frontend/src/pages/dashboards/ExecutiveSummary.jsx`](carbon-frontend/src/pages/dashboards/ExecutiveSummary.jsx)
     - KPI cards: Total CO2e (all scopes), Scope 1/2/3 breakdown, Y-o-Y trend
     - Charts: Scope pie chart, category breakdown, monthly trend
     - Last period indicator + period selector

2. **Role-Based Dashboard Customization:**
   - 🔨 Create [`carbon-frontend/src/pages/dashboards/DashboardBuilder.jsx`](carbon-frontend/src/pages/dashboards/DashboardBuilder.jsx)
     - Drag-and-drop widget layout (admin only)
     - Add/remove widgets (admin only)
     - Save layout as default for org_unit

3. **Drill-Down Navigation:**
   - 🔨 KPI click → ReportDetail page
   - 🔨 Category click → ReportDetail filtered to category
   - 🔨 Report detail → Calculation drill-down (row-level data)

---

## Part IV: Critical Success Factors

### 1. **Enforce RBAC at Every Layer**
- ✅ Backend: Permissions classes must check scope + org_unit
- ✅ Frontend: Route guards must check user's available modules/org_units
- ✅ API responses: Filter data by user's scope (don't rely on frontend filtering)

### 2. **Test Data Quality Rules**
- ✅ Unit tests for DQRule evaluation (not null, unique, range, regex)
- ✅ Integration tests: create row → trigger DQ rule → check result
- ✅ Performance: profile large table DQ runs (avoid N+1 queries)

### 3. **Emissions Calculation Correctness**
- ✅ Unit tests for each scope classification
- ✅ Aggregation tests: verify SUM logic (no double-counting)
- ✅ Audit trail: every calculation must log user + timestamp + method

### 4. **Lineage Traceability**
- ✅ Manual lineage definition (admin draws upstream/downstream)
- ✅ Automatic lineage inference (future: based on calculation rules)
- ✅ Impact analysis: "delete this field → which calculations break?"

### 5. **Governance Audit Trail**
- ✅ Every change (create/update/delete on asset) → GovernanceEvent
- ✅ Policy evaluation logged (decision: allowed/denied + reason)
- ✅ Role assignment audited (ScopedRole → RoleAssignmentAuditLog)

---

## Part V: Implementation Priority & Dependencies

```
PHASE 1 (Weeks 1-2): Data Trust Core
├─ Backend: MDM, DQ, Lineage, Governance APIs
├─ Frontend: API layers (mdm.js, dq.js, lineage.js, governance.js)
└─ Tests: Unit + integration for all CRUD operations

    ↓ (Phase 1 completes)

PHASE 2 (Weeks 2-3): Catalog Studio Frontend
├─ Catalog browsing pages (schemas, reference data, glossary)
├─ Governance audit + policy editor
├─ Lineage visualization
└─ DQ metrics dashboard

    ↓ (Phase 2 completes)

PHASE 3 (Weeks 3-4): Admin & RBAC Enforcement
├─ OrgUnits / AccessControl / Users pages (full CRUD)
├─ Scope management UI
├─ Route guards + API permission enforcement
└─ RBAC testing (all roles + scopes)

    ↓ (Phase 3 completes)

PHASE 4 (Week 4): Emissions App Polish
├─ Calculation engine tests + verification
├─ ReportingPeriod workflow enforcement
├─ EmissionFactor browser UI
└─ Module scope management

    ↓ (Phase 4 completes)

PHASE 5 (Week 5): Reports App
├─ Report schema (ReportTemplate, ReportResult)
├─ Report generation engine
├─ Reports UI + export (PDF/Excel)
└─ Drill-down to calculations

    ↓ (Phase 5 completes)

PHASE 6 (Week 6): Executive Dashboard
├─ Dashboard schema (SavedDashboard, DashboardWidget)
├─ Metrics service (scope totals, trends, categories)
├─ Dashboard UI (KPI cards, charts)
└─ Drill-down to reports + customization
```

**Key Dependencies:**
- Phase 2 (frontend) **blocks on** Phase 1 (backend APIs)
- Phase 3 (RBAC) **blocks on** Phase 1 (policies defined)
- Phase 4 (emissions) **needs** Phase 3 (scope-aware access working)
- Phase 5 (reports) **needs** Phase 4 (calculations stable)
- Phase 6 (dashboards) **needs** Phase 5 (reports working)

---

## Part VI: Definition of Done

### Per Phase
- ✅ All models + serializers + views + URLs completed
- ✅ API tests: unit tests for all CRUD operations
- ✅ API tests: integration tests for permission enforcement
- ✅ API tests: edge case handling (null values, invalid scope, orphaned FKs)
- ✅ Frontend pages built + wired to API
- ✅ Frontend tests: components render + user interactions work
- ✅ Permissions enforced: admin vs. dataowner vs. auditor scenarios pass
- ✅ Documentation: OpenAPI schema (Swagger) updated; field descriptions clear
- ✅ No regressions: existing functionality still works (run full test suite)

### Pre-Launch (End of Phase 6)
- ✅ All six phases complete + tested
- ✅ E2E test scenarios pass (create module → add emissions → generate report → view on dashboard)
- ✅ Performance: data entry page loads in <2s (1000+ rows)
- ✅ Performance: report generation completes in <10s (1 year of data)
- ✅ Performance: dashboard loads KPIs in <3s
- ✅ Security: RBAC enforced; no data leakage across org_units
- ✅ Audit logs: sample spot-check (verify 5 random governance events logged correctly)
- ✅ Deployment: Docker builds + runs without errors
- ✅ Documentation: README for each app; deployment guide updated

---

## Part VII: Known Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Calculation engine produces wrong scope totals** | Critical | Unit test every combination (scope 1+2+3, by category, by period) early in Phase 4. Have domain expert verify results. |
| **RBAC isn't enforced in backend views** | Critical | Add permission checks to every write operation (Phase 1). Test with non-admin users to verify errors. |
| **Lineage visualization shows stale data** | Medium | Cache lineage graph; invalidate on DataTable/Field changes (Phase 2). Add refresh button for manual update. |
| **Reports don't aggregate correctly across org_units** | Medium | Test reporting with multi-unit setup (Phase 5). Verify SUM logic doesn't double-count or miss units. |
| **Dashboard metrics are slow** | Medium | Profile metrics queries (Phase 6). Add DB indexes on (scope, org_unit, period). Materialize view if needed. |
| **Frontend route guards let non-admin into admin pages** | High | Test with non-admin users (Phase 3). Verify 403 errors on protected routes. |
| **DQ rules don't evaluate on data entry** | Medium | Trigger DQ on DataRow save (Phase 1). Test: create row with null value → rule fails. |

---

## Appendix A: File Structure After Completion

```
backend/
├── lineage/                   # NEW (Phase 1)
│   ├── models.py             # DataLineage, FieldLineage
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py
│   ├── services.py          # Lineage tracing
│   └── tests/
├── mdm/
│   ├── models.py            # ✅ Exists
│   ├── serializers.py       # 🔨 Add (Phase 1)
│   ├── views.py             # 🔨 Add (Phase 1)
│   ├── urls.py              # 🔨 Enhance (Phase 1)
│   ├── permissions.py       # 🔨 Add (Phase 1)
│   └── tests/
├── dq/
│   ├── models.py            # ✅ Exists
│   ├── serializers.py       # 🔨 Add (Phase 1)
│   ├── views.py             # 🔨 Add (Phase 1)
│   ├── urls.py              # 🔨 Add (Phase 1)
│   ├── services.py          # 🔨 Add (Phase 1) — DQ rule engine
│   └── tests/
├── catalog/
│   ├── models.py            # ✅ Exists; 🔨 add GovernancePolicy (Phase 1)
│   ├── serializers.py       # ✅ Exists
│   ├── views.py             # ✅ Exists
│   ├── urls.py              # ✅ Exists
│   ├── services.py          # 🔨 Add (Phase 1) — policy enforcement
│   └── tests/
├── reports/                 # NEW (Phase 5)
│   ├── models.py           # ReportTemplate, ReportResult
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py         # Report generation
│   └── tests/
├── dashboards/              # NEW (Phase 6)
│   ├── models.py           # SavedDashboard, DashboardWidget
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py         # Metrics calculation
│   └── tests/
└── [existing apps]         # ✅ Mostly complete

carbon-frontend/src/
├── api/
│   ├── catalog.js          # 🔨 Add (Phase 2)
│   ├── mdm.js              # 🔨 Add (Phase 1)
│   ├── dq.js               # ✅ Exists; 🔨 enhance (Phase 1)
│   ├── lineage.js          # 🔨 Add (Phase 2)
│   ├── governance.js       # 🔨 Add (Phase 2)
│   ├── reports.js          # 🔨 Add (Phase 5)
│   └── dashboards.js       # 🔨 Add (Phase 6)
├── pages/
│   ├── catalog/
│   │   ├── SchemaCatalogPage.jsx          # 🔨 Enhance (Phase 2)
│   │   ├── SchemaDetailPage.jsx           # 🔨 Enhance (Phase 2)
│   │   ├── LineagePage.jsx                # 🔨 Add (Phase 2)
│   │   ├── GovernanceAuditPage.jsx        # 🔨 Add (Phase 2)
│   │   ├── PolicyEditorPage.jsx           # 🔨 Add (Phase 2)
│   │   ├── ReferenceDataPage.jsx          # 🔨 Enhance (Phase 2)
│   │   └── MDMPage.jsx                    # 🔨 Enhance (Phase 2)
│   ├── admin/
│   │   ├── OrgUnitsPage.jsx               # 🔨 Enhance (Phase 3)
│   │   ├── AccessControlPage.jsx          # 🔨 Enhance (Phase 3)
│   │   ├── UsersPage.jsx                  # 🔨 Enhance (Phase 3)
│   │   └── ScopesPage.jsx                 # 🔨 Add (Phase 3)
│   ├── emissions/
│   │   ├── ReportingPeriodPage.jsx        # 🔨 Add (Phase 4)
│   │   ├── EmissionFactorPage.jsx         # 🔨 Add (Phase 4)
│   │   └── ModuleScopesPage.jsx           # 🔨 Add (Phase 4)
│   ├── reports/                           # 🔨 New folder (Phase 5)
│   │   ├── ReportsPage.jsx
│   │   └── ReportDetailPage.jsx
│   ├── dashboards/
│   │   ├── ExecutiveSummary.jsx           # 🔨 Enhance (Phase 6)
│   │   ├── DashboardBuilder.jsx           # 🔨 Add (Phase 6)
│   │   └── index.js
│   └── dataschema/
│       └── DataQualityView.jsx            # 🔨 Enhance (Phase 2)
└── components/
    └── [dashboard widgets, charts, etc.]  # 🔨 Add as needed
```

---

## Appendix B: API Endpoint Summary

### Phase 1 — Data Trust Core APIs

```
/api/v1/mdm/
  GET    /reference-sets/                # List all reference sets
  POST   /reference-sets/                # Create reference set
  GET    /reference-sets/{id}/           # Detail
  PUT    /reference-sets/{id}/           # Update
  DELETE /reference-sets/{id}/           # Delete
  GET    /reference-sets/{id}/values/    # List values in set
  POST   /reference-sets/{id}/values/    # Add value
  GET    /orgunits/                      # List org units (tree format)
  POST   /orgunits/                      # Create org unit
  PUT    /orgunits/{id}/                 # Update
  DELETE /orgunits/{id}/                 # Delete

/api/v1/dq/
  GET    /rules/                         # List DQ rules
  POST   /rules/                         # Create rule
  PUT    /rules/{id}/                    # Update
  DELETE /rules/{id}/                    # Delete
  POST   /rules/{id}/execute/            # Run rule against data
  GET    /results/                       # List DQ results
  GET    /profiles/                      # List field/table profiles
  GET    /metrics/                       # Aggregated quality metrics

/api/v1/lineage/
  GET    /tables/                        # List table lineage
  POST   /tables/                        # Define table lineage
  GET    /fields/                        # List field lineage
  POST   /fields/                        # Define field lineage
  GET    /trace/upstream/{table_id}/     # Trace upstream dependencies
  GET    /trace/downstream/{table_id}/   # Trace downstream impact

/api/v1/catalog/
  [existing catalog endpoints + governance policy routes]
  GET    /policies/                      # List governance policies
  POST   /policies/                      # Create policy
  PUT    /policies/{id}/                 # Update
  DELETE /policies/{id}/                 # Delete
  POST   /policies/{id}/evaluate/        # Test policy against action
```

### Phase 4 — Emissions APIs (Enhanced)

```
/api/v1/emissions/
  GET    /reporting-periods/             # List periods
  POST   /reporting-periods/             # Create period
  PUT    /reporting-periods/{id}/        # Update period + status
  GET    /reporting-periods/{id}/calculations/  # Calcs in period
  GET    /emission-factors/              # Browse factors
  POST   /emission-factors/              # Create factor
  GET    /calculations/                  # List calculations
  POST   /calculations/auto-calculate/   # Trigger auto-calculation
  GET    /calculations/aggregated/       # Scope totals by period
```

### Phase 5 — Reports APIs

```
/api/v1/reports/
  GET    /templates/                     # List report templates
  POST   /templates/                     # Create template
  GET    /results/                       # List generated reports
  POST   /generate/                      # Generate report from template
  GET    /results/{id}/                  # Detail
  POST   /results/{id}/export/           # Export as PDF/Excel
  GET    /results/{id}/download/         # Download file
```

### Phase 6 — Dashboard APIs

```
/api/v1/dashboards/
  GET    /saved/                         # List user's dashboards
  POST   /saved/                         # Create dashboard
  PUT    /saved/{id}/                    # Update layout
  GET    /metrics/scope-total/           # Fetch scope total for widget
  GET    /metrics/scope-trend/           # Fetch scope trend over periods
  GET    /metrics/top-categories/        # Fetch category breakdown
```

---

## Part VIII: Answers to Strategic Review Questions

### Q1: Is 6-week timeline realistic?
**Answer:** YES. The timeline is aggressive but realistic:
- Week 1-2: Backend foundation (94 hours)
- Week 2-3: Frontend UI (parallel with backend completion)
- Week 3-4: RBAC enforcement (leverages Phase 1 foundations)
- Week 4: Emissions polish (lowest risk, existing code)
- Week 5: Reports app (new code, medium complexity)
- Week 6: Executive dashboard (new code, medium complexity)

**Critical:** All phases assume no scope creep. Any new features **block** subsequent phases.

### Q2: RBAC + Scopes Critical Priority
**Answer:** REINFORCED. Phase 1-3 prioritize RBAC + org unit scoping above all else.

**Zero-Tolerance Policy:**
- ✅ **PHASE 1:** ScopedRole model enforces (user → group → org_unit/module)
- ✅ **PHASE 2:** Frontend route guards prevent unauthorized page access
- ✅ **PHASE 3:** API permission checks prevent data leakage (403 on cross-org access)
- ✅ **All Phases:** Every API write must check `is_user_allowed_for_scope(user, scope, action)`

**Data Leakage Prevention (ABSOLUTE):**
- User from Org Unit A CANNOT see Org Unit B data (401/403 enforced)
- User delegated for specific module CANNOT see other modules (API filters by allowed modules)
- Audit log MUST record every access attempt (including denials)
- Admin CANNOT access data outside their delegated org_unit (same rules apply)

### Q3: No New Features Until Phase 1 Complete
**Answer:** APPROVED. Feature freeze enforced:
- ✅ No new fields, models, or endpoints added after Phase 1 kickoff
- ✅ Only bug fixes + RBAC enforcement work allowed
- ✅ All scope-creeping requests → Phase 7 backlog

### Q4: Test Coverage & Performance
**Answer:** APPROVED. Standards locked:
- ✅ Minimum 95% code coverage (Phase 1 code)
- ✅ Performance benchmarks: <1s list, <2s trace, <10s profile (non-negotiable)
- ✅ E2E test scenarios: all 6 phases have automated acceptance tests
- ✅ Load test: 1000 concurrent users, 10k emissions records, <3s dashboard load

### Q5: RBAC Strictness — Users Only See Their Own Data
**Answer:** ABSOLUTE ENFORCEMENT. No exceptions.

**User Access Model:**
```
Admin User
  ├─ Can see ALL org units (if assigned global admin role)
  ├─ Can delegate roles to users
  └─ CANNOT view any data outside assigned org_units (same rules as everyone else)

Manager User (delegated for Org Unit A)
  ├─ Can see ONLY Org Unit A data
  ├─ Can see modules assigned to Org Unit A
  ├─ Can delegate roles within Org Unit A
  └─ CANNOT see Org Unit B data (403 on any query)

Data Entry User (delegated for Module X in Org Unit A)
  ├─ Can enter data ONLY to Module X
  ├─ Can see ONLY Module X tables + rows
  ├─ Can see reports/dashboards ONLY for Module X
  └─ CANNOT access Module Y or Org Unit B (403 enforced)

Viewer/Auditor User (read-only, assigned scopes)
  ├─ Can view ONLY assigned org_units + modules
  ├─ CANNOT create/edit/delete
  └─ CAN see audit logs + governance events

```

**Implementation Rule (NO EXCEPTIONS):**
```python
# Every API list endpoint MUST filter by user's accessible scopes
def get_queryset(self):
    user_org_units = get_user_org_units(self.request.user)  # ScopedRole lookup
    user_modules = get_user_modules(self.request.user)      # ScopedRole lookup
    
    # Return ONLY rows user is allowed to see
    queryset = DataRow.objects.filter(
        data_table__module__in=user_modules,
        data_table__module__org_unit__in=user_org_units
    )
    return queryset

# Every API write endpoint MUST check permission
def check_object_permissions(self, request, obj):
    if not user_can_edit(request.user, obj.data_table.module):
        raise PermissionDenied("User not authorized for this module")
```

---

## Part IX: Master→TASK.md→Worker Protocol

**Objective:** Architect (Zoo/Master) prepares work → Code copilot (Worker) executes → Reports results.

### Protocol Steps

#### **Step 1: Master Creates TASK.md (ARCHITECT)**
- Architect reads Phase 1 requirements
- Creates `TASK_PHASE1_WEEK1.md` with:
  - Day-by-day breakdown (what to code each day)
  - File list (exact files to create/modify)
  - Code snippets (what should be in each file)
  - Test specifications (what tests must pass)
  - Success criteria (how to know day is complete)
  - Git commit messages (for tracking)
  - Blocker detection (what to escalate)

#### **Step 2: Worker Reads TASK.md (CODE COPILOT)**
- Code copilot reads TASK.md
- Asks clarifying questions (if needed)
- Starts executing tasks in order
- Commits code to git
- Writes test results in console
- Reports back with TASK-RESULT.md

#### **Step 3: Worker Writes TASK-RESULT.md (CODE COPILOT)**
- Lists completed tasks (✅ Done)
- Lists failed tasks (❌ Blocked) with root cause
- Includes git log (commits made)
- Includes test output (passing/failing)
- Includes metrics (performance, coverage, errors)
- Asks Master for next steps

#### **Step 4: Master Reviews TASK-RESULT.md (ARCHITECT)**
- Architect reviews results
- Approves → clears for next day
- Rejects → asks for rework
- Escalates → bumps to next phase
- Writes next TASK.md

### Example Flow

```
Master (Zoo/Architect)
  │
  ├─→ Creates: TASK_PHASE1_WEEK1_DAY1.md
  │   ├─ "Day 1: MDM Serializers (4 hours)"
  │   ├─ "Create: backend/mdm/serializers.py"
  │   ├─ "Code snippets for ReferenceSetSerializer"
  │   ├─ "Tests: test_reference_set_serializer.py"
  │   └─ "Success: all tests passing, serializer validates"
  │
  └─→ Commits to git + pushes to Worker

Worker (Claude Code Copilot)
  │
  ├─→ Reads TASK_PHASE1_WEEK1_DAY1.md
  │   ├─ Asks any clarifying questions
  │   ├─ Implements ReferenceSetSerializer
  │   ├─ Writes tests
  │   ├─ Runs: pytest backend/mdm/tests/test_serializers.py
  │   └─ Commits: "PHASE1-D1: Implement MDM serializers"
  │
  └─→ Creates: TASK-RESULT_PHASE1_WEEK1_DAY1.md
      ├─ ✅ Completed: ReferenceSetSerializer
      ├─ ✅ Completed: Tests (5/5 passing)
      ├─ ❌ Blocked: ReferenceValueSerializer validation
      ├─ "Error: need to know if code must be unique per set or globally"
      └─ "Waiting for Master clarification"

Master (Zoo/Architect)
  │
  ├─→ Reads result
  │   ├─ "Ah, I see the blocker"
  │   ├─ "Code is unique per set (constraint in model)"
  │   ├─ Updates: TASK_PHASE1_WEEK1_DAY1.md with clarification
  │   └─ Commits back to Worker
  │
  └─→ Sends message: "ReferenceValue.code is unique_together with reference_set.id. Continue."

Worker
  │
  ├─→ Fixes ReferenceValueSerializer
  │   ├─ Tests pass
  │   └─ Commits: "PHASE1-D1: Fix ReferenceValue validation"
  │
  └─→ Day 1 complete, ready for Day 2
```

---

## Part X: Suggested Improvements to Protocol

### 1. **Pre-Task Checklist (Master)**
- [ ] All dependent Phase 0 work complete (no blockers)
- [ ] All code review standards documented (naming, testing, performance)
- [ ] Git branch strategy clear (main/develop/feature branches)
- [ ] Database migrations reviewed (no breaking changes)
- [ ] Deployment checklist ready (Docker updates, env vars, etc.)

### 2. **Daily Standup Summary (Worker)**
- Start of day: "Here's what I'm doing today"
- During day: "Hit blocker X, investigating"
- End of day: "Completed X, Y. Blocked on Z. Next: Day N+1 tasks."

### 3. **Weekly Rollup (Master)**
- "Phase 1 Week 1 complete: 4/5 days done, 1 blocker"
- "Metrics: 92% code coverage, 0 performance fails, 5 tests fixed"
- "Risks: ReferenceValue uniqueness logic complex, may need refactor"
- "Go/No-Go for Week 2: GO (all blockers cleared)"

### 4. **Escalation Protocol (Either)**
- **Blocker:** Can't proceed without Master input → Escalate
- **Design question:** Implementation approach unclear → Escalate
- **Scope creep:** New requirement discovered → Escalate to Master for Phase 7 backlog
- **Performance fail:** Code doesn't meet benchmarks → Rework or escalate

### 5. **Git Commit Convention**
```
PHASE1-D1: MDM Serializers (4/5 tests passing)

- Implement ReferenceSetSerializer with validation
- Implement ReferenceValueSerializer (nested)
- Add unique_together constraint for code per set
- 92% coverage

Blocked: ReferenceValue.code validation needs clarification
```

---

## Conclusion

This roadmap positions Carbon as a **true data trust platform**: governed, quality-checked, traceable, and auditable. The three-tier phasing ensures:

1. **Data trust core** is rock-solid before apps are built on top
2. **Emissions app** becomes the proof-of-concept for the architecture
3. **Reports & dashboards** leverage the platform's governance + quality + lineage
4. **Future apps** (ESG, energy, water) can plug in without rearchitecting

**RBAC is the foundation.** Every line of code must enforce: *user sees ONLY their org unit + delegated modules.*

**Timeline:** 6 weeks to full feature completion.
**Success metric:** All APIs tested, all pages functional, RBAC enforced 100%, 0 data leakage.

**Protocol:** Master creates TASK.md → Worker executes + writes TASK-RESULT.md → Repeat.

