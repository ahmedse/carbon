# CARBON DATA TRUST PLATFORM — ENTERPRISE QA & VALIDATION PLAN

**Version:** 2.0 | **Date:** 2026-08-01 | **Scope:** Backend + Frontend + Performance + Security + UX  
**Goal:** Enterprise-grade robustness, stability, feature completeness, and usability

---

## EXECUTIVE SUMMARY

| Dimension | Phase | KPIs | Verification Method |
|-----------|-------|------|---------------------|
| 🌐 **Web Robustness** | P10 | 85 pages × 5 roles | Browser simulation |
| 🔐 **RBAC Enforcement** | P11 | 50+ endpoints × 5 roles | API audit + automated tests |
| ⚡ **Performance** | P12 | <200ms p95, <2s page load | Profiling + Lighthouse |
| 🧪 **Test Coverage** | P13 | 80%+ line coverage | pytest + coverage.py |
| 🏗️ **Architecture** | P14 | 0 fat views, 0 dead code | Static analysis |
| 🎯 **Feature Completeness** | P15 | 11/11 apps production-ready | Feature matrix |
| ♿ **Accessibility/UX** | P16 | WCAG 2.1 AA, <0.1s CLS | axe-core + Lighthouse |

---

## PHASE 10: WEB ROBUSTNESS — COMPLETE PAGE AUDIT

**Goal:** Every frontend page works for every role. No dead pages. No broken routes. Consistent UX.

### 10.1 Route Inventory & Audit (85 pages)

#### 10.1.1 Core Pages (11 routes)
| # | Route | Page | Roles | P1-P9 Status | P10 Action |
|---|-------|------|-------|-------------|------------|
| 1 | `/` | PlatformHome / RoleAwareLanding | ALL | ✅ P8 fixed | Re-verify 5 roles |
| 2 | `/login` | Login | public | ✅ | Verify expired/token flow |
| 3 | `/dashboard` | → `/` redirect | ALL | ✅ | Verify redirect |
| 4 | `/dashboard-legacy` | Dashboard (legacy) | ALL | ⚠️ Legacy | **AUDIT: delete or migrate** |
| 5 | `/settings` | SettingsPage | ALL | ⚠️ Not tested | Test 5 roles |
| 6 | `/help` | Help | ALL | ⚠️ Not tested | Test renders |
| 7 | `/feedback` | Feedback | ALL | ⚠️ Not tested | Test submit flow |
| 8 | `/emissions` | EmissionsDashboard | ALL | ⚠️ Legacy dup | **AUDIT: merge with /carbon/dashboard** |
| 9 | `/emissions/dashboard` | EmissionsDashboard | ALL | ⚠️ Dup route | **DELETE: duplicate** |
| 10 | `/emissions/report` | EmissionsReport | ALL | ⚠️ Legacy | **AUDIT: merge with /carbon/reporting** |
| 11 | `*` | NotFound (404) | ALL | ✅ P9 tested | Re-verify |

#### 10.1.2 Carbon Console (16 routes)
| # | Route | Page | Roles | P10 Action |
|---|-------|------|-------|------------|
| 12 | `/carbon/console` | CarbonConsolePage | ALL | Test 5 roles |
| 13 | `/carbon/dashboard` | EmissionsDashboard | ALL | Test 5 roles |
| 14 | `/carbon/analytics` | AnalyticsDashboard | viewer, analyst, admin | Test 3 roles |
| 15 | `/carbon/my-data` | MyDataPage | ALL | ✅ P9 tested | Re-verify |
| 16 | `/carbon/my-data/:moduleId` | ModuleWorkspacePage | dataowner, admin | Test |
| 17 | `/carbon/my-data/:moduleId/:tableId` | DataEntryPage | dataowner, admin | Test |
| 18 | `/carbon/my-data/row/:tableId/:rowId` | RowDetailPage | ALL | ✅ P9 fixed | Re-verify |
| 19 | `/carbon/calculations` | CalculationsPage | dataowner, admin | ✅ P9 tested | Re-verify |
| 20 | `/carbon/verification` | VerificationPage | dataowner, auditor, admin | ✅ P9 tested | Re-verify |
| 21 | `/carbon/admin/factors` | EmissionFactorsPage | admin only | Test AdminRoute |
| 22 | `/carbon/admin/rules` | CalculationRulesPage | admin only | Test AdminRoute |
| 23 | `/carbon/admin/gwp` | GWPReferencePage | admin only | Test AdminRoute |
| 24 | `/carbon/admin/targets` | SBTiTargetsPage | admin only | Test |
| 25 | `/carbon/reporting/generate` | ReportGeneratorPage | ALL | Test 5 roles |
| 26 | `/carbon/reporting/saved` | SavedReportsPage | ALL | Test 5 roles |
| 27 | `/carbon/reporting/periods` | ReportingPeriodsPage | admin only | Test |

