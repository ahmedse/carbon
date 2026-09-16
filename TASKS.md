# TASKS — Carbon Master Task List (ACTIVE)

**This is the SINGLE SOURCE OF TRUTH for outstanding work.** One worker task =
one phase entry = one Worker Role. No phase spans both backend and frontend.

> **History (DONE phases):** archived at
> [`docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md)
> (~12k lines). Do not re-copy DONE specs into this file.
>
> **Results history:** [`docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md`](docs/_archive/tasks-history/TASK-RESULTS-FULL-2026-09-16.md)
>
> **Sprint specs:** [`docs/_archive/sprints/`](docs/_archive/sprints/)

**Status legend:** `DONE` = verified + shipped · `READY` = spec complete, dispatchable · `PLANNED` = sequenced, spec pending · `PROPOSAL` = unratified, do not dispatch · `AUDIT` = code/ADR may already exist — confirm before dispatch.

**Phase-name uniqueness:** before adding a new phase id, grep **both** this file and the archive — phase IDs are never reused.

---

## MASTER DIRECTIVE — Test Partitioning (NON-NEGOTIABLE)

Full-suite `pytest` + `pytest-xdist -n auto` spawns parallel Postgres test DBs and
**hangs the dev laptop**. xdist flags are REMOVED from `backend/pytest.ini` and MUST
NOT be re-added. Every worker MUST follow:

- **Backend:** one app at a time, never full suite:
  `python -m pytest <app> -q --maxfail=5 --disable-warnings -p no:cacheprovider`
  (e.g. `pytest ai -q`, `pytest catalog -q`, `pytest integrations -q`).
  Max 2 apps in one invocation, and only the changed app + direct dependents.
- **Frontend:** one spec file at a time, never whole suite:
  `npx vitest run src/__tests__/<file>.test.jsx`; build **once per phase**
  (`npm run build`), not per file.
- **E2E:** only when a journey changed, one spec at a time (`npx playwright test e2e/journeys/<file>`).
- **NEVER:** `pytest` with no args · `-n auto`/`--dist loadscope`/xdist · `npx vitest run` with no path.
- Stale-test-DB cleanup (only if `test_carbon*` DBs linger): see `.ai-toolkit/shared/testing.md` RULE 7.

**Frontend completion is PROVEN, not claimed:** a frontend phase is `DONE` only
when `npm run lint` + a targeted `vitest` + `npm run build` all pass. No build/test
evidence → not done.

---

## Active focus (2026-09)

| Track | Status | Notes |
|-------|--------|-------|
| **PEC** (Pulse Enterprise Control-plane, P1–P7) | **ACTIVE — DISPATCHED** | Close metabolism/measurement gaps vs enterprise bar. Specs below §PEC. Leverage: 1→4→2→3→ID→5→6→7 |
| **ECF** (Entity Capability Framework, ADR-0032) | ACTIVE | Specs below — parallel track; do not steal PEC P0 workers |
| **OF-15…OF-20** (e-Office expansion) | OPEN | Leave-only vertical is live; expand types + workflow graph |
| **NIR-5/6/7** | AUDIT | ADRs 0027/0028/0029 accepted — likely shipped; confirm Status before re-dispatch |
| **NIR-3C** payroll orchestration | PLANNED | Keep until verified DONE |
| Historical Pulse 0.2/0.3 waves | DONE | See archive only |

---

## PEC — Pulse Enterprise Control-plane (DISPATCHED 2026-09-16)

**Canonical plan:** `docs/pulse/PULSE-ROADMAP.md` · **SSOT:** `docs/pulse/PULSE-CANONICAL.md`  
**Gap map:** Cursor canvas `pulse-enterprise-control-plane.canvas.tsx`  
**Principle:** freeze the spine (boundary/PDP/Flight Director); ship metabolism + measurement.  
**Contracts:** `shared/ai-contract.md`, `security.md`, `api-contract.md`, `testing.md`, `definition-of-done.md`  
**Test partitioning:** MASTER DIRECTIVE above — never full-suite pytest / never bare vitest.

**Wave map (dispatch order):**
| Wave | Phases | Parallel? |
|------|--------|-----------|
| **W1** | PEC-1A, PEC-4A, PEC-7A | YES — non-overlapping files |
| **W2** | PEC-2A, PEC-3A, PEC-3B | After W1 green (3B needs Screen Spec pointer below) |
| **W3** | PEC-ID-1, PEC-5A, PEC-5B, PEC-6A, PEC-6B | After W2; 6B needs Screen Spec |
| **Gate** | Master reviews TASK-RESULTS; mark DoD rows in PULSE-ROADMAP |

---

### Phase PEC-1A — DevOps+Backend: Heartbeat metabolism proof (P1)
**Date:** 2026-09-16  
**Worker Role:** devops-worker (primary) + backend-worker (health surface only if missing)  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** —  
**Roadmap:** P1 Heartbeat

#### Context
Code already exists: `run_pulse_maintenance`, `PulseHeartbeat`, `deploy/instance/setup-pulse-heartbeat.sh`, compose `scheduler` / `learning-scheduler`, tests in `ai/tests/test_pulse_heartbeat.py`. Canonical still marks F5 open because **unattended nibras evidence + health “last heartbeat”** is not proven. This phase closes P1 with **runtime evidence**, not a rewrite.

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P1
- `backend/ai/management/commands/run_pulse_maintenance.py`
- `backend/ai/models/heartbeat.py`
- `deploy/instance/setup-pulse-heartbeat.sh`
- `docker-compose.yml` (scheduler services)
- `backend/ai/sweeps_api.py` (existing heartbeat read path)

#### Implementation
1. Confirm compose schedulers actually invoke `run_pulse_maintenance` (or equivalent) with `DJANGO_BRAND` / instance isolation. Fix command wiring if wrong.
2. Ensure a **health/read API** already exposes last heartbeat per `(instance, loop)` — extend `sweeps_api` or `healthy` only if missing; do not invent a second API.
3. Produce acceptance evidence pack under `docs/pulse/evidence/PEC-1A-heartbeat.md`:
   - command output of a real maintenance run for `nibras` (or local brand)
   - SQL/ORM dump of new `PulseHeartbeat` rows (proactive, consolidation, distill, decay)
   - health endpoint JSON showing last tick
4. If VPS systemd is out of scope for this machine, document exact `setup-pulse-heartbeat.sh nibras` steps as the deploy handoff and prove via compose timer/cron equivalent locally.

#### DO NOT TOUCH
- `backend/ai/engine/` cognition loop internals
- PDP / command_boundary
- Frontend

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python manage.py run_pulse_maintenance --dry-run 2>&1 | tee /tmp/pec1a-dry.txt
# Then a real run (brand=nibras if available):
DJANGO_BRAND=nibras ../.venv/bin/python manage.py run_pulse_maintenance 2>&1 | tee /tmp/pec1a-run.txt
../.venv/bin/python -m pytest ai/tests/test_pulse_heartbeat.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
# Evidence file must exist and cite row ids / timestamps.
test -f ../docs/pulse/evidence/PEC-1A-heartbeat.md
```

#### Handoff
Write `TASK-RESULTS.md` section `## PEC-1A` with terminal proof + evidence path.

---

### Phase PEC-4A — Backend: Eval harness baseline + merge gate (P4)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** — (parallel with PEC-1A)  
**Roadmap:** P4 Evaluation Harness

#### Context
`backend/ai/eval/` has fixtures, `golden_hrms.py`, replay, checks. Canonical: “measurably = not yet.” Need ≥20 golden scenarios for nibras, metrics (grounding-pass, deny-correctness, fabrication-rate=0, latency, tokens), and a **CI-invokable** entrypoint that fails on fabrication or deny regression.

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P4
- `backend/ai/eval/*`
- `backend/ai/tests/redteam/` (pattern for fail-closed)
- `.github/workflows/` (existing CI)

#### Implementation
1. Author/expand golden scenarios to **≥20** nibras cases covering: net-pay grounding, cross-employee deny, payroll lifecycle consent, ambiguous→clarify, compound Q-1 if feasible, topic_guard out-of-scope.
2. Add `backend/ai/eval/run_harness.py` (or pytest marker `eval_golden`) that prints pass-rate + metrics JSON.
3. Wire CI job or document exact `pytest` invocation in workflow that already runs AI tests — prefer extend existing workflow, do not create duplicate full-suite jobs.
4. Add one deliberate negative test proving fabrication/deny regression would fail the harness.
5. Evidence: `docs/pulse/evidence/PEC-4A-eval-baseline.md` with first measured baseline numbers (do not invent targets).

#### DO NOT TOUCH
- Production prompt text in `instance.yaml` except if a scenario requires a fixture override
- Frontend
- Heartbeat code (PEC-1A owns it)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/eval ai/tests/redteam -q --maxfail=8 --disable-warnings
# Harness must print metrics; fabrication_rate must be 0.
./.ai-toolkit/scripts/verify.sh backend
test -f ../docs/pulse/evidence/PEC-4A-eval-baseline.md
```

---

### Phase PEC-7A — Backend: Convergence — remove inert F1a/F3 paths (P7 partial)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** —  
**Roadmap:** P7 (F1a/F3 decision already: REMOVE/DEFER — fold guidance into instance.yaml)

#### Context
Canonical §12: `instance.yaml` is the single prompt-config mechanism. Filesystem `domain_packs/*/skills` guidance is inert (F1a). `PlaybookBlock` empty → unused A/B (F3). Anti-drift L6: delete or defer; do not invest.

#### Files to Read First
- `docs/pulse/PULSE-CANONICAL.md` §5, §9 F1a/F3, §12
- Grep: `guidance_skills`, `PlaybookBlock`, `build_chat_prompt`

#### Implementation
1. Confirm no live path injects `guidance_skills` from filesystem packs.
2. Remove dead call sites / loader hooks **or** mark clearly deferred with a single `# DEFERRED(F1a)` and a verify.sh antipattern that fails if someone re-wires without ADR — prefer **delete dead imports** if unused outside tests.
3. For `PlaybookBlock`: if zero rows and unused in hot path, add module docstring + skip/xfail only if tests assert empty; **do not** seed fake A/B. Prefer deleting unreachable A/B selection code if truly dead (ask Master via TASK-RESULTS if ambiguous — then leave `# DEFERRED(F3)` with ADR stub).
4. Add startup or verify check notes in evidence file.
5. Evidence: `docs/pulse/evidence/PEC-7A-convergence.md` listing deleted symbols + grep proof.

#### DO NOT TOUCH
- `instance.yaml` persona content (except typos)
- Live ProcessDefinition / Capability seed paths
- Frontend

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon && \
  rg -n "guidance_skills=" backend/ai/engine/cognition/turn/runner.py || true
cd backend && ../.venv/bin/python -m pytest ai/tests/test_provider_pulse.py ai/tests/test_adapter.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh antipatterns
test -f ../docs/pulse/evidence/PEC-7A-convergence.md
```

---

### Phase PEC-2A — Backend: Prove learning-reuse OR cut (P2)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** PEC-1A (heartbeat drives consolidation)  
**Roadmap:** P2

#### Context
SkillAwarePlanner + flywheel + gate-only promotion exist; live reuse never observed. Need reuse counter + ledger citation **or** documented cut (L6).

#### Files to Read First
- `docs/pulse/PULSE-ROADMAP.md` §P2
- `backend/ai/feedback/skill_flywheel.py`
- `backend/ai/engine/skills/*`, planner skill preference
- `backend/ai/engine/cognition/plan/`

#### Implementation
1. Add/confirm per-skill `usage_count` (or equivalent) increments when a promoted skill drives a plan/turn; write ledger/telemetry row.
2. Write an integration test that: draft→admit/promote fixture skill → later plan matches → counter +1.
3. If the arc cannot fire on a realistic HRMS scenario after honest attempt: write `docs/pulse/evidence/PEC-2A-CUT.md` with Master decision request to remove the path — **do not leave half-dead code**.
4. Evidence: `docs/pulse/evidence/PEC-2A-reuse.md` with counter before/after.

#### DO NOT TOUCH
- Auto-promote without gate
- Frontend Console promote UI (PEC-6*)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_learning_trigger.py ai/tests/test_flight_learning.py -q --maxfail=5 --disable-warnings
# Plus any new reuse test file created in this phase
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-3A — Backend: Proactive delivery path proof (P3 backend)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** PEC-1A  
**Roadmap:** P3

#### Context
Delivery persists `KgProactiveInsight` + SSE exists; scheduled generation tied to heartbeat. Prove one insight reaches the API/SSE contract with provenance fields (RULE_23).

#### Files to Read First
- `backend/ai/engine/proactive/*`
- insights API / SSE surfaces
- `docs/pulse/PULSE-UX.md` rubric (outcomes-only copy)

#### Implementation
1. Trace proactive → persist → list/stream endpoints; fix gaps.
2. Test: after maintenance/proactive loop (mocked OK), insight visible via API with honest confidence + no engine jargon.
3. Evidence: `docs/pulse/evidence/PEC-3A-proactive-api.md`

#### DO NOT TOUCH
- Frontend notification chrome (PEC-3B)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "proactive or insight" -q --maxfail=8 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-3B — Frontend: Proactive insight surfaces in Nibras UI (P3 UI)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** PEC-3A  
**Screen Spec:** reuse `docs/pulse/PULSE-UX.md` + `PULSE-UX-DESIGN.md` (4-beat story, provenance, dismiss/act). No new full Screen Spec doc required if those cover the panel — attach deviations in TASK-RESULTS.

#### Implementation
1. Wire notification/insights panel to consume SSE/API from PEC-3A.
2. Dismiss + act affordances; RULE_23 copy.
3. Targeted vitest + lint + build.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend && npm run lint && npx vitest run src/__tests__/*insight* src/__tests__/*notif* 2>/dev/null || npx vitest run src/__tests__/ -t "insight|proactive|notif" ; npm run build
```

---

### Phase PEC-ID-1 — Backend: Identity propagation hardening
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** — (can start W3)  
**Contracts:** `shared/security.md`

#### Context
`engine_runtime` passes `user_token=f"inproc:{instance_id}:{host_user_id}"`. Enterprise bar (IBM): propagate/exchange, never substitute. Before MCP egress expands, introduce a **short-lived scoped host credential** (or documented actor-chain on `PolicyDecisionRow`) so every boundary hop attributes user→agent→tool.

#### Implementation
1. ADR in `.ai-toolkit/decisions/` (Master will ratify — draft ADR-00xx-pulse-identity-propagation.md).
2. Implement minimal: persist actor_chain on policy/audit rows for host effects; keep inproc token but include stable `user_id` + `instance_id` + `request_id` in all PDP decisions.
3. Tests for attribution presence; no behavior change to CBAC denies.

#### DO NOT TOUCH
- External IdP / OAuth exchange (out of scope — ADR only marks Phase 2)

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_tenancy_isolation.py ai/tests/pilot/test_pilot_e2e.py -q --maxfail=5 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-5A — Backend: GOSI/WPS governed ProcessDefinitions (P5 slice)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** —  
**Roadmap:** P5

#### Implementation
1. Add `domain_packs/nibras/processes/` YAMLs for GOSI/WPS SIF generation lifecycle with `human_only` on irreversible submit; `refuse_if`/`ask_if`/`kill_switch`.
2. Register capabilities in `api_catalog.yaml` + `capability_registry.py` as needed.
3. Extend `seed_nibras_processes.py` idempotently; tests mirror payroll/leave/loan process tests.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_nibras_payroll_process.py ai/tests/test_nibras_leave_process.py ai/tests/test_nibras_loan_process.py -q --maxfail=5 --disable-warnings
# Plus new gosi/wps tests
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-5B — Backend: Onboarding governed process (P5 slice)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** PEC-5A patterns  

Same pattern as PEC-5A for employee onboarding lifecycle. Evidence + seed + tests.

---

### Phase PEC-6A — Backend: Admin skill promote/reject decision API (P6)
**Date:** 2026-09-16  
**Worker Role:** backend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** —  

#### Context
Admission gate is system-side; Console needs an **admin decision endpoint** that runs gate (or records reject) under CBAC `ai:publisher` / `ai:process_owner`. No bypass of `_authority` token.

#### Implementation
1. POST endpoints: promote (calls gate `_promote_skill` / `admit_skill` path) and reject (sets deprecated/rejected with reason).
2. CBAC-gated; audit log row.
3. Tests: non-admin 403; admin promote increments promoted; forged path still gate-only.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/ -k "skill and (promot or admit or gate)" -q --maxfail=8 --disable-warnings
./.ai-toolkit/scripts/verify.sh backend
```

---

### Phase PEC-6B — Frontend: Console promote/reject + Capabilities registry view (P6 UI)
**Date:** 2026-09-16  
**Worker Role:** frontend-worker  
**Recommended Model:** DeepSeek V4.1-Flash  
**Status:** READY  
**Depends on:** PEC-6A  
**Screen Spec:** extend existing Console shell patterns in `AIWorkspace` Processes/Skills tabs; follow `shared/frontend-ready.md` minimally (states: loading/empty/error/success; CBAC lock). Reuse `SkillsPanel` — add actions, do not duplicate.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/carbon-frontend && npm run lint && npm run build
# targeted vitest for SkillsPanel / Console if present
```

---

## End PEC track specs


---

## Nibras / People — open or audit-needed (summaries)

## Phase NIR-3C — Backend: Payroll-run orchestration service

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED

### Objective
Build the orchestration service that drives `PayrollRun` through
`draft → compute → validate → commit` (and `failed`), composing the NIR-3B engine functions and
gating `commit` on validation. Establishes the **measurement provenance seam** (ADR 0025): every
measurement-derived figure carries its source `dataschema.DataRow` id / `row_hash`.

### Files to Read First
- `backend/people/models.py` (`PayrollRun`, `PayslipLine`, `Employee`, `Loan`, `LoanInstallment`, `AttendanceRecord`, `LeaveRecord`)
- `backend/people/calculation_engine.py` (NIR-3B outputs)
- `backend/emissions/models.py` (`Calculation.create_from_data_row` — the source-row provenance pattern)
- `docs/NIBRAS-MASTER-STRATEGY.md` §8.2 (pipeline)

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5A — Backend: People governed-lookup migration (FK to ReferenceValue, drop code strings)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` (§3 Bucket 1, §4, §6) + ADR-0027

### Objective
Replace every Bucket-1 metadata field in `people` with a real `ForeignKey` to
`mdm.ReferenceValue`, removing the free-text/soft-code duplicates and the string
mirrors. This is the **models + migration** phase only (serializers/views in
NIR-5B).

### Files
- `backend/people/models.py` — the only model file edited.
- New migration `backend/people/migrations/XXXX_governed_lookup_fks.py`.


> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5B — Backend: Governed value resolution (serializers/views/seeds/DQ)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** NIR-5A
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §4 + ADR-0027

### Objective
Build the single shared value-resolution seam and wire every Bucket-1 field
through it; update seed commands to the new FK shape.

### Files
- `backend/mdm/serializers.py` — add `GovernedValueField` (or `GovernedValueSerializer`): read → `{ id, code, label, set }`; write accepts `id` **or** `code`, resolves to `ReferenceValue` within the declared `set_name`, validates current-ness, emits `ValidationError` otherwise.
- `backend/people/serializers.py` — replace `_validate_reference_code` usage: each Bucket-1 field uses the `GovernedValueField` with its `set_name`. Update `EmployeeSerializer`/`PositionSerializer`/`BenefitTypeSerializer`/`ComplianceRuleSerializer` and any serializer for the other 8 models that expose a Bucket-1 field.
- `backend/people/management/commands/seed_gofsco.py` — update seeded employees/positions/benefits to write the FK (by code, resolved through the same helper), not string codes.
- `backend/people/views.py` — add `select_related('*_value__reference_set')` (or a `prefetch`) on list/detail querysets so read joins are cheap.

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5C — Backend: Seed the 7 new reference sets (admin data)

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** NIR-5A (sets can be seeded in parallel with 5B)
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §3 Bucket 1

### Objective
Seed the seven ReferenceSets that do **not** yet exist, so the NIR-5A FKs can be
satisfied. RULE_16: this is **admin data**, entered via a management command
(the sanctioned admin-entry path), never created by serializer code.

### New sets + initial values (canonical codes)
| Set `name` | `slug` | Initial codes |
|---|---|---|
| `grade` | `grade` | `G1`…`G10` (job grades) |

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-5D — Frontend: People pages render nested governed values + dropdowns source reference sets

**Date:** 2026-08-30
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED
**Depends on:** NIR-5B
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §4 + TASKS.md NIR-4A patterns

### Objective
Adapt the People pages to the FK-only read shape and source create/edit dropdowns
from the governed reference sets (via the MDM reference-value API), not hardcoded
option lists.

### Scope (pointer — expand at dispatch)
- `carbon-frontend/src/api/people.js` + new `api/referenceData.js` (fetch values
  for a set: `mdm/reference-values/?reference_set=<name>` or the existing
  `mdm/reference-sets/` surface).

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-6A — Backend: Single-root OrgUnit invariant + instance-gated seeds

**Date:** 2026-08-30
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §2 (ADR-0028) + §6

### Objective
Enforce "one deployment = one root `OrgUnit`" and stop the AASTMT↔GOFSCO tree
mingling at the seed layer.

### Files
- `backend/mdm/models.py` — add `clean()` to `OrgUnit`: a unit with `parent=None`
  is only allowed when no other active `parent=None` root exists for the
  deployment (block creating a second root; allow re-parent of a stale root).
  Emit a `ValidationError` on violation. (Keep idempotent seed re-runs working.)
- `backend/mdm/views.py` — `OrgUnitViewSet.get_queryset()` defaults to the

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-6B — Frontend: Org-unit dropdown scoped to deployment root

**Date:** 2026-08-30
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED
**Depends on:** NIR-6A
**Canonical spec:** `docs/DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md` §2 (ADR-0028)

### Objective
`fetchOrgUnits` (and every org-unit dropdown/tree in People + Carbon) renders only
the deployment's own root subtree, shown as a tree (not a flat global list).

### Scope (pointer — expand at dispatch)
- `carbon-frontend/src/api/orgUnits.js` — default to the root-subtree endpoint
  (e.g. `mdm/org-units/?root=1` or `/tree/`) and return a nested structure.
- `PositionsPage.jsx`, `PayrollRunsPage.jsx` — replace the flat `orgUnits.map(...)`
  `MenuItem` list with a nested/indented tree (group by `full_path` or

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-7A — Backend: Compensation ledger remediation (service, authz, migration, admin, tests)

**Date:** 2026-09-02
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** (none — remediates unphased compensation work)
**Canonical spec:** `ADR-0029` (`.ai-toolkit/decisions/0029-compensation-ledger.md`)

### Objective
Repair the compensation ledger to the toolkit contracts: business logic out of the
view into a service, correct write authorization, `basic_salary`→ledger data
migration, admin registration, and test coverage. No API shape change.

### Scope
1. **New service** `backend/people/compensation_service.py` — `CompensationService`
   with:
   - `current_lines(employee, as_of=None)` → QuerySet of open/effective rows.

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).

## Phase NIR-7B — Frontend: Compensation pay tab remediation (SystemDialog, tokens, i18n)

**Date:** 2026-09-02
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** NIR-7A (API envelope is unchanged; can proceed in parallel)
**Canonical spec:** `ADR-0029` + `.ai-toolkit/roles/shared/compact-ui.md`,
`.ai-toolkit/roles/shared/design-system.md`

### Objective
Rewrite `carbon-frontend/src/apps/people/tabs/EmployeePayTab.jsx` to comply with
compact-ui/design-system and i18n contracts. No behavior regression.

### Scope
1. **SystemDialog, not Drawer** — replace the raw MUI `Drawer` `AddCompLineDrawer`
   with the existing `SystemDialog` component (`src/components/SystemDialog.jsx`),
   matching sibling pages (`EmployeesPage`, `BenefitsPage`).

> Full spec archived: `docs/_archive/tasks-history/TASKS-FULL-2026-09-16.md` (search phase id).


---

# e-Office Correspondence Expansion — OF-15 … OF-20 (requests journey + workflow graph)

> **Driver:** the e-Office correspondence engine is generic and fully wired for the
> *state machine* (draft → submitted → sent_back/rejected/approved, multi-step
> `approver_chain`, per-event timeline), but only **`leave_request`** has a create
> path today (`POST /people/me/leave/` → `people/self_views.py`). The other five
> governed types (`loan_request`, `profile_change`, `internal_memo`, `circular`,
> `decision`) are seeded `ReferenceValue`s with no submit endpoint or UI. The
> "workflow graph" is currently a **vertical stepper** (`ApproverChainStepper`)
> — not a DAG. HR can see the 6-tab employee 360 but has **no Requests tab** and
> **no endpoint to list one employee's correspondence** (the `correspondence`
> list is self-scoped to `requester=request.user`).
>
> **Canonical layering (NON-NEGOTIABLE):** `correspondence` NEVER imports `people`;
> `people` reaches the engine only via `correspondence.fsm`/`services`/`models`.
> Governed enums stay `mdm.ReferenceValue` FKs. Every transition emits a
> `CorrespondenceEvent` + `emit_governance_event`.
>
> **Dependency order (do NOT reorder):** OF-15 → OF-16 (backend, can run in
> parallel) → OF-17 (needs OF-15) · OF-18 (independent, needs neither) ·
> OF-19 (needs OF-16) → OF-20 (QA, last). One phase = one worker session, one domain.

| Phase | Goal | Domain | Deps | Status |
|-------|------|--------|------|--------|
| OF-15 | Generic submit endpoint + subject adapters for the 5 remaining types + acknowledge/review transitions | backend | OF-14 | DONE |
| OF-16 | HR/admin correspondence scoping (list by employee/org/type) + correspondence notifications API (list + mark-read) | backend | — | DONE
| OF-17 | "New Request" multi-type composer + extend MyRequests/RequestDetail | frontend | OF-15 | DONE |
| OF-18 | Workflow DAG graph component + stepper↔graph toggle | frontend | — | DONE |
| OF-19 | HR 360 "Requests" tab in EmployeeDetailPage (view all of an employee's correspondence) | frontend | OF-16 | DONE |
| OF-20 | QA validation (4-layer) of the expanded e-office | qa | OF-17,18,19 | DONE |

---

### Phase OF-15 — Backend: generic submit + subject adapters + acknowledge/review transitions
**Role:** backend-worker · **Depends on:** OF-14 · **Model:** DeepSeek V4-Flash

#### Problem
Only `leave_request` is creatable. The engine already supports `subject=None`
(`submit_correspondence` skips the DQ gate) and the router already maps
`manager`/`hr`/`finance`/`specific_user`/`any_admin` roles. Three gaps:
(1) no generic create for payload-only types, (2) the `intent` field allows
`acknowledge`/`review` but `fsm` has no transition for them (an `internal_memo`
should be *acknowledged*, not "approved"), (3) the `finance` role resolves to
`[]` in `routing.py` (auto-skip) — a loan policy with a finance step would be
silently dropped, which is a thin/broken behaviour, not a real workflow.

#### Change
1. **Generic create endpoint (payload-only types)** — `backend/correspondence/views.py`:
   `POST correspondence/` (a `create` action on the ViewSet, gated by
   `correspondence:submit`). Accepts `{corr_type, title, payload, org_unit}` →
   creates a `Correspondence` with `subject_type=''`, `subject_id=None`,
   `requester=request.user`, `status='draft'`, then
   `fsm.submit_correspondence(corr, by=user, subject=None)`. Reuse the
   `CorrespondenceDetailSerializer` for the 201. Map the same engine exceptions
   (`SubmissionBlocked`→400, `PolicyNotFound`→400, `InvalidTransition`→409) via
   the existing `_transition`-style helper or an explicit try/except.
2. **`acknowledge` + `review` transitions** — `backend/correspondence/fsm.py`:
   add `acknowledge(corr, by, comment)` that marks the current step
   `decision='acknowledged'` and advances (mirrors `approve` but emits
   `event_type='acknowledged'`, no "approved" semantics), and `review(...)`
   (`decision='reviewed'`). Add a generic `act(corr, by, intent, comment)`
   dispatcher so `views.py` needs one action route, not three. Extend
   `correspondence/urls.py` with `POST correspondence/{id}/acknowledge/`.
3. **Subject adapters (typed types stay in `people`)** — `backend/people/`:
   - `POST /people/me/loan/` (loan_request): create `people.Loan` + `Correspondence`
     (`subject_type='people.Loan'`), submit via fsm. **`Loan.STATUS_CHOICES` is
     `active/paid_off/cancelled` — add `'draft'` (migration) and create the Loan in
     `draft` status (mirrors `LeaveRecord.status='draft'`).** Validate
     principal/interest_rate/term_months/start_date/loan_type before submission.
   - `POST /people/me/profile-change/` (profile_change): no new model — create a
     `Correspondence` with `subject_type='people.Employee'`, `subject_id=profile.pk`,
     `payload` = `{field: {from, to}, …}`; the HR approver applies the diff on approve.
   Keep `leave_request` untouched (already works). Memo/circular/decision use the
   generic OF-15.1 endpoint (no subject).
4. **Seed default policies for the 5 new types** — extend
   `backend/correspondence/management/commands/seed_correspondence.py`: add a
   `WorkflowPolicy` per new `corr_type` (default single step): `internal_memo`
   → `any_admin`/`acknowledge`, `circular` → `any_admin`/`acknowledge`,
   `decision` → `manager`/`approve`, `loan_request` → `manager` then `finance`
   (two steps), `profile_change` → `hr`/`approve`. Idempotent (`update_or_create`).
5. **Finance approver resolution (fix `finance` → `[]` auto-skip)** — resolve the
   finance step to a REAL pool, not an empty list:
   - `backend/accounts/capabilities.py`: add `CORRESPONDENCE_FINANCE` (key
     `correspondence:finance`, domain `correspondence`, action `finance`,
     category `admin`) to the capability registry + `ALL_CAPABILITIES`; add
     `finance_group` to `GROUP_CAPABILITIES` mapping `{correspondence:finance,
     correspondence:submit, my:access}`.
   - `backend/accounts/constants.py`: add `FINANCE_GROUP = "finance_group"` (wire
     into `GROUP_BRAND_SCOPE`/`PROTECTED_GROUPS` exactly as the other people groups
     are), then `backend/accounts/management/commands/bootstrap_platform.py`: add a
     `finance_group` `GROUP_DEFS` entry so it is created on bootstrap.
   - `backend/correspondence/routing.py`: `role == 'finance'` →
     `_users_with_capability('correspondence:finance')` (delete the `[]` literal).
   - Update `backend/accounts/tests/test_capability_rbac_extensive.py` expected-
     groups assertion to include `finance_group`.
   - Seed one finance approver in `seed_correspondence.py` (assign an existing
     employee user to `finance_group` via `ScopedRole`), so the live loan
     workflow has a real finance approver.

#### Files to Change
- `backend/correspondence/views.py` (+ `create`, `acknowledge` actions)
- `backend/correspondence/fsm.py` (+ `acknowledge`/`review`/`act`)
- `backend/correspondence/urls.py` (+ `acknowledge` route)
- `backend/correspondence/routing.py` (finance → `correspondence:finance`)
- `backend/accounts/capabilities.py` (+ `CORRESPONDENCE_FINANCE`, `finance_group`)
- `backend/accounts/constants.py` (+ `FINANCE_GROUP`)
- `backend/accounts/management/commands/bootstrap_platform.py` (+ finance group def)
- `backend/accounts/tests/test_capability_rbac_extensive.py` (expected groups)
- `backend/people/models.py` (+ `'draft'` in `Loan.STATUS_CHOICES`) + migration
- `backend/people/self_views.py` (+ `LoanSelfCollectionView`, `ProfileChangeSelfView`)
- `backend/people/urls.py` / `self_urls.py` (+ routes)
- `backend/correspondence/management/commands/seed_correspondence.py` (+ 5 policies + finance approver)
- `backend/correspondence/tests/test_api.py`, `test_fsm.py`, `backend/people/tests/` (new tests)

#### DO NOT TOUCH
- Frontend · `correspondence` importing `people` (never) · leave journey (regression).

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```
Report: `correspondence` + `people` suites green; new tests cover generic submit,
acknowledge/review transitions, loan/profile-change subject creation, AND finance
routing (finance step resolves to a real approver, never auto-skips); `makemigrations
--check` confirms the Loan draft-status migration is applied; no migrations drift.

---

### Phase OF-16 — Backend: HR/admin scoping + correspondence notifications API
**Role:** backend-worker · **Depends on:** — (independent; runs parallel to OF-15) · **Model:** DeepSeek V4-Flash

#### Problem
(1) The `correspondence` list is self-scoped — HR (`people:manage` /
`correspondence:admin`) cannot list an employee's requests to answer "what is
pending for this person?". (2) `fsm.notify()` writes
`correspondence.models.Notification` rows but there is **no API** to read them —
managers/requesters never see "action needed" / "status changed" in-app.

#### Change
1. **Employee-scoped correspondence list (HR)** — `backend/people/views.py`: add
   `GET /people/employees/{id}/correspondence/` (permission `PeopleAccess`), returns
   the employee's correspondence (`requester__employee_profile` OR `subject_id`
   match) via `CorrespondenceSerializer`, paginated. `people` importing
   `correspondence.serializers` is allowed (one-way).
2. **Widen the admin list filter** — `backend/correspondence/views.py`: when the
   caller holds `correspondence:admin`, allow `?requester=`, `?employee=`,
   `?org_unit=`, `?corr_type=`, `?status=` on `GET correspondence/` (non-admin
   stays self-scoped). Add a `correspondence:admin` object check.
3. **Notifications API** — `backend/correspondence/views.py` + `urls.py`: add
   `GET correspondence/notifications/` (self-scoped, `is_read` filter, unread
   count) and `POST correspondence/notifications/{id}/read/` +
   `POST correspondence/notifications/read-all/`. Serializer for
   `correspondence.models.Notification` (id, title, body, type, is_read,
   correspondence reference_no, created_at).

#### Files to Change
- `backend/people/views.py` + `urls.py` (+ employee correspondence list)
- `backend/correspondence/views.py` + `urls.py` (+ admin filters, notification actions)
- `backend/correspondence/serializers.py` (+ `NotificationSerializer`)
- `backend/correspondence/tests/test_api.py`, `backend/people/tests/` (new tests)

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
Report: HR can list an employee's correspondence; admin filters work; notifications list/read/read-all return correct unread counts; non-admin list stays self-scoped.

---

### Phase OF-17 — Frontend: "New Request" multi-type composer + richer request list
**Role:** frontend-worker · **Depends on:** OF-15 · **Model:** DeepSeek V4-Flash

#### Objective
Let an employee submit **any** governed type (not just leave) from `/my`, and
render non-leave payloads correctly in the request list/detail.

#### Deliverables
1. `src/apps/my/components/NewRequestDialog.jsx` — type selector
   (leave/memo/circular/decision/loan/profile-change) driving a dynamic form;
   routes to the right API: leave → `POST people/me/leave/`, loan →
   `POST people/me/loan/`, profile-change → `POST people/me/profile-change/`,
   memo/circular/decision → `POST correspondence/` (generic). Show approver-chain
   preview + confirm. i18n EN/AR.
2. `src/api/my.js` — add `submitLoanRequest`, `submitProfileChange`,
   `submitGenericCorrespondence`; keep `apiFetch` only.
3. `src/apps/my/MyRequests.jsx` + `components/RequestTable.jsx` — render
   non-leave payloads (memo title/body, circular, decision, loan amount, profile
   change field diffs) as a small payload summary instead of leave dates. The
   `corr_type` filter chips already exist — verify they show all 6 types.
4. `src/apps/my/MyDashboard.jsx` — add a "New Request" quick action next to
   "Request Leave".

#### Screen Spec (RULE_29 — required before code)
**Story:** As an employee, I want to submit any request type (leave, loan, memo,
circular, decision, profile change) from one place, so I don't have to learn six
different forms. **Acceptance:** given type X → form X shows only X's fields; submit
→ 201 + success toast + list refreshes; invalid input → inline field errors; no
policy for type → clear message; non-employee → 403 handled.
**Journey:** `/my` → "New Request" → choose type → fill form → review approver
preview → submit → success → `/my/requests`.
**Composition:** `SystemDialog` (NOT raw Dialog) wrapping a type `<Select>` + a
`RequestFormSwitch` (per-type field sets) + `ApproverChainPreview`; submit button
`disabled` while `submitting`. Reuse `RequestTable`/`SummaryCard` for list/detail.
**State Matrix:** page `idle/loading/empty/error/loaded`; dialog `open/closed`;
submit `idle/submitting/error/success`; type selector `default/selected`.
**Data Contract:** `GET /carbon-api/correspondence/` (self list, `corr_type`/
`status` filters); `POST /carbon-api/people/me/leave/`, `/people/me/loan/`,
`/people/me/profile-change/`, `POST /carbon-api/correspondence/` (generic) → 201 |
400 field errors | 403. **A11y:** focus trap in dialog, `aria-live` on submit error,
labels on all inputs. **Performance:** lazy-load dialog, memoize type→field map,
debounce not needed (no search). **i18n/RTL:** every label via `t()`, keys in BOTH
`en` + `ar`; type names in Arabic.

#### Files to Change
- `src/apps/my/components/NewRequestDialog.jsx` (new)
- `src/api/my.js`
- `src/apps/my/MyRequests.jsx`, `components/RequestTable.jsx`, `MyDashboard.jsx`
- `src/i18n/locales/{en,ar}/my.json`

#### DO NOT TOUCH
- Backend · `src/apps/team/**` · raw fetch · inline hex/sx.

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: submit a memo (generic) and a loan, both appear in My Requests with correct type labels.

---

### Phase OF-18 — Frontend: Workflow DAG graph + stepper↔graph toggle
**Role:** frontend-worker · **Depends on:** — (approver_chain already in detail response)

#### Objective
Replace the *only-vertical-stepper* view with an optional **node-edge workflow
graph** so the approval path is visualized as a DAG (steps as nodes colored by
decision: pending/current/approved/rejected/skipped; edges = flow). Keep the
stepper as the default and add a toggle.

#### Deliverables
1. `src/apps/my/components/WorkflowGraph.jsx` (new) — pure presentational DAG
   from `approver_chain` (`order, role, intent, decision, user_ids, comment,
   decided_at`) + `current_step`. Horizontal/SVG layout (or reuse
   `components/graph/` primitives). Color = status, NOT color-only (label each
   node with role/intent/decision text). RTL-safe.
2. Add a Stepper ↔ Graph toggle to `src/apps/my/components/RequestDetail.jsx` and
   `src/apps/team/TeamRequestDetail.jsx` (reuse `WorkflowGraph`). Default = stepper.
3. i18n: `workflowGraph` / `workflowStepper` toggle labels + node legend.

#### Screen Spec (RULE_29 — required before code)
**Story:** As an employee or manager, I want to see the approval path as a graph,
so I understand who is next and where it stalled. **Acceptance:** graph renders
one node per `approver_chain` step + a terminal node; node shows role/intent/decision
as TEXT (never color alone); `current_step` node highlighted; condition-skipped/
auto-approve steps visibly distinct from approved/rejected; empty chain → graph
empty state; RTL mirrors arrow direction.
**Composition:** `WorkflowGraph` = SVG/Styled nodes + edges built from
`approver_chain[]` + `current_step`; a `ToggleButtonGroup` (Stepper | Graph) in
`RequestDetail` + `TeamRequestDetail`. Reuse `components/graph/` primitives if they
exist — else one new presentational component (no data fetching inside).
**State Matrix:** node `pending/current/approved/rejected/acknowledged/reviewed/
skipped(auto|condition)/sent_back`; graph container `loading/empty/loaded` (reuses
detail's fetched data — no separate fetch).
**Data Contract:** consumed from the already-fetched `CorrespondenceDetailSerializer`
(`approver_chain` = `[{order, role, intent, decision, decided_by, decided_at,
comment, user_ids, auto_approve, can_skip, skip_if_self, skipped}]`, `current_step`
int, `status` str). No new endpoint. **A11y:** nodes are buttons/`tabIndex=0` with
`aria-label` (`role + intent + decision`); legend is text-based; not color-only.
**Performance:** pure function of props, `React.memo`, no effects, SVG is light
(< 50 nodes). **i18n/RTL:** legend + toggle labels via `t()` in BOTH catalogs; RTL
flips edge direction.

#### Files to Change
- `src/apps/my/components/WorkflowGraph.jsx` (new)
- `src/apps/my/components/RequestDetail.jsx`, `src/apps/team/TeamRequestDetail.jsx`
- `src/i18n/locales/{en,ar}/{my,team}.json`

#### DO NOT TOUCH
- Backend · AI `PlanDagGraph` (unrelated) · raw fetch · inline hex/sx.

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: open an approved request, toggle graph → nodes show approved/rejected/skipped correctly.

---

### Phase OF-19 — Frontend: HR 360 "Requests" tab (view all of an employee)
**Role:** frontend-worker · **Depends on:** OF-16 · **Model:** DeepSeek V4-Flash

#### Objective
HR staff (holding `people:view`/`people:manage`) can open an employee's 360 and
see **all their correspondence** (leave, loans, memos, …) in a new "Requests" tab,
drill into each, and see the full timeline/chain — closing "HR can view all about
an employee".

#### Deliverables
1. `src/apps/people/tabs/EmployeeRequestsTab.jsx` (new) — `GET
   people/employees/{id}/correspondence/`; table (reference, type, title, status,
   created, resolved) + row → detail dialog/drawer (reuse `SummaryCard` +
   `ApproverChainStepper`/`WorkflowGraph` + `RequestTimeline` from `apps/my/`).
2. `src/api/people.js` — add `fetchEmployeeCorrespondence(id)`.
3. `src/apps/people/EmployeeDetailPage.jsx` — register the `Requests` tab in
   `TAB_KEYS`/`TAB_COMPONENTS` (only render for users with `people:view`).
4. i18n EN/AR for the new tab.

#### Screen Spec (RULE_29 — required before code)
**Story:** As HR, I want to see every request an employee has made (leave, loan,
memo, …) in one tab, so I can answer "what is pending for this person?".
**Acceptance:** tab lists all correspondence for the employee (reference, type,
title, status, created, resolved); filter by status/type; click a row → detail
(timeline + chain/graph); empty → "no requests yet"; 403 (no `people:view`) → tab
hidden; loading → skeleton.
**Composition:** `EmployeeRequestsTab` (inside `BaseDetailPage` tab) = `PageHeader`
(mini) + `StandardDataGrid`/table (paginated) + detail `Dialog` reusing
`SummaryCard` + `ApproverChainStepper`/`WorkflowGraph` + `RequestTimeline` from
`apps/my/`. Register in `TAB_KEYS`/`TAB_COMPONENTS`; gate on `people:view` capability.
**State Matrix:** `idle/loading/loading-empty/empty/loaded/partial/error/forbidden`;
row `selected`; detail dialog `open/closed`; filter `default/active`.
**Data Contract:** `GET /carbon-api/people/employees/{id}/correspondence/` →
paginated `CorrespondenceSerializer` (`count/results`); 403 = hidden tab; 404 =
unknown employee. **A11y:** table has row headers + focus-visible; dialog
focus-trap; status = badge + label. **Performance:** paginate >50 rows; lazy-load
detail dialog; memoize filter map. **i18n/RTL:** tab + column headers + status
labels via `t()` in BOTH catalogs.

#### Files to Change
- `src/apps/people/tabs/EmployeeRequestsTab.jsx` (new)
- `src/api/people.js`
- `src/apps/people/EmployeeDetailPage.jsx`
- `src/i18n/locales/{en,ar}/people.json`

#### Verification Gate (Master runs — paste output)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
node scripts/check-i18n-keys.js
npm run lint
npm run build
```
Report: i18n parity green; lint 0; build clean; smoke: HR opens employee → Requests tab lists their correspondence; drill-in shows timeline.

---

### Phase OF-20 — QA validation (4-layer) of the expanded e-office
**Role:** qa-validator · **Depends on:** OF-15…OF-19 · **Model:** DeepSeek V4-Flash

#### Context
Verify the expanded e-office end-to-end; no new features. Report deficiencies with file:line + repro.

#### Layers
1. **Static/contract:** grep for `GenericForeignKey`/`ContentType` in
   `correspondence/`, hardcoded governed enums, `raw fetch(` in `src/apps/my/` +
   `src/apps/team/`, naive `datetime.now()`, `print()` debug.
2. **Unit:** one app at a time — `correspondence`, `people`, `accounts/tests/test_correspondence_caps.py`.
3. **API integration:** DRF test client walk — submit memo (generic) → inbox →
   acknowledge; submit loan → manager approve → finance approve; submit
   profile-change → hr approve; HR lists employee correspondence; notifications
   read/read-all. Confirm `correspondence` never imports `people`.
4. **Frontend build + smoke:** `npm run build` + `check-i18n-keys.js`; Playwright
   smoke of `/my` new request + `/team` + HR 360 Requests tab.

#### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest correspondence people -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest accounts/tests/test_correspondence_caps.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
```
Report: 4-layer pass/fail matrix + deficiencies with file:line + repro.

---

# Leave Policy Registry — LPR series
# Trigger: Nibras HR — the flat "one row per leave type" config tab in
# PeopleConfigPage is not a real registry. Replace with a named, lifecycle-managed,
# applicability-scoped policy registry + detail 360 + propagation + versioning.
# Full spec: tasks/TASK-LPR-POLICY-REGISTRY.md

## Phase LPR-1A — Backend: LeavePolicy registry model + API
**Role:** backend-worker · **Depends on:** OF-14 (leave_type → ReferenceValue FK) · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0021 applied, 182 people tests pass incl. 5 new LPR-1A tests)

### Objective
Evolve `LeavePolicy` from a one-row-per-leave-type config table into a named,
lifecycle-managed, applicability-scoped registry. Non-destructive migration
backfills existing rows. Add `employee_count` annotation + a basic `propagate`
action so the LPR-1B registry grid has real data to display.

### Files to Read First
- `backend/people/models.py` — `LeavePolicy` (~296), `Employee` (~76), `LeaveEntitlement` (~365)
- `backend/people/serializers.py` — `LeavePolicySerializer` (~222)
- `backend/people/views.py` — `LeavePolicyListCreateView` (~732) + `LeavePolicyDetailView` (~741)
- `backend/people/urls.py` — `leave-policies/` routes (~84-86)

### What to Build
1. **Model — add to `LeavePolicy`** (all null/blank-safe, non-breaking):
   - `name` `CharField(max_length=200, blank=True)` — human-readable policy name (primary identity).
   - `description` `TextField(blank=True)`.
   - `status` `CharField(choices=[('draft','Draft'),('active','Active'),('deprecated','Deprecated')], default='active')`.
   - `effective_from` `DateField(null=True, blank=True)`.
   - `effective_to` `DateField(null=True, blank=True)`.
   - `applies_to_org_units` `M2M('mdm.OrgUnit', blank=True, related_name='+')` — empty = all org units.
   - `applies_to_contract_types` `JSONField(default=list, blank=True)` — list of contract_type codes; empty = all.
   - Keep `is_active` (transition compat) but document `status` as the lifecycle source.
   - `__str__` → `f"{self.name} ({self.leave_type.code})"`.
2. **Migration** `0021_leave_policy_registry` (schema + data): backfill
   `name = leave_type.code`, `status = 'active' if is_active else 'deprecated'`.
3. **Serializer** — add the new fields; add read-only `employee_count`
   (`IntegerField`), annotated in the view = distinct employees with a
   `LeaveEntitlement` matching the policy's `leave_type` in the current year.
   Keep `leave_type_label`.
4. **View** — `LeavePolicyListCreateView.get_queryset()` annotates `employee_count`.
   Add `propagate` action on `LeavePolicyDetailView`:
   `POST /leave-policies/<id>/propagate/` (body `{ year }`, default current year;
   query `?dry_run=true` → returns `{ eligible, will_create, skipped }` without writing).
   Eligible = active employees matching `gender_restriction`, `min_service_days`,
   `applies_to_org_units`, `applies_to_contract_types`.
5. **URL** — `path('leave-policies/<int:pk>/propagate/', ...)` registered BEFORE `<int:pk>/`.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py` (other master WIP).
- `LeaveEntitlement` schema — policy↔employee stays indirect via `leave_type` for LPR-1 (proper `policy` FK is LPR-2).
- `backend/people/management/commands/seed_gofsco.py` (other master WIP).

### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider
```
Report: model diff, migration file name, test output, and a sample list showing `employee_count`.

---

## Phase LPR-1B — Frontend: Policy Registry grid + Policy Detail 360
**Role:** frontend-worker · **Depends on:** LPR-1A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n 2965 keys parity ✓, PeoplePages vitest 7/7 ✓)

### Objective
Replace the flat LeavePolicy tab in `PeopleConfigPage` with a dedicated registry
(`/people/policies`) + a 360 detail page (`/people/policies/:id`), matching the
LPR-1A backend contract.

### Files to Read First
- `carbon-frontend/src/apps/people/PeopleConfigPage.jsx` (LeavePolicy tab to REMOVE)
- `carbon-frontend/src/apps/people/manifest.js` (`navigation.items`)
- `carbon-frontend/src/api/people.js` (`fetchLeavePolicies` + CRUD)
- `carbon-frontend/src/App.jsx` (people routes ~300-311)
- `carbon-frontend/src/shell/Breadcrumbs.jsx` (`/people/config` mapping ~461)
- `carbon-frontend/src/i18n/locales/en/people.json` + `ar/people.json`

### What to Build
1. **Routes** — lazy imports + routes for `/people/policies` (PoliciesPage) and
   `/people/policies/:id` (PolicyDetailPage). Add Breadcrumbs mappings.
2. **`PoliciesPage.jsx`** — FilterBar (leave_type select, status select, search),
   PolicyGrid (name, leave_type badge, status chip, default days, `employee_count`,
   `effective_from`, actions), "New Policy" CTA → create dialog.
   apiFetch-only (RULE_10), FONT theme tokens only (RULE_8).
3. **`PolicyDetailPage.jsx`** — PageHeader + 6 tabs (General / Entitlement /
   Carryover / Eligibility / Workflow / Employees); tab index persisted to
   `localStorage` (RULE_17). Reuse `BaseDetailPage` pattern.
4. **`api/people.js`** — add `propagateLeavePolicy(id, { year, dry_run }, token)`.
5. **Remove** the LeavePolicy tab from `PeopleConfigPage` (TAB_KEYS, form, grid,
   policy state, imports) — keep Overview/Reference/Compliance intact.
6. **`manifest.js`** — add `{ label: 'Policies', path: '/people/policies', role: '*' }`
   under the Configuration group.
7. **i18n** — add `people.json` keys (en + ar) for all new labels.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## Phase LPR-2A — Backend: propagation service + entitlement `policy` FK + scheduler
**Role:** backend-worker · **Depends on:** LPR-1A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0022 applied, 187 people tests pass incl. 5 new service tests)

### Objective
Make propagation production-grade and auditable: give each `LeaveEntitlement` a
nullable `policy` provenance link, extract the inline propagate logic from the view
into a reusable service (DRF-free), and add a year-start management command.

### Files to Read First
- `backend/people/models.py` — `LeaveEntitlement` (~365), `LeavePolicy` (~296)
- `backend/people/views.py` — `LeavePolicyPropagateView` (~807, inline logic to extract)
- `backend/people/serializers.py` — `LeaveEntitlementSerializer`
- `backend/people/services.py` — facade pattern (NO DRF imports)
- `backend/people/management/commands/link_employee_users.py` — command style

### What to Build
1. **Model** — add to `LeaveEntitlement`:
   `policy = models.ForeignKey('LeavePolicy', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`.
   Migration `0022_leaveentitlement_policy`. Non-breaking (nullable).
2. **Service** — new `backend/people/leave_policy_service.py` (DRF-free, no `rest_framework`/`Response`):
   - `propagate_policy(policy, year=None, *, dry_run=False) -> dict` — move the eligibility filter + preview/create logic out of the view. On create, set `policy=policy` in `defaults` (record provenance). Never overwrite an existing entitlement's `entitled_days` or `policy`.
   - `propagate_all_active(year=None, *, dry_run=False) -> dict` — iterate active policies, aggregate `{ eligible, will_create, will_update, skipped, created, updated, per_policy: [...] }`.
3. **Serializer** — add read-only `policy` (id) and `policy_name` to `LeaveEntitlementSerializer` so provenance is visible in the API.
4. **View** — `LeavePolicyPropagateView.post` becomes a thin wrapper calling `propagate_policy(policy, year, dry_run=dry_run)`; identical response shape as LPR-1A.
5. **Management command** — `backend/people/management/commands/propagate_leave_policies.py`:
   `--year` (default current), `--policy-id` (optional single), `--dry-run`. Calls `propagate_all_active`. Document cron usage in the docstring. Idempotent.
6. **Tests** — `backend/people/tests/test_leave_policy_service.py` (or extend the registry test): service dry_run + create sets `policy` FK; propagate_all_active aggregates; command `--dry-run` runs without error; existing entitlement not overwritten.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py`
- Any frontend file.

### Verification Gate (Worker runs + reports output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider --create-db
```

---

## Phase LPR-2B — Frontend: batch propagation + entitlement provenance
**Role:** frontend-worker · **Depends on:** LPR-2A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n parity ✓ 3038 keys, vitest 7/7)

### Objective
Surface the new propagation engine in the UI: batch "Propagate All Active" on the
registry page, and show policy provenance on per-employee entitlements.

### Batch API decision (from LPR-2A — CONFIRMED)
LPR-2A added **NO batch HTTP endpoint**. The only HTTP surface is the per-policy
`POST /people/leave-policies/<id>/propagate/` (body `{"year": <int>}`, query
`?dry_run=true`). `propagate_all_active` is callable ONLY via the management
command. So the frontend "Propagate All Active" button MUST loop per active policy:
1. `fetchLeavePolicies()` → filter `status === 'active'` (and legacy
   `!status && is_active`).
2. For each, `POST /people/leave-policies/<id>/propagate/` (the existing
   `propagateLeavePolicy(id, payload, token)` helper from LPR-1B).
3. Aggregate the returned `{eligible, will_create, will_update, skipped}` counts
   and show a single summary (Snackbar). No new backend needed.

### What to Build
1. `PoliciesPage.jsx` — add a "Propagate All Active" toolbar button. On click,
   loop active policies through the existing `propagateLeavePolicy` helper
   (per the batch decision above), aggregate counts, and show a summary Snackbar
   (e.g. "Propagated N policies: M entitlements created"). Disable during the run.
2. `EmployeeLeaveTab.jsx` / `EmployeeDetailPage.jsx` — display the entitlement's
   `policy_name` where the balance/entitlement rows are rendered (the serializer
   already returns read-only `policy` + `policy_name` from LPR-2A).
3. `api/people.js` — add any small helpers if needed (likely none beyond the
   existing `propagateLeavePolicy`; the "all" loop lives in the page).
4. i18n keys (en + ar) for new labels.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## Phase LPR-3A — Backend: policy versioning (snapshot + fork semantics)
**Role:** backend-worker · **Depends on:** LPR-2A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (migration 0023 applied, 193 people tests pass incl. 6 new versioning tests; fixed latent `policy`/`policy_version` IntegerField→source=_id serializer bug)

### Objective
Make policy edits auditable and non-destructive. Today a `PATCH /leave-policies/<id>/`
mutates the live `LeavePolicy` in place with no history, so entitlements can never
say *exactly* which configuration created them. Introduce a version ledger: each
configuration change is a new `LeavePolicyVersion` snapshot, and every entitlement
records both the `policy` (the live object) and the precise `policy_version` that
created it. Effective-date transitions are derived from the version chain.

### Files to Read First
- `backend/people/models.py` — `LeavePolicy` (~296), `LeaveEntitlement` (~405, has `policy` FK)
- `backend/people/leave_policy_service.py` — DRF-free service pattern (RULE_3) — extend, do NOT duplicate
- `backend/people/serializers.py` — `LeavePolicySerializer` (~226), `LeaveEntitlementSerializer` (~201)
- `backend/people/views.py` — `LeavePolicyListCreateView`/`LeavePolicyDetailView`/`LeavePolicyPropagateView` (~807)
- `backend/people/urls.py` — leave-policies routes (~88)
- `backend/people/management/commands/propagate_leave_policies.py` — command style

### What to Build

#### 1. Model — new `LeavePolicyVersion` (in `people/models.py`)
```python
class LeavePolicyVersion(models.Model):
    policy = models.ForeignKey(LeavePolicy, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)   # full field capture at fork time
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('policy', 'version_number')
        ordering = ['policy', '-version_number']
        verbose_name = 'Leave Policy Version'
        verbose_name_plural = 'Leave Policy Versions'
```
- Add to `LeaveEntitlement`: `policy_version = FK('LeavePolicyVersion', null=True, blank=True, on_delete=SET_NULL, related_name='+')` (provenance at version granularity; nullable for legacy/manual rows). Migration `0023_leave_policy_versioning` (CreateModel + AddField + a RunPython backfill: for each existing entitlement with a `policy`, create version 1 from the current policy snapshot and link it — idempotent).

#### 2. Service — extend `leave_policy_service.py` (DRF-free, no `rest_framework`)
- `snapshot_policy(policy) -> dict` — serialize the policy's configurable fields (leave_type code, default_entitled_days, max_carryover_days, is_carryover_allowed, accrual_method, gender_restriction, requires_approval, min_service_days, name, description, status, applies_to_contract_types, applies_to_org_units ids) into a JSON-safe dict.
- `fork_policy(policy, *, effective_from=None, change_summary='', user=None) -> LeavePolicyVersion`:
  1. Determine `next_version = (existing max version_number) + 1` (or 1).
  2. `effective_from` defaults to `timezone.localdate()`.
  3. Close the previous version: set its `effective_to = effective_from - 1 day` (only if it was open-ended).
  4. Create the new version with `snapshot = snapshot_policy(policy)` and `version_number = next_version`.
  5. **Do NOT mutate the live `LeavePolicy` fields** (versioning records the snapshot; the live row remains the current config). Optionally align `LeavePolicy.effective_from/effective_to` to the newest version's window — your choice, but document it.
  6. Return the new version.
- `get_version_history(policy) -> list[LeavePolicyVersion]` — ordered ascending by `version_number`.
- `latest_version(policy) -> LeavePolicyVersion | None`.

#### 3. Serializer
- New `LeavePolicyVersionSerializer` — fields: `id`, `policy`, `version_number`, `effective_from`, `effective_to`, `change_summary`, `created_by`, `created_at`, `snapshot` (read-only except `change_summary`).
- `LeavePolicySerializer` — add read-only `latest_version` (int, the newest version_number or null) and `version_count` (int).
- `LeaveEntitlementSerializer` — add read-only `policy_version` (int, nullable) + `policy_version_number` (SerializerMethodField → `obj.policy_version.version_number if obj.policy_version_id else None`).

#### 4. Views + URLs (thin, service-backed)
- `LeavePolicyVersionListView` (`GET` list + `POST` fork) at `leave-policies/<int:pk>/versions/`:
  - `GET` → `{ count, results: [...] }` from `get_version_history`.
  - `POST` → body `{ change_summary, effective_from? }` → calls `fork_policy(policy, user=request.user, ...)` → 201 with the new version. Requires PeopleAccess (write gate via existing `_GatedDetailView` pattern or explicit admin check — match `LeavePolicyPropagateView`'s permission style).
- `LeavePolicyVersionDetailView` (`GET` only) at `leave-policies/<int:pk>/versions/<int:version_pk>/`.
- Wire both into `backend/people/urls.py` next to the existing leave-policies routes.

#### 5. Tests — new `backend/people/tests/test_leave_policy_versioning.py`
Follow the fixture style in `test_leave_policy_service.py`. Cover:
- (a) `snapshot_policy` captures configurable fields and is JSON-safe.
- (b) `fork_policy` first version → `version_number == 1`, `effective_from` set, previous version (none) unaffected.
- (c) `fork_policy` second fork → `version_number == 2`, and closes the prior open-ended version's `effective_to`.
- (d) `get_version_history` returns ascending order; `latest_version` returns version 2.
- (e) migration backfill: existing entitlement with `policy` gets `policy_version` linked to version 1 (simulate by asserting the FK is non-null after backfill — or, if hard to test in isolation, assert `LeaveEntitlement.policy_version` is writable and round-trips through the serializer).
- (f) `GET /leave-policies/<id>/versions/` returns history; `POST` creates version 2.

### DO NOT TOUCH
- `backend/correspondence/*`, `backend/ai/*`, `backend/accounts/*`, `backend/config/settings.py`
- Any frontend file.

### Verification Gate (run + report literal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations people --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate people
/home/ahmed/aast/carbon/.venv/bin/python -m pytest people -q --maxfail=5 --disable-warnings -p no:cacheprovider --create-db
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
```
NOTE: `--create-db` is required (new model/field + `--reuse-db --nomigrations` in pytest.ini).

---

## Phase LPR-3B — Frontend: version-history panel
**Role:** frontend-worker · **Depends on:** LPR-3A · **Model:** DeepSeek V4-Flash
**Status:** DONE — verified 2026-09-06 (build ✓, i18n parity ✓ 3075 keys, vitest 7/7)

### Objective
Surface the version ledger in the policy 360: a "Versions" tab showing the full
history, plus a "New Version" fork action that captures a change summary.

### What to Build
1. `PolicyDetailPage.jsx` — add a 7th tab `Versions` to `TAB_KEYS` (persist via the
   existing localStorage key). Render a timeline/table of versions: version number,
   effective_from → effective_to, change_summary, created_by, created_at. Show the
   `snapshot` fields in an expandable/details view (a Dialog or accordion).
2. "New Version" button in the Versions tab → opens a Dialog with a `change_summary`
   field (and optional effective_from date) → calls the fork endpoint → refreshes history.
3. `api/people.js` — add `fetchLeavePolicyVersions(policyId, token)` + `forkLeavePolicy(policyId, payload, token)`.
4. i18n keys (en + ar) for all new labels (version, version history, new version, change summary, effective from/to, etc.).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run build && node scripts/check-i18n-keys.js
npx vitest run src/__tests__/PeoplePages.test.jsx
```

---

## PULSE UNIFIED REMEDIATION PLAN — Phase 2 (Boundaries)

> Canonical spec: `docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md` (Gate 2).
> Tracked here for worker dispatch. Master runs all verification (workers have no terminal).

| ID | Task | Status |
|----|------|--------|
| P2-04 | import-boundary-lint enforcing | DONE |
| P2-05 | Single ORM (SQLAlchemy removed, Django canonical) | DONE — 1738 tests green, sqlalchemy uninstalled |
| P2-06a | Command Boundary core (`command_boundary.py`, 13 stages) | DONE |
| P2-07 | PDP v1 (`pdp.py`, default-deny) | DONE |
| P2-06b | Route `call_host_api` through the boundary | DONE — 1746 tests green, import-boundary-lint clean |
| P2-06c | Route worker fan-out through the boundary | DONE — 1746 tests green, import-boundary-lint clean |
| P2-08 | Domain-pack extraction (forbidden-term grep = 0) | **DONE — source neutralized, `forbidden-term-lint` EXIT 0; handoff issued to Phase 3 master** |
| P2-06e | Route proactive delivery through the boundary | **DONE — `execute_delivery_via_boundary` seam + PDP `deliver` permit; 4 tests green** |
| P2-06d | Route ReAct loop through the boundary | **DONE — `execute_step_via_boundary` seam + fail-closed `_tool_requires_confirmation`; consent gate = boundary outcome; 1772 tests green, 3 lints clean** |
| P2-06f | Route `ops_workflow` host REST through the boundary | **DONE — `_host_effect` seam helper routes 7 host REST calls; 1769 tests green, 3 lints clean** |
| P2-11 | Toolkit gates (`verify.sh intelligence` + `audit-imports` + `audit-routes`) | **DONE — `verify.sh intelligence` (import-linter + fail-open + forbidden-term + vulture-report + replay smoke) wired into CI; `audit-imports`/`audit-routes` fail on seeded violation** |
| — | `PULSE-MASTER.md` §boundary reconciled | **DONE — §2 documents the "one door" CommandBoundary routing (4 seams + PDP default-deny), wired to `verify.sh intelligence`/`audit-imports`/`audit-routes`** |

---

## P2-08 — Domain-pack extraction (DONE — source extraction/neutralization complete)

> Canonical: plan row P2-08a–g. Acceptance: **forbidden-term grep over `engine/**` = 0 per file**.
> Engine becomes domain-agnostic; Carbon-specific vocabulary/constants move to `domain_packs/carbon/`,
> loaded via a `DomainPack` port. **One PR per source (a–g).** Foundation (F) is a prerequisite.

> **STATUS: DONE (Master-verified 2026-09-13).** All domain vocabulary neutralized across
> `engine/**` (14 files). `forbidden-term-lint.py` EXIT 0, `import-boundary-lint.py` EXIT 0,
> `manage.py check` EXIT 0, full `ai` suite 1762 passed. See TASK-RESULTS.md "P2-08 source
> extraction/neutralization".

### Foundation (F) — `DomainPack` port + pack skeleton + forbidden-term lint
> **STATUS: DONE** (Master-verified 2026-09-13). `domain.py` parses, `import-boundary-lint`
> clean, zero forbidden terms in the new port files, loader loads the carbon pack + neutral fallback works.

- **CREATE `backend/ai/engine/ports/domain.py`** — `DomainPack` Protocol with accessors:
  `vocabulary() -> dict`, `api_catalog() -> dict`, `processes() -> list`, `skills() -> list`,
  `triggers() -> dict`, `prompts() -> dict`; plus a module-level `get_domain_pack()`
  loader that resolves the pack by instance/brand (default `"carbon"`) from `domain_packs/`,
  with a **neutral generic fallback** (empty collections + safe defaults) when no pack is loaded —
  the engine must boot and behave identically pack-less. Loader lives in the engine (ports read
  only); it MUST NOT import Django. YAML parsing via stdlib-only fallback if PyYAML absent.
- **CREATE `domain_packs/carbon/`** skeleton: `vocabulary.yaml`, `api_catalog.yaml`,
  `processes/`, `skills/`, `triggers.yaml`, `prompts/`. Each YAML schema is defined here so the
  seven source PRs have a fixed contract.
- **CREATE `.ai-toolkit/scripts/forbidden-term-lint.py` + `forbidden-terms.txt`** — scans
  `backend/ai/engine/**` for the domain terms listed in `forbidden-terms.txt`; allowlist keyed by
  `relpath:lineno` (same convention as `import-boundary-lint.py`). Exits 1 on any non-allowlisted
  hit, prints `Forbidden domain term: clean (engine is domain-agnostic)` on 0. This is the P2-08
  acceptance gate and feeds P2-11's `verify.sh intelligence`.

### Source PRs (one per file; forbidden-term grep must return 0 for that file)
| PR | File | Extract | Into |
|----|------|---------|------|
| a | `engine/cognition/turn/intent.py` | campus names ("South Valley","Smart Village","Abu Qir","Alamein"), `list_emission_factors`, "emission factors", GHG terms ("GHG Protocol","carbon","footprint") | `vocabulary.yaml` |
| b | `engine/cognition/plan/loop.py` | `_allow` set (`create_dq_rule`,`search_knowledge`,`get_entity_details`,`list_my_capabilities`,`plan_task`) | `api_catalog.yaml` (tool allow-list) |
| c | `engine/cognition/plan/planner.py` | supplier/module/category analysis-dimension phrases (`_MULTI_SIGNALS`) | `vocabulary.yaml` |
| d | `engine/cognition/turn/execute.py` | `"carbon_api"` source-type default + `source_map` | `api_catalog.yaml` |
| e | `engine/proactive/delivery.py` | `"carbon"` brand fallback (`app_identifier`) + channel routes | `vocabulary.yaml` / `api_catalog.yaml` |
| f | `engine/proactive/insight_generator.py` | power-domain example metric defaults (`unit_metrics`/`heat_rate`/`demand_forecasts`/`demand_actuals`/`value_mw`, `threshold_pct` 2.0/8.0, "Unit 2 Heat Rate") | `triggers.yaml` |
| g | `engine/core/config.py` | DQ/Carbon constants (`TASK_DQ_VALIDATE_TIMEOUT=10`,`TASK_DQ_SUGGEST_TIMEOUT=60`,`PULSE_CARBON_CONTEXT_ENABLED`) + "Carbon expects …" comments | `api_catalog.yaml` / `vocabulary.yaml` |

**Additional files surfaced by the lint baseline (77 hits / 16 files)** — each needs a PR too,
mostly brand-in-docstring/comments or prompt-string vocabulary. Fold into the fan-out after a–g:
`engine/__init__.py` (brand docstring), `engine/agent/plugins.py` (`create_dq_rule`),
`engine/agent/tools.py` (`footprint`/`emission factors`), `engine/cognition/turn/draft.py`
(`create_dq_rule`), `engine/cognition/turn/runner.py` (`Carbon`/`GHG`/`list_emission_factors`/
`emission factors`/`PULSE_CARBON_CONTEXT_ENABLED`/`create_dq_rule`), `engine/core/event_bus.py`
(brand docstring), `engine/knowledge_graph/store.py` (brand docstring), `engine/llm/playbook.py`
(`carbon`), `engine/llm/prompts.py` (`emission factors`/`list_emission_factors`),
`engine/memory/_redis.py` (brand docstring), `engine/proactive/trigger_evaluator.py`
(`unit_metrics` example). Prompt strings → `domain_packs/carbon/prompts/`; docstrings/comments →
neutralize in place (no data path, no port needed).

**Rules for every source PR:**
- Engine file must read via the `DomainPack` port; keep a **generic neutral fallback** so behavior
  is unchanged when no pack loads (existing fixtures must stay green).
- `import-boundary-lint` stays clean (no new `ai.` host imports; the port is `engine.ports`).
- Do NOT touch other source files — one PR = one file. Cross-cutting schema decisions go in the
  Foundation worker's PR only.

### Forbidden terms (initial `forbidden-terms.txt`, refined by Foundation worker)
`carbon`, `Carbon`, `GHG`, `GHG Protocol`, `footprint`, `emission factors`, `list_emission_factors`,
`carbon_api`, `Alamein`, `South Valley`, `Smart Village`, `Abu Qir`, `Nibras`, `unit_metrics`,
`heat_rate`, `demand_forecasts`, `demand_actuals`, `value_mw`, `Unit 2 Heat Rate`, `TASK_DQ_`,
`PULSE_CARBON_CONTEXT_ENABLED`, `create_dq_rule`. (Words like `carbon` must be word-boundary
matched so `carbon_copy`-style identifiers and generic prose don't false-positive — final list is
the Foundation worker's responsibility, reviewed by Master before dispatch of a–g.)


---

## Pulse command-boundary leftovers (audit)

## Phase P2-06b — Route `call_host_api` through the command boundary
**Role:** backend-worker · **Model:** DeepSeek V4-Flash · **Depends on:** P2-06a, P2-07 (both DONE)

> **STATUS: DONE** (Master-verified). Architectural correction applied by Master:
> the engine tool must NOT import host modules (`ai.command_boundary`,
> `ai.command_boundary_factory`, `ai.protocol`) — that violates RULE_20 / P2-04
> and `command_boundary.py`'s own "MUST NOT be imported by `ai.engine/`" contract.
> Final shape: `execute_call_host_api` delegates its resolved host-effect closure
> to `executor.execute_host_api_via_boundary(...)`; `CarbonHostExecutor` (host) is
> what actually builds the `Command` and calls `CommandBoundary.execute()`.

### Objective
Wire the production `CommandBoundary` (P2-06a) with real dependencies and route the
`call_host_api` tool (`backend/ai/engine/agent/tools.py::execute_call_host_api`) through it,
replacing its ad-hoc `requires_confirmation`/`create_pending_execution` gate with the
13-stage fail-closed boundary. Preserve the user-visible staging flow (mutations still
return `requires_confirmation` + `execution_id`).

### Files
- CREATE `backend/ai/command_boundary_factory.py` — `get_command_boundary(db, *, executor=None, ...)` wiring the real `PDP`, `DjangoLedgerAdapter`, tool catalog (registered tool names), identity resolver, params validator, budget checker.
- EDIT `backend/ai/pdp.py` — add a permit `Policy` for the `call_host_api` host action (and the host verb set) so legitimate calls are not default-denied; mutating verbs still gate on the autonomy dial.
- EDIT `backend/ai/engine/agent/tools.py` — `execute_call_host_api` builds a `Command` and calls `boundary.execute()`; the old gate moves into the boundary executor closure.
- CREATE `backend/ai/tests/test_call_host_api_boundary.py` — proves the tool routes through the boundary.

### Contract (read these first)
- `backend/ai/command_boundary.py` — `Command`, `Outcome`, `CommandBoundary.execute()`, `execute()`.
- `backend/ai/pdp.py` — `PDP`, `Policy`, `Decision`, `DEFAULT_POLICIES`.
- `backend/ai/adapters/ledger.py` — `DjangoLedgerAdapter(db)`.
- `backend/ai/engine/agent/executor.py` — `HostAPIExecutor` (staging API).

### DO NOT TOUCH
- `backend/ai/engine/` port files (engine stays portable — never import `command_boundary` from `ai/engine/`).
- `backend/ai/guards.py`, `backend/ai/protocol.py` (guard contracts unchanged).
- Frontend, `config/settings.py`, `backend/accounts/*`.

### Verification Gate (Master runs)
```bash
cd /home/ahmed/ws/carbon/backend && /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai -q -k "not code_sandbox" -m "not live"
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```

---

## Phase P2-06c — Route worker fan-out through the command boundary
**Role:** backend-worker · **Model:** DeepSeek V4-Flash · **Depends on:** P2-06a, P2-06b, P2-07 (all DONE)

> **STATUS: DONE** (Master-verified). The P1-07 interim hook call is deleted;
> `workers.py` now delegates to `CarbonHostExecutor.execute_worker_tools_via_boundary`,
> which builds a `Command` per tool call (read → `action="read"` → PDP ALLOW;
> mutation → `action="execute"` + `autonomy="human_only"` → PDP ASK → stage-7
> consent refuses, executor never runs). Engine stays host-free.

### Objective
Replace the interim P1-07 hook mechanism in `backend/ai/engine/agent/workers.py`
(`_get_hook_pipeline()` + `ExecuteWitness(is_worker=True, hook_pipeline=...)` +
`readonly_worker_hook`) with the 13-stage fail-closed `CommandBoundary`. Every
worker tool call becomes a `Command`; the boundary's PDP + consent stages block
mutations (workers are read-only), read-only tools execute. Delete the interim
hook call entirely.

### Contract (read these first)
- `backend/ai/command_boundary.py` — `Command`, `Outcome`, `CommandBoundary`, `STAGES`.
- `backend/ai/command_boundary_factory.py` — `get_command_boundary(db, *, executor, tool_catalog, ...)`, `_STATIC_TOOL_NAMES`.
- `backend/ai/pdp.py` — `DEFAULT_POLICIES`, `_READ_ACTIONS`, `_MUTATING_ACTIONS`, `_mutation_outcome`, `_read_outcome`.
- `backend/ai/engine/agent/workers.py` — current `_run_worker` / `_execute_worker_tools` / `_collect_guardrail_outcome` / `_render_worker_tool_results`.
- `backend/ai/engine/cognition/turn/execute.py` — `_execute_single_tool(tool_call, executor_override, hook_pipeline, hook_ctx_defaults, knowledge_store)` returns the completed-tool dict.
- `backend/ai/host_executor.py` — `CarbonHostExecutor.execute_host_api_via_boundary` (the P2-06b seam to mirror).

### How the boundary blocks a worker mutation (the key mechanism)
A worker mutation must be REFUSED, and its executor must NEVER run. Achieve this
with NO new PDP policy, purely by mapping the `Command` fields:

- Read-only worker tool → `Command.action="read"` → PDP `permit-read-only`
  (`"read" ∈ _READ_ACTIONS`) → `Decision.ALLOW` → stage 7 skipped → executor runs.
- Mutation worker tool → `Command.action="execute"` + `autonomy="human_only"` →
  PDP `permit-mutations-by-autonomy` → `_mutation_outcome("human_only")` →
  `Decision.ASK` → stage 7 consent (`requires_confirmation` becomes True because
  ASK ∈ {ALLOW_WITH_CONFIRMATION, ASK}; `confirmation_token`/`_confirmed` absent)
  → `Outcome(status="refused", error="consent: action requires confirmation …")`.
  The boundary executor closure is never invoked.

### Files
1. **EDIT `backend/ai/engine/agent/workers.py`**
   - Delete `_get_hook_pipeline()` and the `self._hook_pipeline` field.
   - `_run_worker`: drop the `_pipeline = self._get_hook_pipeline()` + fail-closed
     block; call the new `_execute_worker_tools` (below) instead.
   - `_execute_worker_tools` → delegate to the host executor seam:
     `self._executor.execute_worker_tools_via_boundary(tool_calls=tool_calls, instance_id=…, conversation_id=…, run_id=worker_run_id, host_user_id=getattr(self._executor, "host_user_id", None), knowledge_store=self._knowledge_store)`.
     If `self._executor` is None or lacks the seam → fail-closed: return one
     blocked dict per tool call (error "worker tool execution unavailable (no boundary seam)",
     `guardrail_flags=["worker_tool_blocked", f"blocked:{name}"]`). No engine imports
     of `command_boundary` / `command_boundary_factory` / `ai.protocol` — ever.
   - Update `_collect_guardrail_outcome` to key the block classification off
     `"worker_tool_blocked"` in `guardrail_flags` (and/or the error prefix), not
     only the old `_GUARDRAIL_CANCEL_PREFIX` string. Preserve the `WorkerArtifact`
     surface (error/guardrail_flags/detail) unchanged.

2. **EDIT `backend/ai/host_executor.py`** — add `CarbonHostExecutor.execute_worker_tools_via_boundary` (mirror the P2-06b seam):
   ```python
   async def execute_worker_tools_via_boundary(self, *, tool_calls, instance_id="",
           conversation_id="", run_id=None, host_user_id=None, knowledge_store=None) -> list[dict]:
       from ai.command_boundary import Command
       from ai.command_boundary_factory import get_command_boundary, _STATIC_TOOL_NAMES

---

## ECF — Entity Capability Framework (ADR-0032)  [2026-09-16]
## Safety: all phases flag-gated (ECF_ENABLED=False default).
## Never break: legacy list_employees / get_employee untouched until Phase ECF-7.
## ════════════════════════════════════════════════════════════════════

### Phase ECF-0 — Golden harness + baseline
**Role:** QA-Validator · **Model:** V4-Flash  
**Scope:** TESTS ONLY — no runtime code touched.

#### Files to create
- `backend/ai/tests/test_ecf_golden.py` — golden regression suite seeded from real failure transcript

#### Exact requirements

The test file must import nothing from ECF code (which doesn't exist yet).
It defines a declarative list of `GoldenCase` entries and a helper that calls
the live nibras instance (or a fixture version) and asserts invariants.

Each case must carry:
- `id: str` — unique slug
- `query: str` — the user message, in the language it was asked
- `must_find: bool` — True = a record must resolve; False = grounded-none required
- `employee_no: str | None` — if must_find=True, the resolved employee_no
- `invariants: list[str]` — prose invariants for the human reviewer

Minimum cases to encode (from the 2026-09-05 → 2026-09-16 transcript failures):

| id | query | must_find | employee_no | invariants |
|----|-------|-----------|-------------|------------|
| lookup_salman_en_full | `"Salman Ali Hussain Zakareya"` | False | None | grounded-none with "searched N of N"; never "not found" without count |
| lookup_salman_ar | `"سلمان علي زكريا"` | False | None | same as above; Arabic in, Arabic response |
| lookup_salman_partial | `"salman zakareya"` | False | None | partial match attempt; no hallucination |
| lookup_employee_no_1046 | `"1046"` (employee_no) | True | `"1046"` | resolves via employee_no not PK; must not return "not found" |
| lookup_employee_no_1021 | `"1021"` (employee_no) | True | `"1021"` | same |
| lookup_pk_104 | `"104"` (internal pk) | True | `"104"` | pk fallback; must resolve if pk 104 exists |
| lookup_reena_sekaran | `"Reena Sekaran"` | True | `"1009"` | name search returns correct emp_no |
| lookup_ar_abrar | `"عبرار"` | True | `"1021"` | transliteration-like Arabic partial |
| existence_over_truncated | `"is there an employee named Salman?"` | False | None | contract: must NOT produce "no such employee" without "searched N of N" |
| headcount_stable | `"كم عدد الموظفين"` | False | None | number matches DB; consistent across calls |
| kuwaiti_count_stable | `"كم كويتي موظف"` | False | None | single definition used; same number repeated; must cite which field |
| position_label | `"tell me about Reena Sekaran"` | True | `"1009"` | response contains position *title* not numeric id |
| arabic_in_arabic_out | `"كم موظف لدينا"` | False | None | response language is Arabic |

For Phase ECF-0 these tests are expected to **fail** (they document the current broken baseline).
The test runner must emit `BASELINE_FAILURE` not `ERROR` for known-bad cases —
use `@pytest.mark.xfail(reason="baseline — ECF not yet implemented", strict=False)`.

#### Contract files to read
`.ai-toolkit/shared/qa-framework.md`, `.ai-toolkit/shared/testing.md`, `.ai-toolkit/shared/uncertainty-provenance.md`

#### DO NOT TOUCH
Any file outside `backend/ai/tests/test_ecf_golden.py`. No runtime code.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v 2>&1 | tail -30
# Expected: all xfail or xpass — NO ERROR / EXCEPTION
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```
Write results to `TASK-RESULTS.md` with the full pytest output block.

---

### Phase ECF-1 — Entity Registry + descriptor schema + config flag
**Role:** Backend-Worker · **Model:** V4-Flash  
**Depends on:** ECF-0 complete  
**Scope:** New module + config flag + ADR-0032 descriptor in instance.yaml. NO tool wiring yet.

#### Files to create / edit

1. **CREATE `backend/ai/engine/cognition/entity/__init__.py`** — empty
2. **CREATE `backend/ai/engine/cognition/entity/registry.py`** — descriptor dataclass + loader:

```python
# Descriptor fields (all optional except name/model):
@dataclass
class EntityDescriptor:
    name: str                          # "employee"
    model: str                         # "people.models.Employee"
    identifiers: list[str]             # ["id", "employee_no", "civil_id"]
    search_fields: list[SearchField]   # bilingual, weighted
    label_map: dict[str, LabelSource]  # {"position": LabelSource(model=..., field="title")}
    masking: dict[str, MaskPolicy]     # {"basic_salary": MaskPolicy(capability="people:view_compensation")}
    metrics: dict[str, MetricDef]      # {"headcount": MetricDef(filter={"is_active": True}), "kuwaiti": MetricDef(filter={"nationality_code": "KW"})}
    scope_lookup: str | None           # org-unit scope kwarg e.g. "org_unit_id__in"

@dataclass
class SearchField:
    field: str
    lang: str         # "en" | "ar" | "any"
    weight: float = 1.0
    normalize: str | None = None  # "arabic" | None

@dataclass  
class LabelSource:
    model: str        # dotted Django model path
    field: str        # field name on the related model

@dataclass
class MaskPolicy:
    capability: str   # Django CBAC capability key; if caller lacks it → "hidden"

@dataclass
class MetricDef:
    filter: dict      # ORM kwargs for count() filter
    description: str = ""

def load_descriptors(instance_config: dict) -> dict[str, EntityDescriptor]:
    """Load entity descriptors from instance_config['entities'] list."""
    ...

def get_descriptor(instance_config: dict, entity_type: str) -> EntityDescriptor | None:
    ...
```

3. **EDIT `backend/ai/engine/core/config.py`** — add ONE flag:
```python
ECF_ENABLED: bool = False   # Entity Capability Framework; off until ECF-7 cutover
```

4. **EDIT `backend/ai/engine/instances/nibras/instance.yaml`** — append `entities:` block:

```yaml
entities:
  - name: employee
    model: people.models.Employee
    identifiers: [id, employee_no, civil_id]
    search_fields:
      - {field: full_name,      lang: en, weight: 1.0}
      - {field: name_en_given,  lang: en, weight: 0.9}
      - {field: name_en_family, lang: en, weight: 0.9}
      - {field: name_ar_given,  lang: ar, weight: 1.0, normalize: arabic}
      - {field: name_ar_family, lang: ar, weight: 1.0, normalize: arabic}
      - {field: employee_no,    lang: any, weight: 2.0}
      - {field: civil_id,       lang: any, weight: 2.0}
    label_map:
      position:  {model: people.models.Position,  field: title}
      org_unit:  {model: mdm.models.OrgUnit,       field: name}
    masking:
      basic_salary: {capability: people:view_compensation}
    metrics:
      headcount: {filter: {is_active: true},  description: "Total active employees"}
      kuwaiti:   {filter: {nationality_code: "KW"}, description: "Employees with nationality_code=KW"}
    scope_lookup: org_unit_id__in
```

5. **CREATE `backend/ai/tests/test_ecf_registry.py`**:
- loads nibras instance.yaml via `_instance_config("nibras", None)`
- calls `load_descriptors(cfg)` → asserts "employee" present with correct fields
- unit-level; no DB; no LLM

#### Contract files to read
`.ai-toolkit/shared/base-rules.md`, `.ai-toolkit/shared/ai-contract.md`, `.ai-toolkit/shared/config.md`, `ADR-0016`, `ADR-0017`, `ADR-0032`

#### DO NOT TOUCH
`tools.py` execution paths, any existing capabilities, `list_employees`/`get_employee`, frontend, `settings.py`.
The engine must never import people/mdm/accounts directly — descriptors are pure data, model paths are strings resolved at runtime in the host layer.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_registry.py ai/tests/test_instance_registry.py -v 2>&1 | tail -20
# Must: test_ecf_registry passes; test_instance_registry still all green (no regression)
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
```
Write results to `TASK-RESULTS.md` with full pytest output.

---

### Phase ECF-2 — Generic resolver (shadow, no tool wiring)
**Role:** Backend-Worker · **Model:** V4-Flash  
**Depends on:** ECF-1 complete  
**Scope:** The resolver algorithm. Purely in-engine. No host imports. No tool wiring. `ECF_ENABLED` irrelevant (not yet on the hot path).

#### Files to create

1. **CREATE `backend/ai/engine/cognition/entity/resolver.py`**

Algorithm (`resolve(descriptor, query, *, fetch_fn) -> ResolveResult`):
```
1. Detect language (reuse navigation.py detect_lang)
2. Normalize query (reuse navigation.py normalize_text for Arabic; strip for English)
3. Try identifier exact match (employee_no, civil_id) → if hits → Return match
4. For each search_field in descriptor (filtered to detected lang or "any"):
     score = similarity(normalize(query), normalize(stored_value))
     Apply weight from descriptor
5. Transliteration bridge: if Arabic query and EN search fields (or vice versa),
   apply transliterate(query) and re-score
6. Threshold: score >= 0.8 → candidate; score >= 0.92 → match
7. If 0 candidates → ResolveResult(action="none", searched_total=N)
8. If 1 match (and gap >= 0.1 from next) → ResolveResult(action="match", record=...)
9. Otherwise → ResolveResult(action="disambiguate", candidates=[...])
```

`fetch_fn` is injected — the engine never imports Django. Signature:
```python
def fetch_fn(model_path: str, filters: dict, fields: list[str], limit: int) -> list[dict]: ...
```

The host layer (host_executor.py) supplies a concrete `fetch_fn` that does the ORM call.

```python
@dataclass
class ResolveResult:
    action: str          # "match" | "disambiguate" | "none"
    record: dict | None = None
    candidates: list[dict] = field(default_factory=list)
    searched_total: int = 0  # always populated — "searched N of N"
    lang: str = "en"
    query_normalized: str = ""
```

2. **CREATE `backend/ai/tests/test_ecf_resolver.py`**:
- Use an in-memory fixture of 530-ish synthetic records (no DB).
- Must prove: "Salman Ali Hussain Zakareya" → action="none", searched_total=530; "Reena Sekaran" → action="match"; "1046" (employee_no) → action="match"; Arabic "سلمان" → action="none" or disambiguate, never a confident false-negative; transliteration bridge.
- Must prove: Arabic query → Arabic-language result context.

#### Contract files to read
`.ai-toolkit/shared/base-rules.md`, `ADR-0032`, `ADR-0016/0017`, navigation.py (reuse pattern)

#### DO NOT TOUCH
`host_executor.py`, `tools.py`, `instance.yaml`, frontend. No DB ORM in this file.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_resolver.py -v 2>&1 | tail -30
cd /home/ahmed/ws/carbon && python3 .ai-toolkit/scripts/import-boundary-lint.py
# CRITICAL: grep -rn "from people\|import Employee\|from mdm" backend/ai/engine/ → must be EMPTY
```

---

### Phase ECF-3 — Boundary contract guards
**Role:** Backend-Worker · **Model:** V4-Flash  
**Depends on:** ECF-2 complete

#### Files to create / edit

1. **CREATE `backend/ai/engine/cognition/entity/contracts.py`** — four enforced invariants as callables hooked into the tool result pipeline:
   - `no_truncation_as_truth(tool_result, claim)`: if source `truncated=True` and claim is existence/universal ("no such", "all", "none") → rewrite claim to "searched N of N, none found in visible page; use resolve_entity for complete search"
   - `resolve_labels(data, descriptor)`: replace FK ids with human labels
   - `honest_masking(data, descriptor, capabilities)`: replace `0.000` with `"(hidden — requires salary access)"` when caller lacks capability
   - `grounded_refusal(result)`: existence-claim requires `searched_total` field populated

2. **EDIT `backend/ai/engine_runtime.py`** — in `_run_chat`, after tool results are collected (after `_build_tool_trace`), add a contract-application pass: `from ai.engine.cognition.entity.contracts import apply_contracts` (gated on `ECF_ENABLED` flag).

3. **CREATE `backend/ai/tests/test_ecf_contracts.py`**:
   - `test_truncated_source_cannot_claim_nonexistence`: assert that a "not found" from a truncated list gets rewritten.
   - `test_salary_zero_becomes_hidden_label`: assert `0.000` → `"(hidden)"` when capability absent.
   - `test_fk_id_resolved_to_label`: assert `position=170` → `position="CT Senior Operator"`.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_contracts.py -v 2>&1 | tail -20
# Full suite still green:
../.venv/bin/python -m pytest ai/ -q -k "not live" 2>&1 | tail -10
```

---

### Phase ECF-4 — Wire resolve_entity tool (flag-gated) + fix get_employee
**Role:** Backend-Worker · **Model:** V4-Flash  
**Depends on:** ECF-3 complete

#### Files to edit

1. **EDIT `backend/ai/engine/agent/tools.py`** — add `resolve_entity` to `STATIC_TOOL_DEFINITIONS` and `STATIC_TOOL_EXECUTORS` gated on `settings.ECF_ENABLED`. Reuse `get_descriptor(instance_config, entity_type)` + resolver + host `fetch_fn` bridge.

2. **EDIT `backend/ai/host_executor.py`** — in `_people_in_process` employees branch: accept `employee_no` as a lookup key in addition to PK (already has `pk` param — add `elif params.get("employee_no")` resolution).

3. **EDIT `backend/ai/engine/instances/nibras/instance.yaml`** — fix `list_employees` description to say "first 100; for lookup by name/number use resolve_entity" and `get_employee` to say "accepts numeric id OR employee_no". Do NOT change the catalog entry path.

4. **CREATE shadow logger** in `resolve_entity` executor: when `ECF_ENABLED` is True, log `shadow_diff = {new_result, legacy_result}` to `ai_shadow_log` table (or JSON log if table doesn't exist yet). This generates the parity evidence needed for ECF-7 cutover decision.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py ai/tests/test_ecf_resolver.py ai/tests/test_ecf_contracts.py ai/tests/test_navigation_resolver.py ai/tests/test_intent_resolver.py -v 2>&1 | tail -40
# ECF golden cases should be flipping from xfail to xpass progressively.
# Navigation + intent tests: zero regression.
```

---

### Phase ECF-5 — MAPE-K feedback loop (trajectory → golden)
**Role:** Data/ML-Worker · **Model:** V4-Flash  
**Depends on:** ECF-4 complete

#### Files to create

**CREATE `backend/ai/engine/cognition/entity/heal.py`**:

```python
# MAPE-K implementation
# Monitor: hooks into contract-guard violations + user-correction signals
#           (turn with text matching "wrong"/"ليس صحيح"/"غلط" shortly after a tool call)
# Analyze: classify as Tier-1 (reversible, auto-heal) or Tier-2 (structural, propose)
# Plan + Execute:
#   Tier-1: re-resolve with broader normalization; abstain honestly; reindex stale entity cache
#   Tier-2: auto-draft a GoldenCase (nominated_by="mape_k") + write to
#            backend/ai/eval/pending_golden_nominations.json (human reviews before CI merge)
```

The pending nominations JSON is a queue; a human reviews, moves to `test_ecf_golden.py`, and runs CI. That is the "self-healing through human gate" pattern.

#### Verification Gate
```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_heal.py -v 2>&1 | tail -20
# Prove: simulated correction → pending_golden_nominations.json gains one entry.
```

---

### Phase ECF-6 — Canonical metrics
**Role:** Backend-Worker · **Model:** V4-Flash  
**Depends on:** ECF-5 complete

Wire descriptor `metrics{}` → `aggregate_entity` capability. "headcount" always uses `is_active=True` count. "kuwaiti" always uses `nationality_code="KW"`. The `analyze_employees` dimension route is unchanged; `aggregate_entity` is an additional, metric-named path.

#### Verification Gate
```bash
# Run golden "same question → same number":
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -k "headcount_stable or kuwaiti_count_stable" -v
```

---

### Phase ECF-7 — Cutover (Master Architect gates this)
**Only triggers after:** ECF golden set fully green; shadow-diff review shows parity; human sign-off.

Flip `ECF_ENABLED = True` in nibras instance config. Mark `slug_resolution` paths as superseded in `tools.py` comment. Do not delete — keep as fallback for 30 days.

---

### Phase ECF-8 — Generalize proof (Backend-Worker)
**Depends on:** ECF-7  
Onboard `LeaveRecord` as entity #2 by writing **only a descriptor entry** in instance.yaml + golden cases. Zero new algorithm code. This is the proof that the framework generalizes.

---

### ECF Edge-Case Matrix (CI must cover all rows)
| Edge case | Phase | Test |
|---|---|---|
| Exists in rows > 100 (only in page 2+) | ECF-2 | test_ecf_resolver: record at index 150 resolves |
| Arabic tashkeel variants | ECF-2 | "سَلمان" = "سلمان" |
| Transliteration (Salman ↔ سلمان) | ECF-2 | near-miss candidates surfaced |
| employee_no vs PK ambiguity | ECF-4 | "1046" → emp 1046, not pk 1046 |
| Prompt injection in name query | ECF-2 | query treated as data, no eval |
| Existence claim over truncated source | ECF-3 | test_ecf_contracts |
| PII masking honest | ECF-3 | test_ecf_contracts |
| FK id label resolution | ECF-3 | test_ecf_contracts |
| Multi-tenant scope isolation | ECF-2 | fetch_fn applies scope; carbon sees no nibras data |
| Language in → language out | ECF-0 | arabic_in_arabic_out golden case |
| Canonical metric stability | ECF-6 | headcount_stable / kuwaiti_count_stable |
| New entity (no code change) | ECF-8 | LeaveRecord descriptor only |

