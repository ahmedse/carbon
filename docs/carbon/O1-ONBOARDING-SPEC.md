# O1 onboarding spec

**Target:** O1 — Smart Village electricity and diesel.  
**Product:** Carbon on AASTMT.  
**Owner:** carbon-inventory-lead.  
**Locked:** 2026-09-29.  
**Limit:** This file does not close South Valley, Abu Qir, Alamein, Scope 3,
or external assurance. It does not store a kilogram. GHG Protocol Corporate
Standard version 3 is a draft (CR-INV-01).

Companion files: `domain_packs/carbon/assurance/principles.yaml` (P-01–P-12),
`domain_packs/carbon/assurance/benchmarks/O1-smart-village.yaml`,
`assurance/carbon/ladder.yaml` subject `carbon.journey.onboarding`.

---

## Test plan

Suites that exist. A row is not a plan until the named test fails when the
rule breaks. Do not treat a live GET as a suite.

| Id | Suite | Proves |
|----|--------|--------|
| O1-COR-EVAL | `backend/emissions/tests/test_onboarding_o1.py` | `evaluate_o1` is pure. Two open periods emit `open_period_count` with `periods` (id, name, period_type, start_date, end_date, status) and no `summary_kg`. Zero open periods emit `periods: []`. A declared campus with an exclusion reason is `other_campus_no_status`. Factor and goal checks use `record_id`. `factor_value` and `target_coverage_pct` are absent from the JSON. |
| O1-COR-CONTRACT | `backend/emissions/tests/test_onboarding_contract.py` | Rule files load. Catalogue is planned. `blocks_release` is empty. O1 sources and closed ids O2–P2 are in the benchmark. Twelve principles. Eight process steps. Non-GET catalog tools require confirmation. |
| O1-USE-PAGE | `carbon-frontend/src/pages/carbon/__tests__/OnboardingPage.test.jsx` | Loading shows a skeleton. Count 0 is EmptyState. Count 2 names both periods and shows no `kg CO2e`. Missing sources name electricity and diesel. Kilograms appear only from `summary_kg`. A `factor_value` of `0.42` on the payload is not rendered. A percent sign is not rendered. Load failure shows Alert and `common:retry`. |
| O1-USE-TWO | Same page test, count 2 | Alert severity warning with `onboarding.tooManyOpen`. Copy names Lock, not Close. Action button `onboarding.openPeriods` navigates to `/carbon/reporting/periods`. The page does not POST or lock. The lead chooses which period leaves Open. |
| O1-USE-PERIODS | `carbon-frontend/src/pages/emissions/__tests__/ReportingPeriodsPage.test.jsx` | When two rows have `status` open, Alert severity warning with flat keys `tooManyOpenPeriods` / `tooManyOpenPeriodsHint`. It names both periods. It does not call `lockPeriod` or `closePeriod`. Close from Open stays 409 on the host. The next legal action remains Lock on the existing admin-gated control. One open period does not show this Alert. |
| O1-SPC-GAUGE | `python -m excellence.gauge --collect --only repo,rbac,budget,design_lint,antipatterns --no-db --tier carbon` | Catalogue problems stay empty. `CARBON-ONB-OBS-05` stays failed until a real calculation-summary payload is stored. Do not `--write` this collect to claim Operated. |
| O1-SEC-BRAND | `backend/emissions/tests/test_onboarding_api.py` | Unauthenticated GET is 401. `DJANGO_BRAND=nibras` authenticated GET is 403 with the Carbon-app message. `DJANGO_BRAND=aastmt` authenticated GET is 200 and `writes` is false. The test does not insert a period. |
| O1-REL-RETRY | `OnboardingPage.test.jsx` `shows an alert and retry` | A rejected load shows Alert and a Retry button that calls `fetchOnboardingO1` again. There is no automatic retry. |
| O1-PRF-STOP | `test_two_open_periods_ignores_factors_and_summary_kg` | When the open count is not 1, the checklist is one row. `factor_met` and `summary_kg` are absent. The function does not invent a millisecond. |
| O1-MNT-BOUND | `test_onboarding_o1_module_does_not_import_people_or_engine` | The source of `onboarding_o1.py` has no `from people` and no `from ai.engine`. |
| O1-OBS-SHAPE | `test_zero_open_periods_is_only_a_count` | Every result has `benchmark` O1, `writes` false, and `benchmark_status` open. |
| O1-GOV-CONTRACT | `test_onboarding_contract.py` | The ten rule ids stay planned. The evidence JSON path must not exist. |

Nightly Pulse goldens and `people:view` for `emp_1067` are not in this plan.

## Capabilities and roles

