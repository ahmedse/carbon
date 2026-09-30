# O1 production rollout plan

**Target:** O1 — Smart Village electricity and diesel.  
**Product:** Carbon on AASTMT. Canonical host name: `carbon.clearturn.tech`.  
**Owner:** carbon-inventory-lead.  
**Locked:** 2026-09-29.  
**What this rollout is:** staff may start the eight host steps.  
**What this rollout is not:** a verified footprint, external assurance, a score of `carbon.clearturn.tech`, or academy complete. The onboarding journey L5 on 30 Sep 2026 was a local collect on `carbon_dev` and was not written.

`carbon.clearturn.tech` was not scored. The live signal is GET `/carbon-api/carbon/onboarding/o1/` on brand `aastmt`, database `carbon_dev`. The open period is FY 2023-24 id 15. FY 2025-26 id 16 is locked. `benchmark_status` is `passed` when the linked calculations match the source files: electricity `1239599.320800` kg (2,704,187 kWh) and generators diesel `8040.000000` kg (3,000 L). `not_assured` stays unmet. Fleet diesel 5,161 L is not this stream. The × 1.018 fill is archived and is not the quote.

This file does not add a ladder cell and does not raise a level.

---

## Sentence you may send

Send this. Do not add a tonne, a percent, or the word assured.

> Carbon inventory work is open on AASTMT. Open Carbon, then Inventory onboarding. FY 2023-24 is Open for Data Entry. FY 2025-26 is Locked. The electricity and generators diesel on that open year are the source file. Fleet diesel is not the O1 stream. Leave South Valley, Abu Qir, and Alamein excluded with insufficient data. Do not publish a footprint. Do not quote the period-wide calculation summary as the Smart Village footprint. Chat can read. Chat does not create a period, a source, or a calculation.

Nibras users are not in this sentence. Carbon on Nibras returns 403.

---

## Go and no-go

| Sentence | Now | Why |
|----------|-----|-----|
| Start Inventory onboarding on AASTMT Carbon | Yes | Screen is shipped. Route `/carbon/onboarding`. Role `*`. |
| Inventory lead locks one extra open period | Done on `carbon_dev` | POST `/carbon-api/carbon/periods/15/lock/` as `ahmed` on 29 Sep 2026. FY 2023-24 is Locked. |
| Which year stays Open | FY 2023-24 id 15 | The Excel year. FY 2025-26 id 16 is locked because that year has no Smart Village file. |
| Enter the two Smart Village sources | Done on `carbon_dev` | Both names are covered. Electricity scope 2. Diesel scope 1, description generators. |
| Say O1 passed | No | Benchmark status stays open. The series is populated, not an invoice. `not_assured` stays unmet. |
| Say a kilogram or a tonne as the Smart Village footprint | No | Quote only the linked-table kilograms, and only from this turn's tool payload. The period-wide mix is not Smart Village. |
| Say a coverage percent | No | Goal 3 is draft, tier 4, 25 percent. Do not publish it as the academy footprint. Do not default 100. |
| Say the academy footprint left the organisation | No | P1 is closed. Needs tier 3 or better. |
| Say externally assured | No | P2 is closed. No verifier. Corporate Standard v3 is a draft. |
| Say L5 means production go-live | No | Journey L5 is a local collect, not written. Module, UI, and pack are L2. The host was not scored. |
| Say `carbon.clearturn.tech` was scored | No | This collect is local `--no-db` plus `carbon_dev`. |
| Tell Nibras staff to open Carbon | No | `CarbonBrandPermission` 403. |

---

## Who does what

| Role | This week | Screen | Rule |
|------|-----------|--------|------|
| Inventory lead | Period lock and both O1 source names are done on `carbon_dev`. Boundary on FY 2025-26 is `operational_control`. | `/carbon/admin/inventory-coverage` | CR-SRC-01 |
| Inventory lead | Keep South Valley, Abu Qir, and Alamein excluded with `insufficient_data`. Do not cover them to finish O1. | `/carbon/admin/inventory-coverage` | CR-EXC-01 |
| Factor steward | Bind an active factor: scope 2 kWh, and scope 1 litre. Country code EGY or blank. Citation non-empty. | `/carbon/admin/factors` | CR-FAC-01 |
| Campus data owner | Enter quantity above zero. Unit kWh or litre. A missing month is a gap, not zero. | `/carbon/my-data` | CR-DQ-01 |
| A person who is not the data owner | Run is confirmed by a person. Then cover or exclude. | `/carbon/calculations`, then inventory coverage | CR-COV-01, CR-EXC-01 |
| Pulse Chat | Quote a kilogram only when this turn's tool payload contains it. Otherwise say the period is opening. | Chat | CR-PULSE-01, CR-WRITE-01 |
| Pulse Agent | May stage enter activity and calculate only after approval and RULE_21 consent. | Agent | ADR-0046 |

