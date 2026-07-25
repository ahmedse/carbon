# Carbon System — Complete Audit

**Date:** 2026-07-25  
**Auditor:** Zoo (Master)  
**Scope:** Entire system — backend, frontend, tests, deployment, documentation  
**Philosophy:** Carbon is a domain app on top of Data Trust Platform

---

## 1. Architecture Health

### 1.1 Data Trust Platform Philosophy ✅

| Principle | Status | Evidence |
|-----------|--------|----------|
| Platform `DataTable`/`DataRow` for ALL domains | ✅ | [`backend/dataschema/`](backend/dataschema/) — generic storage |
| Carbon uses platform tables for activity data | ✅ | [`CalculationRule`](backend/emissions/models.py:474-736) links to `DataTable`/`DataField` |
| Carbon adds domain config only | ✅ | [`EmissionFactor`](backend/emissions/models.py:96-215), [`ReportingPeriod`](backend/emissions/models.py:8-93) |
| Platform admin at `/catalog/`, `/mdm/` | ✅ | [`backend/config/urls.py:63-64`](backend/config/urls.py:63-64) |
| Carbon at `/carbon/` namespace | ✅ | [`backend/config/urls.py:61-62`](backend/config/urls.py:61-62) |
| No platform model violations | ✅ | No carbon-specific DataTable/DataRow subclasses |

### 1.2 URL Architecture ✅

```
/carbon-api/token/           → JWT auth
/carbon-api/accounts/        → User management
/carbon-api/core/            → Core (modules, feedback)
/carbon-api/dataschema/      → DataTable/DataRow CRUD
/carbon-api/carbon/          → Carbon domain (emissions app)
  ├── periods/               → Reporting periods
  ├── factors/               → Emission factors
  ├── gwp/                   → Global warming potentials
  ├── calculations/          → Calculation results
  ├── rules/                 → Calculation rules
  ├── report-configs/        → Saved report configs
  ├── dashboard/             → Executive dashboard
  ├── owner-dashboard/       → Data owner dashboard
  ├── owner/summary/         → Owner summary
  ├── owner/assets/          → Owner emission sources
  ├── owner/activity/        → Owner recent activity
  ├── yearly-comparison/     → Year-over-year comparison
  ├── report/                → Report generation
  └── calculate/             → Trigger calculations
/carbon-api/catalog/         → Catalog (assets, domains, glossary)
/carbon-api/mdm/             → Master data (org units, reference sets)
/carbon-api/dq/              → Data quality (rules, profiling, metrics)
/carbon-api/connections/     → External connections
/carbon-api/importexport/    → Import/export
/carbon-api/swagger/         → API docs
```

---

## 2. Backend Health

### 2.1 Carbon Models (`backend/emissions/models.py`)

| Model | Lines | Status | Notes |
|-------|-------|--------|-------|
| [`ReportingPeriod`](backend/emissions/models.py:8-93) | 8-93 | ✅ Complete | 6 workflow states, period types, constraints |
| [`EmissionFactor`](backend/emissions/models.py:96-215) | 96-215 | ✅ Complete | Scope 1/2/3, categories, GHG breakdown, tags |
| [`GWP`](backend/emissions/models.py:218-282) | 218-282 | ✅ Complete | AR5 + AR6 values, 20yr + 100yr |
| [`Calculation`](backend/emissions/models.py:285-471) | 285-471 | ✅ Complete | Factory method, audit fields, indices |
| [`CalculationRule`](backend/emissions/models.py:474-736) | 474-736 | ✅ Complete | Dynamic field binding, auto-calculate |
| [`ReportConfig`](backend/emissions/models.py:739-804) | 739-804 | ✅ Complete | Saved report configurations |

**Gap:** [`Calculation`](backend/emissions/models.py:285-471) already has `calculated_by` and `calculation_method` — the migration proposed in the task file is **already applied**. The task file needs updating.

### 2.2 Carbon Views (`backend/emissions/views.py`)

