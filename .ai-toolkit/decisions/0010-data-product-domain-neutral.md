# ADR 0010 — Data Product must not carry GHG `scope` (domain vocabulary stays out of the generic core)

- **Status:** Proposed
- **Date:** 2026-08-16
- **Deciders:** Master Architect + QA validator
- **Area:** data | frontend | cross-cutting

## Context
The platform is a generic Data Trust core (Catalog, MDM, DQ, metadata-driven
schema) that *hosts* domain apps; Carbon emissions accounting (GHG Protocol) is
only the **first hosted app** (`project.config.md`). The catalog's "Data Product"
is currently bound 1:1 to `backend/core/models.py::Module`, whose `scope` field is
GHG **emission scope 1/2/3** — carbon-domain vocabulary. That leaked into the
generic UI: `DataProductsPage.jsx` exposes `scope` as a filter, a column, and a
form field, and `terminology.js` ships `SCOPE_LABEL`/`SCOPE_OPTIONS` alongside the
generic `DATA_PRODUCT` label.

Result: a hypothetical second hosted app (e.g. a finance domain) would inherit a
meaningless "Scope 1/2/3" filter on its own data products.

## Decision
1. Treat `Module.scope` (emission scope) as **carbon-domain metadata** that does
   not belong in the domain-agnostic catalog model/UI.
2. Keep "Data Product" (= `Module`) as the generic grouping container. Its generic
   filterable dimensions are: `org_unit` (ownership), name/description (search),
   and — to be added — `domain` (`DataDomain`), `classification`, `tags`,
   owner/steward, and quality status (the last four already exist on
   `AssetProfile`, one level below the Data Product).
3. Move emission-scope off the generic Data Product surface. Options (see
   Alternatives): (a) a per-domain extension/`Module` subclass, (b) a JSON
   `domain_attributes` blob on `Module` keyed by `app_id`, or (c) leave `scope`
   in place but render it only for the carbon domain app.

## Alternatives Considered
- **A — Domain-extension model (preferred):** a `DomainModuleProfile` (app_id →
  extra fields) so carbon keeps `scope` there. Rejected only for effort; it is the
  clean long-term shape.
- **B — `Module.domain_attributes` JSON keyed by `app_id`:** quick, keeps schema
  flat, no migration churn beyond one column. Accepted as the pragmatic near-term
  step; re-litigate when a second domain app actually lands.
- **C — Keep `scope`, conditionally render:** zero migration, but leaves the leak
  in the model and only hides it in the UI. Not enough — the model stays wrong.

## Consequences
- **Positive:** catalog UI stays truthful for any future domain app; the generic
  filter surface becomes domain/classification/tags/owner/quality.
- **Negative / trade-off:** a one-time refactor of `DataProductsPage.jsx`
  (filters/columns/form) and `Module`/`ModuleSerializer`; carbon's scope picker
  must move to a carbon-specific surface.
- **Do NOT re-try:** hard-coding a domain app's enum into a shared catalog
  model/UI and expecting the second domain app to ignore it.

## References
- `backend/core/models.py` (`Module.scope`, GHG `SCOPE_CHOICES`)
- `backend/core/serializers.py` (`ModuleSerializer` — `scope` in fields)
- `carbon-frontend/src/pages/catalog/DataProductsPage.jsx` (scope filter/column/form)
- `carbon-frontend/src/constants/terminology.js` (`SCOPE_LABEL`/`SCOPE_OPTIONS`)
- `catalog/models.py::AssetProfile` (domain/classification/tags/quality — the
  generic metadata that SHOULD be filterable at the product level)
- playbook PB-38 (same leak class as PB-29)