`cover_or_exclude` requires two distinct people: campus data owner and inventory lead.

---

## Eight steps

Order is the process `inventory.onboarding.lifecycle`. A later step does not start while the previous one is open.

| Step | Autonomy | Depends on | Rule |
|------|----------|------------|------|
| `name_boundary` | human only | — | CR-BND-01 |
| `open_period` | human only, consent | name_boundary | CR-PER-01 |
| `declare_sources` | human only, consent | open_period | CR-SRC-01 |
| `bind_factors` | human only | declare_sources | CR-FAC-01 |
| `enter_activity` | confirm, consent | bind_factors | CR-DQ-01 |
| `calculate` | confirm, consent | enter_activity | CR-COV-01 |
| `cover_or_exclude` | human only, consent, two roles | calculate | CR-EXC-01 |
| `verify_quote` | observe | cover_or_exclude | CR-PULSE-01 |

The onboarding page does not POST, lock, or close. It renders `evaluate_o1`.

---

## Principles (P-01–P-12)

Owner `carbon-inventory-lead`. Locked 2026-09-29. A violation is a failed onboarding claim.

| Id | Name | Staff meaning | Binds |
|----|------|---------------|-------|
| P-01 | Boundary before tonnes | No kilogram until the open period has a boundary with one of the three consolidation approaches. | CR-BND-01, CR-PER-01 |
| P-02 | One open period | Exactly one status open. Start before end. A count without id, name, start, and end is an incomplete failure. | CR-PER-01 |
| P-03 | Declared denominator | Coverage uses InventorySource rows. No row means absent, not zero percent. | CR-SRC-01, CR-COV-01 |
| P-04 | Same-period coverage | Covered only with this period's linked tables and a Calculation for that period. | CR-COV-01 |
| P-05 | Quality is not completeness | Tiers 1–5, smaller is better. Onboarding minimum is 4 Estimated. A figure that leaves the organisation needs 3 or better. Tier 5 is Proxy. | CR-COV-01, CR-FAC-01 |
| P-06 | Exclusion is a record | Declared, or excluded with a reason. Silence is neither. | CR-EXC-01 |
| P-07 | Leaf before the academy | O1 is Smart Village electricity and diesel only. | CR-SRC-01 |
| P-08 | Factors are records | The factor number stays on the EmissionFactor row. It is not typed into the checklist. | CR-FAC-01, CR-DQ-01 |
| P-09 | Pulse quotes the tool | A kilogram in Chat must be in `get_calculation_summary` or `get_chairman_overview` for the named period. | CR-PULSE-01 |
| P-10 | Chat does not write | Inventory writes are host screens or Agent after approval. | CR-WRITE-01, CR-PULSE-01 |
| P-11 | Methodology stays provisional | Scopes 1, 2, and 3 exist on the model. Catalogue stays planned. v3 is not the method in force. | CR-INV-01 |
| P-12 | Ready is a sentence | Ready names target O1, product Carbon on AASTMT, evidence, date, and the limit. | CR-PULSE-01 |

---

## Rules

Catalogue is `planned` on every row. `blocks_release` is empty. None of these reject a release today. They report. CR-DQ-01 has no `evaluate_o1` code until a linked activity table exists.

| Id | Predicate the lead can check | Owner |
|----|------------------------------|-------|
| CR-INV-01 | Scopes 1, 2, and 3 exist on the model. That does not mean AASTMT has a populated period. | carbon-inventory-lead |
| CR-BND-01 | The one open period has a boundary. Approach is `equity_share`, `financial_control`, or `operational_control`. Campus words in the name are not a pass. | carbon-inventory-lead |
| CR-PER-01 | Exactly one status `open`. `start_date` < `end_date`. O1 `period_type` is `annual`. Status open means Open for Data Entry. | carbon-inventory-lead |
| CR-SRC-01 | Sources named `Smart Village electricity` (scope 2) and `Smart Village diesel` (scope 1). Diesel description contains exactly one of `generators` or `fleet`. | carbon-inventory-lead |
| CR-FAC-01 | Active factor, scope 2 and kWh, scope 1 and litre. Country `EGY` or blank. `EG` is not a stored code. `factor_value` is omitted from the checklist. Row id is `record_id`. | carbon-factor-steward |
| CR-COV-01 | Goal scope `1+2`, `materiality_bounded`, min tier 4, status `draft`, and only after both O1 sources exist. Do not copy `target_coverage_pct`. Covered needs linked tables and a Calculation. | carbon-inventory-lead |
| CR-EXC-01 | Other campuses: absent, no status, declared, excluded (`insufficient_data` is the O1 default), excluded-with-other-and-blank-notes, `not_material` (fail during O1), or covered (does not open O2–O4). | carbon-inventory-lead |
| CR-DQ-01 | Quantity > 0. Unit matches the factor. A missing month is a gap note, not zero. | carbon-campus-data-owner |
| CR-PULSE-01 | Chat kilograms match the tool payload. `get_chairman_overview` tonnes are kg/1000 from that payload. A sketch number is not legal. | carbon-inventory-lead |
| CR-WRITE-01 | Non-GET catalog tools `create_table`, `create_dq_rule`, `bind_dq_rules` have `requires_confirmation: true`. Inventory writes are not Chat tools. | carbon-inventory-lead |

