# TASK-A10.md — RUN A10: Data Quality Integration & Dashboard

**Date:** 2026-07-19  
**Executor:** Raptor (AI Copilot)  
**Mode:** Execute in 5 phases (similar to A8)  
**Status:** 📋 READY FOR EXECUTION

---

## MASTER CONTEXT

This task continues the Master/Worker protocol established in RUN A0. As Worker (Raptor), execute each phase in sequence and report results after each phase. Master (Architect) will review, validate, and approve before moving to next phase.

**Key Principle:** Keep Data Quality features **integrated within Data Hub context** — no separate `/dataschema/dq` dashboard navigation. DQ is a concern of the Data Hub, not a separate studio.

---

## 1. HEADER

**Project:** Carbon Data Trust Platform  
**Component:** Data Quality Integration & Dashboard  
**Scope:** Backend DQ metrics APIs + Frontend DQ dashboard components  
**Sprint:** A10  
**Epic:** Data Governance & Quality Assurance

---

## 2. OBJECTIVE

Integrate Data Quality features into the Data Hub context. Users should see data quality assessments, rules, and health metrics as part of their module/table view — not as a separate dashboard. Enable org-scoped users to understand data quality at module and table levels with GHG Scope 1/2/3 breakdowns.

**Why This Matters:**
- Users currently must navigate away from Data Hub to see DQ metrics (bad UX)
- DQ rules and results are orphaned from data context
- No visibility into which rows/tables violate DQ rules
- Missing link between bulk import (A9) quality and DQ assessment

---

## 3. SCOPE — IN

### Backend (Django DQ App)
- [x] Existing models: `TableProfile`, `FieldProfile`, `DQRule`, `DQResult` (already in `backend/dq/models.py`)
- [ ] **API 1:** `GET /carbon-api/dq/metrics/` — Scoped org unit DQ summary (completeness, uniqueness, compliance %)
- [ ] **API 2:** `GET /carbon-api/dq/metrics/table/{tableId}/` — Table-level profiles + active rules
- [ ] **API 3:** `GET /carbon-api/dq/metrics/field/{fieldId}/` — Field-level profiles
- [ ] **API 4:** `GET /carbon-api/dq/results/?data_table={id}` — DQ check results for rows (with row ID + rule + status)
- [ ] **API 5:** `POST /carbon-api/dq/rules/run-now/` — Trigger DQ validation for table/rows on demand
- [ ] Fix permission class: Apply `ReadScopedWriteAdmin` (not `ReadAnyWriteGlobalAdmin`)
  - Org-scoped users can read DQ metrics for their modules
  - Only global admins can create/modify rules
- [ ] RBAC: Users see DQ data only from assigned modules (scope-filter ViewSets)

### Frontend (React Components)

#### New Components
- [ ] **`DataQualityCard.jsx`** — Summary card for embedding in module landing page
  - Displays: Overall completeness %, uniqueness %, compliance %
  - Icon badge: Green (>90%) / Yellow (70-90%) / Red (<70%)
  - Click → Opens DQ drawer or modal

- [ ] **`DQMetricsDrawer.jsx`** — Detailed metrics drawer (similar to Evidence modal)
  - Tabs: Overview | Rules | Results | Trends
  - Overview tab: Table profile + field profiles in expandable list
  - Rules tab: Active DQ rules per table + status
  - Results tab: Recent DQ check results with row ID + error details
  - Trend tab: 30-day quality trend chart (optional, Phase 5)

- [ ] **`DQRulesList.jsx`** — Read-only list of active rules for table
  - Rule type, severity, status, last checked
  - Shows which fields are covered by rules

#### Updated Components
- [ ] **`ModuleLandingPage.jsx`** — Add DataQualityCard in top section
  - Position: Below module selector, above table grid
  - Shows org unit health across selected module
  
- [ ] **`TableDataPage.jsx`** — Add "Data Quality" button in toolbar
  - Opens DQMetricsDrawer with table-specific metrics
  - Shows which data rows failed which rules (if available)

