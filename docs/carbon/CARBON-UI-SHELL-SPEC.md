# Carbon UI shell spec (rank 2)

**Subject:** `carbon.ui`  
**Owner:** owner  
**Locked:** 2026-09-29  
**ADR:** `.ai-toolkit/decisions/0016-domain-app-ai-contract.md`  
**Limit:** This file grades `carbon-frontend/src/apps/carbon/manifest.js`.
It does not grade every Carbon page. Inventory onboarding stays on
`carbon.journey.onboarding`. Rank 4 is not claimed. No kilogram is stored.

## Test plan

`carbon-frontend/src/apps/carbon/` has no test file. Do not point
`tests_present` at that folder. Rank 2 is this section. A later contract
test may assert the manifest still contains the Inventory onboarding path.
That test is not written here.

## Capabilities and roles

Declared on the manifest `navigation` items:

| Label | Path | Manifest role |
|-------|------|----------------|
| Inventory onboarding | `/carbon/onboarding` | `*` |
| Chairman Overview | `/carbon/chairman` | `*` |
| Carbon Console | `/carbon/console` | `*` |
| Emissions Dashboard | `/carbon/dashboard` | `*` |
| Data Entry | `/carbon/my-data` | `carbon:data_owner` |
| Calculations | `/carbon/calculations` | `carbon:data_owner` |
| Verification | `/carbon/verification` | `carbon:data_owner` |
| Analytics & Trends | `/carbon/analytics` | `carbon:analyst` |
| Reports | `/carbon/reporting` | `carbon:analyst` |
| Emission Factors through Inventory Coverage | `/carbon/admin/*` | `carbon:admin` |
| Reporting Periods | `/carbon/reporting/periods` | `carbon:admin` |

The route guard for Reporting Periods is `carbon:manage_reporting_periods`
in `authz.js`. That key is not the manifest role string. Do not collapse them.

Inventory onboarding uses role `*`. Do not add `MENU_ITEM_CAPABILITIES` for
that label. Nibras hides the carbon app through `AppEnabledRoute`.

## Failure modes

| Condition | Result |
|-----------|--------|
| Brand does not enable carbon | App route redirects home. Not an empty state inside the manifest. |
| Nav role is a capability the user lacks | The shell hides that item. Onboarding stays visible because role is `*`. |
| Manifest `color` is still `#2e7d32` | Seed only. This rank does not delete it. Pages still must not add hex. |

## Budget

The manifest `version` string is `1.0.0`. That is not a measured release
and not a latency budget. No millisecond SLO.

## Module boundary

| May write | Must not write |
|-----------|----------------|
| `carbon-frontend/src/apps/carbon/manifest.js` | `carbon-frontend/src/apps/people/**` |
| This file | `backend/ai/engine/**` |
| | `backend/people/**` |

`OnboardingPage.jsx` belongs to `carbon.journey.onboarding`, not this subject.

## Signal threshold

| Field | Threshold |
|-------|-----------|
| File | `carbon-frontend/src/apps/carbon/manifest.js` exists |
| Onboarding item | path `/carbon/onboarding`, role `*` |
| App id | `id: 'carbon'` |

A live journey and a p95 are not this signal.
