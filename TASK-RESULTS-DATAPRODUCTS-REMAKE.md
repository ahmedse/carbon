# TASK-RESULT — Data Products Total Remake (AI-Toolkit Compliance)

**Date:** 2026-08-11
**Role:** Frontend Worker
**Scope:** `carbon-frontend/src/pages/catalog/DataProductsPage.jsx` only (no backend edits)
**Task:** "audit and remake according to AI toolkit" (http://localhost:5179/carbon/catalog/products) + "add date column and filter by org unit too"

---

## 1. Audit Findings (OLD page)

| # | Violation | Severity |
|---|-----------|----------|
| 1 | **Admin gate broken**: old gate checked superuser/group membership on the raw user object → Actions column (Edit/Delete/Visibility) never rendered for the real user (CB-13 violation) | CRITICAL |
| 2 | Card-gallery layout — not using `FilteredDataGrid` list shell (CB-15) | High |
| 3 | Drawer-based form — design system mandates SystemDialog modal (CB-14) | High |
| 4 | Raw `Dialog` + `window.confirm` for delete — not `ConfirmDialog` | Medium |
| 5 | Manual Snackbar state — not `useNotification` | Medium |
| 6 | No search / no empty-state in list shell | Medium |
| 7 | **No date column** — module has no created/updated timestamps; nothing displayed | Medium |
| 8 | **No Org Unit filter** — only scope filter; org unit shown only as text | Low |
| 9 | Non-defensive data handling (`context?.modules` without `Array.isArray`) (CB-09) | Medium |

## 2. Remake — What Changed

- **Manage gate**: `const canManage = can(user, 'manage', 'catalog', { perspectives, isGlobalAdminFlag, capabilities, modules: context?.modules || [] })` — same pattern as AdminRoute (CB-13). ✅
- **Shell**: `FilteredDataGrid` (title DATA_PRODUCTS, subtitle `${filtered.length} of ${modules.length} data products`, description, countLabel, actions=New Data Product button when canManage, pageSize 25, rowsPerPageOptions [25,50,100], emptyMessage/emptySubtext with hasFilters awareness, loading, search on name+description). ✅
- **Filters** (`filterDefs`): **Scope** (All Scopes / Scope 1/2/3) + **Org Unit** (NEW — 27 org units from `fetchOrgUnits`, string-compared via `String(m.org_unit)`). `onFilterChange(key, value)` handles both; `handleClearFilters` resets search + scope + org unit. ✅
- **Modified column (NEW)**: derived — Module model has no timestamps, so `statsByModule[row.id].updated` = max `Date.parse(t.updated_at)` across the module's child tables (null → "—"). Rendered via `valueFormatter: (value) => formatModified(value)` → `toLocaleDateString(undefined, { year:'numeric', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })`. ✅
- **Form**: `ProductDialog` on `SystemDialog` (Name*, Description, Scope, Org Unit) — create/update shared (CB-14). ✅
- **Delete**: `ConfirmDialog` destructive — message: `"<name>" has N table(s). Deleting it may remove associated data. This action cannot be undone.` ✅
- **Notifications**: `useNotification` (success on create/update/delete; `notifyFromError` on failures). ✅
- **Data**: `modules = useMemo(() => Array.isArray(context?.modules) ? context?.modules : [], [context?.modules])` (CB-09); `statsByModule` useMemo groups tables + failing/warning quality + max updated_at by module id. ✅
- **8 DataGrid columns**: Name (flex 1, min 180, Button → navigate detail), Org Unit (170, `row.org_unit_name || '—'`), Description (flex 1.4, min 200), Tables (90, right, count chip), Scope (110, SCOPE_LABEL chip), Quality (150, error/warning chips), **Modified (170, valueGetter + valueFormatter)** (NEW), Actions (120, canManage-only: Visibility/Edit/Delete IconButtons with Tooltips; Delete sets deleteConfirm). ✅

## 3. Verification Gate Results

| Check | Result |
|-------|--------|
| `npx eslint src/pages/catalog/DataProductsPage.jsx` | ✅ exit 0, 0 errors |
| `npm run build` | ✅ `✓ built in 14.79s` (chunk-size warnings pre-existing, not errors) |
| Pylance/editor diagnostics on file | ✅ No errors found |
| Anti-pattern grep (window.confirm/CardHeader/DialogTitle/DialogActions/RefreshIcon/CircularProgress/InputAdornment/access_route in actions) | ✅ 0 hits (only a CB-13 comment) |
| MUI Grid v6 syntax grep (`\bitem\b.*xs=`, `<Grid item`) | ✅ 0 hits |
| **Browser** — page loads, 24 of 24 products, search + Scope/Org Unit filter chips render | ✅ |
| **Browser** — 8 column headers render (Name, Org Unit, Description, Tables, Scope, Quality, **Modified**, Actions) | ✅ (previous 6-header view was stale HMR bundle — CB-17 hard reload fixed) |
| **Browser** — Modified column shows dates e.g. "Aug 4, 2026, 05:27 PM", "—" for no tables | ✅ |
| **Browser** — **Org Unit filter**: select "Alamein Campus" → 24 → **9 rows**, all ALM/Alamein Campus | ✅ |
| **Browser** — Scope filter composes with Org Unit (Alamein Campus + Scope 2 → 2 rows: ALM Electricity, ALM Chilled Water) | ✅ |
| **Browser** — Search composes with filters ("DP1" + Alamein Campus → 0, correct) | ✅ |
| **Browser** — "Clear Filters" resets to 24 of 24 | ✅ |
| **Browser** — New Data Product → SystemDialog with 4 fields (Name*, Description, Scope, Org Unit) + Cancel/Save | ✅ |
| **Browser** — Delete → destructive ConfirmDialog ("ALM - Water Consumption" has 1 table... cannot be undone), Cancel closes, **no data deleted** | ✅ |
| **Browser** — Actions column buttons render (Open data product / Edit / Delete) per row | ✅ (was the CRITICAL gate fix) |
| **Browser** — post-test data integrity: footer still "1–24 of 24" | ✅ |

## 4. Notes / Observations

- **Stale-bundle phantom (CB-17)**: on first load the grid showed only 6 headers and no Actions column despite the code having 8. A hard reload after rebuild resolved it — the earlier `npm run build` + running dev server had stale HMR state. Lesson re-confirmed: always hard-reload/restart before concluding a code bug.
- **Modified column is derived, not stored**: Module model has no created_at/updated_at. The column shows the max `updated_at` across the product's child dataschema tables — a reasonable proxy for "last modified". If true product-level timestamps are needed, that's a backend model change (out of frontend scope).
- **Org Unit filter values are strings**: `onFilterChange` passes string values; comparison uses `String(m.org_unit ?? '') === filterOrgUnit`. Verified working.
- No backend edits were made. Both services running (backend PID :8009, frontend :5179) throughout verification.
