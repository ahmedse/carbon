# TASK: QA-DEEP-MYDATA — Comprehensive My Data Audit
# ======================================================
# Phase: My Data Manager End-to-End QA Audit
# Assigned to: QA/Validator (Low-Medium budget, DeepSeek-V3)
# Author: Master Architect
# Date: 2026-08-03
# Status: READY FOR ASSIGNMENT

---

## 1. SCOPE — The My Data Flow (4 Pages)

The "My Data" experience spans 4 nested page levels. Audit ALL of them:

| # | Page | Route | Component |
|---|------|-------|-----------|
| L1 | My Data (list) | `/carbon/my-data` | `MyDataPage.jsx` |
| L2 | Module Workspace | `/carbon/my-data/:moduleId` | `ModuleWorkspacePage.jsx` |
| L3 | Table Data Entry | `/carbon/my-data/:moduleId/:tableId` | `TableDataPage.jsx` or similar |
| L4 | Row Detail | `/carbon/my-data/row/:tableId/:rowId` | `RowDetailPage.jsx` |

**Every tab, every button, every chip, every text string on all 4 pages must be audited.**

---

## 2. PRE-FLIGHT — Before You Start

```bash
# 1. Read your role file
# 2. Read the QA framework (shared/qa-framework.md)
# 3. Confirm services are running
./manage.sh status

# 4. Login as admin (ahmed/AdminPa_132) on http://localhost:5179/carbon/my-data
# 5. Login as dataowner (facilities.officer/Facilities_123) on a separate browser session
#    to test RBAC. Also try transport.officer/Transport_123 for cross-org isolation.
```

---

## 3. LAYER 1 — STRUCTURAL GATE (run first)

```bash
cd carbon-frontend && npm run build 2>&1 | tail -5
./.ai-toolkit/scripts/verify.sh antipatterns
```

Expected: build clean, 0 new lint errors, 0 hardcoded hex.

---

## 4. LAYER 2 — MyDataPage (L1) Checklist

Navigate to `/carbon/my-data` as **ahmed**.

### 4.1 Header + Breadcrumb
| # | Check | Method | Expected |
|---|---|---|---|
| H1 | Page title | Browser tab | `My Data — Carbon Platform` |
| H2 | Breadcrumb | Read breadcrumb bar | `Home > Carbon Console > My Data` |
| H3 | PageHeader title | Visual | `My Data` |
| H4 | PageHeader subtitle | Visual | Org unit name (e.g., `AAST`) |
| H5 | Description text | Visual | Non-empty, helpful description |

### 4.2 Filter Bar
| # | Check | Method | Expected |
|---|---|---|---|
| F1 | Search field | Type "Facilities" | Filters to Facilities modules only |
| F2 | Clear search | Delete text | All 8 modules reappear |
| F3 | Scope dropdown | Select "Scope 2" | Shows only Scope 2 modules |
| F4 | Scope dropdown | Select "All scopes" | All modules return |
| F5 | Status dropdown | Select "Passing" | Shows only passing modules |
| F6 | Status dropdown | Select "All" | All modules return |
| F7 | Count badge | Visual | Shows `N of 8` where N matches filter |
| F8 | Refresh button | Click | Reloads data (spinner briefly) |

### 4.3 DataGrid
| # | Check | Method | Expected |
|---|---|---|---|
| G1 | Column headers | Visual | Scope, Source Name, Tables, Rows, Status, DQ%, Last Entry, Actions |
| G2 | Scope header tooltip | Hover "Scope" header | Tooltip explains GHG Protocol scopes |
| G3 | DQ% header tooltip | Hover "DQ%" header | Tooltip explains DQ score ranges |
| G4 | Scope chip colors | Visual | S1=green, S2=blue, S3=amber |
| G5 | Status chip icons | Visual | Passing=check, Warning=warn, Failing=error |
| G6 | Row count | Visual | 8 rows (all seeded modules) |
| G7 | Workspace icon per row | Visual | Eye/visibility icon in Actions column |
| G8 | Row click → highlight | Click any row | Row highlights, right panel opens |
| G9 | Row click → panel reset | Click different row | Right panel resets to Trust tab |
| G10 | Pagination | Visual | Shows "1–8 of 8", page size selector |

