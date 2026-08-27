# ADR-0020 — Inventory Coverage: declared-universe completeness for GHG accounting

- **Status:** Accepted
- **Date:** 2026-08-27
- **Deciders:** Master Architect
- **Area:** backend + frontend (cross-cutting, split into 2 phases)
- **Extends:** ADR-0006 (DQ rule standalone), ADR-0010 (domain-neutral core)

## Context

Carbon tracks emissions via `Calculation` rows against `ReportingPeriod`, `SBTiTarget`,
and `OrganizationalBoundary` — but nothing records **what you are accountable for
measuring** versus **what you have actually measured**. The denominator problem:

- "0% coverage" (measured nothing) is indistinguishable from "0 sources exist".
- Scope 3 has 15 categories, many unbounded upstream — a naive absolute denominator
  is always "failing".
- PCAF assigns a Data Quality Score (1–5 per asset class) *separately* from completeness;
  conflating them yields a "95% complete" figure that is secretly all tier-5 proxy.

GHG Protocol Corporate Standard Ch. 7 ("Managing Inventory Quality") resolves this via
an **Inventory Management Plan (IMP)** with an **exclusions register**, and the
Completeness accounting principle. CDP requires a per-scope coverage % + exclusions
register + verification coverage %. The existing models (SBTiTarget, boundary, period,
verification) cover the *targets* and *audit* layers — the **declared-universe**
layer is missing.

## Decision

Add an **Inventory Coverage** capability to the Carbon domain app (`backend/emissions/`),
**not** a new core app. The generic "declare → measure → gap → act" pattern already
exists in core (catalog + dq + mdm); the load-bearing fields (scope, scope-3 category,
PCAF tier, SBTi link) are emissions-specific and therefore live here (RULE_3). Extract
to core only under the Rule of Three — not now.

### Entities (all in `backend/emissions/models.py`)

1. **`InventorySource`** — the declared-universe *binding* (period-invariant fact).
   Keyed by `(org_unit, scope, scope3_category, source_name)`. It is NOT a new domain
   object and NOT extension fields on `DataTable`: one physical table can be both scope 1
   and scope 3 cat 3, so scope semantics must not live on the table.

2. **`InventorySourceStatus`** — through-model (slowly-changing dimension). One row per
   `(source, reporting_period)`. Carries `status` (declared / covered / excluded),
   `data_quality_tier` (PCAF 1–5), `exclusion_reason`, and the **period-scoped** M2M
   `linked_tables`. Putting the M2M *here* (not on `InventorySource`) prevents ghost
   coverage: a table linked in 2024 no longer reads as "covered" in 2026.

3. **`CoverageGoal`** — `org_unit` × `scope` × `target_coverage_pct` × `min_quality_tier`
   × `completeness_definition` (`absolute` | `materiality_bounded`) × `target_year`,
   optionally linked to an `SBTiTarget`.

4. **`CoverageAction`** — remediation work item (collect data / improve quality /
   obtain verification / formalize exclusion), FK to `InventorySource`.

5. **`InventoryCoverageService.compute_coverage(period, org_unit=None)`** — returns the
   **five** outputs (not four): `{ total, covered, gaps, pct, avg_quality_tier,
   material_exclusions, completeness_definition }`. `material_exclusions` = count +
   reasons, feeding the CDP exclusions register. `min_quality_tier < 3` on a goal
   implies a verification requirement surfaced at compute time.

### API

Routers under `/carbon-api/carbon/`: `inventory-sources/`,
`inventory-source-statuses/`, `coverage-goals/`, `coverage-actions/`, plus a read-only
`coverage/?reporting_period=<id>&org_unit=<id>` endpoint that calls the service.
Write gate: `ReadAnyWriteAdmin` + `required_write_capability =
'carbon:manage_inventory_coverage'` (mirrors boundaries/base-years pattern).

### Capability

New CBAC capability `carbon:manage_inventory_coverage` (category `admin`), implied →
`carbon:view_console`; added to `carbon_lead` group; mirrored in frontend
`src/capabilities.js`.

## Alternatives Considered

- **Option A — compute coverage as a view-only derived metric** from `DataTable`.
  Rejected: the denominator (declared universe) is not stored anywhere; you cannot
  derive accountability from what happens to exist. The exclusions register and PCAF
  tier both presuppose a declaration.
- **Option B — new core app `backend/inventory/`.** Rejected: the generic half already
  exists in catalog+dq+mdm; the emissions-specific half belongs in `emissions/` (RULE_3).
  Re-extract only under Rule of Three.
- **Option C — extension fields on `DataTable`, or 1:1 `InventoryProfile`.** Rejected:
  scope is not a table property (table × scope × boundary is N:M), so it must be a
  binding keyed by scope/source, not a table column.

## Consequences

- **Positive:** a defensible coverage % (absolute vs materiality-bounded), a PCAF-aligned
  quality axis separate from completeness, an exclusions register for CDP, and a
  period-safe slowly-changing dimension.
- **Negative / trade-off:** five new tables + service + 4 viewsets + a new page; the
  period-scoped M2M means more writes when re-verifying a source each period.
- **Do NOT re-try:** view-only coverage (no stored denominator); `InventorySource`
  holding `status`/`tier` directly (breaks base-year recalculation + audit);
  scope/tier as columns on `DataTable`.

## References

- `backend/emissions/models.py` (ReportingPeriod, SBTiTarget, VerificationRecord)
- `backend/emissions/services.py` (TargetService — service-layer precedent)
- `backend/accounts/capabilities.py` (CBAC registry)
- GHG Protocol Corporate Standard Ch. 7 (IMP + Completeness); PCAF Data Quality Score 1–5
- TASKS.md Phase 28-A (backend) + Phase 28-B (frontend)