### API Integration
- [ ] Update `carbon-frontend/src/api/dq.js` (new file):
  - `getOrgDQMetrics()` — Org-scoped summary
  - `getTableDQMetrics(tableId)` — Table + field profiles
  - `getFieldDQMetrics(fieldId)` — Field profile details
  - `getDQResults(tableId)` — Rule check results
  - `runDQValidation(tableId)` — Trigger on-demand DQ run

### Navigation & Context
- [ ] Breadcrumbs: Ensure DQ context preserved (not breaking breadcrumb chain)
- [ ] No separate route like `/dq` or `/dataschema/dq` — DQ is embedded in Data Hub flows

---

## 4. SCOPE — OUT (DO NOT TOUCH)

- ❌ Separate `/dataschema/dq` dashboard page (out of scope — intentional)
- ❌ Advanced DQ rule creation UI (global admins only, via API if needed)
- ❌ Machine learning-based anomaly detection (future feature)
- ❌ DQ automation scheduling/triggers (future feature)
- ❌ Historical DQ audit logs (consider for A11)
- ❌ Pulse integration (separate from this RUN)

---

## 5. PRECONDITIONS / SETUP

### Database & Backend Ready
- [x] `backend/dq/models.py` exists with `TableProfile`, `FieldProfile`, `DQRule`, `DQResult`
- [x] `backend/dq/views.py` exists with ViewSets (may need permission fixes)
- [x] Database migrations applied (`python manage.py migrate dq`)
- [x] Test data seeded (some DQRule + TableProfile/FieldProfile records exist)

### Frontend Ready
- [x] React 18 + Material-UI v5
- [x] React Router (nav structure)
- [x] Axios + AuthContext (API calls with auth)
- [x] Layout + Shell + Navigation (context preserved)

### Current Architecture
- [x] Shell layout enabled by default (A6)
- [x] Perspective tabs in header (A5)
- [x] Module landing page exists (A6)
- [x] Evidence drawer pattern established (A8)

### Test Fixtures
Ensure these exist in test data:
- 1+ org unit (AAST Transportation)
- 1+ module assigned to org unit (Transport Scope 1/2)
- 1+ data table in module (Fuel Consumption)
- 1+ data fields in table
- 1+ DQRule for at least one field (not_null, unique, range, etc.)
- 1+ TableProfile (with completeness_pct, row_count)
- 1+ FieldProfile (with null_count, uniqueness_pct)
- 1+ DQResult (rule_id, data_row_id, passed=True/False, message)

**Setup Command:**
```bash
python manage.py migrate
python manage.py seed_demo_data  # Or run test setup in Phase 1
```

---

## 6. EXECUTION PLAN — 5 PHASES

### Phase 1: Backend API Setup & RBAC Fixes
**Duration:** 1-2 hours  
**Owner:** Worker (Raptor)

**Steps:**

1. **Audit existing DQ views**
   - Read: [`backend/dq/views.py`](backend/dq/views.py)
   - Check: Permission class on each ViewSet
   - Issue: Currently using `ReadAnyWriteGlobalAdmin` (allows all users to read)
   - Fix needed: Apply `ReadScopedWriteAdmin` (org-scoped read, admin write)

2. **Fix ViewSet permissions**
   - [ ] `TableProfileViewSet` → Add `ReadScopedWriteAdmin` + `get_queryset()` scope filter
     - Query: `filter(data_table__org_unit_id__in=get_allowed_org_unit_ids(user))`
   - [ ] `FieldProfileViewSet` → Same scoping via data_field.data_table.org_unit_id
   - [ ] `DQRuleViewSet` → Same scoping
   - [ ] `DQResultViewSet` → Same scoping (so users see results only from their tables)

