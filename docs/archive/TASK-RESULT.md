# TASK RESULT — RUN CATALOG-DP-1 (Catalog Studio → Data Products)

> The previous worker run did NOT implement CATALOG-DP-1 (it re-reported the earlier Schema Manager Unification run). Master implemented it directly. Verified against a clean production build.

## Summary
Reframed Catalog Studio from the misleading "Schema Catalog" (flat table list) to the correct **Data Products (Modules) → Tables → Table workbench** model. `Module` code/API untouched — only the UI label ("Data Product") and navigation changed. Data Hub studio left unchanged.

## Files created
- `carbon-frontend/src/constants/terminology.js` — `DATA_PRODUCT` / `DATA_PRODUCTS` label constants (one-line switch to "Dataset").
- `carbon-frontend/src/pages/catalog/DataProductsPage.jsx` — grid of Data Products (modules) with table counts + quality rollup.
- `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` — a product's tables + New Table / Edit / Delete (admin-gated).

## Files modified
- `carbon-frontend/src/App.jsx` — routes `/catalog/products`, `/catalog/products/:moduleId`, `/catalog/tables/:tableId`; redirects `/catalog/schemas` → `/catalog/products`, `/catalog/schemas/:tableId` → `/catalog/tables/:tableId`, `/catalog/schema-manager` → `/catalog/products`.
- `carbon-frontend/src/shell/ShellSidebar.jsx` — group `Schema & Tables` → `Data Products`; `Browse Schemas`/`Manage Tables` → single `Data Products` (`/catalog/products`).
- `carbon-frontend/src/shell/Breadcrumbs.jsx` — added Data Products / Data Product / Table crumbs; retired "Schema Catalog"/"Schema Detail"/"Schema Manager".
- `carbon-frontend/src/pages/catalog/CatalogHome.jsx` — quick-access cards → Data Products + Governance Audit; subtitle → "data-product catalog".
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` — breadcrumb parent → Data Products (→ product when module known); title fallback `Schema` → `Table`.
- `carbon-frontend/src/pages/catalog/tabs/SchemaStructureTab.jsx` — post-delete nav → `/catalog/products`.
- `carbon-frontend/src/pages/TableManagerPage.jsx` + `carbon-frontend/src/pages/Help.jsx` — link/copy → Data Products.

## Build verification
- `cd /home/ahmed/aast/carbon/carbon-frontend && npm run build` → ✓ built in 12.77s, no errors.

## Manual checklist
| Step | Status | Notes |
|---|---|---|
| Sidebar shows "Data Products" (no Browse Schemas/Manage Tables) | ✅ | ShellSidebar catalog group updated |
| `/catalog/products` lists modules w/ table counts | ✅ | uses context.modules + grouped tables |
| `/catalog/products/:moduleId` lists product tables | ✅ | fetch by module_id + quality chips |
| New Table / Edit / Delete inside product (admin) | ✅ | reuses schema table CRUD; module fixed |
| `/catalog/tables/:tableId` opens workbench (Structure/DQ/Gov/Audit) | ✅ | existing SchemaDetailPage |
| Legacy redirects (`/catalog/schemas*`, `/catalog/schema-manager`) | ✅ | Navigate + param-preserving wrapper |
| Top breadcrumb no longer says "Schema Catalog" | ✅ | Breadcrumbs.jsx updated |
| Data Hub studio unchanged | ✅ | not touched |
| Build passes | ✅ | 12.77s |

## Not done / notes
- `SchemaCatalogPage.jsx` and `SchemaManagerPage.jsx` remain as unused files (routes redirect away). Safe to delete in a later cleanup.
- Live browser verification pending (master to confirm after HMR reload).
