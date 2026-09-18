# DESIGN — Resilient Agent Workflow Engine + Agent UI Remake

Status: ACCEPTED (ADR-0034) · Author: Master Architect (Pulse) · Date: 2026-09-14 · Updated: 2026-09-17
Scope: (A) a real resilient workflow engine with per-step controls; (B) a full Agent UI remake.

> **Implementation status (2026-09-17):** Board ~**92%** weighted (W+U).
> Engine W-1…W-7 shipped (wait timers, replay goldens, hard-cancel mid-step).
> UI U-1…U-4 largely done (token/status consolidation + journey-12 retry/skip e2e).
> See canvas `pulse-agent-workflow-board` and §7.
> Remaining polish: classic-tab fallback removal · SSE edge badge · compensate UX.

---

## 1. Problem & Goals

Two problems, one initiative.

**Workflow engine.** Today a "task plan" is a *linear list of steps with `depends_on`
edges* plus optional parallel groups. It cannot branch, loop, react to results, heal
itself, or return partial results. When one step fails the whole run fails (as the AASHE
research run did). There are plan-level controls (approve/run/pause/resume/fork/stop/
compensate/retry) but **no per-step controls**.

**UI.** The Agent panel exposes **6 top-level tabs** — Tasks, Run, Monitor, Results,
Templates, Scheduled — inside a single 1,983-line `AITaskPanel.jsx`. Monitor / Results /
Run overlap; Templates + Scheduled are power-user features occupying prime real estate.
The result is noisy, inconsistent, and not user-friendly.

### Goals
1. A **typed workflow graph** with branching (choice), parallel fan-out, loops (map/while),
   wait, human-in-the-loop, sub-workflows, and terminal nodes.
2. **Per-node resilience**: retry policy (attempts, backoff, jitter, retryable classes),
   `catch`/on-error routing, timeout, compensation (saga), and **partial completion**.
3. **Self-healing**: an `observe` node that can bounded-replan the remaining graph when a
   step fails unrecoverably (gated, never for authority).
4. **Per-step toolbar**: stop / resume / cancel / retry / skip on every step, gated by the
   step's state and RULE_21 consent for mutations.
5. A **clean, consistent Agent UI** — one cockpit, not six tabs.
6. **Backward compatible**: today's linear+depends_on+parallel plans are a strict subset;
   the durable journal, replay, resume, and fail-closed boundary are preserved.

---

## 2. Research — top approaches and what we adopt

| Source | Key idea | Adopt |
|---|---|---|
| **Temporal / durable execution** | Workflow vs Activity split; deterministic replay from an event history; retry policies; signals; timers | Already partially present (journal + workflow/activity split). Extend retry policy per-node; keep deterministic replay. |
| **AWS Step Functions (ASL)** | Explicit state types: `Task`, `Choice`, `Parallel`, `Map`, `Wait`, `Pass`, `Succeed`, `Fail`; per-state `Retry`/`Catch` | Adopt the **state/node taxonomy** and `Retry`/`Catch` as the schema backbone. |
| **BPMN 2.0** | Gateways: exclusive (XOR), parallel (AND), inclusive (OR), event-based; boundary error events | Adopt gateway semantics for `choice`/`parallel`; boundary error = `catch`. |
| **Saga pattern** | Compensating transactions for partial rollback of committed effects | Already present (`compensate`); wire it as a node-level `on_error` target. |
| **LangGraph** | Graph of nodes with **conditional edges + cycles**, checkpointer for resume | Adopt conditional edges + bounded cycles for agentic loops + self-heal. |
| **Netflix Conductor** | JSON-defined DAG workflows, task workers, partial success | Confirms a **declarative JSON graph** + worker execution is the right shape. |

**Decision:** a **declarative JSON workflow graph** (ASL-inspired node taxonomy + BPMN
gateway semantics + Temporal-style deterministic replay + Saga compensation + LangGraph
conditional edges/cycles for self-heal). No new runtime dependency — implemented on the
existing durable engine.

---

## 3. Current state (verified)

