# ADR 0051 — Excellence Ledger: one evidence store, many ladders

- **Status:** Accepted (human, 2026-09-24)
- **Date:** 2026-09-24
- **Deciders:** Owner (platform track) with Pulse Master; canvas `excellence-ladder-coverage-framework`
- **Area:** cross-cutting (backend core app · admin frontend · eval · docs)

## Context

Carbon measures completeness in four places that do not share a subject model, an evidence
schema, or a store: the Pulse gauge (`ai.eval.pulse_gauge`, ratchet + L0–L7), the Data Trust
Index (ADR-0039, weighted 0–100 per asset), Inventory Coverage (ADR-0020, declared denominator),
and the Assurance workboard (`core/assurance_api.py`, rule × evidence event × commit, file ledger).
Sixteen of seventeen backend apps have no gauge at all; no coverage tooling is configured; the
assurance stream reads a file and runs nothing. Status in `TASKS.md` is self-reported.

The owner wants completeness and quality of **software, business processes, features, data,
and artefacts** (`.ai-toolkit`, docs, plans) graded on a ladder, with a live admin dashboard per
tier and per domain app, triggers that run engineered collectors, production observation, and a
separate database.

## Decision

1. **One ledger, many ladders.** A core app `backend/excellence/` owns the schema, the evaluator,
   the collectors, the API, and the page templates. It does **not** own any ladder's content.
   `core/assurance_api.py` is absorbed by it (P1).
2. **Tier → track → subject.** A *tier* is a pack (platform, pulse, datatrust, nibras, carbon,
   eduos, tectona). A *track* is a product surface inside a tier with its own checks, owner and
   dashboard (Pulse: Chat · Agent/Plan · Memory · Packs · Ops; Nibras: People · My · Team ·
   Payroll · Correspondence; Data Trust: Catalog · DQ · MDM). A *subject* is the graded thing:
   `module`, `process`, `journey`, `dataset`, `artifact`, `ai_pack`. Subjects are **declared**
   in manifests, never inferred from the tree (the ADR-0020 denominator rule).
3. **Manifests live with their owner.** Platform and Pulse tiers: `assurance/<tier>/ladder.yaml`
   plus `assurance/<tier>/tracks/<track>.yaml`. Domain apps: `domain_packs/<id>/assurance/ladder.yaml`
   plus `tracks/`. Git is the SSOT; the DB mirrors the catalogue. Platform checks are inherited by
   every tier and cannot be lowered; a tier may only add ranks above them.
4. **Default level scale** (a pack may rename, not reorder): L0 Unmanaged · L1 Declared ·
   L2 Specified · L3 Built · L4 Proven · L5 Operated · L6 Excellent. A subject reaches level N only
   when every check with `rank ≤ N` passes (Soundcheck rule). **Overall level is the minimum
   across dimensions, never the mean.** Dimensions use ISO/IEC 25010:2023 vocabulary plus
   `governed`: `specified · correct · secure · reliable · performant · usable · maintainable ·
   observed · governed`.
5. **Evidence, not status.** The only writes are append-only `Event` rows:
   `{check_id, subject_id, tier, track, commit, result, evidence_class, source, runner, duration_ms, at, detail}`.
   `evidence_class ∈ {configured, executed, enforcement-verified, fault-demonstrated, unknown, conflict}`
   (kept from the assurance plan). Derived row state: no event on HEAD → catalogue class, never
   green; latest event commit ≠ HEAD → **stale**; skipped / `-x` truncation / docs "READY" without
   an event → **unknown**; `conflict` is not passable. Levels are computed on read and frozen only
   as dated `Snapshot` rows for trends (the `pulse_gauge` series pattern).
6. **Exemptions expire.** `Exemption {check_id, subject_id, reason, granted_by, until}`. An
   expired exemption renders red. Exempt is counted separately from pass.
7. **Separate database.** Django alias `excellence` (env `EXCELLENCE_DB_NAME`, default
   `carbon_excellence`) via `excellence.router.ExcellenceRouter`. One ledger across all brand
   databases. No foreign keys into brand tables; subjects are referenced by stable id plus commit
   hash. Same server, same credentials; not a second Postgres.
8. **Collectors wrap what exists.** `pytest` one app, `vitest` one spec, one Playwright journey,
   `verify.sh antipatterns`, `pulse_gauge --gate`, `pack_contract --gate`, trust-index rollup,
   inventory coverage, docs linker, git facts, CI facts, runtime probe. The test-partitioning
   directive in `TASKS.md` stands: collectors run **one app / one spec / one journey**, queued.
   Collectors shell out to the systems under test or read their outputs; they never import
   `people/`, `emissions/`, `gradevance/`, or `ai/engine`.
9. **Ratchet, not target.** `python -m excellence.gauge --gate` exits 1 when a subject's level
   regresses against the previous snapshot. Deploy gating on a level waits until pass rates are
   credible (P4).
10. **Dashboards are templates.** Seven pages (Ladder, Subject, Runs, Trends, Checks, Exemptions,
    Evidence) rendered per tier and per track under `/admin/excellence/<tier>/<track>`. Tier and
    platform pages are roll-ups with no formula of their own. Data Trust admin links to the module;
    the ledger does not live in `catalog/`.
11. **Never per person.** Subjects are modules, processes, journeys, data, artefacts. No developer
    or agent-session metric is ever a check.

## Alternatives Considered