#### 10.1.3 Data Owner (4 routes)
| # | Route | Page | P10 Action |
|---|-------|------|------------|
| 28 | `/carbon/owner/assets` | DataOwnerAssetsPage | Test |
| 29 | `/carbon/owner/portal` | → `/carbon/console` | Verify redirect |
| 30 | `/carbon/owner/dashboard` | → `/carbon/console` | Verify redirect |
| 31 | `/data-owner` | → `/carbon/console` | Verify redirect |
| 32 | `/data-owner/dashboard` | → `/carbon/console` | Verify redirect |
| 33 | `/data-owner/assets` | → `/carbon/owner/assets` | Verify redirect |

#### 10.1.4 Legacy Redirects (3 routes) — **AUDIT FOR DELETION**
| # | Route | Action |
|---|-------|--------|
| 34 | `/carbon/data-entry` | → `/carbon/my-data` — OK |
| 35 | `/carbon/data-entry/entry/:m/:t` | RedirectLegacyEntry — **DELETE if no external links** |
| 36 | `/carbon/data-entry/row/:t/:r` | RedirectLegacyRow — **DELETE if no external links** |

#### 10.1.5 Admin Pages (11 routes)
| # | Route | Page | P10 Action |
|---|-------|------|------------|
| 37 | `/schema-admin/table-manager` | TableManagerPage | admin only | Test |
| 38 | `/admin/org-units` | OrgUnitsPage | admin only | Test CRUD |
| 39 | `/admin/org-units/:id` | OrgUnitDetailPage | admin only | Test tabs |
| 40 | `/admin/access` | AccessControlPage | admin only | Test |
| 41 | `/admin/users` | UsersPage | admin only | Test CRUD |
| 42 | `/admin/groups` | GroupsPage | admin only | Test CRUD |
| 43 | `/admin/groups/:id` | GroupDetailPage | admin only | Test 4 tabs |
| 44 | `/admin/role-matrix` | RoleRegistryPage | admin only | Test |
| 45 | `/admin/apps` | RegisteredAppsPage | admin only | Test enable/disable |
| 46 | `/admin/audit` | AuditLogPage | admin only | Test |
| 47 | `/admin/policies` | → `/catalog/policies` | Verify redirect |

#### 10.1.6 Catalog Pages (25+ routes)
| # | Route | Page | P10 Action |
|---|-------|------|------------|
| 48 | `/catalog` | CatalogHome | ALL | Test 5 roles |
| 49 | `/catalog/products` | DataProductsPage | ALL | Test |
| 50 | `/catalog/products/:id` | DataProductDetailPage | ALL | Test |
| 51 | `/catalog/policies` | GovernancePage | ALL | Test |
| 52 | `/catalog/glossary` | GlossaryPage | ALL | Test |
| 53 | `/catalog/tags` | TagsPage | admin only | Test |
| 54 | `/catalog/tags/:id` | TagDetailPage | admin only | Test 4 tabs |
| 55 | `/catalog/domains` | DomainsPage | admin only | Test |
| 56 | `/catalog/domains/:id` | DomainDetailPage | admin only | Test 3 tabs |
| 57 | `/catalog/assets` | AssetsPage | ALL | Test |
| 58 | `/catalog/assets/:id` | AssetDetailPage | ALL | Test 5 tabs |
| 59 | `/catalog/dq-dashboard` | DQDashboardPage | ALL | Test |
| 60 | `/catalog/dq-rules` | DQRulesPage | admin only | Test |
| 61 | `/catalog/sources` | DataSourcesDetailPage | admin only | Test |
| 62 | `/catalog/schemas` | SchemaCatalogPage | ALL | Test |
| 63 | `/catalog/schemas/:id` | SchemaDetailPage | ALL | Test tabs |
| 64 | `/catalog/schemas/manage` | SchemaManagerPage | admin only | Test |
| 65 | `/catalog/connections` | ConnectionsPage | admin only | Test |
| 66 | `/catalog/metadata` | MetadataManagementPage | admin only | Test |
| 67 | `/catalog/import-export` | ImportExportPage | admin only | Test |
| 68 | `/catalog/imports/:id` | ImportsDetailPage | admin only | Test |
| 69 | `/catalog/exports/:id` | ExportsDetailPage | admin only | Test |
| 70 | `/catalog/reference-data` | ReferenceDataPage | ALL | Test |
| 71 | `/catalog/reference-data/:id` | ReferenceSetDetailPage | admin only | Test 3 tabs |
| 72 | `/catalog/mdm` | MDMPage | admin only | Test |