| View | Lines | Status | Notes |
|------|-------|--------|-------|
| [`ReportingPeriodViewSet`](backend/emissions/views.py:45-80) | 45-80 | ✅ Complete | CRUD + active endpoint |
| [`EmissionFactorViewSet`](backend/emissions/views.py:83-138) | 83-138 | ✅ Complete | CRUD + summary + categories |
| [`GWPViewSet`](backend/emissions/views.py:141-145) | 141-145 | ✅ Complete | Read-only |
| [`CalculationViewSet`](backend/emissions/views.py:148-198) | 148-198 | ✅ Complete | Filtered + scoped |
| [`CalculationRuleViewSet`](backend/emissions/views.py:201-239) | 201-239 | ✅ Complete | CRUD + execute action |
| [`DashboardAPIView`](backend/emissions/views.py:242-357) | 242-357 | ✅ Complete | Scope/category/monthly breakdown |
| [`YearlyComparisonAPIView`](backend/emissions/views.py:360-471) | 360-471 | ✅ Complete | YoY comparison with baseline |
| [`ReportAPIView`](backend/emissions/views.py:474-621) | 474-621 | ✅ Complete | JSON + CSV export |
| [`CalculateAPIView`](backend/emissions/views.py:624-697) | 624-697 | ✅ Complete | Validation for rule_id, closed periods, incomplete data |
| [`ReportConfigViewSet`](backend/emissions/views.py:799-822) | 799-822 | ✅ Complete | CRUD + run action |
| [`OwnerDashboardAPIView`](backend/emissions/views.py:825-938) | 825-938 | ✅ Complete | Scoped dashboard with DQ metrics |
| [`OwnerSummaryAPIView`](backend/emissions/views.py:941-988) | 941-988 | ✅ Complete | Module summary |
| [`OwnerAssetsAPIView`](backend/emissions/views.py:991-1046) | 991-1046 | ✅ Complete | Scoped asset list |
| [`OwnerActivityAPIView`](backend/emissions/views.py:1049-1076) | 1049-1076 | ✅ Complete | Recent activity |

**Fixed:** [`CalculateAPIView`](backend/emissions/views.py:624-697) now validates:
- `rule_id` is required (400 error)
- Reporting period exists (404 error)
- Period is not closed (422 error)
- Rule is active (422 error)
- Activity data is complete (422 error with incomplete row IDs)

### 2.3 Carbon Serializers (`backend/emissions/serializers.py`)

| Serializer | Status | Notes |
|------------|--------|-------|
| `ReportingPeriodSerializer` | ✅ | Includes `duration_days`, `is_active` |
| `EmissionFactorSerializer` | ✅ | Full fields |
| `EmissionFactorSummarySerializer` | ✅ | Minimal for dropdowns |
| `GWPSerializer` | ✅ | Read-only |
| `CalculationSerializer` | ✅ | Full fields |
| `CalculationRuleSerializer` | ✅ | Full fields |
| `DashboardSummarySerializer` | ✅ | Dashboard response |
| `EmissionReportSerializer` | ✅ | Report response |
| `ReportConfigSerializer` | ✅ | Full fields |

### 2.4 Carbon Tests

| Test File | Tests | Status | Notes |
|-----------|-------|--------|-------|
| [`backend/emissions/tests.py`](backend/emissions/tests.py:1-116) | `OwnerApiEndpointsTest` | ✅ | 4 tests: summary, assets, activity, namespace |
| [`backend/emissions/tests/test_owner_endpoints.py`](backend/emissions/tests/test_owner_endpoints.py:1-111) | `OwnerApiEndpointsTest` | ✅ | Same as above (duplicate?) |
| [`backend/emissions/tests/test_report_config.py`](backend/emissions/tests/test_report_config.py:1-229) | `ReportConfigAPITest` | ✅ | CRUD, scoping, run |

**Gap:** No tests for:
- ✅ `CalculateAPIView` validation (3 tests added in `test_calculation_validation.py`)
- `DashboardAPIView` filtering
- `EmissionFactorViewSet` CRUD
- `ReportingPeriodViewSet` workflow transitions
- Edge cases (empty data, invalid factors)