3. **Create new API endpoints**
   - [ ] `GET /carbon-api/dq/metrics/`
     - Query string: `?scope=1` (optional, filter by GHG scope if data supports it)
     - Returns: `{ org_unit_id, org_unit_name, completeness_pct, uniqueness_pct, compliance_pct, table_count, total_rows }`
     - Logic: Aggregate TableProfile stats for user's org units

   - [ ] `GET /carbon-api/dq/metrics/table/{tableId}/`
     - Returns: `{ table_id, table_name, row_count, completeness_pct, active_rules: [...], field_profiles: [...] }`
     - Guards: User must have module role for this table

   - [ ] `GET /carbon-api/dq/metrics/field/{fieldId}/`
     - Returns: Full FieldProfile + recent rule check results

   - [ ] `GET /carbon-api/dq/results/?data_table={id}` (existing, but verify scoping)
     - Returns: DQResult list for table (should already be scoped)

   - [ ] `POST /carbon-api/dq/rules/run-now/`
     - Body: `{ "data_table": id }`
     - Action: Trigger `run_dq()` from `dq/services.py` (should already exist)
     - Returns: `{ status: "queued|running|complete", message }`

4. **Test API endpoints manually**
   - [ ] Start backend: `python manage.py runserver`
   - [ ] Use curl or Postman to test each endpoint
   - [ ] Verify org-scoped user gets data only from assigned modules
   - [ ] Verify global admin gets all data
   - [ ] Verify non-admin cannot modify rules (403)

5. **Update `config/urls.py`** (if new endpoints not auto-registered)
   - Ensure DQ ViewSets are registered in router

**Acceptance Criteria — Phase 1:**
- [ ] All 5 API endpoints respond (200 OK)
- [ ] Org-scoped user sees only their modules' DQ data
- [ ] Global admin sees all DQ data
- [ ] Non-admin cannot POST/DELETE rules (403)
- [ ] Response schemas match component expectations (see Phase 2)
- [ ] No console errors in backend logs

---

### Phase 2: Frontend API Integration Layer
**Duration:** 1 hour  
**Owner:** Worker (Raptor)

**Steps:**

1. **Create `carbon-frontend/src/api/dq.js`**
   - [ ] Import: `{ apiFetch, API_ROUTES }`
   - [ ] Function: `getOrgDQMetrics(token, options={})`
   - [ ] Function: `getTableDQMetrics(token, tableId)`
   - [ ] Function: `getFieldDQMetrics(token, fieldId)`
   - [ ] Function: `getDQResults(token, tableId, options={})`
   - [ ] Function: `runDQValidation(token, tableId)` — POST with spinner
   - [ ] Error handling: Catch and return null on 403 (user not authorized for table)

2. **Test functions in browser console**
   - [ ] Login as data-owner (single module)
   - [ ] Run `getOrgDQMetrics(token)` → Should return their org's metrics
   - [ ] Run `getTableDQMetrics(token, 1)` → Should return table 1 metrics (if assigned)
   - [ ] Try table outside their assignment → Should return null or empty
   - [ ] Login as admin → All functions should work for all tables

**Acceptance Criteria — Phase 2:**
- [ ] `dq.js` exports all 6 functions
- [ ] All functions properly construct URLs and headers
- [ ] Error handling graceful (no unhandled promise rejections)
- [ ] Console tests show correct scoping behavior

---

### Phase 3: Frontend Components — DQ Card & Drawer
**Duration:** 2-3 hours  
**Owner:** Worker (Raptor)

**Steps:**

1. **Create `carbon-frontend/src/components/dq/DataQualityCard.jsx`**
   - Props: `tableId` (optional), `metrics` (object with completeness_pct, etc.), `onViewDetails` (callback)
   - Display:
     ```
     ┌─────────────────────────────┐
     │ 📊 Data Quality: 87%         │
     │                             │
     │ Completeness: ████░ 92%    │
     │ Uniqueness:   ███░░ 75%    │
     │ Compliance:   ███░░ 82%    │
     │                             │
     │ Rules: 3 active | Last: now │
     │ [View Details] [Run Check]  │
     └─────────────────────────────┘
     ```
   - Color coding: Green ≥90%, Yellow 70-89%, Red <70%
   - Callbacks: `onViewDetails()` → Open drawer, `onRunNow()` → Trigger validation

