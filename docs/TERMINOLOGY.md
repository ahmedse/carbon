# Carbon — Canonical Terminology & Information Model

**Status:** AUTHORITATIVE. When any other doc, label, or code comment conflicts with this file, **this file wins**. Last updated 2026-07-20.

Carbon is a **Data Trust Platform** (Ataccama-inspired) that hosts domain apps on top of trusted, governed data. "Carbon"/emissions is the first hosted app.

---

## 1. The core hierarchy

```
OrgUnit ── owns ──▶ Module ──▶ DataTable ──▶ DataField ──▶ DataRow
```

| Concept | Code entity | UI label | Meaning |
|---|---|---|---|
| Org tree / access anchor | `OrgUnit` (mdm) | "Org Unit" | Who owns data; the axis access control is scoped to (ScopedRole subtree). |
| Governed grouping of tables | `Module` (core) | **"Data Product"** | An org-owned, access-scoped bundle of tables that can host an app. **This is what a database calls a "schema/namespace" — but we call it a Data Product.** |
| A table | `DataTable` (dataschema) | **"Table"** | A single dataset/table inside a Data Product. |
| A field / column | `DataField` (dataschema) | **"Field"** (collectively a table's **"Structure"**) | A column. The set of fields IS "the table's schema". |
| A record | `DataRow` (dataschema) | "Row" / "Record" | Actual data. |

### The word "schema" — banned as a table label
- ❌ Do NOT call an individual table "a schema".
- ✅ "A table's schema" (correct DB sense) = its **fields** → surface as the **Structure** tab.
- ✅ The grouping that DBs call a "schema" = our **Module = Data Product**.

---

## 2. Cross-cutting layers (attached to tables/fields, NOT to Module)

| Layer | Code | Purpose |
|---|---|---|
| Business classification | `DataDomain` | Business domains (org-agnostic grouping for governance). |
| Vocabulary | `GlossaryTerm`, `Tag` | Shared definitions & labels. |
| Governance metadata | `AssetProfile` (per table/field) | owner, steward, classification (`public/internal/confidential/pii/sensitive`), quality_status (`unknown/passing/warning/failing`), quality_score. Auto-provisioned; PATCH-only. |
| Audit | `GovernanceEvent` (asset changes) + `SchemaChangeLog` (table/field structural changes) | Who changed what, before/after. |
| Lineage | `TableRelation` | table→table relationships. |
| Quality | `dq.DQRule` / `DQResult` / `TableProfile` / `FieldProfile` | Rules + runs; rolls up into `AssetProfile.quality_status/score`. |
| Reference/master data | `mdm.ReferenceSet` / `ReferenceValue` | Controlled vocabularies. |

**Access control** is a separate axis: `OrgUnit` + `ScopedRole`. Governance/lineage/quality do **not** live on `Module`.

---

## 3. Three different meanings of "scope" (never conflate)
1. **GHG Scope 1/2/3** — emissions taxonomy; a property of an emission factor / calculation. `Module.scope` is **advisory/default only**; authoritative scope comes from the emission factor at calc time.
2. **Access scope** — which `OrgUnit` subtree a user may see (`get_allowed_org_unit_ids`).
3. **Rule scope** — DQ rule `scope` = `table` | `field`.

---

## 4. UI surfaces (perspectives)
- **Catalog Studio** = the **governance/trust workbench**. Browse **Data Products → Tables → Table workbench** (Structure · Relations · DQ · Governance · Audit). Routes: `/catalog/products`, `/catalog/products/:moduleId`, `/catalog/tables/:tableId`.
- **Data Hub** = the **operator data-entry** perspective. Modules grouped by GHG scope → tables → rows. Routes: `/dataschema`, `/modules/:id`, `/dataschema/entry/...`. (Uses "Module" wording; keep as-is for now.)
- **Admin** = Org Units, Users, Access Control.

---

## 5. Naming rules for contributors
- Container grouping tables → **"Data Product"** in UI; `Module` in code. Never rename the `Module` model/API.
- Never label a table "schema". Table's columns → **Structure / Fields**.
- The UI label lives in `carbon-frontend/src/constants/terminology.js` (`DATA_PRODUCT`, `DATA_PRODUCTS`) — change there if the term ever moves to "Dataset".
- Access = OrgUnit/ScopedRole. Governance = AssetProfile/Domain. Lineage = TableRelation. Quality = dq app.

---

## 6. Known legacy terms to migrate (historical docs may still use these)
| Legacy term | Correct term |
|---|---|
| "Schema Catalog" / "Browse Schemas" | **Data Products** |
| "Schema Manager" / "Manage Tables" | (retired) create tables inside a Data Product |
| calling a table "a schema" | **Table** |
| "schema detail" | **Table workbench** |
| `DataModule` (old, removed) | `core.Module` |
| `Tenant` / multi-tenancy (removed) | — (org model is `OrgUnit`) |

Older `TASK-A*`, `MASTER_PROMPT_*`, and some `plans/*` files predate this decision and may use legacy terms; treat this file as the override rather than rewriting all history.
