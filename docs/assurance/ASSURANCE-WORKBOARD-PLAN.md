# Assurance workboard — design plan

**Status:** Catalogue + probe layer implemented 23 Sep 2026.  
Nibras probes were executed (honesty, independent formulas, signed conservation, static host bindings).  
The HTTP stream, frontend route, and Django host tests are not built.  
Static binding is not a same-actor HTTP test and not a PIFSS legal check.  
**Companion canvas:** the Assurance workboard canvas beside chat (design board, not the product stream).

This plan does not claim the system never breaks, is zero-defect, or is certified.

---

## 1. Decision

Build one **shared assurance core** plus a **domain-pack adapter**. The live work dashboard is a projection of an append-only evidence ledger. Domain packs supply rules, journeys, and oracles. The core supplies gates, the event schema, staleness, and the screen.

Prefer this over a new quality platform. The repo already has:

- `.ai-toolkit/` contracts, `verify.sh`, and the 4-layer QA model
- `domain_packs/nibras`, `domain_packs/carbon`, `domain_packs/eduos`
- People host SoD, payroll status machine, correspondence leave/loan
- Pulse SSE (`text/event-stream`) for plans and the task inbox
- GitHub Actions CI (configured; branch protection **not verified**)

The dashboard does not replace those controls. It shows whether each control has evidence on the current commit.

## 2. Dependency rule

Same direction as the platform: **core never imports a domain app**.

```
domain_packs/<pack>/assurance/     rules, journeys, oracles, pack manifest
        │ loaded by id
        ▼
assurance core                     schema, ledger, evaluator, SSE, gates
        │
        ▼
Assurance app (carbon-frontend)    work dashboard for engineering seats
```

`people/`, `emissions/`, and `gradevance/` stay the systems under test. They do not import the dashboard.

Pulse Chat does not narrate gate status and does not mark a row passed.

## 3. Pack contract

Each pack that opts in ships:

```
domain_packs/<pack>/assurance/
  pack.yaml          id, title, brand, journeys, owners
  rules/<rule-id>.yaml
  gates.yaml         which shared gate ids apply, and pack-specific checks
  oracles/           independent expected values (not the code under test)
```

`pack.yaml` (normative shape):

| Field | Meaning |
|---|---|
| `id` | `nibras`, `carbon`, `eduos`, `platform` |
| `brand` | `DJANGO_BRAND` this pack is valid for, or `*` for platform |
| `journeys` | Critical flows the pack owns |
| `owners` | Named roles who may mark a rule owner-approved |
| `blocks_release` | Rule ids that must be `fault-demonstrated` or explicitly excepted before a release candidate |

`rules/<id>.yaml`:

| Field | Meaning |
|---|---|
| `id` | Stable, e.g. `NR-PAY-02` |
| `meaning` | One sentence |
| `source` | Doc, ADR, or statute. Not “the code” |
| `owner` | Role. Empty until a person accepts it |
| `failure` | Consequence if the rule is false |
| `validation` | Test, oracle, or manual evidence method |
| `implementation` | Module that is supposed to enforce it |
| `confidence` | `high-code`, `medium`, `low`, `conflict` |
| `owner_status` | `documented`, `implemented`, `owner-approved` |

A rule with `confidence: conflict` cannot be marked passed. Leave over-balance is the current example: Deep QA M-BAL-04 requires HTTP 4xx; `leave.request.lifecycle.yaml` still lists negative entitlement as `ask_if` advisory.

**Platform pack** (`domain_packs` is the wrong home for cross-cutting engineering gates). Those live in the core catalogue `assurance/platform/` and always load beside the active brand pack.

**Packs observed today**

| Pack | What it is | Assurance folder | Phase |
|---|---|---|---|
| `nibras` | GOFSCO People / My / Team / payroll / WPS | Absent | Pilot |
| `carbon` | Pulse vocabulary for the emissions brand | Absent. Accounting code is `backend/emissions/` | Phase 4 |
| `eduos` | GradeVance profiles, rubrics, gold JSON | `scripts/validate_packs.py` and `gold/` exist. No assurance manifest | Phase 5 |
| platform | `verify.sh`, CI, CBAC, import boundary, Pulse G2 | Scattered | Always on |

Loading a pack the way Pulse loads `domain_packs/<brand>/` is the seam: `DJANGO_BRAND` selects the brand pack; the platform pack is unconditional.

## 4. Evidence event

One JSON object per check. Append-only. The dashboard never stores a status that is not derived from these events plus the rule file.