### 2.5 Platform Backend Health

| App | Status | Notes |
|-----|--------|-------|
| `accounts` | ✅ | JWT auth, ScopedRole RBAC |
| `core` | ✅ | Module model, middleware |
| `dataschema` | ✅ | DataTable/DataRow CRUD |
| `catalog` | ✅ | AssetProfile, Governance, Glossary |
| `mdm` | ✅ | OrgUnit tree, ReferenceSet lifecycle |
| `dq` | ✅ | 6 rule types, profiling, metrics |
| `connections` | ✅ | External connections |
| `importexport` | ✅ | Bulk import/export |
| `evidence` | ✅ | Evidence uploads |
| `ai_copilot` | ❌ Frozen | Superseded by Pulse |

---

## 3. Frontend Health

### 3.1 Route Structure (`carbon-frontend/src/App.jsx`)

| Route | Component | Status | Notes |
|-------|-----------|--------|-------|
| `/carbon/dashboard` | `EmissionsDashboard` | ✅ | |
| `/carbon/admin/factors` | `EmissionFactorsPage` | ✅ | Admin-only |
| `/carbon/reporting/generate` | `ReportGeneratorPage` | ✅ | |
| `/carbon/reporting/saved` | `SavedReportsPage` | ✅ | |
| `/carbon/reporting/periods` | `ReportingPeriodsPage` | ✅ | Admin-only |
| `/carbon/owner/portal` | `DataOwnerPortalPage` | ✅ | |
| `/carbon/owner/dashboard` | `DataOwnerDashboardPage` | ✅ | |
| `/carbon/owner/assets` | `DataOwnerAssetsPage` | ✅ | |
| `/carbon/data-entry` | `DataHubHome` | ✅ | |
| `/carbon/data-entry/entry/...` | `DataEntryPage` | ✅ | |
| `/carbon/data-entry/row/...` | `RowDetailPage` | ✅ | |
| **`/carbon/console`** | **MISSING** | ❌ | **No Carbon Console landing page** |
| `/catalog/*` | Various | ✅ | Full catalog studio |
| `/dashboards/*` | Various | ✅ | Executive, analytics, targets, DQ, reporting |
| `/admin/*` | Various | ✅ | Users, groups, roles, org units, apps |

### 3.2 API Client (`carbon-frontend/src/api/emissions.js`)

| Function | Status | Notes |
|----------|--------|-------|
| `fetchEmissionsDashboard` | ✅ | |
| `fetchEmissionsReport` | ✅ | |
| `triggerCalculations` | ✅ | |
| `fetchReportingPeriods` | ✅ | |
| `fetchActiveReportingPeriod` | ✅ | |
| `fetchEmissionFactors` | ✅ | |
| `fetchFactorCategories` | ✅ | |
| `fetchCalculationRules` | ✅ | |
| `executeCalculationRule` | ✅ | |
| `fetchCalculations` | ✅ | |
| `fetchYearlyComparison` | ✅ | |
| `fetchOwnerDashboard` | ✅ | |
| `fetchOwnerSummary` | ✅ | |
| `fetchOwnerAssets` | ✅ | |
| `fetchOwnerActivity` | ✅ | |
| `fetchReportingPeriodsFiltered` | ✅ | |

### 3.3 Extended API Client (`carbon-frontend/src/api/emissions-extended.js`)

| Function | Status | Notes |
|----------|--------|-------|
| `fetchEmissionFactors` | ✅ | Duplicate of `emissions.js` |
| `fetchFactorCategories` | ✅ | Duplicate |
| `createEmissionFactor` | ✅ | |
| `updateEmissionFactor` | ✅ | |
| `deleteEmissionFactor` | ✅ | |
| `fetchReportingPeriods` | ✅ | Duplicate |
| `createReportingPeriod` | ✅ | |
| `updateReportingPeriod` | ✅ | |
| `deleteReportingPeriod` | ✅ | |
| `fetchReportConfigs` | ✅ | |
| `createReportConfig` | ✅ | |
| `updateReportConfig` | ✅ | |
| `deleteReportConfig` | ✅ | |
| `runReportConfig` | ✅ | |
| `generateReport` | ✅ | |
| `downloadReportCsv` | ✅ | |

