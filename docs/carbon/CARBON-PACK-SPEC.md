# Carbon pack spec (rank 2)

**Subject:** `carbon.pack`  
**Owner:** carbon-inventory-lead  
**Locked:** 2026-09-29  
**Limit:** This file specifies the pack. It does not close O1. It does not
store a kilogram. Catalogue stays planned. `blocks_release` stays empty.
Rank 4 is not claimed from these headings.

Companion: `docs/carbon/O1-ONBOARDING-SPEC.md`,
`domain_packs/carbon/pack.yaml` version 4,
`domain_packs/carbon/assurance/pack.yaml`.

## Test plan

The pack gate is `python -m ai.eval.pack_contract --gate`. It checks that
the pack is versioned and self-contained and that `backend/ai/engine/**`
stays free of host-domain words. This section does not run that command.
Onboarding pytest and vitest stay on `carbon.journey.onboarding`. They are
not this subject's suite.

## Capabilities and roles

| Surface | Who | What it allows |
|---------|-----|----------------|
| Read tools | Pulse Chat | `list_organizational_boundaries`, `list_inventory_sources`, `get_inventory_coverage`, `get_calculation_summary`, `get_chairman_overview`. `requires_confirmation: false`. |
| Non-GET catalog tools | Pulse, after confirmation | `create_table`, `create_dq_rule`, `bind_dq_rules`. `requires_confirmation: true` (CR-WRITE-01). |
| Inventory writes | Host UI and Agent after approval | Not Chat tools (ADR-0046). |
| Route `carbon_onboarding` | Staff on a brand that enables carbon | `/carbon/onboarding`. |

A kilogram in Chat must be the same number in `get_calculation_summary` or
`get_chairman_overview` for this turn (CR-PULSE-01).

## Failure modes

| Condition | What fails | What does not happen |
|-----------|------------|----------------------|
| Host-domain word in `backend/ai/engine/**` | `pack_contract` | The word is not moved into the engine to pass |
| Chat states a tonne absent from the tool payload | CR-PULSE-01 | Chat does not write the inventory |
| A planned rule is added to `blocks_release` | This spec | Catalogue planned is not a release block |
| Pack version bumped without a separate change | This spec | Version stays 4 |

## Budget

- No new `re.compile` routing table and no phrase list in `backend/ai/engine/**` (ADR-0050).
- `pack.yaml` `version: 4` until a version bump is its own change.
- A millisecond ceiling is not declared.

## Module boundary

| May write | Must not write |
|-----------|----------------|
| `domain_packs/carbon/**` | `backend/ai/engine/**` |
| This file | `backend/people/**` |
| `docs/carbon/CARBON-PACK-SPEC.md` | `docs/carbon/evidence/O1-smart-village.json` |

## Signal threshold

| Field | Threshold |
|-------|-----------|
| `domain_packs/carbon/pack.yaml` | `id: carbon` and `version: 4` |
| `domain_packs/carbon/assurance/pack.yaml` | `blocks_release: []` |
| Live O1 GET | Belongs to `carbon.journey.onboarding`, not this file |

A latency SLO is not declared because none is measured.