2. **Create `carbon-frontend/src/components/dq/DQMetricsDrawer.jsx`**
   - Props: `open`, `onClose`, `tableId`, `token`
   - State: `activeTab` (0-2: Overview | Rules | Results)
   - **Tab 0: Overview**
     - Fetch: `getTableDQMetrics(token, tableId)`
     - Display: Table profile (row_count, completeness_pct)
     - Expandable list: Field profiles (name, null_count, uniqueness_pct)
   - **Tab 1: Rules**
     - Fetch: DQ rules for table (from metrics endpoint)
     - Display: Rule type, severity, status
     - Read-only (edit rules requires admin studio)
   - **Tab 2: Results**
     - Fetch: `getDQResults(token, tableId)`
     - Display: Recent check results (data_row_id, rule_id, passed, message)
     - Table format: Row ID | Rule | Status | Message
     - Limit: Show last 20 results
   - **Button:** "Run DQ Now" → Call `runDQValidation(token, tableId)` + spinner

3. **Create `carbon-frontend/src/components/dq/DQRulesList.jsx`**
   - Simple read-only component (nested in drawer)
   - Props: `rules` (array)
   - Display: `rule_type | field | severity | active`

4. **Test components in browser**
   - [ ] Import components in `ModuleLandingPage`
   - [ ] Pass mock metrics data → Verify rendering
   - [ ] Verify color coding (green/yellow/red)
   - [ ] Verify "Run DQ Now" button is functional
   - [ ] Check responsive design (mobile view)

**Acceptance Criteria — Phase 3:**
- [ ] DataQualityCard renders correctly
- [ ] DQMetricsDrawer opens/closes properly
- [ ] Tab switching works
- [ ] API calls made on mount (with error handling)
- [ ] "Run DQ Now" makes POST request to backend
- [ ] No console errors

---

### Phase 4: Component Integration & UX Polish
**Duration:** 1-2 hours  
**Owner:** Worker (Raptor)

**Steps:**

1. **Integrate DataQualityCard into `ModuleLandingPage.jsx`**
   - [ ] Add import: `import { DataQualityCard } from '../components/dq/DataQualityCard'`
   - [ ] Add state: `const [dqDrawerOpen, setDqDrawerOpen] = useState(false)`
   - [ ] Add useEffect to fetch org metrics:
     ```javascript
     useEffect(() => {
       if (token) {
         getOrgDQMetrics(token)
           .then(metrics => setOrgMetrics(metrics))
           .catch(e => console.error('DQ fetch failed:', e));
       }
     }, [token, selectedModule]);
     ```
   - [ ] Render card in JSX (below module selector, above table grid)
   - [ ] Hook up `onViewDetails` → `setDqDrawerOpen(true)`

2. **Integrate DataQualityCard into `TableDataPage.jsx`**
   - [ ] Add "Data Quality" icon button in toolbar (next to Export/Evidence)
   - [ ] Click handler: `setDqDrawerOpen(true)`
   - [ ] Fetch table-specific metrics:
     ```javascript
     useEffect(() => {
       if (dqDrawerOpen) {
         getTableDQMetrics(token, tableId)
           .then(metrics => setTableDqMetrics(metrics));
       }
     }, [dqDrawerOpen]);
     ```

3. **Render DQMetricsDrawer in both pages**
   - [ ] Props: `open={dqDrawerOpen}`, `onClose={() => setDqDrawerOpen(false)}`, `tableId`, `token`

4. **Verify breadcrumbs not broken**
   - [ ] Navigate: Data Hub → Module → Table → Click DQ button
   - [ ] Verify breadcrumb still shows: Home > Data Hub > Module > Table

5. **Verify navigation isolation**
   - [ ] Ensure opening DQ drawer does NOT change URL
   - [ ] DQ is modal overlay (drawer), not a route

