Data Trust Core — Catalog & Governance. Domain-agnostic: MUST NOT import from `emissions` or any hosted app.

## Identity map (ADR-0040)
| UI term | Code | Role |
|---------|------|------|
| **Data Product** | `core.Module` | Studio browse/authoring (`/catalog/products`) |
| **Table** | `dataschema.DataTable` | Rows under a Module |
| **Asset Profile** | `catalog.AssetProfile` | Catalog card + Data Trust Index |
| **Dataset** | `catalog.Dataset` | Dataset Hub (versions/contracts/health) — not a Data Product |

## Data Trust Index (ADR-0039 + DTR-5)
Read-time score on every `AssetProfile`: Quality ≤35 + Ownership ≤20 + Context ≤35 + Freshness ≤10.
Freshness uses enabled `FreshnessPolicy` (fresh=10 / unknown=5 / stale=0); field assets inherit the table.
Exposed as `trust_index` / `trust_tier` / `trust_breakdown` on AssetProfile APIs and catalog search hits.
UI: `TrustChip` on assets, search, schema header, governance panel.

## Pickers
Catalog Studio entity/enum pickers use platform `SearchSelect` (design-system RULE 13) — same standard as `FilteredDataGrid`.
