# Carbon footprint — concept map

Grounding notes for the `domain-guidance` skill. Everything here is backed by a
shipped carbon host model, view or pack file. It names no kilogram and no factor
value; a number is only quoted when the current turn's tool payload holds it.

## 1. Standards and units

- **GHG Protocol Corporate Standard** (Scope 1 direct, Scope 2 purchased energy,
  Scope 3 value chain).
- **GHG Protocol Scope 2 Guidance** — location-based and market-based.
- **GHG Protocol Scope 3 Standard 2011** — category 5 is waste generated in
  operations.
- **ISO 14064-3** — the verification standard for the assurance engagement.
- **IPCC AR6** global warming potentials (AR5 also exists in the GWP reference).
- Units: `kg CO2e` (canonical), `tCO2e` = 1000 kg, `CO2e` = CO2 equivalent.

## 2. Inventory math

`emissions = activity x emission factor`. The factor is an EmissionFactor row
(factor_value, factor_unit, activity_unit, scope, source). Calculation rows hold
`co2e_kg`. Offsets, credits, RECs and EACs are a separate statement and are never
subtracted from the inventory.

## 3. Scope 2 — two labelled totals

- **Location-based** uses the grid factor (Egypt grid for Smart Village electricity).
- **Market-based** exists only when the calculation rule selects an active
  contractual factor whose primary key is not the grid factor.
- Without that factor the market-based total is **absent**, not zero and not a copy
  of the grid. There is no Egypt residual mix in this product. Never sum the two
  methods into one unlabelled figure.

## 4. Data-quality tiers (PCAF)

Smaller is better. 1 Audited, 2 Verified, 3 Calculated, 4 Estimated, 5 Proxy.
Onboarding accepts tier 4. Tier 5 may be stored and must be labelled Proxy; it is
not the academy footprint. A figure that leaves the organisation needs tier 3 or
better. The target's `min_quality_tier` is a floor on *settlement at target*:
a measured stream below the floor stays in the measured ratio but does not settle;
a stream with no tier is counted `tier_unknown` and is not credited.

## 5. Coverage — layers, states, gaps

Two layers: **Targets** (a period-scoped KPI over the declared universe) and
**Streams** (`InventorySource` + per-period `InventorySourceStatus`). **Tasks**
are causal work under a target.

- Streams are the solo reporter of **Missing / Entered / Excluded**.
- **Missing is not 0 kg.** An empty universe is an explicit `no_declared_sources`
  finding, never a blank or `0%`.
- `measured_pct` counts measured (entered-with-kg) streams; `excluded_pct` is
  reported separately and is never blended in.
- Gap codes: `no_declared_sources`, `missing`, `in_progress`, `awaiting_factor`,
  `below_floor`, `tier_unknown` — each with its verb (`declare_sources`,
  `enter_stream`, `complete_entry`, `secure_factor`, `improve_quality`,
  `declare_tier`).
- A task closes only when its evidence is met **and** the declared gap actually
  changed. A done status alone moves no measured count.
- The payload carries `claim="measured_not_claimed"` and `coverage_complete=false`.

## 6. Reporting period

One period is open for entry. States and legal transitions: draft → open →
locked → submitted → verified → closed; locked → open; submitted → rejected →
submitted; verified → closed. A locked period is read-only; a rejected period
carries the verifier's note.

## 7. Assurance (P1)

Five fields: assurer_name, engagement_type (limited | reasonable), standard
(ISO 14064-3), opinion_date, statement_id. `not_assured` stays visible and unmet
until a named engagement exists with an opinion dated on or after the period end.
Recording the fields does not by itself mark the inventory assured.

## 8. Disclosure (P2)

A labelled projection of existing Calculation, InventorySource, ReportingPeriod
and OrganizationalBoundary fields into column names:

- ESRS E1-6, IFRS S2, CDP C6.
- It computes no new total, is not a filing, and does not mark P2 passed.
- Market-based is absent unless the distinct contractual factor exists; Scope 3 is
  omitted until O5.

## 9. Base-year recalculation

GHG Protocol Chapter 5 triggers: structural change, methodology change, error
correction, significance threshold. Policies: significant-only, all-changes, or
never. A base year with open triggers cannot be deleted; history is restated by
appending, never rewritten in place.

## 10. Campuses and the O1 leaf (as shipped)

- **Smart Village** — O1: electricity (scope 2, location-based, kWh) and diesel
  (scope 1, litre; one stream, generators or fleet).
- **South Valley** (O2), **Abu Qir** (O3), **New Alamein** (O4) — declared or
  explicitly excluded with a reason in O1.
- **O5** — Scope 3 category 5 (waste generated in operations), the single named
  source being Smart Village waste disposal (tonne). Status stays closed until the
  source and a matching factor exist; the 73 tonne activity line carries no kg.

## 11. Honest-measurement rules to keep

- Do not state a kilogram or tonne that is not in this turn's payload.
- Do not claim "coverage complete", an assured inventory, or a filed disclosure.
- Do not invent a factor, a residual mix, a campus name, or a department.
- Chat reads; host writes are Agent + approval or a host screen (ADR-0046).
