# Pulse — Unified Remediation & Build Plan (v1)

**Merges:** *Deep Audit II* (governance, process expertise, fail-open register) + *Research-backed Architectural Audit* (four representations, capability catalog, command boundary, durable runs, outcome-grounded evals).

**Inputs held constant:** [PULSE-DETAILED-AUDIT-ARCHITECTURE.md](../PULSE-DETAILED-AUDIT-ARCHITECTURE.md), the AI-toolkit audit.

**Status of claims:** everything about Pulse's code is *as reported* in the audits; everything below marked "task" is a proposal, not something that exists yet.

**Repo conventions this plan follows:**
- ADRs live in [.ai-toolkit/decisions/](../../.ai-toolkit/decisions) (current range 0001–0030; the plan's decision record is **ADR-0031**).
- Toolkit gates/scripts live in [.ai-toolkit/scripts/](../../.ai-toolkit/scripts).
- Pulse canon lives in [docs/pulse/](.) — `PULSE-MASTER.md` is the single source of truth to reconcile against.

---

## 0. How to read this plan

**Five principles every task must satisfy.** If a task violates one, the task is wrong — not the principle.

1. **Fail-closed.** A guard, critic, gate, store, or generator that cannot evaluate refuses or errors loudly. Never `return True` in an `except`.
2. **One door.** Every Pulse-originated effect — chat tool, ReAct step, worker, skill, proactive delivery, MCP, sandbox, retry — passes through the same host-owned command boundary.
3. **Knowledge ≠ authority.** Observed behavior, approved definition, executable implementation, and current case state are four different artifacts. Learning can only ever produce *candidates*.
4. **Host owns state and effects; engine owns inference.** Engine code imports only `engine.**` and `engine.ports.*`. Persistence happens in host adapters.
5. **Docs follow code.** A rule that isn't a CI check is a wish. Every phase ends by reconciling `PULSE-MASTER.md` to what actually runs.

**Task format:** `ID | Task | Where | Done when (evidence) | Size | Depends`.

**Size legend:** **XS** ≤ ½ day · **S** ≤ 1 day · **M** 2–3 days · **L** ≤ 1 week (an **L** must be split into sub-PRs before starting).

**Every task ships with:** a test, a one-paragraph doc update, and — where it touches a guard — a red-team case.

---

## 1. Reconciliation of the two audits

### 1.1 Where they agree (no decision needed)

| Topic | Both audits say |
|---|---|
| Fail-open is the dominant defect | Close the ~12-item register before anything else |
| `AI_STORE_BACKEND=inmemory` default | Must be impossible in non-test environments |
| Worker fan-out bypass, skill-promotion bypass, dead `MutationGuard`, no-op tenancy filter | P0 |
| Dual ORM (SQLAlchemy schema mirrored by class-name into Django) | Pick one; Django canonical |
| Engine imports `ai.models.*` in 14+ files | Enforce boundary in CI, not docs |
| Hardcoded Carbon/DQ/GHG vocabulary in cognition | Extract into a domain pack |
| Process discovery today = schema discovery | Need an event substrate + registry + conformance |
| Skills reuse is shallow; `invoke_skill` returns body "as data only" | Must resolve to governed execution, never a second executor |
| Raw SQL in proactive path | Structured predicates, read-only role, timeout |
| RestrictedPython / in-process module boundary ≠ sandbox | Do not claim isolation |
| Toolkit rot is the same disease | Referenced scripts must exist and run in CI |
| Evaluate outcomes (final state, pass^k), not activity | τ-bench-style business-process evals |

### 1.2 Where they differ — and the resolved decision

| # | Deep Audit II | Research Audit | Decision |
|---|---|---|---|
| **D1** — Invariant I2 | Rebase: engine may *author* writes via ports; host *owns* storage | Keep I1/I2 literally: engine emits proposals, host persists | **Both, by layer.** Cognitive state (episodic, ledger, working memory) → engine calls a *port*, host adapter persists. Business effects → engine emits an `ActionProposal`; host command boundary executes. Rewrite I2 as: *"Engine holds no process-lifetime state and never commits durable state directly; all persistence and all effects go through host-implemented ports."* |
| **D2** — Process definition shape | Declarative constraints in YAML + autonomy dial | Rich contract: steps, human tasks, predicates, exceptions, tests | **Unified schema:** steps + constraints + autonomy per activity + policies + evidence + exceptions + tests. Constraints give cheap conformance checking; steps give executability; tests gate publication. |
| **D3** — Policy engine | PDP with Cedar/OPA, 5 outcomes (allow / allow_with_confirmation / ask / defer / refuse) | 13-step execution sequence; Cedar skip-on-error caveat | **PDP is a stage inside the command boundary**, not a peer. Start with an in-house evaluator (default-deny, forbid-overrides-permit, *error → refuse* for mandatory policies). Cedar spike in Phase 7 with an explicit diagnostics wrapper. |
| **D4** — Skills | Skills-as-folders (Agent Skills spec), `invoke_skill` executes steps | Split: guidance skills / executable-procedure references / candidates | **Adopt the split; use the folder format for packaging.** Guidance skills are `SKILL.md` folders with progressive disclosure. An "executable" skill is a `SKILL.md` whose body *references* a registry `process.id@version`; `invoke_skill` creates/resumes a host run. No arbitrary `sql_macro`/`api_call` execution from skill bodies. |
| **D5** — Tool coverage | `get_tools()` 2/9 → 9/9 | Don't chase 9/9; go deep on few governed capabilities | **Depth first.** Coverage metric = number of *capabilities with full contracts + process + evals*. Second domain only after the pilot passes the Phase 4 gate. |
| **D6** — Mining order | Nightly mining → candidates from day one | Conformance against admin-approved definitions first | **Conformance first (Phase 5), discovery second (Phase 6).** Mining output is never authoritative. |
| **D7** — Durable runtime | Temporal or Postgres-outbox homegrown | Evaluate Django-hardened vs Temporal vs Camunda against the pilot | **Harden Django for the pilot** with a strict workflow/activity split, idempotency keys, and the 9-state run machine. **Bounded Temporal spike** in Phase 7; ADR decides. No custom BPMN engine; no two runtimes in prod. |
| **D8** — Admin console | 7 screens under `/admin/ai/*` | 6 jobs + separation-of-duties roles | **7 screens, 6 roles.** Add `process_owner`, `policy_owner`, `publisher`, `operator`, `auditor`, `platform_admin`; `AI_VIEW_CONSOLE` never implies publish. |
| **D9** — Escalation lane | Configure `LLM_REASON_MODEL` or delete claim | Escalate based on measured need | **Measure, then decide.** A/B on replay fixtures in Phase 2; keep only if it moves an outcome metric. |
| **D10** — Approvals | Confirmation stage (RULE_21) | Approval bound to revision/args/evidence digest; three concepts (authorization / business approval / consent) | **Adopt binding + three-concept split.** RULE_21 consent preserved; standing authorization is a separate future ADR, never inferred from an autonomy setting. |
| **D11** — Requirements | — | Interviewing process owners is a first-class discovery capability | **Adopt.** Pulse generates an interview kit per process; answers become definition fields. |
| **D12** — MCP | Wire `init_mcp_tools()` or delete surface | MCP is connectivity; tools register as capabilities | **Delete the UI surface now (Phase 1); wire in Phase 7 through the catalog + boundary.** |

---

## 2. Target architecture (one page)

```
HUMAN CONTROL PLANE  (/admin/ai/*)
  Process Registry · Review Queue · Policy Editor · Conformance · Evals · Spend · Audit Explorer
  Roles: process_owner · policy_owner · publisher · operator · auditor · platform_admin
                                   │ publishes versions, sets autonomy, approves tasks
                                   ▼
HOST (backend/ai/, Carbon-owned)
  Business Capability Catalog ──► Process Registry (versioned definitions)
  Command Boundary  = resolve identity → scope → contract → validate → state-eligibility
                     → PDP.decide → consent/approval → budget → revision check
                     → execute(idempotency key) → persist events → verify postconditions
                     → confirmed | failed | pending | outcome_unknown
  Durable Run Machine (9 states) · Approval Grants · Human Task Inbox · Reconciliation
  Event Substrate (OCEL-2.0-compatible, outbox) · AuditLog (single trail) · Adapters for ports
        ▲ observations / snapshots                          │ authorized effects
        │                                                   ▼
PULSE ENGINE (backend/ai/engine/, imports only engine.** + engine.ports.*)
  Six-witness spine (unchanged shape) · Memory tiers · Retrieval by applicability
  Emits: ActionProposal · MemoryProposal · ProcessCandidate · SkillCandidate
  Loads: DomainPack (vocabulary, catalog, seed processes, skills, triggers, prompts)
```

**Four representations, four stores, never merged:** observed behavior (events) · approved definition (registry) · executable implementation (capabilities + host services) · current instance (run state + verified outcomes).

---

## 3. Phase overview

| Phase | Weeks | Theme | Exit gate (all must hold) |
|---|---|---|---|
| **0** | 1 | Ground truth & harness | Invariants text recovered; effect-path inventory approved; CI baselines reported; CRLF fixed |
| **1** | 2–3 | Fail-closed | Red-team suite (≥10 mutation attempts across every path) all blocked; startup refuses without store; usage accounting complete |
| **2** | 4–8 | Boundaries | `import-linter` enforcing; single ORM; every path in inventory routes through command boundary (tested); forbidden-term grep = 0 |
| **3** | 9–14 | Registry + pilot process | 16-step demonstration passes steps 1–15 via both UI and Pulse |
| **4** | 15–18 | Expertise on the pilot | Business-process eval suite ≥ threshold; Pulse cites policy version when allowing/blocking |
| **5** | 19–23 | Events + conformance | Real deviation detected in staging; incomplete-log false-violation test passes |
| **6** | 24–30 | Governed learning | One learned improvement through full lifecycle with zero authority widening (tested) |
| **7** | 31+ | Scale | Runtime ADR; MCP behind boundary; second domain onboarded; `water` pack boots engine untouched |

**Cadence:** weekly task review; phase-gate review with the six roles present; no phase starts before the previous gate is green.

---

## 4. Phase detail

### Phase 0 — Ground truth & harness (Week 1)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P0-01 | Recover full text of I1–I8 and L1–L7 from ADRs; publish `docs/pulse/INVARIANTS.md` with a "currently violated by" column | `docs/pulse/`, ADRs | File exists; each invariant has status + violating files | S | — |
| P0-02 | Write `ADR-0031-unified-plan.md` recording decisions D1–D12 and this plan | `.ai-toolkit/decisions/` | ADR merged | S | P0-01 |
| P0-03 | Repo-wide line endings: `.gitattributes` `* text=auto eol=lf`; `git add --renormalize .`; CI step fails on `\r` in text files | repo root, CI | CI green; `grep -rl $'\r'` over tracked text = 0 | S | — |
| P0-04 | `scan.sh cfg()` strips `\r`; every generator asserts non-empty output and exits non-zero on empty | `.ai-toolkit/scripts/` | Registry regenerates; simulated empty output fails CI | XS | P0-03 |
| P0-05 | Remove references to nonexistent scripts (`audit-routes.py`, `audit-imports.sh`, `verify-intelligence.sh`, `model-serving-boundary.md`); fix `check-i18n-keys.js` path. Real replacements arrive in P2-11 | `.ai-toolkit/**` | `grep` for each reference = 0 or points to a file that exists | S | — |
| P0-06 | **Effect-path inventory.** Enumerate every path that can produce a host effect or durable write: `tools.py:call_host_api`, `workers.py`, `plan/loop.py`, `skills` invoke, `proactive/delivery.py`, `ingestion/ops_workflow.py`, MCP, sandbox, ledger writes, memory writes. Column: guard coverage today | `docs/pulse/EFFECT-PATHS.md` | Table reviewed & signed by policy_owner | M | — |
| P0-07 | **Replay fixtures.** Capture 30 representative real conversations + 10 mutation attempts (incl. indirect phrasing, cross-tenant refs, self-approval) as replayable fixtures; record current behavior as baseline | `backend/ai/tests/fixtures/replay/` | Fixtures run; baseline JSON committed | M | — |
| P0-08 | Add `vulture`, `import-linter`, forbidden-term grep to CI in **report-only** mode | CI | Baseline counts in CI artifact | S | — |
| P0-09 | Confirm dead-code candidates with coverage run over tests + one smoke session + entry-point analysis; produce `confirmed_dead` vs `dynamically_registered` lists | `docs/pulse/DEAD-CODE.md` | Each item classified with evidence | M | P0-07 |
| P0-10 | Choose pilot process and owner: `dq.rule.release` (validate → review → publish → verify) or equivalent whose host services already exist | `docs/pulse/PILOT.md` | Owner named; existing endpoints listed; gaps listed | XS | — |
| P0-11 | **QA & measurement framework.** Two axes (intelligence = spine S1→S6; features = P0-06 capability surface) × two modalities (tests binary / gauges thresholded). 4-layer evidence ladder L0 static → L1 replay → L2 red-team+process → L3 live canary. Core rule: **outcome not activity** — every feature claim ends in a final-state assertion + pass^k. Consolidated harness at `backend/ai/eval/` (fixtures, scorer, reporter, gauges) | `docs/pulse/QA-FRAMEWORK.md`, `backend/ai/eval/` | Ladder wired to CI/phase gates; every gauge ships a test that fails when the gauge is silent; `eval_pulse_behavior.py`/`qa_pulse_smoke.py` superseded by one reporter | M | P0-06, P0-07 |

### Phase 1 — Fail-closed (Weeks 2–3)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P1-01 | `AI_STORE_BACKEND`: remove default; raise `ImproperlyConfigured` if unset or `inmemory` unless `PYTEST_CURRENT_TEST` or explicit `PULSE_ALLOW_INMEMORY=1` | `config/settings.py` | Startup test: unset → fails; `django` → ok | XS | — |
| P1-02 | Critic rules tier: `unconfirmed_mutation` → `veto`; execution stops | `cognition/turn/critic.py` | Test: unconfirmed mutation never reaches S5 | XS | — |
| P1-03 | Verification witness on by default; exception → `passed=False`, error stored in ledger row | `cognition/turn/verify.py` | Test: injected exception yields failed verdict + ledger entry | S | — |
| P1-04 | Admission critics: exception → `rejected(reason="critic_error")`; skill stays `pending` | `skills/gate.py` | Test: LLM key removed → nothing promoted | S | — |
| P1-05 | `Skill.gate_status` default `"pending"`; migration backfills `NULL`; sweep picks them up | `ai/models/`, migration | Migration applied; zero NULLs; sweep test | S | — |
| P1-06 | Close promotion bypass: `promote_skill`, `SkillsStore.promote_to_instance`, `SkillRegistry.update_status` become private and callable only from `gate.admit()`; explicit transition table | `skills/registry.py`, `skills/crud.py`, `ai/store.py` | Tests: direct calls raise; only gate path promotes | M | P1-05 |
| P1-07 | Worker fan-out runs the HookPipeline (interim until P2-06) with `is_worker=True` | `agent/workers.py` | Test: mutation inside worker is blocked | S | — |
| P1-08 | LLM accounting: `_log_call` commits in its own short session; `provider.chat_completion*` → `_chat_completion*`; all callers use `router.route_*` | `llm/router.py`, `llm/provider.py` | Test: every provider call (incl. retries, failures, workers) produces a usage row; budget test trips | M | — |
| P1-09 | Proactive SQL: replace `f"WHERE {where_clause}"` with structured predicates `(field, op, value)` rendered with params from an allowlist; run under read-only role with `statement_timeout`; route through `sql_validator` | `proactive/trigger_evaluator.py`, `proactive/context_assembler.py` | Injection tests fail closed; existing triggers migrated | M | — |
| P1-10 | Delete `MutationGuard.validate` (replaced by P2-06); update `guards.py` docstring to the four guards that actually run | `ai/guards.py` | No dead guard; docstring matches `run()` | XS | — |
| P1-11 | `DjangoStore._apply_tenancy_filter` applies `scope_q()` (or is deleted with docstring corrected); cross-tenant test on 3 stores | `ai/store.py` | Cross-tenant read returns 0 rows | S | — |
| P1-12 | Persist `learning/preferences.py` into `AIUserProfile`; drop thread-local dict | `learning/preferences.py` | Preference survives restart test | S | — |
| P1-13 | **Fail-open lint** in CI: regex for `except .*:\s*(return True\|passed\s*=\s*True)` and `return qs` inside `_apply_*filter`; allowlist file with justification per entry | CI, `.ai-toolkit/scripts/` | CI fails on new offenders; allowlist empty or justified | S | — |
| P1-14 | Capability health: `GET /admin/ai/health` → per capability `configured/healthy/degraded/disabled/unavailable` (store, reason lane, verify, MCP, sandbox); UI shows it; **remove MCP UI affordances** until P7-02 | `ai/workspace_api.py`, frontend admin | Endpoint + panel; MCP menu gone | M | — |
| P1-15 | Delete confirmed-broken dead code already removed in earlier cleanup + remaining `plan_executor.py` (NameError), `bm25.py` stub, `migration.py` (per P0-09 list) | per P0-09 list | Tests pass; `vulture` count drops | M | P0-09 |
| P1-16 | `get_task()`: return honest `{"status":"not_supported"}` and stop UI polling it (real implementation P7-08) | `engine_runtime.py`, frontend | No UI path calls it | S | — |
| P1-17 | Red-team suite v1: 10 mutation attempts × every path in P0-06 (direct, indirect phrasing, worker, skill, proactive, ingestion) | `backend/ai/tests/redteam/` | All blocked; suite runs in CI | M | P1-02…P1-09 |

**Gate 1:** P1-17 green · P1-01 startup test green · P1-08 accounting complete · `PULSE-MASTER.md` §guards/§learning reconciled.

### Phase 2 — Boundaries (Weeks 4–8)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P2-01 | Define `engine/ports/` Protocols: `EpisodicStore`, `LongTermStore`, `SkillStore`, `LedgerSink`, `EventBus`, `ProcessRegistry`, `PolicyDecisionPoint`, `HostActions`, `OrgMemory`, `Clock` | `engine/ports/` | Protocols + docstrings; no implementation | M | P0-01 |
| P2-02a–e | Host adapters implementing ports over Django + `scope_q()`: (a) memory, (b) ledger, (c) skills, (d) knowledge graph, (e) proactive/user watches. Generalize existing `CarbonHostAdapter` pattern | `backend/ai/adapters/` | Each adapter has contract tests against its Protocol | 5×S | P2-01 |
| P2-03a–n | Migrate each of the 14+ engine files importing `ai.models.*` to ports — **one file per PR**: `knowledge_graph/store.py`, `knowledge/store.py`, `cache_store.py`, `feedback.py`, `proactive/user_watches.py`, `cognition/turn/execute.py` (`EvidenceRecord`), `cognition/turn/ledger.py`, `cognition/loop.py`, `cognition/monitors.py`, `runner.py` (`CarbonContextAssembler`), … | engine | File has zero `ai.` imports; behavior test unchanged | 14×S | P2-02 |
| P2-04 | Flip `import-linter` to **enforce**: `engine.**` may import only `engine.**`, stdlib, LLM SDK | CI | CI red on any violation | XS | P2-03 |
| P2-05a–d | Dual ORM resolution, Django canonical: (a) inventory 49 SQLAlchemy tables vs Django mirrors, diff schemas; (b) replace `core/models.py` with dataclasses/TypedDicts; (c) same for `knowledge_graph/models.py`; (d) remove `sqlalchemy` imports from `tools.py`, `skills/registry.py`, `executor.py`, `gate.py`; delete `store.resolve_model` class-name lookup | `engine/core/`, `engine/knowledge_graph/` | `pip uninstall sqlalchemy` → tests pass | L (4×M) | P2-03 |
| P2-06a | **Command Boundary core**: `backend/ai/command_boundary.py` with `execute(Command) -> Outcome` implementing the 13 stages (identity → scope → contract → validate → state-eligibility → PDP → consent/approval → budget → revision check → execute w/ idempotency key → persist events → verify → outcome). Fold `HookPipeline` + `GuardChain` into stages | host | Unit tests per stage; stage-order test | M | P2-01 |
| P2-06b | Route `call_host_api` through the boundary | `agent/tools.py` | Tool test hits boundary; old gate removed | S | P2-06a |
| P2-06c | Route worker fan-out through the boundary; delete interim P1-07 hook call | `agent/workers.py` | Worker mutation test still blocked via boundary | S | P2-06a |
| P2-06d | Route ReAct steps (`plan/loop.py`) through the boundary; consent gate becomes a boundary outcome | `cognition/plan/loop.py` | Replay fixtures unchanged; consent test | M | P2-06a |
| P2-06e | Route proactive delivery through the boundary (delivery is an action) | `proactive/delivery.py` | PDP decision row per delivery | S | P2-06a |
| P2-06f | Route `ops_workflow.py` host REST calls through the boundary | `ingestion/ops_workflow.py` | Test | S | P2-06a |
| P2-07 | **PDP v1**: `decide(principal, action, objects, process_state, autonomy, budget, time) → allow / allow_with_confirmation / ask / defer / refuse (+reason, +policy_version)`; default deny; forbid overrides permit; *evaluation error → refuse* for mandatory policies; every decision persisted | `backend/ai/pdp.py` | Property tests for the three semantics; decision rows queryable | M | P2-06a |
| P2-08a–g | **Domain pack extraction** `domain_packs/carbon/{vocabulary.yaml, api_catalog.yaml, processes/, skills/, triggers.yaml, prompts/}` loaded via a `DomainPack` port — one PR per source: (a) `turn/intent.py` (campus names, `list_emission_factors`, GHG terms), (b) `plan/loop.py` `_allow`, (c) `planner.py` supplier/module phrases, (d) `turn/execute.py` `"carbon_api"` source map, (e) `proactive/delivery.py` routes + `"carbon"` brand, (f) `insight_generator.py` power defaults, (g) `core/config.py` DQ constants | engine + `domain_packs/` | Forbidden-term grep over `engine/**` = 0 per file | 7×S | P2-01 |
| P2-09 | Audit trail unification: `AI_AUDIT` structured log emitted *from* `AuditService.log`; one write path | `ai/audit_service.py` | Single call site; log and row always paired | S | — |
| P2-10 | Escalation lane A/B: set `LLM_REASON_MODEL` to a distinct model in staging; run P0-07 fixtures; measure outcome delta, cost, latency; ADR keep/remove | `llm/router.py`, `.ai-toolkit/decisions/` | ADR with numbers | M | P0-07 |
| P2-11 | Real toolkit gates replacing P0-05 removals: `verify.sh intelligence` = import-linter + fail-open lint + forbidden-term grep + vulture + replay smoke; `audit-imports` = import-linter contract; `audit-routes` = registry drift check | `.ai-toolkit/scripts/` | Each script exists, runs in CI, fails on seeded violation | M | P2-04 |
| P2-12 | Delete confirmed-dead KG subsystems already removed in earlier cleanup; verify single-step NL→SQL remains under validator + read-only role + timeout | `engine/knowledge_graph/` | LOC drop confirmed; tests pass | M | P0-09 |

**Gate 2:** P2-04 enforcing · P2-05 single ORM · every P0-06 path has a boundary test · P2-08 grep = 0 · `PULSE-MASTER.md` §boundary reconciled.

### Phase 3 — Registry + pilot process (Weeks 9–14)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P3-01 | `Capability` model + loader from `api_catalog.yaml`: id, business name, purpose, inputs (typed), preconditions, permissions, effects, side effects, approval requirements, idempotency, verification, failure semantics, recovery, owner, version. Loader fails if referenced host action doesn't exist | `ai/models/capability.py`, `domain_packs/carbon/api_catalog.yaml` | Loader test; unknown action → validation error | M | P2-08 |
| P3-02 | Author pilot capability contracts: `dq.rule.validate` (read-only), `dq.rule.review` (human task), `dq.rule.publish` (mutation, consent required), predicate `dq.rule.active_revision_matches_approved_revision` as reviewed host code | domain pack + host predicates module | Contracts load; predicate unit-tested | M | P3-01, P0-10 |
| P3-03 | `ProcessDefinition` unified schema (JSON Schema): `id, version, owner, status(draft/review/active/deprecated), objects, inputs, scope(source: authenticated_host_context), objective predicate, steps[kind: command/human_task/assertion; capability; depends_on; autonomy; separation_of_duties; binds_to; consent; approval_ref; concurrency; idempotency_scope; unknown_outcome], constraints[precedence/response/not_coexist], evidence, policies[refuse_if/ask_if], exceptions, kill_switch, tests`. Unknown step kinds/capabilities fail validation | `ai/models/process.py`, `ai/process_schema.json` | Schema validates the pilot YAML; rejects 6 malformed fixtures | M | P3-01 |
| P3-04 | **Process-owner interview kit**: Pulse generates questions for the pilot (emergency waivers, approval validity after edit, reconciliation owner, SLA); answers recorded into definition fields with provenance | `ai/process_interview.py`, prompts in pack | Interview transcript → filled definition; owner signs | S | P3-03 |
| P3-05a | Registry API: create/edit draft, diff vs active, submit for review, publish (author ≠ publisher enforced), deprecate; autonomy dial per activity per org unit (`observe/propose/act_confirm/act_notify/act_silent/human_only`); kill switch | `ai/registry_api.py` | Tests incl. self-publish refused | M | P3-03 |
| P3-05b | Roles: add `process_owner`, `policy_owner`, `publisher`, `operator`, `auditor` capabilities; `AI_VIEW_CONSOLE` grants view only | `ai/permissions.py`, `ScopedRole` | Test matrix role × action | S | — |
| P3-05c | Registry screen + Review Queue screen under `/admin/ai/*` (diff, rationale, evidence, missing evidence, permissions delta, tests, affected runs) | frontend | Manual walkthrough + Cypress | M | P3-05a |
| P3-06 | `ApprovalGrant` model bound to tenant/app/process instance/process version/capability version/canonical args/object revisions/evidence digest/expiry/effect limits; invalidate on any material change. Three concepts separated in code: authorization (PDP), business approval (grant), user consent (RULE_21 stage) | `ai/models/approval.py`, boundary stage | Tests: revision 7 approval doesn't authorize revision 8; expired grant refused | M | P2-06a |
| P3-07a | **Durable run machine**: extend `Run`/`RunStep` with states `planned → awaiting_approval → ready → executing → succeeded / failed / outcome_unknown → awaiting_reconciliation / cancelled`; idempotency key = `(instance, step)`; definition version pinned per instance; current authorization + kill switch re-checked before every new effect | `ai/plans_service.py`, models | State-transition property tests | M | P3-03 |
| P3-07b | Workflow/activity split: orchestration code deterministic and replayable from step journal; LLM calls and host calls are activities with retry policy | `ai/plans_service.py` | Restart mid-run → resumes from journal test | M | P3-07a |
| P3-08 | Reconciliation worker for `outcome_unknown`: authoritative read-back by operation id; escalate to operator inbox if undeterminable; never blind-retry | `ai/reconciliation.py`, scheduler job | Timeout-after-commit test → exactly one effect | M | P3-07a |
| P3-09 | Human Task Inbox (durable approval tasks): consequence, objects+revisions, before/after, evidence, reversibility, required authority, expiry, alternatives; SSE delivery; approving writes an `ApprovalGrant` | backend + frontend | Inbox item survives restart; approval creates bound grant | M | P3-06 |
| P3-10 | `invoke_skill` reimplementation: resolve `process.id@version` → registry → create/resume run → boundary. Remove "body as data only"; `sql_macro`/`api_call` skill bodies rejected at admission | `agent/tools.py`, `skills/` | Skill invocation produces run + PDP rows; legacy body types rejected | M | P3-07, P2-06 |
| P3-11 | Cancellation semantics: `cancel` = no further work starts; separate `compensate` requires its own authorized action; UI copy reflects both | boundary, frontend | Tests + copy review | S | P3-07a |
| P3-12 | **Pilot end-to-end**: run via UI and via Pulse; tests for restart survival, concurrent edit invalidates approval, duplicate submit no duplicate effect, revoked permission blocks publish, self-approval refused | `tests/pilot/` | All green in CI | L | all above |

**Gate 3:** 16-step demonstration (§6) steps 1–15 pass in staging, both channels.

### Phase 4 — Expertise on the pilot (Weeks 15–18)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P4-01 | Knowledge classes with metadata (source, owner, scope, version, effective period, ingestion time, review status, sensitivity, supersedes): approved policy · process definition · business fact · procedural heuristic · episodic observation · user preference. Conflict rules: mandatory constraints always hold; docs/memories never grant permission | `ai/models/knowledge.py`, `engine/knowledge/` | Schema + conflict-resolution unit tests | M | P3-03 |
| P4-02 | **Applicability-first retrieval** in S2: scope → resolve objects + process state → applicable policy/process versions → mandatory dependencies (never cut by rank) → semantic/BM25 → attach freshness metadata | `cognition/turn/retrieve.py` | Test: mandatory clause present even when ranked low | M | P4-01 |
| P4-03 | Guidance skills as folders (Agent Skills spec): `SKILL.md` frontmatter (name, description, allowed-tools) + `references/`; progressive disclosure (metadata in prompt, body on demand); migrate playbook blocks + `RENDERING_CAPABILITIES` + catalog prose into skills/references | `domain_packs/carbon/skills/` | Prompt token budget drops measurably; behavior on fixtures unchanged or better | M | P2-08 |
| P4-04 | Executable skill = folder whose body references `process.id@version`; `allowed-tools` enforced by PDP, not trusted from file | `skills/schema.py`, PDP | Test: skill listing a tool it isn't allowed → refused at PDP | S | P3-10 |
| P4-05 | Read-only case-inspection capability: current activity, blocker, SLA, applicable SOP clause, event ids — used by Pulse to answer "where are we on R-118?" | host capability + tool | Answer cites run state + event ids | M | P3-07 |
| P4-06 | Clarification policy: ask when object identity ambiguous, evidence missing, or authority unclear; never guess authority | `cognition/turn/draft.py`, prompts | Fixture tests for the three cases | S | — |
| P4-07 | Critic roles made explicit in code/docs: hard host gates (boundary) · deterministic quality checks (missing evidence, malformed plan, invalid refs) · LLM critique (plausibility, alternatives). LLM critique never described as security | `cognition/turn/critic.py`, docs | Docstrings + UI copy updated | S | P1-02 |
| P4-08 | Memory epistemics validation: tests for negation/units/dates/entity identity in contradiction detection; store both claims with `possible_contradiction`; causal auto-link relabeled `temporal_association` unless supported; provenance preserved through compaction | `engine/memory/long_term.py`, `episodic.py`, `compactor.py` | Test suite; docstring "SQLite" fixed | M | — |
| P4-09 | **Business Process Evals v1** for the pilot: 20 scenario classes (normal, missing info, ambiguous object, unauthorized, cross-tenant, self-approval, stale approval, revoked mid-wait, duplicate, timeout-after-commit, worker crash, partial completion, policy change mid-run, prompt injection in retrieved content, malicious tool output, conflicting approved docs, unsupported exception, budget exhaustion, irreversible cancel, correct refusal). Deterministic graders for state + authorization; pass^k over 8 trials | `tests/evals/` | Suite runs nightly; thresholds in CI | L | P3-12 |
| P4-10 | Prompt-optimizer governance: versioned prompt fragments; cannot modify policy text or capability contracts; regression against P4-09 before activation; rollback | `cognition/*prompt*` | Test: attempted policy edit refused | S | P4-09 |
| P4-11 | Zone/salience cleanup: S1 regex used only for urgency weight; effect classification comes from capability contract, not mutation verbs | `turn/salience.py`, `turn/intent.py` | Indirect-mutation fixture passes | S | P3-01 |

**Gate 4:** P4-09 above threshold (proposed: 100% on authorization/forbidden-effect classes; ≥90% outcome; pass^8 ≥ 80%) · Pulse cites `policy_version` on allow/refuse.

### Phase 5 — Event substrate + conformance (Weeks 19–23)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P5-01 | Semantic event schema, OCEL-2.0-compatible: `event_id, event_type, schema_version, occurred_at, recorded_at, tenant_id, app_id, actor_id, execution_identity, source_channel, objects[{type,id,qualifier}], process_instance_id?, correlation_id, causation_id, command_id, idempotency_key, revision_before/after, outcome(requested/authorized/rejected/committed/verified), evidence_refs` | `ai/models/event.py`, docs | Schema + JSON export validates against OCEL 2.0 JSON schema | S | — |
| P5-02 | Transactional outbox in the same DB transaction as the business write; idempotent consumer | `ai/outbox.py`, worker | Crash-between-commit-and-publish test → exactly-once delivery | M | P5-01 |
| P5-03 | Emit events from pilot domain services (UI, jobs, integrations, Pulse) at requested/authorized/rejected/committed/verified | host domain services, boundary | Failed request never yields `committed` (test) | M | P5-02 |
| P5-04 | Backfill from `AuditLog`/`ToolExecution` where semantics suffice; flag gaps as `incomplete` | one-off command | Report of coverage | S | P5-01 |
| P5-05 | OCEL 2.0 JSON export job (for pm4py / external tools) | scheduler job | Export loads in pm4py | S | P5-01 |
| P5-06 | **Conformance checker**: evaluate active definitions' constraints (precedence/response/not_coexist) on the stream; deviations → insights via the boundary (P2-06e); SLA breaches from `response(...within)` | `ai/conformance.py` | Seeded deviation detected; seeded incomplete log → `unknown`, not `violation` | M | P5-03, P3-03 |
| P5-07 | Event-quality report: missing-event rate, incomplete cases, org coverage, observation window — gates any mining | admin API | Report screen | S | P5-03 |
| P5-08 | Conformance screen + Audit Explorer merging PDP decisions, commands, events, approvals, memory writes with provenance and revoke | frontend | Walkthrough; auditor role read-only | M | P5-06 |
| P5-09 | Episodic memory links `process_instance_id` + event ids | `engine/memory/episodic.py`, adapter | Memory rows carry links | S | P5-03 |
| P5-10 | Proactive triggers for the pilot derived from conformance; retire hand-authored raw-SQL triggers for those cases | `proactive/` | Trigger registry shows derived triggers; SQL ones deleted | M | P5-06 |
| P5-11 | Retire two parallel `Conversation/Message` model families (engine mirror vs host `AIConversation/AIMessage`); host canonical | models + adapter | Single family; migration | M | P2-05 |

**Gate 5:** Real deviation surfaced in staging via SSE · false-violation test green · export validates.

### Phase 6 — Governed learning (Weeks 24–30)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P6-01 | `ProcessCandidate` + `SkillCandidate` models with evidence quality (cases complete/incomplete, window, coverage, variants, missing-event rate, conflicts with active definitions, supporting/contradicting examples); Review Queue lists them | models, admin | Queue shows candidate with all fields | M | P5-07 |
| P6-02 | **Mining job**: nightly over events (gated by P5-07): pm4py inductive/Declare miner for control flow, Agent-Miner-style handoff analysis, variant analysis. LLM used *only* to name activities, write rationale, draft definition + `SKILL.md`; raw logs never sent to the LLM | `ai/mining.py`, scheduler | Candidate from staging data with support/confidence; drafts validate against P3-03 schema | L | P6-01, P5-05 |
| P6-03 | Reflection → guidance-skill candidates from trajectories (`trajectory.py`/`consolidation.py`) into the same queue; nothing auto-promotes | `cognition/consolidation.py` | Candidates appear; none active without publisher | M | P6-01 |
| P6-04 | Candidate lifecycle: `candidate → structurally_valid → sandbox_evaluated → reviewed → shadow → published → monitored → deprecated/revoked`; publication bound to artifact digest + test evidence; re-evaluation on dependency change; runtime selects only eligible published versions | `skills/gate.py`, registry | Transition tests; digest mismatch refuses activation | M | P1-06 |
| P6-05 | Publish gate requires **security regression** (red-team suite) + **outcome regression** (P4-09) to pass; report attached to candidate | CI + gate | Test: failing regression blocks publish | M | P4-09 |
| P6-06 | Shadow mode: candidate computes proposals alongside active version; diff reported; no effects | runtime | Shadow run rows; zero PDP `allow` from shadow | M | P6-04 |
| P6-07 | Replace `learned_triggers.py`, `seed_from_domain_pack`, `kg_seeding` (conf 0.3) with pack seeding (`processes/`, `triggers.yaml`) + candidate flow; delete old modules | pack loader, engine | Old modules gone; seeding test | S | P2-08 |
| P6-08 | Negative-example store: rejected candidates with reason feed future mining/reflection | models | Rejected candidate not re-proposed unchanged | XS | P6-01 |
| P6-09 | Second acceptance demo: after two weeks of staging use, queue contains a process nobody wrote down; admin edits/accepts; version increments; nothing active before acceptance | staging | Demo recorded | S | P6-02 |

**Gate 6:** One learned improvement through the full lifecycle · authority-widening test (candidate requesting new tool → refused) green.

### Phase 7 — Scale (Weeks 31+)

| ID | Task | Where | Done when | Size | Dep |
|---|---|---|---|---|---|
| P7-01 | Durable-runtime decision: run the pilot on Temporal (Python SDK) in a spike; compare restart, waits (3-day approval), retries, versioning, ops burden vs hardened Django; ADR | spike repo, `.ai-toolkit/decisions/` | ADR with measurements | M | P3-12 |
| P7-02 | MCP: wire `init_mcp_tools()`; each MCP tool registers as a `Capability` (contract required; annotations untrusted) and executes through the boundary; re-add UI surface | `agent/tools.py`, catalog | MCP tool mutation blocked by PDP test | M | P3-01 |
| P7-03 | Learned-code execution: replace RestrictedPython-as-security with process/container isolation, no credentials, no network, CPU/mem limits — or disable `code_snippet` execution; document decision | `skills/sandbox.py` | Isolation tests (network egress, env read) fail closed | L | — |
| P7-04 | Cedar/OPA evaluation for PDP with wrapper: policy `error` on mandatory policies → refuse; diagnostics logged; admin dry-run/simulation | `ai/pdp.py` | Parity with in-house PDP on decision fixtures | M | P2-07 |
| P7-05 | Domain onboarding playbook: contracts → process → interview → evals; onboard `emissions` (5 read tools already exist) as second domain | pack + docs | Second domain passes Gate 3+4 criteria | L | Gate 4 |
| P7-06 | Portability test: minimal `water` domain pack boots Pulse with own processes/skills; engine untouched; forbidden-term grep still 0 | `domain_packs/water/` | CI job | M | P2-08 |
| P7-07 | PostgreSQL RLS as defense-in-depth with tests using **production roles** (superuser/`BYPASSRLS`/owner caveats) | DB migrations | Cross-tenant test under app role = 0 rows | M | P1-11 |
| P7-08 | Real async: `get_task()` reads run state; submit methods return run id; UI polls honestly | `engine_runtime.py`, frontend | Long-running run visible without holding request | S | P3-07 |
| P7-09 | Frontend prune: `AIAgentPanel.jsx`, `AIActionRunner.jsx`, `useOptimisticItem.js` (already removed: `PulsePane.jsx`, `useDomainManifests.js`) | `carbon-frontend/src/` | Bundle size drop; no imports | XS | — |
| P7-10 | Retire remaining register items: `_get_llm()` deprecated branch, `detect_performance_drift`, legacy `PulseAgent` (keep `AgentResponse` + 2 helpers), `_builtin_plugins()` placeholder, unreachable `except NotImplementedError` in `intelligence.py` | engine/host | `vulture` strict threshold green | M | P0-09 |

---

## 5. Cross-cutting tracks

### 5.1 CI gates (added incrementally; all enforcing by Gate 2)

| Gate | Introduced | Enforces |
|---|---|---|
| CRLF check | P0-03 | Principle 5 |
| Non-empty generator output | P0-04 | Principle 1 |
| Fail-open regex lint | P1-13 | Principle 1 |
| Red-team suite | P1-17 | Principle 2 |
| `import-linter` (engine boundary) | P2-04 | Principle 4 |
| Forbidden-domain-term grep over `engine/**` | P2-08 | Portability |
| `vulture` (report → strict by P7-10) | P0-08 | No dead scaffolding |
| Startup config check | P1-01 | Principle 1 |
| Business-process evals (nightly) | P4-09 | Outcome grounding |
| Security + outcome regression on publish | P6-05 | Principle 3 |
| Domain-pack portability job | P7-06 | Portability |

### 5.2 Dead-code register → phase mapping

| Item | Phase |
|---|---|
| `storage_migration`, `instance_export`, `encryption`, KG cluster, `migration` (**already removed** in prior cleanup) | Done |
| `plan_executor` (NameError), `bm25` stub | P1-15 |
| `MutationGuard.validate` | P1-10 |
| `learned_triggers`, `seed_from_domain_pack`, `kg_seeding` | P6-07 |
| `_get_llm()`, `detect_performance_drift`, legacy `PulseAgent`, `_builtin_plugins`, unreachable except | P7-10 |
| Frontend orphans (`AIAgentPanel`, `AIActionRunner`, `useOptimisticItem`) | P7-09 |
| `get_task()` stub | P1-16 → P7-08 |
| `init_mcp_tools()` | P1-14 (hide) → P7-02 (wire) |

### 5.3 Documentation reconciliation (every gate)

`PULSE-MASTER.md`, `PULSE-0.3-ROADMAP.md`, `INVARIANTS.md`: delete "holds NO memory / stores NO graphs" language (replaced by D1 wording); remove "five mandatory guards"; remove "strong reasoning lane" unless P2-10 keeps it; remove "Pulse Console `/ai/console`" (console = `/admin/ai/*`); mark MCP as Phase 7.

---

## 6. Acceptance demonstrations

**Gate 3/4 — the 16-step pilot demonstration** (illustrative `dq.rule.release`):

1. `process_owner` defines review + publication rules via the registry (interview-kit answers recorded).
2. A different `publisher` reviews and publishes the process version.
3. A user asks Pulse to release a rule.
4. Pulse identifies the exact rule and revision (or asks).
5. Pulse explains missing evidence and required approvals, citing the policy version.
6. Host validates the rule (read-only capability).
7. An independent reviewer approves the exact revision in the Inbox → `ApprovalGrant`.
8. User provides RULE_21 consent.
9. Backend restarts.
10. Run resumes from the journal with approval intact.
11. A concurrent edit bumps the revision → approval invalidated, run returns to `validate`.
12. After fresh review, publish executes exactly once despite an injected retry/timeout.
13. Host verifies `active_revision == approved_revision`.
14. Pulse reports the confirmed outcome with event ids as evidence.
15. Admin sees the full record in the Audit Explorer (PDP rows, commands, events, grant).
16. *(Gate 6)* Pulse later proposes a process improvement into the Review Queue — and cannot publish it itself.

**Additional acceptance tests carried from Deep Audit II** (mapped): admin flips autonomy `human_only ↔ act_confirm` with no deploy (P3-05a) · "where are we on R-118?" answered from case state (P4-05) · kill LLM key mid-admission → nothing promoted (P1-04) · unset store → refuses to start (P1-01) · one door: worker/ReAct/skill/proactive all produce PDP rows (P2-06) · `water` pack boots (P7-06) · 3-day approval survives restart (P3-07b) · every referenced script exists and runs (P2-11).

---

## 7. Risks and things to refuse

| Risk / anti-pattern | Mitigation |
|---|---|
| Building a second reasoning spine (reviving KG planner, new agent framework) | Refuse. Registry + run machine replace it; spine shape unchanged |
| "Autonomous mode" toggle implying standing authorization | Refuse. Autonomy dial sets per-activity level; RULE_21 consent stays; standing auth = separate ADR |
| Treating frequent observed shortcuts as approved process | Mining → candidates only; conformance uses admin-approved definitions |
| Claiming sandbox security from RestrictedPython or module boundaries | P7-03 or disable |
| Reused `sql_validator` treated as sufficient for arbitrary predicates | Structured allowlisted predicates + read-only role + timeout (P1-09) |
| Coverage vanity (9/9 domains with `[]`-quality tools) | Metric = governed capabilities with evals (D5) |
| Two process runtimes in prod | P7-01 decides one |
| Cedar "we use a policy engine" false comfort | Error→refuse wrapper; decision diagnostics logged (P7-04) |
| Docs drifting again | Every gate includes reconciliation; CI checks are the rules |
| Big-bang refactor stalls | Every L split; one file per PR in P2-03/P2-08; gates block, not phases-in-parallel |

---

## 8. This week (first 10 actions, in order)

1. P0-01 recover I1–I8 / L1–L7 text.
2. P0-06 effect-path inventory (this decides how many boundary PRs Phase 2 needs).
3. P0-03 + P0-04 CRLF and `scan.sh` (cheap, removes a silent-failure class immediately).
4. P1-01 `AI_STORE_BACKEND` required.
5. P1-02 critic vetoes `unconfirmed_mutation`.
6. P1-07 worker fan-out runs hooks (interim).
7. P1-09 proactive SQL structured predicates.
8. P0-07 replay fixtures (needed for every later A/B and regression).
9. P0-10 pick the pilot process and name its owner.
10. P0-02 write ADR-0031 with D1–D12 so nobody re-litigates the decisions mid-build.
11. P0-11 QA & measurement framework (the connective tissue for P0-07 / P1-17 / Phase 4 / D9).

---

## 9. Roles (separation of duties)

| Role | Capability | May | May not |
|---|---|---|---|
| `process_owner` | author/edit draft definitions, answer interview kit | define processes, set evidence/exceptions | publish, set org autonomy |
| `policy_owner` | author policies, sign effect-path inventory | edit PDP policy text | author processes, approve tasks |
| `publisher` | publish reviewed versions | activate a version (author ≠ publisher) | author the version they publish |
| `operator` | run ops, handle reconciliation/inbox escalations | resume/cancel runs, reconcile | change definitions or policies |
| `auditor` | read Audit Explorer, conformance | inspect everything read-only | mutate anything |
| `platform_admin` | manage roles, kill switch, CI gates | operational control | bypass PDP or approvals |

---

## 10. Non-goals

- No new agent framework or second reasoning spine.
- No BPMN engine; no two durable runtimes in production.
- No standing autonomous authorization inferred from an autonomy setting.
- No mining output treated as authoritative without a publisher.
- No sandbox security claims from RestrictedPython.
- No chasing domain-tool coverage as a metric; depth (governed capabilities with evals) only.

---

### Closing note

The two audits disagreed on framing more than substance: one said "rebase the invariants," the other said "keep them literally." The unified answer — ports for cognitive state, proposals for business effects, one command boundary for everything — honors both. The rest is sequencing discipline: fail-closed before boundaries, boundaries before the registry, a registry before expertise, events before conformance, conformance before discovery, and discovery before anything Pulse learns is allowed to become authoritative.