When the open count is not 1, the checklist returns one row: code `open_period_count`, fields `count` and `periods` (id, name, period_type, start_date, end_date, status), no kilograms. Live `carbon_dev` 30 Sep 2026:

| Id | Name | Type | Start | End | Status |
|----|------|------|-------|-----|--------|
| 15 | FY 2023-24 | annual | 2023-07-01 | 2024-06-30 | open |
| 16 | FY 2025-26 | annual | 2025-07-01 | 2026-06-30 | locked |

---

## Benchmark O1

Status `open`. Campus Smart Village, code `AASTMT-SV`. Evaluator `evaluate_o1`, writes false.

**Pass**

- Exactly one open annual period, start before end, boundary approach one of the three.
- Both source names at the scopes above. Diesel description exactly one stream.
- Covered only under the coverage requirements below.
- Pulse repeats a figure only from the named tool payload.
- South Valley, Abu Qir, and Alamein declared or excluded. They are not required to be covered.

**Fail**

- A tonne with no payload.
- Covered with empty linked tables.
- A second open period.
- O1 marked passed from another campus or from Scope 3.
- `target_coverage_pct` stored before any source exists.

**Closed until O1 has one named period and a calculation summary**

| Id | Title | Stays closed because |
|----|-------|----------------------|
| O2 | South Valley electricity and one fuel | Opens after O1 has a named period and a calculation summary |
| O3 | Abu Qir electricity and one fuel | Same gate |
| O4 | Alamein electricity and one fuel | Same gate |
| O5 | Scope 3 categories declared | Outside O1. Do not mark a category covered |
| P1 | A figure leaves the organisation | Tier 3 or better, and CR-INV-01 still planned |
| P2 | External assurance | No verifier. v3 is a draft |

---

## Coverage

| Field | O1 value | When |
|-------|----------|------|
| `CoverageGoal.scope` | `1+2` | After both O1 sources exist |
| `completeness_definition` | `materiality_bounded` | Same row |
| `min_quality_tier` | 4 Estimated | While O1 is the open benchmark |
| `status` | `draft` | Not active during onboarding |
| `target_coverage_pct` | Chosen by the lead | Absent until sources exist. The screen must not default 100 |
| status covered | linked tables plus a Calculation | Same reporting period only |
| Other campuses | declared, or excluded `insufficient_data` | `not_material` is not the O1 default |

Quality scale, smaller is better: 1 Audited, 2 Verified, 3 Calculated, 4 Estimated, 5 Proxy.

Known stop, from CR-SRC-01: an InventorySource cannot be saved without an org unit. This plan does not invent an org id. If Smart Village has no org unit, O1 stays open and the lead creates the org unit on the host. That is not a tonne.

---

## Excellence plan

Overall is the minimum dimension, not the mean. Levels: 0 Unmanaged, 1 Declared, 2 Specified, 3 Built, 4 Proven, 5 Operated, 6 Excellent.

Repo-only collect 29 Sep 2026, HEAD `88b5ca3`, not written to the ledger:

| Subject | Overall | What you may say | What you may not say |
|---------|---------|------------------|----------------------|
| `carbon.journey.onboarding` | L4 with `--run`; L3 on repo-only | The onboarding suites passed on this HEAD | Operated. The evidence file exists. Production was scored |
| `carbon.pack` | L2 Specified | The pack contract is written. Version 4 | `pack_contract` was run in this collect. Catalogue is configured |
| `carbon.ui` | L2 Specified | The manifest and shell spec exist | Every Carbon page is proven |
| `carbon.module.emissions` | L2 Specified | CARBON-MODULE-SPEC.md exists | Proven, or O1 complete |

Rank 5 check `CARBON-ONB-OBS-05` is the served GET, evidence class enforcement-verified. A file at `docs/carbon/evidence/O1-smart-village.json` does not raise the level, and the contract test fails if that file exists. Do not hand-write it. Do not `--write` the gauge. Overall stays the minimum dimension.

---

## Stops that are not a staff shortcut

- Do not lock a period from Inventory onboarding. Use Reporting periods. On `carbon_dev` the extra period is already Locked.
- Do not insert a zero for a missing month.
- Do not type a factor number into a note.
- Do not mark South Valley, Abu Qir, Alamein, or Scope 3 covered to finish O1.
- Do not grant `people:view` to `emp_1067`. That user is not the AASTMT inventory lead.
- Do not edit `backend/ai/engine/**` to make this rollout pass.