| Cap / gate | Who | What it allows |
|------------|-----|----------------|
| Authenticated + `CarbonBrandPermission` | Any user on a brand that enables the carbon app | GET `/carbon-api/carbon/onboarding/o1/`. Nibras returns 403. |
| App route `appId=carbon` | Same brand gate on the frontend | `/carbon/onboarding`. Nibras `AppEnabledRoute` redirects home. |
| Nav role `*` | Chairman pattern. Do not add `MENU_ITEM_CAPABILITIES` for the label | Sidebar item “Inventory onboarding”. A capability map would hide the item. |
| `carbon:admin` | Inventory lead and factor steward | Workflow-card destinations: boundaries, periods, inventory coverage, factors. The onboarding page itself does not require this cap. |
| Pulse Chat | Read tools only | May quote a kilogram only from `get_calculation_summary` or `get_chairman_overview` for the named period. Inventory writes are not Chat tools (CR-WRITE-01, ADR-0046). |
| Pulse Agent | After approval | May stage `enter_activity` and `calculate`. Does not skip RULE_21 consent. |
| `ahmed` | Platform SUPERUSER | May open the page on AASTMT. Password is `AdminPa_132` / `CARBON_ADMIN_PASSWORD`. Do not demote. |

`emp_1067` is a Nibras ESS persona. Do not grant `people:view` to pass coworker goldens. That user is not the AASTMT inventory lead.

## Failure modes

| Condition | Checklist / UI | What does not happen |
|-----------|----------------|----------------------|
| Zero `ReportingPeriod` with status `open` | `open_period_count` met false, count 0, `periods: []`. EmptyState. | No kilogram. No factor check. |
| Two or more open periods | `open_period_count` met false, `periods` sorted by id. Live `carbon_dev` 29 Sep 2026: FY 2023-24 id 15 and FY 2025-26 id 16. | The checklist does not pick which period to close. |
| One open period, dates inverted | `open_period_dates` | Period type and sources are still scored. |
| One open period, type not `annual` | `open_period_type` | O1 does not accept quarterly. |
| No boundary | `boundary_missing` | Campus words in a blank name are not a pass. |
| Approach outside the three model choices | `boundary_approach` | Free text is not accepted. |
| Source name missing | `source_missing` | The other campus is not used to pass O1. |
| Diesel description has both `generators` and `fleet` | `diesel_stream_both` | |
| Diesel description has neither word | `diesel_stream_missing` | |
| Other campus `not_material` | `other_campus_not_material` met false | Not the O1 default. |
| Other campus covered | `other_campus_covered` met false | Does not open O2, O3, or O4. |
| Brand is Nibras | API 403. Frontend redirects home. | Not a page bug. |
| GET fails | Alert + Retry | The page does not invent a period. |
| Chat states a tonne not in the tool payload | CR-PULSE-01 fail | Chat does not write the inventory. |

There is no automatic lock or close of the extra period. Close from Open is 409
(`test_close_invalid_transition_409`). The next legal host action is Lock
(open → locked). After that, exactly one row may remain `status` open. The
inventory lead chooses which period leaves Open. The onboarding page only
navigates to `/carbon/reporting/periods`.

## Budget

Declared, not measured as a live p95:

- One GET: `/carbon-api/carbon/onboarding/o1/`. The page does not poll.
- The checklist copies kilograms only from `CalculationSummaryService.get_summary` for the single open period.
- The checklist omits `factor_value`, `factor_unit`, and `target_coverage_pct`.
- When the open-period count is not 1, `EmissionFactor` and `CoverageGoal` are not queried.
- Chat does not add a domain phrase table in `backend/ai/engine/**` (ADR-0050).
- A millisecond ceiling is not declared. A missing number is not a measured latency.

## Module boundary

| May write | Must not write |
|-----------|----------------|
| `backend/emissions/onboarding_o1.py` and its tests | `backend/ai/engine/**` |
| `domain_packs/carbon/**` | `backend/people/**` |
| `assurance/carbon/ladder.yaml` | `carbon-frontend/src/apps/{people,my,team}/**` |
| `carbon-frontend/src/pages/carbon/OnboardingPage.jsx` and its test | `docs/carbon/evidence/O1-smart-village.json` until a real payload exists |
| `docs/carbon/O1-ONBOARDING-SPEC.md`, `docs/carbon/SCREEN-SPEC-O1-ONBOARDING.md` | A second evaluator that re-decides the rules in the browser |

`evaluate_o1` is the only checklist. The React page renders codes. It does not POST. Catalogue stays planned. `blocks_release` stays empty until a fault-demonstrated event exists.

## Signal threshold

The live signal is GET `/carbon-api/carbon/onboarding/o1/` as `ahmed` on brand `aastmt`, database `carbon_dev`.

| Field | Threshold |
|-------|-----------|
| HTTP | 200 on AASTMT. 403 on Nibras. |
| `writes` | `false` |
| `benchmark` | `O1` |
| `benchmark_status` | `open` until the evidence file exists |
| When count ≠ 1 | `checks` has exactly one row, code `open_period_count`, and `periods` lists every open row |
| Rank 5 file | `docs/carbon/evidence/O1-smart-village.json` stays absent until that GET returns one open period and a calculation summary with a kilogram that was not invented |

A latency SLO is not declared because none is measured.

## Rank 2 contract

Rank 2 cells on `carbon.journey.onboarding` are bound. Do not reopen them by
deleting the section headers in this file.

## Rank 3 contract (acceptance ids the tests must cite)