- **Extend the Pulse gauge to every app** — rejected: its meters are engine-specific; Nibras and
  Data Trust would inherit AI vocabulary.
- **Extend the Data Trust Index to modules** — rejected: a weighted mean hides a missing dimension;
  the ladder needs minimum-across-dimensions and rank gating.
- **One flat platform ladder and one dashboard** — rejected by the owner: each tier and each track
  owns its checks and its view; the platform page is a roll-up.
- **Store a status column** — rejected: statuses get edited; events plus rule files are the only
  truth (assurance plan §4).
- **Second Postgres server** — rejected: an alias plus router isolates the data and lets the ledger
  be wiped or exported independently at no operational cost.
- **Coverage % as the KPI** — rejected (Goodhart). Direction and rank are gated, not a number.

## Consequences

- **Positive:** every module gets an honest L0–L2 on day one from manifests alone; the four gauges
  become event writers instead of files; a Nibras HR lead and the Pulse seat each see their own
  ladder; the production 429 of 2026-09-24 would have been a red `reliable` cell on the Pulse Ops
  track before a user saw it.
- **Negative / trade-off:** a new core app, a second DB alias, and YAML manifests to maintain; first
  levels must stay small (five checks at L1) or the board reads as an indictment; semi-annual check
  curation is now a duty.
- **Do NOT re-try:** a fifth formula; deriving subjects from the file tree; storing levels; permanent
  exemptions; full-suite runs from a dashboard button; scoring individuals; gating deploys before
  the ladder has bitten at least once (fault-demonstrated).

## Rollout

| Phase | Content | Exit |
|---|---|---|
| P0 Declare — **landed 2026-09-24** | `backend/excellence` (models, router, catalogue, evaluator, collectors `repo` / `antipatterns` / `pulse_gauge` / `pytest`), `excellence` DB alias, `assurance/platform/ladder.yaml`, `assurance/pulse/ladder.yaml` + 5 tracks, `python -m excellence.gauge` (`--collect --write --gate --no-db`), first snapshot: 19 subjects, 82 events, ratchet clean | levels on CLI, no UI |
| P1 Show — **landed 2026-09-24** | Ladder + subject pages; Rules tab absorbs `/admin/assurance` (redirect). Staff read API + SSE. | every module has a level and a next step |
| P2 Run — **landed 2026-09-24** | `Run` model; `POST /excellence/runs/` (repo / pulse_gauge / antipatterns; pytest one-app only); Measure button; exemptions grant/revoke with expiry | L3–L4 reachable from UI |
| P3 Observe — **landed 2026-09-24** | `observe` collector: CI files, runbooks, migrations, gauge-series freshness, evaluator fault self-check (`fault-demonstrated`); rank-5 Operated checks on platform.repo + modules + pulse.ops | L5 reachable when L4 already green |
| P4 Ratchet — **landed 2026-09-24** | `--changed [base]` gates only touched subjects; `verify.sh excellence`; CI step (migrate excellence DB, `pytest excellence`, changed ratchet); vitest one-file collector; UI Measure includes observe + recent runs | L6 possible once fault-demo + ratchet have bitten |
| Domain ladders — **landed 2026-09-24** | `domain_packs/nibras/assurance/ladder.yaml` + 5 tracks; `assurance/datatrust/`; `assurance/carbon/`; regulations owner; shell vitest check | every active product tier has a ladder |
| P5 Standard — **landed 2026-09-24** | `assurance/standard/standard.yaml`. Evaluator: an open cell, or a dimension with no checks, caps that dimension. Re-baseline `assurance/standard/baseline.yaml` date 2026-09-24. Ratchet ignores snapshots before that date. | levels are the weakest dimension, including empty ones |
| P6 Pulse bind — **landed 2026-09-24** | Pulse rank-1 cells for secure (ADR-0046), performant (budget ceiling), usable (Chat surface). Higher rungs: tests present, budget gate, shell vitest. | those three dimensions leave 0; the subject stays L0 until every dimension has a rank-1 pass |
| P7 Collectors — **landed 2026-09-24** | `rbac`, `budget`, `design_lint` (UI-safe) and `playwright` (one journey, `--run` only). Platform rank-1 checks inherited by every tier. | secure, performant, and usable are declared on every module, not only Pulse |
| P8 Domain rank 1 — **landed 2026-09-24** | Nibras, Data Trust, and Carbon each declare rank-1 checks for specified, correct, reliable, observed, and maintainable. Context console shows standard coverage (declared cells ÷ applicable cells). | each product tier has its own rank-1 ladder, not only the platform floor |
| P9 Runtime — **landed 2026-09-24** | Evidence below the rung floor does not count. Rank 5 needs a live loopback window (`runtime`: p95, error rate, 429 rate). A file check stays configured. | L5 means operated |

## References

- Canvas `excellence-ladder-coverage-framework.canvas.tsx` (audit + design)
- `docs/assurance/ASSURANCE-WORKBOARD-PLAN.md` (P0 input; evidence classes)
- ADR-0020 (declared denominator), ADR-0039 (DTI), ADR-0047/0049/0050 (Pulse gauge lineage)
- `backend/excellence/`, `assurance/platform/`, `assurance/pulse/`
- External: Spotify Soundcheck / Tech Insights, OpsLevel maturity, Cortex scorecards, Google SRE PRR,
  ISO/IEC 25010:2023, DORA 2025
