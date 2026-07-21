# TASK.md — RUN: Catalog Studio → Data Products (terminology + navigation)

## MASTER CONTEXT
**RUN ID:** CATALOG-DP-1
**Type:** Frontend IA / terminology refactor (no backend changes)
**Worker:** Raptor (Code Mode) — works ALONGSIDE master. **Master owns docs/terminology; worker owns the frontend UI below.**
**Frontend:** `carbon-frontend/` (React + Vite + MUI), dev `:5179`, base `/carbon/`.
**Backend:** Django/DRF `:8009`, prefix `/carbon-api/`. Admin `ahmed` / `AdminPa_132`. **DO NOT touch backend.**
**Canonical terminology:** see [`docs/TERMINOLOGY.md`](docs/TERMINOLOGY.md) (master is writing it). If any doubt on a word, that file wins.

---

## 1. THE DECISION (why this run exists)
"Schema" was wrongly used as the label for an individual **table**. That is wrong by every catalog convention. Correct model:

```
OrgUnit ─ owns ─▶ Module  ─▶ DataTable ─▶ DataField ─▶ DataRow
                  =“Data Product”  =Table    =Field/     =record
                  (grouping,                  “Structure”
                   org-scoped, hosts app)
```
- **Module is surfaced in the UI as a "Data Product"** (a governed, org-owned grouping of tables). Code/model name stays `Module` — DO NOT rename any model, API, or `Module` identifier.
- A **table's "schema" = its fields** → call that the **Structure** tab. Do not use the word "schema" for a table anywhere in the UI.
- **Label is a single constant** (see §3) so it can be switched to "Dataset" later in one line.

**Target navigation (Catalog Studio only):**
```
Catalog Home
 └─ Data Products (list of Modules)         /catalog/products
      └─ Data Product detail (its Tables)   /catalog/products/:moduleId
           └─ Table workbench                /catalog/tables/:tableId
                (Structure · Relations · DQ Rules · Governance · Audit History)
```
Leave the **Data Hub** studio (data-entry: `/dataschema`, `/modules/:id`, `/dataschema/entry/...`) **UNCHANGED** — that is the operator perspective and is out of scope.

---

## 2. SCOPE