- `Run` / `RunStep` (`ai/models/core.py`): `depends_on_json`, `retry_count`, `step_kind`
  (workflow|activity), `status`, `outcome`, `last_error`, `operation_id`.
- `workflow.py`: deterministic driver — earliest eligible activity whose `depends_on` are
  committed; retry cap 3.
- `plans_service.py`: sequential + `parallel_group`; bounded exp-backoff retry for transient
  failures; `compensate` (reversal, separate approval); `cancel`; `replay_step`.
- `durable_service.py`: resume / replay / fork / timeline. `step_journal.py`: append-only
  journal + deterministic replay fold.
- Plan schema (`planner.py`): `PlanStep`, `PlanPhase(strategy)`, `Plan(phases)`.
- Statuses — Run: `pending_approval, approved, running, paused, completed, failed,
  cancelled, resumed, replaying`. Step: `pending, running, completed, failed, skipped,
  awaiting_approval`.
- Endpoints (`ai/plans/<pk>/`): discover, approve, decline, run, steps/confirm,
  steps/decline, steps/<step_id>/ (GET), pause, resume, fork, stop, compensate, ledger,
  timeline; `runs/<id>/resume`, `replay`.

**Gap:** no conditionals/loops/guards, no per-node retry/catch policy, no self-heal, no
partial-complete, no per-step control endpoints.

---

## 4. Part A — Resilient workflow engine

### 4.1 Node taxonomy (extends `PlanStep`, backward compatible)

A plan becomes a **graph of typed nodes**. Existing `task` steps are unchanged; new
`node_type` defaults to `task` so old plans validate as-is.

```
node_type ∈ {
  task,        # run a tool/skill/agent (today's PlanStep)
  choice,      # XOR gateway: evaluate guards, take first matching edge
  parallel,    # AND gateway: fan out to N branches, join on all/any/quorum
  map,         # for_each over a collection → run a sub-graph per item (bounded)
  loop,        # while(guard) run body, bounded max_iterations
  wait,        # timer / until-condition
  human,       # human-in-the-loop task (approval / input) — RULE_21
  subflow,     # invoke a named sub-workflow (process.id@version)
  observe,     # self-heal: inspect state, optionally bounded-replan remainder
  succeed,     # terminal OK
  fail,        # terminal error
}
```

### 4.2 Edges & guards

Edges carry an optional **guard** — a pure, sandboxed boolean expression over a
whitelisted context (prior step outcomes, counts, error classes). No arbitrary code:
guards are a small deterministic expression grammar (`==, !=, <, >, in, and, or, not`,
dotted field access) evaluated by a pure evaluator (RULE_20 safe). `choice` takes the
first edge whose guard is true (plus a `default` edge). This is the XOR gateway.

### 4.3 Per-node resilience policy

```jsonc
"retry":   { "max_attempts": 3, "backoff": "exponential_jitter",
             "base_ms": 1000, "max_ms": 10000, "retry_on": ["transient"] },
"catch":   [ { "on": ["permanent","timeout"], "next": "compensate_node" } ],
"timeout_ms": 60000,
"compensation": "reverse_write_node"   // saga hook
```

- **retry_on** uses the existing transient/permanent taxonomy (`classify_llm_error` +
  tool error classes). Backoff reuses the jittered policy we just added.
- **catch** routes to a fallback branch/compensation instead of failing the run.
- **compensation** is the Saga hook — reuses `compensate` (separate approval, RULE_21).

### 4.4 Self-healing (`observe`)

On an unrecoverable node failure whose `catch` routes to an `observe` node, the engine
calls the planner with (goal, completed outcomes, failure) to propose a **repaired
sub-graph for the remainder only**. Bounded (`max_heals`, default 1), never modifies
approved policy or authority (P4-10 governance), and the repaired graph re-enters the
approval gate if it adds mutations. Deterministic under replay (the heal decision is
journaled).

### 4.5 Partial results / partial completion

