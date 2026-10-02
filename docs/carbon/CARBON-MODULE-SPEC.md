# Carbon emissions module spec (rank 2)

**Subject:** `carbon.module.emissions`  
**Owner:** owner  
**Locked:** 2026-09-29  
**ADR:** `.ai-toolkit/decisions/0025-typed-vs-dataschema-storage.md`  
**Product:** Carbon on AASTMT.  
**Limit:** This file grades `backend/emissions`. It does not close O1. It does
not store a kilogram. Rank 4 is not claimed from these headings. Catalogue
stays planned.

Activity measurements live in `dataschema.DataRow`. Authority lives on typed
models: `EmissionFactor`, `CalculationRule`, `OrganizationalBoundary`,
`ReportingPeriod`, `InventorySource`, `InventorySourceStatus`, `CoverageGoal`.

## Test plan

Suites that exist under `backend/emissions/tests`. A row is not a plan until
the named test fails when the rule breaks.

| Id | Suite | Proves |
|----|--------|--------|
| O1-COR-EVAL | `test_onboarding_o1.py` | `evaluate_o1` is the checklist. Two open periods emit no kilogram. |
| O1-COR-CONTRACT | `test_onboarding_contract.py` | Ten rule ids. Catalogue planned. `blocks_release` empty. |
| O1-SEC-BRAND | `test_onboarding_api.py` | Nibras 403. Unauthenticated 401. AASTMT GET `writes` false. |
| E2-LOCK | `test_e2_b3_period_lock.py` | Close from Open is 409. Lock from Open is 200. |

Onboarding suites stay on `carbon.journey.onboarding` for Rank 4 `--run`.
This subject does not steal those tokens.

## Capabilities and roles

| Cap | Who | What it allows |
|-----|-----|----------------|
| Authenticated + `CarbonBrandPermission` | Users on a brand that enables carbon | Emissions APIs. Nibras 403. |
| `carbon:manage_reporting_periods` | Inventory lead | Periods host screen. Lock is admin-gated in the UI. |
| Pulse Chat | Read tools | Kilogram only from `get_calculation_summary` or `get_chairman_overview` for that turn. |
| Pulse Chat | Writes | Not allowed. ADR-0046. |

## Failure modes

| Condition | Module behaviour | What does not happen |
|-----------|------------------|----------------------|
| Two periods status `open` | `evaluate_o1` returns `open_period_count` and stops | A kilogram. A factor check. |
| Close from Open | 409 | Status does not become `closed` |
| Covered with empty `linked_tables` | Checklist fail | O1 does not pass |
| Chat states a tonne absent from the tool payload | CR-PULSE-01 fail | Chat does not write the row |
| `EMISSIONS_AUTO_CALC` left default | No auto calculation on `DataRow` save | A silent footprint |
| Open data-entry period is not the single status `open` row | Console, chairman header, and intake bind to that one period | FY 2023-24 shown as the open year. Closed-year kilograms added to Calendar year 2026. A missing stream shown as 0 kg |

## Budget

- `evaluate_o1` is one function. The onboarding page does one GET.
- When the open count is not 1, `EmissionFactor` and `CoverageGoal` are not queried.
- A millisecond SLO is not declared.
- No domain phrase table in `backend/ai/engine/**`.

## Module boundary

| May write | Must not write |
|-----------|----------------|
| `backend/emissions/**` | `backend/ai/engine/**` |
| This file | `backend/people/**` |
| | `docs/carbon/evidence/O1-smart-village.json` until a real payload exists |

`evaluate_o1` does not import `people` or `ai.engine`.

## Signal threshold

| Field | Threshold |
|-------|-----------|
| Storage ADR | ADR-0025 exists |
| Tests | `backend/emissions/tests` exists |
| Live O1 | Belongs to `carbon.journey.onboarding`. This file does not score `carbon.clearturn.tech` |

A latency SLO is not declared because none is measured.