6. **Test in browser**
   - [ ] Login as data-owner
   - [ ] Navigate to module landing page → See DataQualityCard with metrics
   - [ ] Click card → Drawer opens with details
   - [ ] Click "Run DQ Now" → Spinner shows, then completes
   - [ ] Close drawer → Module page still visible
   - [ ] Navigate to table grid → See "Data Quality" button in toolbar
   - [ ] Click button → Drawer shows table-specific metrics
   - [ ] Verify RBAC: Try table outside assignment → Should not see metrics

**Acceptance Criteria — Phase 4:**
- [ ] DataQualityCard visible in ModuleLandingPage
- [ ] DataQualityCard visible in TableDataPage toolbar
- [ ] DQMetricsDrawer opens/closes without breaking navigation
- [ ] Breadcrumbs preserved throughout flow
- [ ] API calls made on demand (not on every render)
- [ ] Org-scoped user sees only their data
- [ ] No 404s or console errors
- [ ] Build succeeds: `npm run build`

---

### Phase 5: Testing & Documentation
**Duration:** 1-2 hours  
**Owner:** Worker (Raptor)

**Steps:**

1. **Backend API Testing** (automated)
   - [ ] Create test file: `backend/dq/tests/test_api_scoping.py`
   - [ ] Test 1: Org-scoped user gets only their org's metrics
   - [ ] Test 2: Org-scoped user cannot access other org's metrics
   - [ ] Test 3: Global admin gets all metrics
   - [ ] Test 4: Non-admin cannot POST DQ rules (403)
   - [ ] Test 5: DQ results endpoint returns only user's table results
   - [ ] Run tests: `pytest backend/dq/tests/test_api_scoping.py -v`
   - [ ] Target: 5/5 PASS

2. **Frontend Component Testing** (manual browser tests)
   - [ ] Test scenario: Data-owner (single module)
     - Navigate to module landing page
     - Verify DataQualityCard shows (not empty)
     - Click card → Drawer opens with 3 tabs
     - Verify Overview tab shows table + field profiles
     - Verify Rules tab shows active rules
     - Verify Results tab shows recent DQ checks
     - Click "Run DQ Now" → API call made, spinner visible
   
   - [ ] Test scenario: Admin user
     - Same flow, but should see all org metrics (not scoped)
   
   - [ ] Test scenario: Unauthorized table
     - Try direct URL to table user not assigned → DQ drawer should not show metrics (or show error gracefully)
   
   - [ ] Test scenario: RBAC
     - Org-scoped admin for Org A tries to view Org B's metrics → Should get 403 or empty
   
   - [ ] Test scenario: Responsive design
     - Open drawer on mobile (375px width) → Drawer should be readable
   
   - [ ] Test scenario: No data
     - If org has no DQ metrics yet → Card should show "No data" or "—" gracefully

   - Create test report: `PHASE4_DQ_BROWSER_TESTS.txt` (document findings)

3. **Build & Lighthouse Check**
   - [ ] Build frontend: `npm run build`
   - [ ] Expected: Success in <15 seconds
   - [ ] Check bundle size: `npm run build` shows size info
   - [ ] Expected: No significant increase (components are ~30KB with compression)
   - [ ] Run Lighthouse on module page (Chrome DevTools)
   - [ ] Target: Performance >80, Accessibility >90

4. **Create TASK-RESULT-A10.md**
   - Summary (what was built)
   - Implementation details (APIs, components, integration)
   - Phase 5 test results (29/29 PASS target)
   - Acceptance criteria validation (checklist)
   - Files changed (count + list)
   - Known limitations / future work
   - Git commit hashes

5. **Git Commit**
   - [ ] Stage all files: `git add -A`
   - [ ] Commit message:
     ```
     RUN A10 Phase 5: DQ Integration complete
     
     - Backend: 5 new API endpoints with scoped RBAC
     - Frontend: 3 new components (Card, Drawer, RulesList)
     - Integration: ModuleLandingPage + TableDataPage
     - Testing: 5 backend tests + 8 browser scenarios
     - Acceptance: All criteria PASS
     
     Signed-off by: Raptor
     ```
   - [ ] Verify commit: `git log --oneline -1`

