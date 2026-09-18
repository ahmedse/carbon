# ADR 0039 — Data Trust Index (catalog consumer score)

- **Status:** Accepted (amended DTR-5 2026-09-18)
- **Date:** 2026-09-18
- **Deciders:** Master Architect (Catalog); human go on DTR-1/2; DTR-5 freshness follow-on
- **Area:** backend | frontend | cross-cutting

## Context
Enterprise platforms (Ataccama ONE DTI, Collibra quality tab, Purview Unified Catalog)
expose a single 0–100 trust score so consumers and AI agents can answer “can I use
this?” without opening every tab. Carbon already stores quality, ownership, and
context fields on `AssetProfile` but exposes them as fragmented chips.

## Decision
1. **Compute a Data Trust Index (DTI)** on every `AssetProfile` (table or field) as a
   read-time aggregate — no new persisted score column required for v1.
2. **Weights (max 100) — DTR-5:**
   - **Quality ≤35:** `quality_score` (0–100) → `score/100 * 35`. Missing/unknown → 0.
     Canonical quality for DTI is **`AssetProfile.quality_score`** (DQ rule pass-rate
     write-back). Scorecard dimensions remain diagnostic only.
   - **Ownership ≤20:** owner assigned → 20; else steward only → 10; else 0.
   - **Context ≤35:** description non-empty → 8; glossary_term → 12; domain → 10;
     ≥1 tag → 5.
   - **Freshness ≤10 (DTR-5):** enabled `FreshnessPolicy` + within SLA → 10; no policy /
     unknown → 5; stale → 0. Field assets inherit the parent table’s policy/age.
3. **Tiers:** `trusted` (70–100), `limited` (20–69), `untrustworthy` (0–19).
4. **API:** expose `trust_index`, `trust_tier`, `trust_breakdown` on AssetProfile
   serializers and catalog search hits for tables/fields. Breakdown includes
   `freshness.status` / `age_hours` / `max_age_hours`.
5. **UI:** one Trust badge (score + tier label) on asset surfaces; do not invent a
   second quality ring for DTI. Freshness remains a separate chip on schema headers;
   trust tooltip explains the freshness slice.
6. **Pickers:** Catalog Studio entity/enum pickers use platform `SearchSelect`
   (design-system RULE 13) — no raw `<Select>` walls for data-driven lists.
7. **Product identity:** Data Product = Module; Dataset Hub = parallel path — see
   ADR-0040. DTI stays on AssetProfile (not Dataset health).

## Alternatives Considered
- **Persist DTI column + Celery recompute** — rejected for v1; read-time is enough
  and stays consistent with latest metadata/DQ write-back.
- **Use Dataset health as DTI** — rejected; Dataset Hub is a parallel product path;
  AssetProfile is the catalog card consumers browse.
- **Freshness as subtractive penalty only** — rejected; positive “fresh” credit makes
  the SLA visible and keeps max 100 additive/explainable.
- **v1 without freshness (40Q+20O+40C)** — shipped first; superseded by DTR-5 weights above.

## Consequences
- **Positive:** one consumer-facing score; AI/search can filter by trust; aligns with
  Ataccama DTI mental model without cloning their product; stale monitored tables
  lose the freshness slice without collapsing quality.
- **Negative / trade-off:** read-time compute on list endpoints; mitigated with
  `batch_freshness_for_table_ids` + serializer context seeding.
- **Do NOT re-try:** inventing a fourth quality formula; scoring ownership via
  Collibra-style workflows before a Trust Index exists.

## References
- Audit canvas `data-trust-catalog-audit`
- `backend/catalog/models.py::AssetProfile`, `FreshnessPolicy`
- `backend/catalog/trust_index.py`
- `backend/dq/services.py::_rollup_to_catalog`
- `.ai-toolkit/shared/design-system.md` RULE 13 (`SearchSelect`)
- Track **DTR** in `TASKS.md`
