# ADR 0040 — Product identity: Module (Data Product) vs Dataset Hub

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** Master Architect (Catalog); DTR-4 follow-on after Trust Index
- **Area:** frontend | backend | cross-cutting

## Context
Catalog Studio labels **“Data Product”** for `core.Module` (RULE_7 / ADR-0010), while
Dataset Hub (`catalog.Dataset`) is a parallel versioned/contracted path whose
docstrings historically called Datasets “semantic data products.” Users and AI
agents conflated the two. ADR-0039 already kept DTI on `AssetProfile`, not Dataset
health — identity clarity was still missing in copy and soft links.

## Decision
1. **Glossary (binding):**
   - **Data Product** = `Module` + its `DataTable`s — Catalog Studio browse/authoring
     (`/catalog/products`).
   - **Asset / Asset Profile** = consumable catalog card + Data Trust Index (ADR-0039).
   - **Dataset** = Dataset Hub artifact (versions, contracts, health) scoped to a
     Module for CBAC — **never** labeled “Data Product” in UI or help.
2. **No schema merge.** Do not rename models, collapse FKs, or move DTI onto Dataset
   health. Soft-link only: Data Product detail may list related Datasets via
   `GET /catalog/datasets/?module=<id>` (name/status, degrade on error).
3. **Copy:** Module descriptions must not claim Dataset Hub features (“version
   tracking”) unless referring to Datasets explicitly.
4. **Pulse / AI:** remain free to ground on AssetProfile trust; Dataset Hub stays a
   separate contract path (DTR-3 COMMS for trust ranking).

## Alternatives Considered
- **Merge Module and Dataset into one entity** — rejected; breaks CBAC, Hub APIs,
  and Studio flows.
- **Rename UI “Data Product” → “Module”** — rejected; contradicts RULE_7 / ADR-0010
  and user vocabulary already shipped.
- **Full Dataset Hub Studio UI in this slice** — deferred; soft-link is enough for
  identity without a new product surface.

## Consequences
- **Positive:** one glossary; Studio vs Hub distinguishable; Trust Index stays on
  AssetProfile.
- **Negative / trade-off:** Dataset Hub remains API-first until a dedicated FE track.
- **Do NOT re-try:** calling Dataset a “Data Product” in docs/UI; inventing a second
  trust score from Dataset health.

## References
- ADR-0010 / RULE_7 (`Data Product` = Module)
- ADR-0039 (DTI on AssetProfile)
- `backend/catalog/models.py::Dataset`
- Track **DTR-4** in `TASKS.md`