6. **Update docs/RUN_LOG.md**
   - Add A10 entry (similar to A8 format):
     ```markdown
     ### A10: Data Quality Integration & Dashboard (2026-07-19) ✅
     **Objective:** Integrate DQ features into Data Hub context (no separate dashboard)
     **Actions:**
     - Backend: 5 scoped API endpoints (metrics, rules, results)
     - Frontend: 3 components (Card, Drawer, RulesList)
     - Integration: ModuleLandingPage + TableDataPage
     - Testing: 29/29 PASS (5 backend + 8 browser + 16 regression)
     ...
     ```

**Acceptance Criteria — Phase 5:**
- [ ] All backend tests pass (5/5)
- [ ] All browser test scenarios pass (8/8)
- [ ] Build succeeds with no warnings
- [ ] TASK-RESULT-A10.md created (full documentation)
- [ ] docs/RUN_LOG.md updated with A10 entry
- [ ] Git commit created and verified
- [ ] No regressions (existing features still work)

---

## 7. ACCEPTANCE CRITERIA

| Criterion | Phase | Verify How | Expected |
|-----------|-------|-----------|----------|
| **A10.1** | 1 | curl GET `/carbon-api/dq/metrics/` | 200 OK, org-scoped data |
| **A10.2** | 1 | curl GET `/carbon-api/dq/metrics/table/{id}/` | 200 OK + table profile + rules |
| **A10.3** | 1 | curl GET `/carbon-api/dq/results/?data_table={id}` | 200 OK, scoped results |
| **A10.4** | 1 | Non-admin POST rule → 403 | Forbidden response |
| **A10.5** | 2 | Browser console: `getOrgDQMetrics(token)` | Returns object with metrics |
| **A10.6** | 2 | Browser console: Org-scoped user API call | Returns only their org data |
| **A10.7** | 3 | Render `DataQualityCard` with mock data | Card displays metrics + % bars |
| **A10.8** | 3 | Render `DQMetricsDrawer` | 3 tabs render, data visible |
| **A10.9** | 4 | Navigate ModuleLandingPage → Click card | Drawer opens, no URL change |
| **A10.10** | 4 | Click "Data Quality" button in table toolbar | Drawer opens with table metrics |
| **A10.11** | 4 | Breadcrumb during DQ interaction | Unchanged from before drawer open |
| **A10.12** | 4 | npm run build | Success, <15s, no errors |
| **A10.13** | 5 | pytest backend/dq/tests/test_api_scoping.py | 5/5 PASS |
| **A10.14** | 5 | Browser test: Data-owner flow | Complete without errors |
| **A10.15** | 5 | Browser test: Admin flow | All metrics visible |
| **A10.16** | 5 | Browser test: Unauthorized table | Graceful error or no data |
| **A10.17** | 5 | TASK-RESULT-A10.md | All sections complete |
| **A10.18** | 5 | git log | A10 commit exists |

**Target: 18/18 = 100% PASS**

---

## 8. DELIVERABLE FORMAT

### Phase 1 Deliverable
- Modified files: `backend/dq/views.py`, `config/urls.py` (if needed)
- Test results: curl output for all 5 endpoints
- Git commit hash

### Phase 2 Deliverable
- New file: `carbon-frontend/src/api/dq.js`
- Browser console test output
- Git commit hash

### Phase 3 Deliverable
- New files: `carbon-frontend/src/components/dq/DataQualityCard.jsx`, `DQMetricsDrawer.jsx`, `DQRulesList.jsx`
- Browser screenshot: Components rendered
- Git commit hash

### Phase 4 Deliverable
- Modified files: `ModuleLandingPage.jsx`, `TableDataPage.jsx`
- Browser screenshot: DQ card visible in module page
- Browser screenshot: DQ button in table toolbar
- Git commit hash