### 4.4 Right Panel — Trust Tab (selected row)
| # | Check | Method | Expected |
|---|---|---|---|
| T1 | Tab label | Visual | `Trust` (selected) |
| T2 | DQ circular gauge | Visual | Colored progress circle with % |
| T3 | DQ status chip | Visual | Passing/Warning/Failing/No data |
| T4 | Failing rules | Visual | Number (or "—" if no metrics) |
| T5 | Locked | Visual | Yes/No |
| T6 | Last verified | Visual | Date or "Never" |
| T7 | Evidence | Visual | "N docs" |
| T8 | Quality status | Visual | Text status |
| T9 | No row selected state | Click away to deselect | Shows "Select a source to see trust metrics." |
| T10 | Dark mode | Toggle dark mode | All colors adjust (gauge, chips, text) |

### 4.5 Right Panel — Impact Tab
| # | Check | Method | Expected |
|---|---|---|---|
| I1 | Tab label | Click Impact tab | `Impact` |
| I2 | Dependency chain | Visual | Source → Tables → Calc → Reports (4 chips with arrows) |
| I3 | SBTi targets | Visual | "N references this org unit" |
| I4 | Calculations | Visual | "N records linked" |
| I5 | Data consumers | Visual | "Carbon app" chip |
| I6 | No row selected state | Deselect | "Select a source to see downstream impact." |

### 4.6 Right Panel — Activity Tab
| # | Check | Method | Expected |
|---|---|---|---|
| A1 | Tab label | Click Activity tab | `Activity` |
| A2 | Filter chips | Visual | All, Data, DQ, Gov, Calc (5 chips) |
| A3 | Filter active state | Click "Data" | Only Data shows, chip becomes filled |
| A4 | Filter reset | Click "All" | All activity returns |
| A5 | Activity items | Visual | Each has icon + text + timestamp |
| A6 | Empty state | Filter to a type with no data | Shows "No recent activity." |

### 4.7 Workspace Navigation
| # | Check | Method | Expected |
|---|---|---|---|
| W1 | Click workspace icon | Click eye icon on "Facilities - Electricity" | Navigates to `/carbon/my-data/33` |
| W2 | Back button | Click "My Data" in breadcrumb | Returns to `/carbon/my-data` |

---

## 5. LAYER 3 — ModuleWorkspacePage (L2) Checklist

Navigate to `/carbon/my-data/33` (Facilities - Electricity) as **ahmed**.

### 5.1 Header + Breadcrumb
| # | Check | Method | Expected |
|---|---|---|---|
| MH1 | Page title | Browser tab | `My Data Workspace — Carbon Platform` |
| MH2 | Breadcrumb | Visual | `Home > Carbon Console > My Data > Facilities - Electricity` |
| MH3 | Module name | Visual | `Facilities - Electricity` |
| MH4 | Scope chip | Visual | `Scope 2` (blue) |
| MH5 | Subtitle line | Visual | `Scope 2 — 1 tables, N rows` — **N must match grid** |

### 5.2 Tables Grid
| # | Check | Method | Expected |
|---|---|---|---|
| MT1 | Column headers | Visual | Table Name, Rows, Status |
| MT2 | Table row | Visual | "Monthly Electricity Consumption (kWh)" |
| MT3 | Row count | Visual | Actual row count must match subtitle |
| MT4 | Status chip | Visual | "Has Data" or similar |
| MT5 | Open button | Visual | Eye/arrow icon per table row |
| MT6 | Click open | Click the button | Navigates to table data |

### 5.3 Right Panel — Health Tab
| # | Check | Method | Expected |
|---|---|---|---|
| MQ1 | DQ gauge | Visual | Shows a % (NOT "No data" if DQ rules exist) |
| MQ2 | DQ score label | Visual | Passing/Warning/Failing (NOT "No data" for seeded tables) |
| MQ3 | Completion bar | Visual | % of tables with data |
| MQ4 | Table quality list | Visual | Per-table DQ score breakdown |

### 5.4 Right Panel — Lineage, Governance, Activity Tabs
| # | Check | Method | Expected |
|---|---|---|---|
| ML1 | Lineage tab | Click | Shows factor provenance (not empty/error) |
| ML2 | Governance tab | Click | Shows governance events or empty state |
| ML3 | Activity tab | Click | Shows activity feed or "No recent activity" |