```json
{
  "rule_id": "NR-PAY-02",
  "pack_id": "nibras",
  "commit": "3d0c045",
  "gate_id": "pr-people-pytest",
  "result": "passed",
  "evidence_class": "executed",
  "source": "people/tests/test_host_sod.py::SoDUnitTests.test_same_actor_refused",
  "duration_ms": 840,
  "runner": "local",
  "at": "2026-09-23T06:48:00Z"
}
```

`evidence_class` is only one of:

| Class | Meaning |
|---|---|
| `configured` | The check exists in repo or CI. Nobody has run it for this claim |
| `executed` | A command produced this event |
| `enforcement-verified` | Branch protection or an equivalent control was observed to block |
| `fault-demonstrated` | A seeded defect failed the gate; the repair passed |
| `unknown` | The check could not run |
| `conflict` | Two sources disagree. Not passable |

`result` is `passed`, `failed`, or `unknown`.

**Derived row state** (the only state the UI shows):

1. No event on this commit → catalogue class (`configured`, `conflict`, `planned`). Never green.
2. Latest event commit ≠ `HEAD` → **stale**.
3. Latest event result on this commit → that result, labeled with its evidence class.
4. Skipped job, `pytest -x` truncation, or a docs “READY” line with no event → **unknown**.

## 5. Live stream

The product dashboard is live. The canvas beside chat is the design twin and is not connected to pytest.

| Piece | Role |
|---|---|
| `assurance/ledger/*.jsonl` | Append-only log, one file per day, gitignored if it contains run output |
| Wrapper | `./manage.sh` test target, or a pytest plugin, writes one event per test that maps to a rule id. It does not launch the full suite |
| `HEAD` watcher | On commit change, the evaluator marks older events stale. No new “pass” is invented |
| `GET /assurance/stream/` | SSE, `text/event-stream`, same response type Pulse already uses in `plans_api.py` and `task_inbox_api.py`. Separate channel from Chat |
| CI | The backend job emits the same JSON schema as an artifact. The board shows `local` and `ci` as two chips on one row |
| Runtime (later) | Payroll, WPS, and auth failures join the same schema when a trace exists. Not in the pilot |

The board listens. It does not schedule `pytest` with no arguments. `shared/testing.md` RULE 7: an unscoped suite saturates this machine.

Flake count is a property of the rule over the last N events. It is not folded into a health score.

## 6. Work dashboard

Internal route, engineering seats only. Not My, Team, People, or the emissions dashboard.

**Header:** active pack, `HEAD`, stream connection (live / stale / disconnected).

**Primary table:** one row per rule in the loaded packs.

| Column | Source |
|---|---|
| Rule | Pack file |
| Journey | Pack file |
| Meaning | Pack file |
| Owner status | Pack file |
| Evidence | Latest event on this commit |
| Class | Derived |
| Residual | Pack file, plus open exceptions |

**Selecting a row** opens the trace:

`requirement → invariant → implementation → test → gate → runtime signal → residual`

**Filters:** pack, journey, class, “blocks release”.

**Charts allowed:** counts of rows by evidence class; gate duration when events have `duration_ms`; exception age. No `GateScore` until the underlying metrics have been measured. The formula in `docs/nibras/QA-DEEP-MULTI-USER-JOURNEY.md` stays a target definition.

**Narration:** optional and citation-only. A sentence may quote rule id, commit, and event id. It may not assign status.

## 7. Pilot slice — Nibras payroll commit

Journey **J4**: draft → compute → validate → distinct-actor commit.

First rules to encode (owner confirmation still open):

| ID | Meaning | Confidence now |
|---|---|---|
| NR-PAY-01 | Compute uses a verified compensation-ledger basic line, not `Employee.basic_salary` | High in code (ADR-0029). Owner not confirmed |
| NR-PAY-02 | Commit actor ≠ preparer stamped at compute | High in `people/governance/sod.py`. Not re-run this session |
| NR-PAY-03 | Commit requires status `validated`. Re-commit is illegal. No `unknown` outcome if the response is lost | Medium. Idempotent resubmit exists on WPS submit, not on payroll commit |
| NR-WPS-01 | WPS submit requires committed run, passed validation, distinct actor | High in `wps_submit_filing` |
| NR-LV-04 | Over-balance leave | **Conflict.** Do not encode as pass/fail until you rule |

Traceability target for NR-PAY-02:

| Link | Where |
|---|---|
| Requirement | ADR-0045 honesty matrix, payroll process YAML `refuse_if: preparer equals approver` |
| Invariant | `require_distinct_actor` raises `SoDViolation` |
| Implementation | `PayrollRunService.commit` |
| Test | `people/tests/test_host_sod.py` |
| Gate | Scoped `pytest people/tests/test_host_sod.py` on the pull request, after the pilot wires rule ids |
| Runtime signal | Not present. Pilot does not pretend an alert exists |
| Residual | Lost HTTP response after commit has no reconciliation key |