**Gap:** Duplicate functions between `emissions.js` and `emissions-extended.js` — should be consolidated.

### 3.4 Sidebar (`carbon-frontend/src/components/SidebarMenu.jsx`)

| Section | Status | Notes |
|---------|--------|-------|
| Scope 1/2/3 grouping | ✅ | Dynamic from modules |
| Module → Table drilldown | ✅ | |
| Scope expand/collapse | ✅ | |
| App menu | ⚠️ | Uses generic terms: "Data Entry", "Executive Summary" |
| Carbon Console | ❌ | Missing from menu |
| Tooltips | ❌ | No GHG Protocol educational tooltips |

---

## 4. Operational Health (Track E)

### 4.1 Structured Logging ✅

| Component | Status | File |
|-----------|--------|------|
| JSON logging | ✅ | [`backend/config/settings.py`](backend/config/settings.py:253-289) |
| Correlation IDs | ✅ | [`backend/core/middleware.py`](backend/core/middleware.py:8-53) |
| Rotating file handler | ✅ | 10MB files, 5 backups |
| Request timing | ✅ | Logs slow requests >5s |

### 4.2 Performance Optimization ✅

| Optimization | Status | File |
|-------------|--------|------|
| Database indices | ✅ | [`backend/catalog/migrations/0004_add_performance_indices.py`](backend/catalog/migrations/0004_add_performance_indices.py) |
| `select_related` in views | ✅ | [`backend/mdm/views.py:43-86`](backend/mdm/views.py:43-86) |
| `annotate` for counts | ✅ | [`backend/mdm/views.py:43-86`](backend/mdm/views.py:43-86) |

### 4.3 Resilience ✅

| Feature | Status | File |
|---------|--------|------|
| Retry decorator | ✅ | [`backend/core/utils.py`](backend/core/utils.py) |
| Chunked processing | ✅ | [`backend/dq/services.py:65-180`](backend/dq/services.py:65-180) |
| Graceful degradation | ✅ | [`backend/dq/views.py`](backend/dq/views.py) |

---

## 5. Gap Analysis

### 5.1 Critical Gaps (Blocking Production)

| # | Gap | Severity | Location | Fix |
|---|-----|----------|----------|-----|
| 1 | ✅ **Carbon Console landing page** | ✅ Done | Frontend | Created `/carbon/console` with workflow cards, quick stats, and getting started guide |
| 2 | ✅ **Input validation on CalculateAPIView** | ✅ Done | [`backend/emissions/views.py:624-697`](backend/emissions/views.py:624-697) | Validates rule_id, period status, rule active status, data completeness |
| 3 | ✅ **Production seed data** | ✅ Done | Backend | Created `seed_carbon_reference_data.py` with 17 factors, 3 GWP values, 6 activity units |
| 4 | ✅ **Enterprise terminology in UI** | ✅ Done | Sidebar manifest | Updated to "Activity Data Entry", "Emissions Dashboard", "My Emission Sources" |
| 5 | ✅ **Breadcrumbs** | ✅ Done | Frontend | Added Carbon Console and all Carbon routes to breadcrumb configuration |
| 6 | **No contextual help/tooltips** | 🟡 Medium | Frontend | Create CarbonTooltip component |
| 7 | ✅ **Calculation audit tracking** | ✅ Done | [`CalculateAPIView`](backend/emissions/views.py:624-697) | Passes `user=request.user` to `calculate_for_table`, populates `calculated_by` |

### 5.2 Moderate Gaps