### 5.5 Module-level Workspace Actions
| # | Check | Method | Expected |
|---|---|---|---|
| MA1 | Description text | Visual | Non-empty description |
| MA2 | Empty state (if no tables) | Navigate to module with 0 tables | "No tables defined" message |

---

## 6. LAYER 4 — TableDataPage (L3) Checklist

Navigate to `/carbon/my-data/33/69` (Monthly Electricity Consumption) as **ahmed**.

### 6.1 Header + Breadcrumb
| # | Check | Method | Expected |
|---|---|---|---|
| TH1 | Page title | Browser tab | `Data Entry — Carbon Platform` or meaningful |
| TH2 | Breadcrumb | Visual | `Home > Carbon Console > My Data > Facilities - Electricity > Monthly Electricity Consumption (kWh)` |
| TH3 | Table name heading | Visual | `Monthly Electricity Consumption (kWh)` |
| TH4 | "Back to source" button | Click | Returns to module workspace |

### 6.2 Toolbar Buttons
| # | Check | Method | Expected |
|---|---|---|---|
| TB1 | Bulk Import | Visual | Button present, clickable |
| TB2 | Download Template | Visual | Button present, clickable |
| TB3 | Data Quality | Visual | Button present, clickable |
| TB4 | Evidence | Visual | Button present (may be disabled if no rows selected) |
| TB5 | Add Row | Visual | Button present, clickable |

### 6.3 DataGrid
| # | Check | Method | Expected |
|---|---|---|---|
| TD1 | Column headers | Visual | Checkbox, Period Month, Building ID, Consumption, Meter ID, Cost, Evidence, Actions |
| TD2 | Row count | Visual | 48 rows (or current count) |
| TD3 | View Details button | Click on a row | Opens Row Detail page |
| TD4 | Delete button | Visual | Present per row (admin only, dataowner may not see) |
| TD5 | Search/Sort filtering | Use search | Filters rows correctly |

### 6.4 State Coverage
| # | Check | Method | Expected |
|---|---|---|---|
| TS1 | Loading state | Hard refresh page | Skeleton/spinner (not blank white) |
| TS2 | Empty state | Navigate to empty table | "No rows" message (not blank) |
| TS3 | Error state | Disconnect API, reload | Error message with retry |

---

## 7. LAYER 5 — RowDetailPage (L4) Checklist

Navigate to `/carbon/my-data/row/69/476` as **ahmed**.

### 7.1 Header + Breadcrumb
| # | Check | Method | Expected |
|---|---|---|---|
| RH1 | Page title | Browser tab | `Row Detail — Carbon Platform` |
| RH2 | Breadcrumb | Visual | Full path — NOT just `Home > Carbon Console > My Data > Row #476` |
| RH3 | Back button | Visual | Arrow icon, present |
| RH4 | Title | Visual | Row identifier (e.g., "401") |
| RH5 | Subtitle | Visual | `Table Name · Module Name` |
| RH6 | Scope chip | Visual | Scope 2 (blue) |
| RH7 | CO₂e chip | Visual | e.g., `52.75 tCO₂e` (if calculations exist) |
| RH8 | Edit button | Visual | Pencil icon |
| RH9 | Download button | Visual | Download icon |
| RH10 | Refresh button | Visual | Refresh icon |

### 7.2 Overview Tab
| # | Check | Method | Expected |
|---|---|---|---|
| RO1 | Tab label | Visual | `Overview` (selected by default) |
| RO2 | Emission Calculations card | Visual | Factor name, CO₂e value, scope, category, date |
| RO3 | No calculations state | Navigate to row without calcs | Card not shown or shows "No calculations" |
| RO4 | Row Data section | Visual | Field name: value pairs |
| RO5 | Metadata section | Visual | Created date, Updated date |
| RO6 | All field names correct | Visual | Matches actual field names (not raw DB names) |
| RO7 | Hex color audit | Inspect elements | ZERO hardcoded hex colors |

### 7.3 Edit Tab
| # | Check | Method | Expected |
|---|---|---|---|
| RE1 | Tab label | Click Edit tab | `Edit` |
| RE2 | Form fields | Visual | All row fields editable |
| RE3 | Save button | Change a value, click Save | Value persists on reload |
| RE4 | Cancel button | Change a value, click Cancel | Original values restored |
| RE5 | Validation | Enter invalid data | Error message appears |

