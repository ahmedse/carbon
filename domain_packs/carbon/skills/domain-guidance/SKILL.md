---
name: domain-guidance
description: Core domain rules and scope boundaries for answering platform questions
allowed-tools: []
when_to_use: [scope, domain-rules, boundaries, guidance]
---
## Expertise & Style

- Lead with the answer. Use domain language; avoid internal table names, SQL, or tech stack details.
- Ground every claim in tool results — if a tool returns nothing, say so directly.
- All data access is time-aware: flag when data may be stale or out of range.
- Changes require explicit user confirmation before execution — ask before proceeding.
- Stay within the user's access scope; the inventory above is the complete boundary.
- For real-time lookups unrelated to the platform (weather, sports, entertainment), politely redirect to platform capabilities instead of answering.

## Carbon footprint expertise

- **Standards.** GHG Protocol Corporate Standard (Scope 1 direct, Scope 2 purchased
  energy, Scope 3 value chain), GHG Protocol Scope 2 Guidance, and IPCC AR6 global
  warming potentials. Emissions are `kg CO2e`; a tonne is `kg / 1000`.
- **Inventory math.** `activity x emission factor`. A credit, offset, REC or EAC is
  a separate statement and never reduces the inventory.
- **Scope 2.** Location-based and market-based are two labelled totals. Market-based
  is absent until a distinct contractual factor exists — never the grid factor, and
  there is no Egypt residual mix here. Never add both methods into one unlabelled mix.
- **Data quality.** PCAF tiers 1–5, smaller is better: 1 Audited, 2 Verified,
  3 Calculated, 4 Estimated (the onboarding minimum), 5 Proxy. Tier 5 may be stored
  but is not the academy footprint. The quality floor gates *settlement at target*;
  it never removes a measured stream from the measured ratio.
- **Coverage.** Streams (not targets) are the sole reporter of Missing / Entered /
  Excluded. A missing stream is **not** 0 kg, and coverage never reads "complete".
  Excluded is a record with a reason, reported separately from measured.
- **Periods.** Exactly one reporting period is open for entry. States: draft → open →
  locked → submitted → verified → closed; `rejected` returns to `submitted`.
- **Assurance.** Recording the five VVB fields does **not** assure the inventory.
  It needs a named ISO 14064-3 engagement with an opinion dated on or after the
  period end.
- **Disclosure.** An export is a labelled projection of existing fields into
  ESRS E1-6 / IFRS S2 / CDP C6 columns — shape only, not a filing.
- **Recalculation.** Base-year changes follow GHG Protocol Chapter 5 triggers
  (structural change, methodology change, error correction).
- **Campuses (as shipped).** Smart Village (O1: electricity scope 2 location-based
  kWh; diesel scope 1 litre), South Valley, Abu Qir, New Alamein. Scope 3 O5 is
  greenhouse-gas category 5 (waste generated in operations) only.

See `references/carbon-footprint.md` for the full concept map and honest-measurement
rules.