#### 10.1.7 Misc Routes (5 routes)
| # | Route | Page | P10 Action |
|---|-------|------|------------|
| 73 | `/modules/:moduleId` | ModuleLandingPage | ALL | Test |
| 74 | `/scopes/:scopeId` | ScopeInfoPage | ALL | Test |
| 75 | `/dataschema` | DataHubHome | ALL | Test |
| 76 | `/dataschema/entry/:m/:t` | DataEntryPage | dataowner, admin | **LEGACY** — verify redirect |
| 77 | `/dataschema/row/:t/:r` | RowDetailPage | ALL | **LEGACY** — verify redirect |

#### 10.1.8 Dashboard Legacy Redirects (5 routes) — **AUDIT FOR DELETION**
| # | Route | Redirect | Action |
|---|-------|----------|--------|
| 78 | `/dashboards/executive` | → `/carbon/console` | Keep if external links |
| 79 | `/dashboards/analytics` | → `/carbon/analytics` | Keep if external links |
| 80 | `/dashboards/targets` | → `/carbon/admin/targets` | Keep if external links |
| 81 | `/dashboards/data-quality` | → `/catalog/dq-dashboard` | Keep if external links |
| 82 | `/dashboards/reporting` | → `/carbon/reporting/generate` | Keep if external links |

### 10.2 Frontend Consistency Checklist

| # | Check | Method | KPI |
|---|-------|--------|-----|
| C1 | All pages render without console errors | Browser log scan | 0 errors |
| C2 | All pages have breadcrumbs | Visual scan | 100% |
| C3 | All pages show page title in browser tab | `document.title` | Not "AAST Carbon Platform" default |
| C4 | Loading states shown (not blank white) | Throttle network | <500ms skeleton shown |
| C5 | Error boundaries catch JS crashes | Throw in useEffect | Friendly error, not white screen |
| C6 | No duplicate pages (multiple routes → same component) | Route audit | 0 unnecessary dupes |
| C7 | Dark mode works on EVERY page | Toggle + scan | No light-mode-only pages |
| C8 | All forms have validation feedback | Submit empty forms | Inline errors, not just toast |
| C9 | All data tables have empty states | Filter to no results | "No data" not blank table |
| C10 | All links are valid (no 404 internal links) | Crawler scan | 0 broken internal links |
| C11 | apiFetch callers use correct pattern | grep audit | 0 `response.json()` after apiFetch |
| C12 | No inline `sx={{}}` | grep audit | <5 remaining |

### 10.3 Dead Page & Route Cleanup

**Candidate deletions** (verify no external links first):
- [ ] `/dashboard-legacy` → delete page + route
- [ ] `/emissions` + `/emissions/dashboard` → merge into `/carbon/dashboard`
- [ ] `/emissions/report` → merge into `/carbon/reporting/generate`
- [ ] `/dataschema/entry/:m/:t` → already redirected, delete if safe
- [ ] `/dataschema/row/:t/:r` → already redirected, delete if safe
- [ ] Legacy redirect components (`RedirectLegacyEntry`, `RedirectLegacyRow`) → delete if safe