A run whose terminal state is reached with some branches failed-but-caught completes as
**`completed_with_gaps`** (new run status). Each node emits partial artifacts to the
journal as it finishes, so the UI streams partial results live and the final synthesis
explicitly reports "what we have / what's missing." No all-or-nothing failure.

### 4.6 Determinism & journal

Every control-flow decision (guard evaluation, chosen edge, loop iteration, heal) is a
**journaled event**, so replay is deterministic and the timeline is auditable. The
append-only journal and replay fold are extended with the new event kinds; no rewrite.

### 4.7 Backward compatibility

`Plan.phases(strategy=sequential|parallel)` + `depends_on` map onto the graph:
sequential phase → chain of `task` edges; parallel phase → a `parallel` node. A migration
shim compiles old `plan_json` into the graph form at load; nothing in the DB must change
on day one (graph stored in the existing `plan_json`/`run_state` JSON).

---

## 5. Part B — Per-step controls

### 5.1 Step control state machine

| Step status | Allowed controls |
|---|---|
| `pending` | skip, cancel |
| `running` | pause, cancel |
| `paused` | resume, skip, cancel, edit-instructions |
| `awaiting_approval` | confirm, decline, skip |
| `failed` | retry, skip, compensate, cancel |
| `completed` | (view only) · compensate if it wrote |
| `skipped` | (view only) |

Mutating controls (retry of a write, compensate) require RULE_21 consent — the boundary
already enforces this; the UI surfaces the confirm.

### 5.2 Endpoints (additive, mirror existing plan-level verbs)

```
POST ai/plans/<pk>/steps/<step_id>/retry/
POST ai/plans/<pk>/steps/<step_id>/skip/
POST ai/plans/<pk>/steps/<step_id>/cancel/
POST ai/plans/<pk>/steps/<step_id>/pause/
POST ai/plans/<pk>/steps/<step_id>/resume/
```

Each stages a journaled control event and re-enters the durable driver from the affected
node (never re-executes completed effects — replay fold guarantees idempotency). Reuses
`plans_service` + `durable_service`; no bypass of the boundary.

---

## 6. Part C — Agent UI remake

### 6.1 Principles
Fewer surfaces, one cockpit, consistent tokens, progressive disclosure, action where the
user is looking.

### 6.2 New information architecture

Collapse **6 tabs → a 2-pane cockpit + a secondary Library**:

```
┌ Agent ─────────────────────────────────────────────────────────────┐
│  [Chat] [Agent]                                   ⚙  ⋯  ✕           │
├──────────────┬──────────────────────────────────────────────────────┤
│ TASKS (rail) │  RUN COCKPIT (single, contextual)                     │
│  • search    │  ┌ Run header: title · status · global toolbar ─────┐ │
│  • new task  │  │  ▶ Run  ⏸ Pause  ⤾ Resume  ■ Stop  ↻ Retry  ⑂ Fork│ │
│  ▸ task A ✓  │  └──────────────────────────────────────────────────┘ │
│  ▸ task B ⟳  │  [ Plan ]  [ Steps ]  [ Output ]  [ Metrics ]  (seg.) │
│  ▸ task C ✗  │  ── Steps (default) ─────────────────────────────────  │
│              │   ① Search benchmarks      ✓  done    ⋯(toolbar)      │
│              │   ② Fetch AASHE PDF        ⟳  running ⏸ ■             │
│              │   ③ Extract figures        �ದ  pending  ⏭ ✕            │
│              │      └ guard: if ② has results                        │
│              │   ✗ ④ Compare peers        ✗  failed   ↻ ⏭ ⚑         │
│              │  ── live output streams inline under the active step ─ │
└──────────────┴──────────────────────────────────────────────────────┘
```

- **Top-level tabs drop from 6 → the cockpit’s segmented control (Plan / Steps / Output /
  Metrics).** "Monitor" and "Results" become the **Metrics** and **Output** segments of the
  same run — no separate tabs.
- **Templates** and **Scheduled** move into a **Library** overflow menu (⋯) — they are
  power features, not primary navigation.