### IN — files to CREATE
1. `carbon-frontend/src/pages/catalog/DataProductsPage.jsx` — grid of Data Products (Modules). Card: name, description, org unit, table count, (optional) quality rollup. Click → `/catalog/products/:moduleId`. Admin gets **"+ New Data Product"** is OUT (modules are created by admins in Admin studio) — instead show **"+ New Table"** only inside a product (see #2). No module CRUD here.
2. `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` — header (product/module name, description, org unit, scope chip) + grid/list of that module's **Tables** with per-table quality chip + eye→ `/catalog/tables/:tableId`. Admin: **"+ New Table"** (dialog with title/description; module is fixed = this product) + per-card Edit/Delete. Reuse the create/edit/delete logic already in `SchemaCatalogPage.jsx`.

### IN — files to MODIFY
3. `carbon-frontend/src/App.jsx`
   - Add routes: `/catalog/products` → `DataProductsPage`; `/catalog/products/:moduleId` → `DataProductDetailPage`; `/catalog/tables/:tableId` → `SchemaDetailPage` (the existing workbench component; do not rename the file this run).
   - Redirects (keep old links alive): `/catalog/schemas` → `/catalog/products`; `/catalog/schemas/:tableId` → `/catalog/tables/:tableId` (use a small wrapper that reads `:tableId` param and `<Navigate>` to the new path); keep existing `/catalog/schema-manager` → `/catalog/products`.
4. `carbon-frontend/src/shell/ShellSidebar.jsx` — in the `catalog` case of `getSidebarItems`:
   - Replace group `'Schema & Tables'` → `'Data Products'`.
   - Replace item `Browse Schemas` (`/catalog/schemas`) → **`Data Products`** (`/catalog/products`, keep `TableChartIcon`).
   - Remove the `Manage Tables` (`/catalog/schema-manager`) item.
   - Leave Governance / Master Data / Data Integration groups unchanged.
5. `carbon-frontend/src/pages/catalog/CatalogHome.jsx`
   - "Schema Browser" quick-access card → **"Data Products"** (nav `/catalog/products`, copy: "Browse data products and their tables"). Remove/replace the "Schema Manager" card (route retired) with a **"Data Products"**-oriented card or drop it. Change subtitle "Centralized schema catalog…" → "Centralized data-product catalog with governance and lineage". Card titled "Tables" may stay (it counts tables).
6. `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` (the table workbench — keep filename)
   - Breadcrumbs: `Home / Catalog / Data Products / <table title>` where "Data Products" links `/catalog/products` (replace the old `Schemas → /catalog/schemas`). If the table's `module` id is available, make the parent crumb link `/catalog/products/:moduleId`.
   - Header title fallback `'Schema'` → `'Table'`. Description fallback stays.
   - No other behavior change (Structure/DQ/Governance/Audit tabs already correct).

### OUT — do NOT touch
- Backend, any `Module` model/API identifiers, the Data Hub studio (`/dataschema*`, `/modules/:id`, `ModuleLandingPage`, `SidebarMenu.jsx` DataEntry view), `AuthContext.jsx`, `api/api.js`, DQ/Governance/Audit/Structure tab components, `docs/**` (master owns docs).
- Do NOT delete `SchemaCatalogPage.jsx` / `SchemaManagerPage.jsx` files (they become unused/redirected — leave them; remove only their sidebar/route references as specified). If an unused import breaks lint/build, remove just that import line.
- No new npm packages.

---

## 3. IMPLEMENTATION NOTES (exact)
- **Label constant:** create `carbon-frontend/src/constants/terminology.js` exporting:
  ```js
  export const DATA_PRODUCT = 'Data Product';
  export const DATA_PRODUCTS = 'Data Products';
  ```
  Use these constants for all new user-facing labels so the term can change in one place.
- **Modules source:** use `const { context } = useAuth(); const modules = context?.modules || [];` (already loaded; each has `id, name, description, scope, org_unit_name`). No new fetch needed for the product list. If you prefer fresh data, `fetchModules(token)` from `src/api/modules.js`.
- **Tables for a product:** `fetchDataSchemaTables(token, null, moduleId)` returns that module's tables (backend filters by `module_id`). Or filter the full list by `t.module === Number(moduleId)`.
- **Table count per product card:** either `fetchDataSchemaTables(token, null, module.id)` per card (fine for small N) OR one full `fetchDataSchemaTables` then group by `t.module`. Prefer the single-fetch-and-group approach to avoid N calls.
- **Quality rollup (optional, nice-to-have):** `fetchAssetProfiles(token)` → map by `data_table`; per product show count of tables with `quality_status==='failing'/'warning'`. Skip if time-boxed.
- **New Table dialog inside product:** reuse `SchemaCatalogPage.jsx`'s create dialog logic verbatim, but the module is fixed to the current product (`module = moduleId`), so hide the module dropdown.
- **Admin gate (same as existing pages):**
  ```js
  const isAdmin = Boolean(user?.is_superuser ||
    (user?.roles||[]).some(r => r?.active !== false && (r.role==='admins_group' || r.role==='admin')));
  ```
- **All API calls via existing `apiFetch` wrappers** — never raw `fetch`, never prepend `API_BASE_URL`.
- **Layout consistency:** product/table lists use the same MUI Card grid style already in `SchemaCatalogPage.jsx` (border `1px solid divider`, no hover transforms).

---

## 4. ACCEPTANCE CRITERIA
- [ ] `npm run build` passes clean.
- [ ] Catalog sidebar shows **"Data Products"** (no "Browse Schemas"/"Manage Tables").
- [ ] `/catalog/products` lists Data Products (modules) with table counts; card click → product detail.
- [ ] `/catalog/products/:moduleId` lists that product's tables; eye → `/catalog/tables/:tableId` opens the workbench.
- [ ] Admin sees **+ New Table** inside a product; create/edit/delete work; non-admin sees read-only.
- [ ] `/catalog/tables/:tableId` shows the existing Structure/DQ/Governance/Audit workbench; breadcrumb parent is **Data Products** (→ product if module known).
- [ ] Old links redirect: `/catalog/schemas` → `/catalog/products`; `/catalog/schemas/:tableId` → `/catalog/tables/:tableId`; `/catalog/schema-manager` → `/catalog/products`.
- [ ] The word "schema" no longer appears as a label for a table in Catalog Studio UI (Structure tab keeps the field list).
- [ ] Data Hub studio (`/dataschema`, `/modules/:id`) is visually unchanged.

---

## 5. MANUAL TEST (login ahmed / AdminPa_132)
1. Catalog Studio → sidebar shows **Data Products**. Click it → list of modules (e.g. Facilities modules) with table counts.
2. Open a product → see its tables (Monthly Electricity/Water/etc.) with quality chips.
3. **+ New Table** in the product → create "QA Temp" → appears; open it → **Structure** tab; add a field; delete the table.
4. Visit `/carbon/catalog/schemas` → redirects to `/carbon/catalog/products`. Visit an old `/carbon/catalog/schemas/7` → redirects to `/carbon/catalog/tables/7`.
5. Confirm Data Hub (`Data Entry` studio) still works (modules by scope → tables → rows).

---

## 6. GUARD RAILS
- ❌ No backend edits, no model/API renames, no new deps.
- ❌ Do not touch Data Hub studio, AuthContext, api.js, or docs.
- ❌ Do not rename the `Module` code identifier — only the **UI label** becomes "Data Product".
- ❌ Do not use raw `fetch()`.
- ✅ Keep old routes working via redirects.

---

## 7. REPORT
Write results to `TASK-RESULT.md`: files changed, build output line, §4 checklist pass/fail. Do NOT commit/push — master reviews live.

---
### Coordination (who does what)
- **Worker (Raptor):** everything in §2–§3 (frontend).
- **Master (in parallel):** `docs/TERMINOLOGY.md`, doc cleanup, repo memory. No frontend edits from master during this run to avoid conflicts.