| # | Gap | Severity | Location | Fix |
|---|-----|----------|----------|-----|
| 8 | **Duplicate API functions** | 🟡 Medium | `emissions.js` + `emissions-extended.js` | Consolidate into single file |
| 9 | **Duplicate test file** | 🟡 Medium | `tests.py` + `tests/test_owner_endpoints.py` | Remove duplicate |
| 10 | **No Scope 3 category definitions** | 🟡 Medium | Backend seed | Add Categories 1, 3, 6, 7 |
| 11 | **No activity units reference set** | 🟡 Medium | Backend seed | Create CARBON_ACTIVITY_UNITS |
| 12 | **No GWP seed data** | 🟡 Medium | Backend seed | Add CO2, CH4, N2O values |
| 13 | **No reporting period transition API** | 🟡 Medium | [`ReportingPeriodViewSet`](backend/emissions/views.py:45-80) | Add `transition` action |
| 14 | **No submission tracking** | 🟡 Medium | [`ReportingPeriod`](backend/emissions/models.py:8-93) | Add `get_submission_status()` |
| 15 | **No emission factor CRUD tests** | 🟡 Medium | Tests | Add CRUD tests for factors |

### 5.3 Minor Gaps

| # | Gap | Severity | Location | Fix |
|---|-----|----------|----------|-----|
| 16 | **No empty state handling** | 🟢 Low | Frontend pages | Add empty state components |
| 17 | **No responsive layout testing** | 🟢 Low | Frontend | Test mobile viewports |
| 18 | **No loading skeletons** | 🟢 Low | Frontend | Add Skeleton components |
| 19 | **No error boundary** | 🟢 Low | Frontend | Add React error boundary |
| 20 | **No pagination on calculation list** | 🟢 Low | [`CalculationViewSet`](backend/emissions/views.py:148-198) | Add pagination class |

---

## 6. Test Coverage

### 6.1 Backend Tests

| Test File | Tests | Status |
|-----------|-------|--------|
| `backend/emissions/tests.py` | 4 | ✅ Passing |
| `backend/emissions/tests/test_owner_endpoints.py` | 4 | ✅ Passing |
| `backend/emissions/tests/test_report_config.py` | 6+ | ✅ Passing |
| `backend/emissions/tests/test_calculation_validation.py` | 3 | ✅ Passing |
| **Total carbon tests** | **17+** | **✅** |

**Missing tests:**
- ✅ `CalculateAPIView` validation (3 tests added)
- `EmissionFactorViewSet` CRUD (0 tests)
- `ReportingPeriodViewSet` transitions (0 tests)
- `DashboardAPIView` filtering (0 tests)
- Edge cases: empty data, invalid factors, closed periods (0 tests)

### 6.2 Frontend Tests

No frontend test files found. The frontend has **zero test coverage**.

---

## 7. Deployment Health

| Component | Status | Notes |
|-----------|--------|-------|
| `docker-compose.yml` | ✅ | Present |
| `combined-apps_nginx.example` | ✅ | Nginx config |
| `manage.sh` | ✅ | Management script |
| `DEPLOYMENT_PLAN_AASTMT_CARBON.md` | ✅ | Deployment docs |
| `QUICKSTART_DEPLOYMENT.md` | ✅ | Quick start |
| `install.md` | ✅ | Install guide |
| `.env` | ⚠️ | Not checked (secrets) |
| `.env.production` | ⚠️ | Not checked (secrets) |

---

## 8. Documentation Health

| Document | Status | Notes |
|----------|--------|-------|
| `docs/roadmap.md` | ✅ | Phase 1-4 roadmap |
| `docs/data-model.md` | ✅ | Data model docs |
| `docs/api.md` | ✅ | API documentation |
| `docs/design.md` | ✅ | Design docs |
| `docs/deployment.md` | ✅ | Deployment |
| `docs/TERMINOLOGY.md` | ✅ | Terminology |
| `docs/workflows.md` | ✅ | Workflow docs |
| `docs/ADMIN_USER_GUIDE.md` | ✅ | Admin guide |
| `docs/PLATFORM_APP_MODEL.md` | ✅ | Platform app model |
| `CARBON_WORKFLOWS_AND_PROCESSES.md` | ✅ | Carbon workflows |
| `CARBON_PRODUCTION_ROADMAP.md` | ✅ | Production roadmap |
| `plans/CARBON_UI_TERMINOLOGY_ENTERPRISE_AUDIT.md` | ✅ | UI audit |