**Mark for deletion after audit (P10):**
- [ ] `DataOwnerPortalPage.jsx` — redirected to CarbonConsolePage, is it still imported?
- [ ] `DataOwnerDashboardPage.jsx` — redirected, is it still used?
- [ ] `Dashboard.jsx` — legacy, verify no users

---

## PHASE 11: RBAC ENFORCEMENT — COMPLETE HARDENING

**Goal:** Every API endpoint enforces correct RBAC. Read-only roles cannot write. Scoped roles cannot cross org-units.

### 11.1 Permission Class Inventory (50+ endpoints)

#### 11.1.1 Permission Class Types Used
| Class | Scope | Used By |
|-------|-------|---------|
| `HasScopedRole` | Module-scoped, role-based | accounts, dataschema |
| `ReadScopedWriteAdmin` | Scoped read, admin write | dataschema (tables, fields, relations) |
| `AdminOrSuperuserOnly` | Admin/superuser only | catalog, connections, emissions admin, importexport |
| `ReadAnyWriteAdmin` | Anyone read, admin write | emissions (ReportingPeriod) |
| `ReadAnyWriteGlobalAdmin` | Anyone read, global admin write | mdm |
| `CanManageScopedRoles` | Scoped role management | accounts |
| `IsAuthenticated` | Any logged-in user | dq, emissions dashboards, core |
| `IsEvidenceOwnerOrAdmin` | Owner or admin | evidence |
| `AllowAny` | Public | swagger |

#### 11.1.2 Endpoints Using `IsAuthenticated` Only (HIGH RISK — write audit)
These endpoints allow ANY authenticated user to perform writes. Must verify they're read-only or add write protection:

| # | Endpoint | View | Method Risk |
|---|----------|------|-------------|
| 1 | `POST/PUT/PATCH/DELETE /carbon-api/dq/rules/` | DQRuleViewSet | ⚠️ **ANY user can CRUD DQ rules!** |
| 2 | `POST/PUT/PATCH/DELETE /carbon-api/carbon/calculations/` | CalculationViewSet | ⚠️ **ANY user can CRUD calculations!** |
| 3 | `POST/PUT/PATCH/DELETE /carbon-api/carbon/report-configs/` | ReportConfigViewSet | ⚠️ **ANY user can CRUD report configs!** |
| 4 | `POST/PUT/PATCH/DELETE /carbon-api/core/modules/` | ModuleViewSet | ⚠️ **ANY user can CRUD modules!** |
| 5 | `POST/PUT/PATCH/DELETE /carbon-api/core/feedback/` | FeedbackViewSet | ⚠️ POST only for feedback — OK? |
| 6 | `POST/PUT/PATCH/DELETE /carbon-api/mdm/org-units/` | OrgUnitViewSet | ⚠️ **ANY user can CRUD org units!** |

**P11 Action:** Add `AdminOrSuperuserOnly` to at least #1, #2, #3, #4, #6.

#### 11.1.3 RBAC Role × Action Matrix Audit
| Role | View Data | Edit Data | Create Data | Delete Data | Admin Pages | DQ Rules | Calculations |
|------|-----------|-----------|-------------|-------------|-------------|----------|--------------|
| **admin1** (admins_group) | ✅ All | ✅ All | ✅ All | ✅ All | ✅ All | ✅ | ✅ |
| **dataowner2** (dataowners_group) | ✅ Scoped | ✅ Scoped | ✅ Scoped | ❌ | ❌ | ❌ | ❌ |
| **auditor1** (auditors_group) | ✅ Scoped | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **viewer1** (viewers_group) | ✅ Scoped | ❌ (P9 fixed) | ❌ (P9 fixed) | ❌ (P9 fixed) | ❌ | ❌ | ❌ |
| **analyst1** (analysts_group) | ✅ Scoped | ❌ (P9 fixed) | ❌ (P9 fixed) | ❌ (P9 fixed) | ❌ | ❌ | ❌ |