### 7.4 Evidence Tab
| # | Check | Method | Expected |
|---|---|---|---|
| EV1 | Tab label | Click Evidence tab | `Evidence` |
| EV2 | Upload area | Visual | Drag & drop zone with file type hints |
| EV3 | Empty state | Visual (if no files) | "No evidence yet" |
| EV4 | File list | If files exist | Shows file names, sizes, delete button |

### 7.5 History Tab
| # | Check | Method | Expected |
|---|---|---|---|
| HX1 | Tab label | Click History tab | `History` |
| HX2 | Activity items | Visual | Each has type + detail + timestamp |
| HX3 | Meaningful content | Visual | NOT just "update —" repeated 40 times |
| HX4 | Empty state | Navigate to new row | "No history recorded" |

### 7.6 Right Panel — DQ Metrics Tab
| # | Check | Method | Expected |
|---|---|---|---|
| DQ1 | Tab label | Visual | `DQ Metrics` (default) |
| DQ2 | Status summary | Visual | "X/Y Checks Passed" — numbers must be correct |
| DQ3 | No rules state | Navigate to table with 0 DQ rules | Shows "No validation rules configured" friendly message |
| DQ4 | Re-run button | Click | Triggers validation, refreshes results |
| DQ5 | Rule list | Visual | Each rule: type icon + name + completeness % |
| DQ6 | Rule count | Visual | Matches number of active DQ rules for this table |

### 7.7 Right Panel — Lineage Tab
| # | Check | Method | Expected |
|---|---|---|---|
| LN1 | Tab label | Click Lineage tab | `Lineage` |
| LN2 | Provenance chain | Visual | Factor → Code → Scope chip → Category chip → CO₂e output |
| LN3 | Calculation date | Visual | Shows "Calculated DATE" |
| LN4 | No calcs state | Navigate to row without calcs | Shows "No emission calculations" or similar |

### 7.8 Right Panel — Related Tab ⚠️ CRITICAL
| # | Check | Method | Expected |
|---|---|---|---|
| RL1 | Tab label | Click Related tab | `Related` |
| RL2 | Heading | Visual | "Other rows in this table" |
| RL3 | **Row LIMIT** | Count items | **MUST be ≤ 8** (page_size=8 in API call) — NOT all 48 rows |
| RL4 | Row labels | Visual | period_month or name as label |
| RL5 | Field chips | Visual | 2 field chips per row |
| RL6 | Clickable | Click a related row | Navigates to sibling row detail |
| RL7 | Scroll/pagination | If > 8 rows exist | "View all" link or pagination |

---

## 8. LAYER 6 — RBAC & Data Trust Isolation

Test with **3 different users**. Login as each, navigate the full flow.

### 8.1 Admin (ahmed / AdminPa_132)
| # | Check | Expected |
|---|---|---|
| RB1 | Sees all 8 modules | 8 rows in grid |
| RB2 | Can navigate to any module workspace | 200 OK |
| RB3 | Can edit/delete rows | Buttons visible, actions succeed |
| RB4 | Can run DQ validation | Re-run button works |

### 8.2 Data Owner (facilities.officer / Facilities_123)
| # | Check | Expected |
|---|---|---|
| RD1 | Sees ONLY Facilities modules | 3 modules (Electricity, Water, Chilled Water) |
| RD2 | Does NOT see Transportation/Procurement/Maritime | Those modules absent from grid |
| RD3 | Can navigate to own module workspace | 200 OK |
| RD4 | Can edit rows in own tables | Edit button visible, save succeeds |
| RD5 | Cannot see admin-only actions | No delete on rows (if applicable) |

### 8.3 Cross-Org Isolation (transport.officer / Transport_123)
| # | Check | Expected |
|---|---|---|
| RC1 | Sees ONLY Transportation modules | 1 module (Fleet Fuel) |
| RC2 | Cannot access Facilities module by URL | Navigate to `/carbon/my-data/33` → 403 or redirect |
| RC3 | Cannot access Facilities row by URL | Navigate to `/carbon/my-data/row/69/476` → 403 or redirect |

---

## 9. CROSS-CUTTING CONCERNS