---

## 9. Summary

### What's Solid ✅
- **Architecture:** Data Trust Platform philosophy fully respected
- **Backend models:** All 6 carbon models complete with indices, constraints, factory methods
- **Backend views:** 14 views covering all CRUD, dashboards, reports, calculations
- **RBAC:** ScopedRole enforcement in all owner endpoints
- **Operational:** JSON logging, performance optimization, resilience (Track E complete)
- **API client:** Full coverage in `emissions.js` + `emissions-extended.js`
- **Tests:** 14+ passing tests for owner endpoints and report configs
- **Documentation:** Comprehensive docs across all areas

### What's Missing ❌
- **Carbon Console landing page** — no workflow-based navigation
- **CalculateAPIView validation** — no input validation, can crash on bad data
- **Production seed data** — no emission factors, GWP values, or activity units
- **Enterprise terminology** — generic terms in sidebar and pages
- **Breadcrumbs** — no navigation hierarchy
- **Contextual help** — no GHG Protocol tooltips

### What's Duplicated ⚠️
- `tests.py` and `tests/test_owner_endpoints.py` — same test class
- `emissions.js` and `emissions-extended.js` — overlapping functions

---

## 10. Recommended Execution Order

### Phase 1 (Current Task — 2 Workers Parallel)
```
Worker 1 (raptor) — Backend: ✅ COMPLETE
├── ✅ B1: Seed carbon reference data (factors, GWP, units)
├── ✅ B2: Add validation to CalculateAPIView
├── ✅ B3: Add calculation audit tracking
└── ✅ B4: Write unit tests (test_calculation_validation.py)

Worker 2 (mai-code flash) — Frontend: ✅ COMPLETE
├── ✅ F1: Update terminology in sidebar and manifest
├── ✅ F2: Create Carbon Console landing page with workflow cards
├── ✅ F3: Add breadcrumbs for all Carbon routes
├── ✅ F4: Register `/carbon/console` route in App.jsx
└── ✅ F5: Update sidebar icon mapping
```

### Phase 2 (Next)
```
├── Consolidate duplicate API functions
├── Remove duplicate test file
├── Add reporting period transition API
├── Add submission tracking to ReportingPeriod
├── Add empty state components
└── Add loading skeletons
```

### Phase 3 (Production Hardening)
```
├── Add frontend tests
├── Add error boundaries
├── Add pagination to calculation list
├── Performance load testing
└── Security audit
```

---

## 11. Key Metrics

| Metric | Value |
|--------|-------|
| Backend models | 6 carbon models |
| Backend views | 14 views |
| Backend serializers | 9 serializers |
| Backend tests | 14+ passing |
| Frontend pages | 10+ carbon pages |
| Frontend API functions | 25+ functions |
| Frontend tests | 0 |
| Critical gaps | 7 |
| Moderate gaps | 8 |
| Minor gaps | 5 |
| Duplicate files | 2 pairs |

---

## 12. Conclusion

The system is **architecturally sound** with the Data Trust Platform philosophy correctly implemented. The carbon domain app has comprehensive models, views, and API coverage. 

**However, the system is NOT production-ready** due to:
1. **No input validation** on the calculation endpoint — users can trigger calculations on invalid data
2. **No seed data** — production deployment starts with empty emission factors
3. **No Carbon Console** — users have no workflow-based landing page
4. **Generic terminology** — confuses non-expert users

The task file [`TASK-CARBON-PHASE1-UI-WORKFLOWS.md`](TASK-CARBON-PHASE1-UI-WORKFLOWS.md:1-1085) addresses all critical gaps and is ready for worker execution.

**Note:** The `Calculation` model already has `calculated_by` and `calculation_method` fields (lines 382-394). The migration proposed in the task file is already applied — the task file needs this section removed before execution.