- **Per-step toolbar** appears on hover/selection of each step row, driven by §5.1.
- **Plan** segment renders the graph (`PlanDagGraph` upgraded to show branches/loops/guards).
- One design-token pass for spacing/typography/status colors (consistent chips: done=success,
  running=primary+spinner, pending=neutral, failed=error, skipped=muted, awaiting=warning).

### 6.3 Components
- New `RunCockpit.jsx` (replaces the tab body of `AITaskPanel`), `StepRow.jsx`
  (+ `StepToolbar.jsx`), `RunHeaderToolbar.jsx`, `TaskRail.jsx`, `LibraryMenu.jsx`.
- Reuse: `PlanDagGraph` (extended), `AITaskPlanCard` (slimmed → header), streaming hooks in
  `aiWorkspace.js`.
- Delete/absorb: the 6-tab `Tabs` block; Monitor/Results/Templates/Scheduled tab bodies move
  into segments/Library.

---

## 7. Part D — Phased plan (worker dispatch + gates)

Each phase: dispatch a worker with a non-shallow spec; Master verifies personally
(`manage.py check`, targeted tests, full `ai` suite, 3 engine lints; frontend: `vitest` +
build). No phase ships shallow.

| Phase | Deliverable | Status | Done when / remaining |
|---|---|---|---|
| **W-1** | Graph schema + validator + compile shim | **DONE** | Schema + round-trip tests |
| **W-2** | Guard expression evaluator | **DONE** | Grammar + injection tests |
| **W-3** | Driver choice/parallel/map/loop + journal | **DONE ~98%** | Replay goldens + wait timers shipped |
| **W-4** | Retry/catch/timeout + compensation | **DONE ~95%** | Hard-cancel mid-step I/O; compensate UX polish |
| **W-5** | `observe` self-heal | **PARTIAL ~85%** | Heuristic heal shipped; LLM repair optional |
| **W-6** | `completed_with_gaps` | **DONE ~95%** | Status + UI chip; artifact stream polish |
| **W-7** | Per-step control endpoints | **DONE ~95%** | Endpoints + StepToolbar (+ Done List) |
| **U-1** | Chat-first cockpit | **PARTIAL ~85%** | AgentStage shipped; classic 6-tab fallback remains |
| **U-2** | StepToolbar + live controls | **DONE ~98%** | Vitest + journey-12 Playwright retry/skip |
| **U-3** | PlanDagGraph branches/guards + segments | **DONE ~92%** | Live chosen/unchosen edge tint |
| **U-4** | Design-token consistency pass | **DONE ~90%** | STEP_STATUS single source + FONT chips |

**Sequencing:** W-1→W-2→W-3 are the engine core (blocking). W-4..W-7 build on W-3. UI
U-1 can start after W-7 endpoints exist (or against mocks). Ship in vertical slices so each
phase is demoable.

---

## 8. Risks & mitigations
- **Determinism regressions** — every control decision journaled; replay-golden fixtures per
  node type gate each phase.
- **Scope creep in self-heal** — bounded `max_heals=1`, gated by approval + P4-10 (no policy/
  authority edits).
- **UI regression** — keep behavior parity tests; ship cockpit behind a flag until U-4.
- **Backward compat** — compile shim; DB schema unchanged initially (graph in existing JSON).

## 9. Testing / verification per phase
Backend: `manage.py check` · targeted + full `ai` pytest · `import-boundary`, `failopen`,
`forbidden-term` lints · replay-golden fixtures. Frontend: `vitest` unit/interaction ·
`npm run build` · targeted Playwright e2e for retry/skip/branch.

---

## 10. Follow-on — Pulse Ops Canvas (Job Map)

**ADR-0041** accepts a durable Job Map board beside Chat/Agent (closed typed kit;
WorkObjectives + FlightDirector surfaced; optional attach to People/EduOS records).
Does **not** replace ADR-0014 mode split or the Agent cockpit lifecycle — canvas is
the reopenable artifact host. Research: `pulse-ops-canvas-research.canvas.tsx`.
Implementation starts at ADR-0041 Phase 1 (host shell + canvas shelf).
