# TASK-RESULT — Data Product Detail Page Remake (AI-Toolkit Compliance)

**Date:** 2026-08-11
**Role:** Frontend Worker
**Task:** `TASK-DATA-PRODUCT-DETAIL-REMAKE.md` — remake the Data Product detail page following the `BaseDetailPage` golden pattern, wire the new backend endpoints (quality_summary / audit_trail / module timestamps), and fix the remaining list-page anti-patterns.
**Scope:** Frontend only (`carbon-frontend/src/`) — **no backend edits** (backend Phase 1 delivered by backend worker).
**Task File Section 7 deliverable filenames matched EXACTLY** (10 frontend files listed there + 1 supporting constants file).

---

## 1. Audit Findings (OLD detail page)

| # | Violation | Severity |
|---|-----------|----------|
| 1 | **Not a BaseDetailPage shell** — bespoke layout with own header/tabs/metrics, bypassing the design system's shared detail scaffolding (CB-15) | CRITICAL |
| 2 | **`window.confirm` for delete** — no table-count warning, not `ConfirmDialog` | High |
| 3 | **Module data from context, not API** — stale module list snapshot; no `fetchModule(id)`; timestamps not available | High |
| 4 | **No Quality tab** — quality info absent despite `quality_summary` endpoint existing | High |
| 5 | **No Audit tab** — governance events invisible despite `audit_trail` endpoint existing | High |
| 6 | **Inline Edit form duplicated from list page** — two divergent copies of the product form (A7) | Medium |
| 7 | **No Metrics panel** — detail pages must show the resizable metrics panel with product statistics | Medium |
| 8 | **No table sub-navigation** — Tables tab was a static list, not a navigable DataGrid with create/edit/delete | Medium |
| 9 | **No created/updated timestamps** — Module had no timestamps until backend Phase 1; nothing displayed | Medium |
| 10 | **Inline raw Dialog + manual Snackbar** — not `SystemDialog` + `useNotification` | Medium |

## 2. Remake — What Changed

### New files (7)
- **`src/pages/catalog/tabs/DataProductOverviewTab.jsx`** (NEW) — read-only metadata: Basic Information (ID/Name/Description/Scope chip via `SCOPE_COLOR {1:'error',2:'warning',3:'primary'}`), Governance (Org Unit, Status chip Locked→warning/Unlocked→success, Quality chips), Statistics (Tables, Quality Score), Timestamps (Created/Updated via `toLocaleString`). Follows `ReferenceSetOverviewTab` pattern (`DetailTabContent` + `Table size="small"` + label cell `fontWeight 500, width '25%', bgcolor 'grey.50'`).
- **`src/pages/catalog/tabs/DataProductTablesTab.jsx`** (NEW) — DataGrid `density="compact"` (height 420, pageSizeOptions [10,25,50]) of child dataschema tables: Title (Button → `/catalog/tables/:id`), Description, Rows (`row_count`), Quality (Chip), Modified (`updated_at`), Actions (admin-gated View/Edit/Delete). Search box + "New Table" (admin-gated). Create/edit via `SystemDialog`, delete via `ConfirmDialog` (table-count message). All hooks declared before the `if (!entityData)` guard (rules-of-hooks).
- **`src/pages/catalog/tabs/DataProductDQTab.jsx`** (NEW) — stat-card grid (auto-fit minmax 150px): Tables Checked / Passing / Warning / Failing / Pass Rate / Avg Score, then per-table quality table (row hover, navigate on click). Data from `qualitySummary` + `assets` maps.
- **`src/pages/catalog/tabs/DataProductEditTab.jsx`** (NEW) — shared `ProductForm` (readOnly when `!isAdmin`), "Save Changes" (PATCH via `updateModule`) + "Delete Data Product" (admin-gated) → `ConfirmDialog` with table-count warning (NO `window.confirm`). `handleDelete` → `deleteModule` → navigate `/catalog/products`. Alert when `!isAdmin`.
- **`src/pages/catalog/tabs/DataProductAuditTab.jsx`** (NEW) — DataGrid `density="compact"` of governance events: Timestamp / Action (Chip via `ACTION_COLOR` map: add|create→success, edit|update→info, delete→error, archive|lock→warning, unlock|publish→info) / Entity (`entity_type #entity_id`) / User / Details. Empty → Alert "No governance events recorded for this data product."
- **`src/pages/catalog/tabs/DataProductMetricsPanel.jsx`** (NEW) — follows `ReferenceSetMetricsPanel`: caption-label MetricCards — Tables, Total Rows (sum `row_count`), Quality Pass Rate (≥80% success else warning), Avg Score, Last Modified (max of product + tables `updated_at`); `<Divider sx={{my:3}} />` then Governance summary (Org Unit, Scope, Lock Status, Audit Events count).
- **`src/components/dataproducts/ProductForm.jsx`** (NEW) — shared form field set (A7 fix): Name (required), Description (multiline rows=2), Scope (select, `SCOPE_OPTIONS`), Org Unit (select with "— None —"), Is Locked (Switch, `showLock` only). All `size="small"`, NO `margin="normal"`, theme tokens only.