**P11 Action items:**
- [ ] 11a: Verify viewer1/analyst1 cannot POST/PUT/PATCH/DELETE on ALL endpoints
- [ ] 11b: Verify auditor1 has read-only on ALL endpoints (can't PATCH data)
- [ ] 11c: Verify dataowner2 is scoped to own org-unit (can't see other org-units)
- [ ] 11d: Add `AdminOrSuperuserOnly` to all admin CRUD viewsets (DQRuleViewSet, CalculationViewSet, ReportConfigViewSet, ModuleViewSet, OrgUnitViewSet)
- [ ] 11e: Verify `HasScopedRole` write-blocking works for ALL viewsets using it (accounts, dataschema)
- [ ] 11f: Verify token refresh doesn't leak privileges
- [ ] 11g: Verify rate limiting on /token/ endpoint

### 11.2 RBAC Automated Test Expansion

| Test | Current | Target |
|------|---------|--------|
| RBAC test files | 3 (accounts, dataschema, emissions) | 8 (all apps with viewsets) |
| Write-blocking tests | 0 explicit | 15+ (one per write-endpoint per read-only role) |
| Cross-org isolation tests | 0 | 5+ (dataowner2 can't see admin1 org data) |
| Token security tests | 1 (test_security.py) | 5+ (refresh, expiry, tampering) |

---

## PHASE 12: PERFORMANCE & OPTIMIZATION

**Goal:** p95 API response <200ms. Page load <2s. No N+1 queries. No memory leaks.

### 12.1 Backend Performance KPIs

| Metric | Current (estimated) | Target | Method |
|--------|---------------------|--------|--------|
| API p95 latency | Unknown | <200ms | Django Debug Toolbar + profiling |
| API p99 latency | Unknown | <500ms | Same |
| N+1 query count | Unknown (likely high in emissions) | 0 | `assertNumQueries` in tests |
| DB query count per dashboard | Unknown | <15 | django-querycount |
| Redis cache hit rate | Unknown | >80% | Redis INFO |
| Memory per worker | Unknown | <200MB | psutil monitoring |
| Bulk import 1000 rows | Unknown | <5s | Timed import |

### 12.2 Optimization Actions

| # | Area | Action |
|---|------|--------|
| P1 | Emissions dashboard | `select_related` / `prefetch_related` audit |
| P2 | MyDataPage | Add pagination to API (check if already paginated) |
| P3 | Calculations | Bulk calculation should use `bulk_create` not individual saves |
| P4 | Cache | Add Redis caching for emission factors, GWP values, module list |
| P5 | DQ profiles | Profile queries should use DB-level aggregation, not Python loops |
| P6 | Static files | Enable gzip/brotli compression in nginx |
| P7 | API responses | Add `select_related` to all list viewsets |

### 12.3 Frontend Performance KPIs

| Metric | Target | Method |
|--------|--------|--------|
| First Contentful Paint | <1.5s | Lighthouse |
| Largest Contentful Paint | <2.5s | Lighthouse |
| Time to Interactive | <3s | Lighthouse |
| Cumulative Layout Shift | <0.1 | Lighthouse |
| Total Bundle Size | <500KB gzipped | `vite build` |
| Lazy-loaded routes | All non-critical pages | Route-based code splitting |
| JavaScript heap after 5min browsing | <50MB | Chrome DevTools |

### 12.4 Frontend Optimization Actions

| # | Action |
|---|--------|
| F1 | Add `React.lazy()` + `<Suspense>` for all route components |
| F2 | Add `memo()` to heavy components (data grids, charts) |
| F3 | Virtualize large data tables (>100 rows) |
| F4 | Debounce search inputs (300ms) |
| F5 | Optimize MUI imports (tree-shaking, no barrel imports) |
| F6 | Add bundle analyzer to build |

---

## PHASE 13: TEST COVERAGE — ENTERPRISE GRADE

**Goal:** 80%+ line coverage. Every service method tested. Every permission class tested.

### 13.1 Current State

| App | Test Files | Est. Coverage | P13 Target |
|-----|-----------|---------------|------------|
| accounts | 7 | ~60% | 85% |
| catalog | 6 | ~45% | 80% |
| core | 3 | ~50% | 80% |
| dataschema | 3 | ~40% | 80% |
| dq | 3 | ~55% | 85% |
| emissions | 8 | ~35% | 80% |
| evidence | 0 | 0% | 70% |
| importexport | 0 | 0% | 70% |
| mdm | 6 | ~55% | 80% |
| connections | 0 | 0% | 60% |
| **TOTAL** | **36** | **~40%** | **80%** |

### 13.2 Test Expansion Plan

| # | App | Tests to Add | Priority |
|---|-----|-------------|----------|
| T1 | emissions | Service layer tests (DashboardService, CalculationEngine, ReportService) | P0 |
| T2 | emissions | Owner endpoint tests with scoped data | P0 |
| T3 | dataschema | ScopedViewSet write-blocking tests per role | P0 |
| T4 | accounts | HasScopedRole write-block regression tests | P0 |
| T5 | accounts | ReadScopedWriteAdmin write-block tests | P1 |
| T6 | dq | DQRuleViewSet permission tests | P1 |
| T7 | dq | Bulk profile + validation tests | P1 |
| T8 | evidence | Evidence CRUD + ownership tests | P1 |
| T9 | importexport | Import/export flow tests | P2 |
| T10 | connections | DataSource CRUD + connection tests | P2 |
| T11 | mdm | ReferenceSet bind/unbind field tests | P1 |
| T12 | catalog | Catalog search + governance compliance tests | P2 |

### 13.3 Test Types Required

| Type | Count Target | Coverage |
|------|-------------|----------|
| Unit tests (service methods) | 100+ | Every service method |
| API integration tests | 80+ | Every endpoint × auth state |
| RBAC tests | 60+ | Every role × every action |
| Permission class tests | 25+ | Every permission class in isolation |
| Error handling tests | 30+ | 400, 401, 403, 404, 500 for all endpoints |
| Frontend component tests | 40+ | Key components (forms, grids, drawers) |

---

## PHASE 14: ARCHITECTURE EXCELLENCE

**Goal:** 0 fat views. Service layer in every app. No dead code. Clean dependency graph.

### 14.1 Service Layer Audit

| App | Has services.py? | Lines | Status | P14 Action |
|-----|-----------------|-------|--------|------------|
| accounts | ❌ | — | 🔴 Missing | Create `accounts/services.py` |
| catalog | ✅ | 17 | 🟡 Too thin | Expand |
| connections | ❌ | — | 🔴 Missing | Create `connections/services.py` |
| core | ❌ | — | 🔴 Missing | Create `core/services.py` |
| dataschema | ❌ | — | 🔴 Missing | Create `dataschema/services.py` |
| dq | ✅ | 535 | 🟢 Good | Maintain |
| emissions | ❌ | — | 🔴 CRITICAL (1418 line views) | Create `emissions/services.py` |
| evidence | ❌ | — | 🔴 Missing | Create `evidence/services.py` |
| importexport | ❌ | — | 🔴 Missing | Create `importexport/services.py` |
| mdm | ❌ | — | 🔴 Missing | Create `mdm/services.py` |

### 14.2 Fat View Extraction (CRITICAL)

**`emissions/views.py` (1,418 lines) → extract to:**
- `emissions/services/dashboard.py` — DashboardAPIView business logic
- `emissions/services/calculation.py` — CalculationEngine, batch calculation
- `emissions/services/reporting.py` — Report generation, GHG protocol
- `emissions/services/owner.py` — Owner dashboard, summary, assets
- `emissions/services/console.py` — Console aggregation
- `emissions/services/comparison.py` — Yearly comparison, trends

### 14.3 Code Quality Checklist

| # | Check | KPI |
|---|-------|-----|
| Q1 | No view >200 lines | 0 violations |
| Q2 | No service >500 lines | 0 violations |
| Q3 | No function >50 lines | <5 violations |
| Q4 | No unused imports | 0 (pylance verified) |
| Q5 | No dead code (unused pages, components, utils) | 0 |
| Q6 | No commented-out code blocks | 0 |
| Q7 | Consistent error response format | 100% of endpoints |
| Q8 | All models have `__str__` | 100% |
| Q9 | All serializers have field validation | 100% |

---

## PHASE 15: FEATURE COMPLETENESS MATRIX

**Goal:** Every planned feature works end-to-end. No half-built features.

### 15.1 Carbon Domain Features — Per App

| App | Feature | Status | P15 Action |
|-----|---------|--------|------------|
| **accounts** | User CRUD | ✅ | — |
| | Group CRUD | ✅ | — |
| | ScopedRole CRUD | ✅ | — |
| | JWT auth + refresh | ✅ | — |
| | Pulse AI authentication | ⚠️ | Test end-to-end |
| | Role registry | ✅ | — |
| | Platform apps enable/disable | ✅ | — |
| **catalog** | Data domains | ✅ | — |
| | Glossary | ✅ | — |
| | Tags (4 tabs) | ✅ | — |
| | Asset profiles (5 tabs) | ⚠️ | Test all tabs |
| | Governance policies | ⚠️ | Test policy engine |
| | Governance compliance | ⚠️ | Test compliance view |
| | Catalog search | ⚠️ | Test search relevance |
| **connections** | Data sources CRUD | ⚠️ | Test + add tests |
| | Consuming connections | ⚠️ | Test + add tests |
| **core** | Modules CRUD | ⚠️ | Write-protect |
| | Feedback system | ✅ | — |
| **dataschema** | Dynamic tables | ✅ | — |
| | Dynamic fields | ✅ | — |
| | Data rows CRUD | ✅ P9 fixed | — |
| | Schema change logs | ⚠️ | Test |
| | Table relations | ⚠️ | Test |
| **dq** | Field profiles | ⚠️ | Test profiling |
| | Table profiles | ⚠️ | Test profiling |
| | DQ rules CRUD | ⚠️ | Write-protect |
| | DQ results | ⚠️ | Test |
| | Bulk profile | ⚠️ | Test |
| | DQ run + validation | ⚠️ | Test |
| | DQ metrics dashboards | ⚠️ | Test |
| **emissions** | Reporting periods | ⚠️ | Test |
| | Emission factors | ✅ | Admin-protected |
| | GWP reference | ✅ | Admin-protected |
| | Calculations | ⚠️ | Write-protect, test engine |
| | Calculation rules | ⚠️ | Test rule execution |
| | Calculation summary | ⚠️ | Test |
| | Dashboard (scope breakdown) | ⚠️ | Optimize queries |
| | Yearly comparison | ⚠️ | Test |
| | Report generation | ⚠️ | Test GHG protocol |
| | Report configs | ⚠️ | Write-protect |
| | Batch calculation | ⚠️ | Test |
| | Owner dashboard | ⚠️ | Test scoping |
| | Owner summary/assets/activity | ⚠️ | Test scoping |
| | My Data | ✅ P9 tested | — |
| | SBTi targets | ⚠️ | Test CRUD |
| | Console | ⚠️ | Test scoping |
| | Verifications | ✅ P9 tested | — |
| | Calculation audits | ⚠️ | Test |
| **evidence** | Evidence CRUD | ❌ | **No tests, no service** |
| **importexport** | Export projects | ❌ | **No tests, no service** |
| | Import jobs | ❌ | **No tests, no service** |
| | Export jobs | ❌ | **No tests, no service** |
| **mdm** | Reference sets | ⚠️ | Test 3 tabs |
| | Reference values | ✅ | — |
| | Bind field | ⚠️ | Test |
| | Field options | ⚠️ | Test |
| | Org units | ⚠️ | Write-protect, test scoping |

### 15.2 Feature Completeness Score

| Status | Count | % |
|--------|-------|---|
| ✅ Complete & tested | 10 | 20% |
| ⚠️ Exists, needs testing | 30 | 61% |
| ❌ Broken/untested | 9 | 18% |
| **TOTAL** | **49** | **100%** |

---

## PHASE 16: ACCESSIBILITY & USER EXPERIENCE

**Goal:** WCAG 2.1 AA. Consistent UX patterns. Professional polish.

### 16.1 Accessibility Checklist

| # | Check | KPI |
|---|-------|-----|
| A1 | All images have alt text | 100% |
| A2 | All form inputs have labels | 100% |
| A3 | Color contrast ratio ≥4.5:1 | 100% |
| A4 | Keyboard navigation works on all pages | Tab through every page |
| A5 | Focus indicators visible | All interactive elements |
| A6 | ARIA landmarks (banner, nav, main, contentinfo) | All pages |
| A7 | Screen reader announces page titles | Test with VoiceOver/NVDA |
| A8 | Skip-to-content link | Present on all pages |

### 16.2 UX Consistency Checklist

| # | Check | KPI |
|---|-------|-----|
| U1 | Same header/banner across all pages | 0 layout shifts between pages |
| U2 | Same sidebar navigation structure | No missing/extra items |
| U3 | Consistent button styling (size, color) | Audit MUI theme |
| U4 | Consistent table styling | Same DataGrid component |
| U5 | Consistent form layout | Same FormField component |
| U6 | Consistent empty state component | Use EmptyState everywhere |
| U7 | Consistent error component | Use ErrorAlert everywhere |
| U8 | Consistent loading component | Use LoadingSkeleton everywhere |
| U9 | Toast notifications for async actions | Use NotificationProvider |
| U10 | Breadcrumbs on every nested page | 100% of non-top-level pages |

### 16.3 Responsive Design

| # | Check | KPI |
|---|-------|-----|
| R1 | All pages render on 320px width | No horizontal scroll |
| R2 | All pages render on 768px (tablet) | No overlapping elements |
| R3 | All pages render on 1440px+ (desktop) | No stretched content |
| R4 | Sidebar collapses on mobile | Hamburger menu works |
| R5 | Data tables scroll horizontally on mobile | No overflow hidden |

---

## PHASED EXECUTION PLAN

| Phase | Name | Duration (est.) | Dependencies | Exit Criteria |
|-------|------|-----------------|--------------|---------------|
| **P10** | Web Robustness | 3-4 sessions | None | 85 pages tested, dead pages deleted, console clean |
| **P11** | RBAC Hardening | 2-3 sessions | P10 | All 50+ endpoints tested × 5 roles, 6 write-protects added |
| **P12** | Performance | 2 sessions | P11 | p95 <200ms, page load <2s, N+1 queries eliminated |
| **P13** | Test Coverage | 3-4 sessions | P11 | 80%+ coverage, 150+ new tests |
| **P14** | Architecture | 2-3 sessions | P13 | 0 fat views, services in all 11 apps, 0 dead code |
| **P15** | Feature Completeness | 2-3 sessions | P14 | 49/49 features tested, 9 broken fixed |
| **P16** | Accessibility & UX | 1-2 sessions | P10 | WCAG 2.1 AA, consistent UX |

### Total: 15-21 sessions for enterprise-grade QA

---

## KPI DASHBOARD — TARGET STATE

| Dimension | Metric | Current | Target | Phase |
|-----------|--------|---------|--------|-------|
| 🌐 Web | Pages with errors | Unknown | 0 | P10 |
| 🌐 Web | Dead pages/routes | Unknown | 0 | P10 |
| 🔐 RBAC | Endpoints with proper RBAC | ~70% | 100% | P11 |
| 🔐 RBAC | Write-blocking for read-only roles | ~60% | 100% | P11 |
| ⚡ Perf | API p95 latency | Unknown | <200ms | P12 |
| ⚡ Perf | Page LCP | Unknown | <2.5s | P12 |
| 🧪 Tests | Line coverage | ~40% | 80%+ | P13 |
| 🧪 Tests | Test count | 310 | 460+ | P13 |
| 🏗️ Arch | Apps with services.py | 2/11 | 11/11 | P14 |
| 🏗️ Arch | Fat views (>200 lines) | ~5 | 0 | P14 |
| 🎯 Features | Features tested | ~20% | 100% | P15 |
| ♿ A11y | WCAG compliance | Unknown | AA | P16 |
| ♿ UX | Consistency score | Unknown | 95%+ | P16 |

---

## IMMEDIATE NEXT ACTIONS (P10 Start)

1. [ ] Start browser, login as admin1
2. [ ] Navigate to every route in 10.1.1 (Core Pages)
3. [ ] Check console for errors on each page
4. [ ] Verify breadcrumbs on each page
5. [ ] Toggle dark mode on each page
6. [ ] Repeat for dataowner2, auditor1, viewer1, analyst1
7. [ ] Log any broken pages, missing breadcrumbs, console errors
8. [ ] Identify dead pages for deletion
9. [ ] Commit P10 findings
