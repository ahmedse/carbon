# SEED_SPEC_METADATA — Carbon DQ Rules + Catalog (CSV-driven)

Complements `SEED_SPEC.md` (raw activity data). While `seed_carbon_raw.py` seeds
only the *rows* present in the source CSVs, this spec defines the *metadata*
layer: **Data Quality rules** and **Catalog** entries for those same tables.

## Principle

No fabrication: DQ rules are authored metadata grounded in the seeded tables'
field types (`number`, `date`, `string`, `select`) and observed values — not
numbers invented from thin air. Catalog entries describe the seeded assets.
Everything is data-driven (CSV) and idempotent.

## Files

| CSV | Ingested by | Produces |
|-----|-------------|----------|
| `carbon_dq_rules.csv` | `seed_carbon_metadata.py` | `dq.DQRule` + `dq.RuleFieldAssignment` |
| `carbon_catalog_domains.csv` | `seed_carbon_metadata.py` | `catalog.DataDomain` |
| `carbon_catalog_tags.csv` | `seed_carbon_metadata.py` | `catalog.Tag` |
| `carbon_catalog_glossary.csv` | `seed_carbon_metadata.py` | `catalog.GlossaryTerm` |
| `carbon_catalog_asset_profiles.csv` | `seed_carbon_metadata.py` | `catalog.AssetProfile` |
| `carbon_catalog_policies.csv` | `seed_carbon_metadata.py` | `catalog.GovernancePolicy` |

## CSV schemas

### carbon_dq_rules.csv
`module,table,field,rule_type,level,dimension,severity,rule_name,description,min,max,values,reference_set,operator,value,active`

- `module` — campus token matched via `Module.name icontains` (`Smart Village` |
  `Abu Qir` | `South Valley`) — avoids em-dash ambiguity.
- `table` — `DataTable.name` (e.g. `monthly_electricity`).
- `field` — `DataField.name`; blank = table-level (unused here).
- `rule_type` — one of `not_null|unique|allowed_values|range|regex|reference_integrity|threshold|nl_check|anomaly_detect`.
- `level` — `field` | `business` (maps to `field_validation` / `business_rule`).
- `dimension` — DAMA code (`completeness|validity|accuracy|consistency|timeliness|uniqueness|integrity|reasonability`).
- `severity` — `info|warn|error`.
- `rule_name` — the **shared** natural key (idempotency). Rows that share a
  `rule_name` are collapsed by the command into ONE reusable `DQRule` bound to
  many fields via `RuleFieldAssignment` — never one rule per field.
- `min`/`max` — for `range`.
- `values` — pipe-delimited list, for `allowed_values`.
- `reference_set` — `ReferenceSet.name`, for `allowed_values` or `reference_integrity`.
- `operator`/`value` — for `threshold`.

### carbon_catalog_*.csv
See the CSVs themselves; column names are the field names of the target models.
`tags` (asset profiles) is pipe-delimited. `config` (policies) is `k=v|k2=v2`.

## Run

```bash
cd /home/ahmed/aast/carbon && source .venv/bin/activate
python backend/manage.py seed_carbon_metadata
```

## Contents (this run)

- **DQ rules (7 reusable, 36 field bindings)**: one `range >= 0` rule bound to all
  17 numeric fields (validity/error); one `not_null` rule bound to 14 required/key
  fields (completeness/error); three `allowed_values` rules (`existence`,
  `scope` long form `Scope 1|Scope 2|Scope 3`, `scope` short form `1|2`); two
  `reference_integrity` rules (`refrigerant` → `refrigerants`, `campus` →
  `campuses`).
- **Catalog**: 1 domain, 9 tags, 10 glossary terms, 9 table asset profiles,
  4 governance policies.
