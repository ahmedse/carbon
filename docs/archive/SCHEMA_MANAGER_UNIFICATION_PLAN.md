# Schema Manager Unification — Short Plan

> ⚠️ **SUPERSEDED (2026-07-20) by RUN CATALOG-DP-1.** Terminology corrected: "Schema Catalog" → **Data Products (= `Module`)**, table detail = **table workbench**, fields tab = **Structure**. Authoritative model: [`docs/TERMINOLOGY.md`](../docs/TERMINOLOGY.md). The table/field CRUD described here was implemented and still applies; only the naming/navigation moved to Data Products.

**Companion to:** [`TASK.md`](../TASK.md) · **Worker:** Raptor · **Backend changes:** none

## Why
Three overlapping pages confuse users: Catalog (browse), Manager (hidden CRUD), Detail (read-only fields). Users can't find where to create schemas, can't CRUD fields inside the detail, and the right panel differs from Row Detail.

## Goal
Collapse **3 pages → 2**: one **Catalog** (browse + create) and the **Detail page as the full table workbench**.

## The 3 fixes
1. **Detail = manager** — Structure tab does full field CRUD (add/edit/delete) + delete table. Admin-gated.
2. **Catalog creates** — "+ New Table" (module dropdown) + card Edit/Delete; retire `/catalog/schema-manager` via redirect.
3. **Panel parity** — right metrics panel gets **Summary + Quality** tabs (matches RowDetailPage's multi-tab pattern).

## Phases
| Phase | Deliverable | Files |
|---|---|---|
| 1 | Field CRUD + delete table in detail | `SchemaStructureTab.jsx`, `FieldEditorDialog.jsx`, edit `SchemaDetailPage.jsx` |
| 2 | New Table + card CRUD; retire manager | edit `SchemaCatalogPage.jsx`, `App.jsx` |
| 3 | Quality metrics tab + fixes | `SchemaQualityMetrics.jsx`, edit `SchemaDetailPage.jsx` |

## Key contracts (already verified live)
- `DataField.type`: `string|text|number|date|boolean|select|multiselect|file|reference`. Fix `field.field_type` → `field.type`.
- `select`/`multiselect` need `options: [{value,label}]` (non-empty). Field `name` unique per table.
- Table create needs `module` (required FK). Schema writes = **global-admin only** → gate all write UI on `isAdmin`.
- Reuse existing field-CRUD logic in `TableManagerPage.jsx`. All calls via `apiFetch` wrappers.
- Schema changes now auto-log → visible in Audit History tab.

## Guard rails
No backend edits · no new deps · don't touch AuthContext/Sidebar/api.js/DQ+Gov+Audit tabs · don't delete `SchemaManagerPage.jsx` (only stop routing).

## Done when
`npm run build` clean + TASK.md §11 checklist passes. Report to `TASK-RESULT.md`; no commit/push (master reviews live).