### Rewritten / updated files (4)
- **`src/pages/catalog/DataProductDetailPage.jsx`** (REWRITE) — thin `BaseDetailPage` shell:
  - Data via `Promise.all` in `loadData`: `fetchModule(token, moduleId)` + `fetchDataSchemaTables(token, null, moduleId)` + `fetchAssetProfiles(token)` + `fetchOrgUnits(token)` + `fetchModuleQualitySummary(token, moduleId)` + `fetchModuleAuditTrail(token, moduleId)` — optional fetches `.catch(() => [])`/`null`.
  - `assetMap` built `{data_table: asset}` for assets with no `data_field`; `unwrap()` helper (array or `data.results`).
  - Admin gate: `can(user, 'manage', 'catalog', { perspectives, isGlobalAdminFlag, capabilities, modules })` (CB-13) → `isAdmin`; Edit tab + edit/delete actions gated on it.
  - Not-found guard → `DetailHeader` "Data Product Not Found".
  - `mainTabs = [Overview, Tables, DQ, Edit (admin), Audit]`, `metricsTabs = [Metrics]`, `storageKey="carbonDataProductDetail"` (tab/panel persistence via localStorage).
  - `headerComponent = <DetailHeader title description icon={Inventory2Icon} onClose={() => navigate(-1)} />`.
- **`src/pages/catalog/DataProductsPage.jsx`** (UPDATE) — removed inline `ProductDialog` + now-unused imports; uses shared `ProductForm` inside `SystemDialog` (same dialog geometry as before: 520/560/420/460/calc-32px). `SCOPE_LABEL`/`SCOPE_OPTIONS` now from `constants/terminology.js`.
- **`src/api/modules.js`** (UPDATE) — added `fetchModule(token, id)`, `fetchModuleQualitySummary(token, id)` → `.../{id}/quality_summary/`, `fetchModuleAuditTrail(token, id)` → `.../{id}/audit_trail/` (existing CRUD untouched).
- **`src/constants/terminology.js`** (UPDATE, supporting) — added shared `SCOPE_LABEL` + `SCOPE_OPTIONS` (deduped from list + detail pages).

## 3. Verification Gate Results