### Phase 5 Deliverable
- Test file: `backend/dq/tests/test_api_scoping.py` (5 tests)
- Test report: `PHASE4_DQ_BROWSER_TESTS.txt` (8 scenarios)
- Build output: `npm run build` success confirmation
- **Final:** `TASK-RESULT-A10.md` (full report, 400-500 lines)
- Updated: `docs/RUN_LOG.md` (A10 entry added)
- Git commit message + log

---

## 9. DEFINITION OF DONE

A phase is complete when:
1. ✅ All code is written and committed
2. ✅ All manual tests pass (or automated tests pass)
3. ✅ No console errors (F12 DevTools clean)
4. ✅ No new test failures (regression check)
5. ✅ Code follows project patterns (see existing components)
6. ✅ RBAC is enforced (org-scoped users see only their data)
7. ✅ Response ready for Master review

---

## 10. ESCALATION

If Worker encounters blocking issues:
- Phase 1: Backend API design unclear → Ask Master for API response schema examples
- Phase 2: API endpoint returning different schema → Adjust component expectations or ask Master to clarify backend
- Phase 3: Material-UI pattern unfamiliar → Reference existing component (e.g., `EvidenceUploader.jsx` from A8)
- Phase 4: Breadcrumb navigation breaking → Check Shell component integration (Master can advise)
- Phase 5: Test failures → Document exact error, ask Master for guidance

---

## 11. REFERENCE

**Backend Models:**
- [`backend/dq/models.py`](backend/dq/models.py) — TableProfile, FieldProfile, DQRule, DQResult

**Backend Views:**
- [`backend/dq/views.py`](backend/dq/views.py) — Existing ViewSets (need permission fixes)

**Existing API Pattern:**
- [`backend/dataschema/views.py`](backend/dataschema/views.py:104-131) — DataRowViewSet pattern
- [`carbon-frontend/src/api/dataschema.js`](carbon-frontend/src/api/dataschema.js) — API client pattern

**Existing Components (Reference Patterns):**
- [`carbon-frontend/src/components/EvidenceUploader.jsx`](carbon-frontend/src/components/EvidenceUploader.jsx) — Drag-drop + upload pattern
- [`carbon-frontend/src/components/EvidenceViewer.jsx`](carbon-frontend/src/components/EvidenceViewer.jsx) — Drawer + tabs pattern
- [`carbon-frontend/src/pages/ModuleLandingPage.jsx`](carbon-frontend/src/pages/ModuleLandingPage.jsx) — Where to integrate card

**Shell & Navigation:**
- [`carbon-frontend/src/shell/Shell.jsx`](carbon-frontend/src/shell/Shell.jsx) — Shell layout
- [`carbon-frontend/src/components/Layout.jsx`](carbon-frontend/src/components/Layout.jsx) — Breadcrumbs integration

**RBAC Utilities:**
- [`backend/accounts/rbac_utils.py`](backend/accounts/rbac_utils.py) — Scoping helpers
- [`backend/accounts/permissions.py`](backend/accounts/permissions.py) — ReadScopedWriteAdmin class

**Testing Examples:**
- [`backend/test_governance_rbac.py`](backend/test_governance_rbac.py) — RBAC test pattern
- Phase 4 test results from A8/A9 (format reference)

---

## 12. MASTER REVIEW CHECKPOINTS

After each phase, Worker will create a summary report (similar to PHASE2_A9_COMPLETION_SUMMARY.txt) with:
- Phase objective
- Steps completed
- Acceptance criteria validation (checkbox list)
- Test results (if applicable)
- Files changed (with line counts)
- Git commit hash
- Any blockers or decisions made

Master will then:
1. Review code/API design
2. Validate against acceptance criteria
3. Approve or request revisions
4. Sign off: "Approved for Phase N+1"

---

**Ready for execution. Worker: Begin Phase 1.**