Standard rank 3: criteria have ids; forbidden-path tests exist; error and
retry are tested; a probe exists; the import boundary is clean; the payload
shape is asserted; the contract gate exists.

A test cites an id only when the id string appears in that test function
body. A comment on the class is not a citation.

| Id | Dimension | Must fail when |
|----|-----------|----------------|
| O1-COR-EVAL | specified, correct | Two open periods emit a kilogram or omit `periods` |
| O1-SEC-BRAND | specified, secure | Nibras returns 200, or the unauthenticated GET is 200 |
| O1-REL-RETRY | specified, reliable | The error Alert has no Retry, or load() is called on a timer |
| O1-PRF-STOP | specified, performant | A second check appears when the open count is not 1 |
| O1-MNT-BOUND | specified, maintainable | `onboarding_o1.py` imports `people` or `ai.engine` |
| O1-OBS-SHAPE | specified, observed | `writes` is true, or `benchmark` is not O1 |
| O1-GOV-CONTRACT | specified, governed | A rule is `blocks_release`, or the evidence JSON is created to pass a test |

Do not claim Built (L3) until every row above has a bound ladder check that
passed. Rank 5 still fails. Closing a reporting period is a host action for
the inventory lead. It is not this rank.

## Rank 4 contract (green on HEAD)

Standard rank 4 is executed evidence. Each cell names the pytest or vitest
app token and the node. `python -m excellence.gauge --no-db --tier carbon`
must be given those `--run` tokens. A repo `file_contains` is not this rank.
Do not `--write`. Do not create `docs/carbon/evidence/O1-smart-village.json`.
Do not run the whole emissions app.

| Id | Dimension | `--run` | Nodes |
|----|-----------|---------|-------|
| O1-SPC-HEAD | specified | `pytest:onboarding-criteria` | `emissions/tests/test_onboarding_o1.py`, `emissions/tests/test_onboarding_contract.py`, `emissions/tests/test_onboarding_api.py` |
| O1-SEC-HEAD | secure | `pytest:onboarding-secure` | `test_onboarding_api.py::OnboardingO1APITests::test_nibras_brand_is_forbidden`, `test_unauthenticated_is_unauthorized` |
| O1-REL-HEAD | reliable | `pytest:onboarding-reliable` | `test_onboarding_o1.py::EvaluateO1Tests::test_evaluate_o1_is_idempotent` |
| O1-PRF-HEAD | performant | `pytest:onboarding-performant` | `test_two_open_periods_ignores_factors_and_summary_kg` |
| O1-USE-HEAD | usable | `vitest:src/pages/carbon/__tests__/OnboardingPage.test.jsx` | That file only. Not a Playwright live journey. |
| O1-MNT-HEAD | maintainable | `pytest:onboarding-maintainable` | `test_onboarding_o1_module_does_not_import_people_or_engine` |
| O1-OBS-HEAD | observed | `pytest:onboarding-observed` | `test_zero_open_periods_is_only_a_count`, `test_aastmt_authenticated_is_read_only` |
| O1-GOV-HEAD | governed | `pytest:onboarding-governed` | `test_onboarding_contract.py` |

Idempotent means `evaluate_o1` with the same arguments returns an equal dict
the second time. It does not close a period. It does not call the database.

Do not claim Proven (L4) until every row above has a bound check that passed
on this HEAD with `--run`. Rank 5 still fails.

## Pack and Carbon UI rank 1 (locked, not Operated)

These cells exist so `carbon.pack` and `carbon.ui` are not Unmanaged for
missing rank-1 only. They do not close O1. They do not write the evidence
file. Catalogue stays planned.

| Id | Subject | Dimension | Probe |
|----|---------|-----------|--------|
| CARBON-PACK-SPC-01 | carbon.pack | specified | `domain_packs/carbon/pack.yaml` contains `id: carbon` and `version: 4` |
| CARBON-PACK-COR-01 | carbon.pack | correct | `principles.yaml` contains `P-01` through `P-12` |
| CARBON-PACK-REL-01 | carbon.pack | reliable | Subject owner field is non-empty |
| CARBON-PACK-MNT-01 | carbon.pack | maintainable | Subject `paths` exist |
| CARBON-PACK-OBS-01 | carbon.pack | observed | `domain_packs/carbon/assurance/pack.yaml` contains `blocks_release: []` |
| CARBON-UI-COR-01 | carbon.ui | correct | `carbon-frontend/src/apps/carbon/manifest.js` exists |

Do not add a `tests_present` probe on `carbon.ui`. That folder is the app
manifest, not a test tree.

## Pack and Carbon UI rank 2 (locked)

| File | Subject | What rank 2 is |
|------|---------|----------------|
| `docs/carbon/CARBON-PACK-SPEC.md` | `carbon.pack` | Test plan, roles, failure modes, budget, boundary, signal. Screen spec stays the O1 screen. `pack_contract` is named and not run by the probe. |
| `docs/carbon/CARBON-UI-SHELL-SPEC.md` | `carbon.ui` | Manifest nav and roles. ADR-0016. Does not grade every Carbon page. |

`carbon.module.emissions` stays L1. It has no rank-2 spec in this slice.