| Check | Result |
|-------|--------|
| `npx eslint` on all 11 changed files | ✅ exit 0, 0 errors |
| `npm run build` | ✅ `✓ built in 12.05s`, exit 0 (chunk-size warnings pre-existing, not errors) |
| Anti-pattern grep — `window.confirm` in changed files | ✅ 0 hits in code (only "no window.confirm" comments); remaining hits are pre-existing untouched files |
| Anti-pattern grep — `margin="normal"` in changed files | ✅ 0 hits (remaining hits are pre-existing untouched files) |
| MUI Grid v6 syntax grep (`\bitem\b.*xs=`, `<Grid item`) in changed files | ✅ 0 hits |
| Hex-color grep in changed files | ✅ 0 hits (all theme tokens) |
| `density="compact"` on both new DataGrids | ✅ (TablesTab:234, AuditTab:89) |
| Backend endpoints (curl with ahmed token) — `core/modules/1/`, `quality_summary/`, `audit_trail/`, `dataschema/tables/`, `catalog/assets/`, `mdm/org-units/` | ✅ all HTTP 200, 0.08–0.47 s |
| **Browser** — detail page renders `BaseDetailPage` shell (breadcrumb "DP1: Medicine Carbon", DetailHeader icon + title + description + close) | ✅ |
| **Browser** — 5 main tabs (Overview / Tables / DQ / Edit / Audit) + Metrics panel tab on right | ✅ (Edit present because ahmed is admin) |
| **Browser** — Overview: Scope 1 chip, Org Unit "كلية الطب — College of Medicine", Status Unlocked chip, Quality "2 passing", Tables 2, Quality Score 100.0%, Created/Updated timestamps | ✅ |
| **Browser** — Tables tab: "Tables (2)" DataGrid with 2 rows (med_electricity 63 rows passing, med_gen_log 62 rows passing), search + "New Table" (admin) | ✅ |
| **Browser** — DQ tab: stat cards Tables Checked 2 / Passing 2 / Warning 0 / Failing 0 / Pass Rate 100% / Avg Score 100.0% + per-table table | ✅ |
| **Browser** — Edit tab: shared ProductForm (Name/Description/Scope/Org Unit/Locked switch) + Save Changes + Delete Data Product | ✅ |
| **Browser** — Audit tab: "Governance Events (0)" + Alert "No governance events recorded for this data product." | ✅ (0 events confirmed via API) |
| **Browser** — Metrics panel: Product Statistics — Tables 2, Total Rows 125, Pass Rate 100%, Avg Score 100.0%, Last Modified + Governance (Org Unit/Scope/Lock Status/Audit Events 0) | ✅ |
| **Browser** — Delete → destructive ConfirmDialog with table-count warning (`"DP1: Medicine Carbon" has 2 tables... cannot be undone`), Cancel closes, **no data deleted** | ✅ |
| **Browser** — Lock toggle works (checkbox unchecked → checked, UI only, not saved) | ✅ |
| **Browser** — Tab persistence: reloaded on Edit tab → Edit restored; reloaded on Audit tab → Audit restored (localStorage `carbonDataProductDetail`) | ✅ |
| **Browser** — No console errors/warnings (React Router future-flag warnings only, project-wide & non-fatal) | ✅ |

## 4. Notes / Observations

- **Stale-session phantom during verification**: after opening the delete ConfirmDialog the first time, the browser session was bounced to `/login` (auth token state), and the Vite dev server threw `ERR_CONNECTION_RESET` + "Maximum update depth exceeded" console errors. Services were confirmed RUNNING (backend PID :8009, frontend :5179) and a clean page reload resolved it — consistent with the known stale-HMR/session quirk (CB-17). No code defect involved; re-login + reload passed all gates.
- **Hooks-before-guard (rules-of-hooks)**: three tab components originally declared `useMemo` after the `if (!entityData)` early return → 5 lint errors (`React Hook useMemo is called conditionally`). Fixed by hoisting all hooks above the guards. Golden pattern confirmed: hooks first, guard second.
- **Edit tab persistence quirk**: BaseDetailPage persists the selected main tab; the Edit tab is only rendered when `isAdmin`. If a non-admin previously selected Edit (as admin) and reloads, the persisted tab index falls back to the first available tab — BaseDetailPage handles this via clamped index. No defect observed in admin flow.
- **Backend Phase 1 confirmed working from the frontend**: Module serializer now returns `table_count/created_at/updated_at`; `quality_summary` returns `{total:2, passing:2, warning:0, failing:0, unknown:0, avg_score:100.0}`; `audit_trail` returns 0 events for module 1 (no governance actions recorded yet — tab shows the empty state correctly).
- No backend edits were made. Services running throughout verification (backend :8009, frontend :5179).