## 8. Gate layers

Every gate row in the catalogue has: purpose, packs, tool, pass/fail, environment, duration budget, owner, flake policy, exception expiry, enforcement mechanism, and behavior when the gate cannot run.

| Layer | Pilot behavior | Enforcement today |
|---|---|---|
| Local | Scoped pytest + `verify.sh` emit events | Configured. `verify.sh` default tests are `ai dq accounts`, not `people` |
| Pull request | Existing `.github/workflows/ci.yml` backend job | Configured. `pytest -x` stops at first failure and the log is `tail -40`. Python 3.11 / Postgres 17 vs local 3.12 / Postgres 16 in the docs |
| Merge | Required checks on `main` | **Unverified.** No ruleset was read |
| Release candidate | Tag `v*` already runs CI then SSH deploy | Deploy has a health curl. No provenance (SLSA v1.2 not applied) |
| Deploy verify | Health URL only | Configured in the workflow. Not a domain invariant |
| Runtime | Later | No consequence SLO catalogue |

When a critical gate cannot run, the release row stays `unknown`. Missing evidence is not a pass.

Exception record: approver, reason, compensating control, expiry date. Expired exceptions return the row to failing.

## 9. Domain extension order

1. **Nibras payroll** (this plan’s pilot).
2. Nibras leave, loan, onboarding, attendance, after NR-LV-04 is decided.
3. **Carbon footprint**, only after you freeze the methodology. Code today is an organizational inventory (`ReportingPeriod`, scopes, `GWP` with AR5 and AR6 fields, period lock). Current published basis to evaluate against: GHG Protocol Corporate Standard, Revised Edition 2004, plus Scope 2 Guidance (2015). Corporate Standard Version 3 is a draft (standard development plan dated 2026-07-29), not a requirement. Software tests do not establish assurance or certification. Computing-energy efficiency is out of scope unless you add it.
4. **EduOS** gold-pack validation (`validate_packs.py`, held-out JSON) on the same event schema.
5. Other brands reuse the platform pack only until they ship an assurance folder.

## 10. Rollout

| Phase | Outcome | Promotion |
|---|---|---|
| 0 | Discovery. Done as a read-only pass on 23 Sep 2026 | — |
| 1 | This plan + canvas. Then, after approval: pack schema, ledger, SSE, dashboard, NR-PAY-01..03 wired | Advisory. Existing `verify.sh` and CI stay as they are |
| 2 | Seeded defects: same-actor commit, unverified basic, double commit, broken people import. Record which gate caught each. Repair passes | A gate becomes blocking only after fault detection is demonstrated on that rule |
| 3 | Remaining Nibras journeys | Same promotion rule |
| 4 | Carbon inventory pack | Separate methodology sign-off |
| 5 | EduOS and other brands | Pack folder only |

Advisory mode does not delete or weaken a current check.

## 11. Success measures

Record baselines before claiming a change. None of these numbers exist yet:

- Seeded defects detected / seeded
- Escaped defects after the pilot
- Rules with a full trace / rules in the pack
- Flake rate and false-fail rate on the pilot gates
- Time from local run to row update
- Open exceptions and age of the oldest
- Recovery: lost-response drill, once designed

## 12. Files

**In the repo**

- `assurance/` — loader, evaluator, platform pack, `python -m assurance`
- `domain_packs/nibras/assurance/`, `domain_packs/carbon/assurance/`, `domain_packs/eduos/assurance/`
- `docs/assurance/ASSURANCE-WORKBOARD-PLAN.md` (this file)
- Canvas design board (not the product stream)

**Not written**

- `carbon-frontend` Assurance route and `GET /assurance/stream/`
- CI job change to emit the event artifact
- Fault-injection fixtures
- Binding a pytest run to ledger events

## 13. Still unresolved

1. Confirm J4 payroll as the first wired journey.
2. Pulse Chat/Agent in the pilot security rows, or host People only.
3. Named owner for PIFSS, Kuwait labor leave/EOSI, and WPS file format. Seeds are not that owner.
4. Ruling on NR-LV-04 (host 4xx versus YAML `ask_if`).
5. Carbon methodology freeze before Phase 4.
6. Whether Phase 1 may change GitHub branch protection, or local + design-only CI.
7. GitHub ruleset access so merge enforcement can leave **unverified**.