| # | Check | Method | Expected |
|---|---|---|---|
| C1 | Loading states | Hard refresh each page | Skeleton/spinner, NEVER blank white |
| C2 | Error states | Stop backend, reload | Error message with retry button |
| C3 | Empty states | Filter to no results | "No sources match" / "No rows" messages |
| C4 | Dark mode | Toggle on each page | All elements adjust correctly |
| C5 | Responsive 768px | Resize browser | Grid collapses, panels stack |
| C6 | Console errors | Check DevTools on each page | 0 errors (warnings tolerated) |
| C7 | Console warnings | Check DevTools | Only known pre-existing warnings |
| C8 | 404 links | Click every link/button | No broken links |
| C9 | Breadcrumb consistency | Check all 4 pages | Home present, chain complete, no gaps |
| C10 | Page title consistency | Check all 4 tabs | Unique, meaningful titles |

---

## 10. KNOWN ISSUES TO VERIFY (from Master Reconnaissance)

These were observed by the Master Architect during pre-audit reconnaissance. Verify each:

| # | Observation | Where | Expected Resolution |
|---|---|---|---|
| K1 | History tab shows 40+ "update —" entries with no detail | RowDetailPage > History | Must show meaningful activity or empty state |
| K2 | Related tab shows ALL rows (48+), not limited to 8 | RowDetailPage > Related | MUST limit to page_size=8 or add pagination |
| K3 | DQ Score "No data" despite DQ rules seeded | ModuleWorkspacePage > Health tab | Should show actual DQ score from AssetProfile |
| K4 | Subtitle says "0 rows" but grid shows 48 | ModuleWorkspacePage header | Count must be consistent |
| K5 | Breadcrumb missing module+table names | RowDetailPage breadcrumb | Should show full path: My Data > Module > Table > Row |
| K6 | Page title "Data Entry" for table browsing | TableDataPage tab title | Should be `Table Data — Carbon Platform` or similar |
| K7 | Evidence button permanently disabled | TableDataPage toolbar | Should enable when row(s) selected |
| K8 | Row Detail Edit tab not yet verified | RowDetailPage > Edit | Confirm form works with all field types |
| K9 | RowDetailPage receives unused `onRefresh`/`onClose` props | RowDetailPage.jsx | Confirm removed or kept intentionally |
| K10 | Health tab shows table quality as 0% with 0 rules | ModuleWorkspacePage > Health | Should show seeded DQ rules |

---

## 11. VERIFICATION GATE (run before reporting)

```bash
# Run these and include raw output in TASK-RESULTS:
cd /home/ahmed/aast/carbon
./.ai-toolkit/scripts/verify.sh full
cd carbon-frontend && npm run build 2>&1 | tail -5
```

---

## 12. DELIVERABLE — TASK-RESULTS.md

Write a single `TASK-RESULTS-QA-MYDATA.md` at the repo root with:

1. **Executive Summary** — 1 paragraph: what was tested, checklist item count, pass/fail/issue counts by severity
2. **Layer 1 Gate Output** — raw terminal output from verify.sh + build
3. **Checklist Matrix** — complete item-by-item table with #, Check, Method, Expected, Actual, Severity, Evidence
4. **Findings** — each P0/P1/P2 issue: symptom, reproduction steps, severity, suggested fix, evidence
5. **RBAC Matrix** — per-user, per-page access results
6. **Recommendations** — prioritized list of what Master should dispatch next

---

## 13. FILES YOU MAY NEED TO READ

- `/home/ahmed/aast/carbon/carbon-frontend/src/pages/carbon/MyDataPage.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/pages/dataschema/RowDetailPage.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/components/entity/EntityDetailShell.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/components/entity/useDetailPanel.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/pages/dataschema/tabs/RowOverviewTab.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/pages/dataschema/metrics/DQMetricsTab.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/pages/dataschema/metrics/RelatedRecordsTab.jsx`
- `/home/ahmed/aast/carbon/carbon-frontend/src/api/emissions.js`
- `/home/ahmed/aast/carbon/carbon-frontend/src/api/dq.js`
- `/home/ahmed/aast/carbon/carbon-frontend/src/api/catalog.js`

## 14. DO NOT TOUCH

- Do NOT edit any source file — this is an audit, not a fix phase
- Do NOT run database migrations or seed commands
- Do NOT modify .env or configuration
- Report findings ONLY — fixes are dispatched separately by the Master

---

*End of TASK spec. Assign to QA/Validator worker with model DeepSeek-V3.*
