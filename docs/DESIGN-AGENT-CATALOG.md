# Design — Unified Agent Catalog & Agentic Workflow Evolution

**Owner:** Master Architect
**Status:** Ratified (dispatchable — see TASKS.md W3-C → W3-G)
**Applies to:** `backend/ai/` + `carbon-frontend/src/`
**Depends on:** W3-A / W3-B (Agentic Task Orchestration — DONE)

---

## 1. Purpose

W3-A/W3-B shipped a reviewable *plan lifecycle* (brief → pending_approval →
approve → SSE streamed run → step consent → audit ledger). That work answered
*"can a user safely run a multi-step agentic task?"*.

This design answers the follow-on: *"can we see, evolve, resume, and trust the
agentic system?"*. It closes five gaps identified in the gap analysis:

| Gap | Today | Target |
|---|---|---|
| **Plan editing** | Plans are immutable once created | `PATCH` brief → replan with **diff**; per-step edit |
| **Lifecycle control** | approve/run/stop only | add **pause**, **resume**, **fork-from-plan** |
| **Catalog visibility** | `AgentRegistry` is DB-only, no CRUD/UI | REST CRUD + federated discovery + UI |
| **Durability** | Run/RunStep persist, but no crash-resume/replay surface | **resume**, **replay** (deterministic from ledger) |
| **Observability** | Ledger endpoint only | Plan DAG live view, agent topology, run timeline |

Everything below reuses existing engine seams. **No new Django apps** (ADR-0008).
**No changes under `backend/ai/engine/`** — this design only *calls* public seams.

---

## 2. Invariants (binding on all phases)

1. **ADR-001 declared topology.** Agents are roles, handoffs are declared edges.
   No LangGraph, no free-form agent chat. The catalog *reads* the declared graph;
   it never invents edges.
2. **RULE_21 consent.** Every mutation (edit, fork, resume, replay, catalog
   write) is explicit and user-initiated. No auto-mutation.
3. **CBAC everywhere.** Every plan/run/catalog row is owner-scoped via
   `host_user_id` (plans) or the equivalent instance/user guard (catalog).
4. **No engine edits.** `plans_service.py` calls
   `SkillAwarePlanner.decompose`, `ReActLoop`, `CarbonHostExecutor` — it does not
   reimplement them. `makemigrations --check --dry-run` stays clean.
5. **Fail-visible errors.** Engine frame types/statuses are *product terms*
   (`step_start`, `step_result`, `paused`, …) — never class names (RULE_23).
6. **Token budget.** Edits/replans are bounded: replan diffs ≤ current plan size;
   no full-context rebuild unless the brief changed structurally.
7. **Fan-out artifact refs.** `WorkerPool.fan_out` returns artifact references,
   not inline payloads. Visualization reads refs, never re-runs work.
8. **Two surfaces, never mingled.** Carbon has TWO distinct AI frontends:
   - **AI Workspace / Pulse** (`src/shell/`) — where end users **engage** with
     AI: conversations, running tasks, reviewing/editing/forking their own plans,
     seeing their own plan progress.
   - **AI Admin** (`src/pages/admin/ai/`) — where admins **manage & observe** the
     system: agent/skill catalog CRUD, handoff topology, run ledger/timeline,
     monitoring.
   The shared backend API serves both, but a frontend phase targets ONE surface
   only. A graph that shows a *user's own* plan belongs in the Workspace; a graph
   that shows the *system's* agents/runs belongs in Admin.

---

## 3. Architecture

```
        ┌──────────────────────────────┐      ┌──────────────────────────────┐
        │   AI WORKSPACE  (shell/)     │      │     AI ADMIN  (admin/ai/)    │
        │  engage: run/plan/consent    │      │  manage+observe: catalog/    │
        │  W3-F plan controls + DAG    │      │  topology/timeline  W3-G     │
        └───────────────┬──────────────┘      └───────────────┬──────────────┘
                        │ apiFetch (RULE_10)                  │ apiFetch
        ┌───────────────▼─────────────────────────────────────▼──────────────┐
        │        plans_api.py (extended) · catalog_api.py (new) ·            │
        │                  observability_api.py (extended)                   │
        └───────────────────────────────┬────────────────────────────────────┘
                                        │ delegates
        ┌───────────────────────────────▼────────────────────────────────────┐
        │  plans_service.py (extended) · catalog_service.py (new)            │
        └──────┬──────────────────────────────────────┬──────────────────────┘
               │ calls                                │ reads
      ┌────────▼────────┐                   ┌─────────▼─────────┐
      │   engine seams  │                   │   durable store   │
      │  SkillAware     │                   │  Run / RunStep    │
      │  Planner        │                   │  Agent/Handoff    │
      │  ReActLoop      │                   │  Skill/Admission  │
      │  WorkerPool     │                   │  Trajectory       │
      └─────────────────┘                   └───────────────────┘
```

**Key rule:** the service layer is the *only* place that composes engine seams.
Views → service → engine. Nothing else reaches across. **The frontend surfaces
stay separate** — Workspace for engagement, Admin for management/observation.

---

## 4. Phase decomposition

> **Naming note:** W3-A (backend) and W3-B (frontend) of "Agentic Task
> Orchestration" already exist and are DONE. New work is W3-C → W3-G.
> **Surface rule:** backend phases (W3-C/D/E) are surface-agnostic. Frontend
> phases are surface-bound: **W3-F = AI Workspace** (`shell/`), **W3-G = AI
> Admin** (`pages/admin/ai/`). Never mix the two in one phase.

### W3-C — Plan lifecycle: edit / pause / resume / fork (backend)

Extend `plans_service.py` + `plans_api.py`.

- **`PATCH /plans/{id}/`** — edit `brief` (and optional `step_deltas`).
  - If plan is `pending_approval` → re-run `decompose()` → return **diff**
    (`added`/`removed`/`changed` steps) for review; do NOT auto-approve.
  - If plan is `approved`/`running`/`paused` → require a **replan gate**: return
    the diff as `pending_approval`-style review payload; user must re-approve.
  - Per-step edit: `PATCH /plans/{id}/steps/{step_id}/` (fields allowed: `title`,
    `instructions`, `depends_on`) with the same diff-review rule.
- **`POST /plans/{id}/pause/`** — only from `running`; sets `STATUS_PAUSED`.
  Cooperates with step-consent (a paused consent step is already effectively
  paused — `pause` must not corrupt `awaiting_approval` steps).
- **`POST /plans/{id}/resume/`** — from `paused` or `approved` (reuses
  `_RUNNABLE_STATUSES`); re-enters `run_plan_stream` with `resume_run_id=plan_id`.
- **`POST /plans/{id}/fork/`** — clone plan JSON + brief into a new `Run` row
  (`parent_plan_id`/`forked_from`), status `pending_approval`. Fork is a *copy*,
  not a link; no shared mutable state.

**Files:** `backend/ai/plans_service.py` (modify), `backend/ai/plans_api.py`
(modify), `backend/ai/tests/test_plans.py` (extend).

**Gate:** `python -m pytest ai/tests/test_plans.py -q --maxfail=5 -p no:cacheprovider`;
`manage.py check`; `makemigrations --check --dry-run` clean.

### W3-D — Unified Agent Catalog (backend + UI)

Expose the existing `AgentRegistry` (`Agent`, `AgentHandoff`, `Skill`,
`SkillAdmissionLog` models) as a federated, read-mostly catalog.

**Backend (`catalog_service.py` + `catalog_api.py` — new):**

- `GET /catalog/agents/` — list roles (orchestrator/researcher/planner/critic/
  domain_specialist) with their declared handoff edges + skills.
- `GET /catalog/agents/{id}/` — one agent: metadata, incoming/outgoing handoffs,
  admitted skills, last admission log.
- `GET /catalog/topology/` — the **declared graph** as nodes+edges (feeds W3-G).
- `POST /catalog/agents/` + `PATCH/DELETE /catalog/agents/{id}/` — admin-gated
  registration (maps to `register_agent` / `remove_agent`). RULE_21: explicit.
- `GET /catalog/skills/` — skill catalog + admission status.
- **Federated discovery:** an in-memory registry index (built at request time
  from `AgentRegistry.list_agents`) that merges the DB catalog with any
  `ToolPlugin`/`WorkflowPlugin` extensions discovered via `plugins.py`. The merge
  is read-only; the DB remains the source of truth.

**Surface:** **Admin** (`pages/admin/ai/`). The catalog UI upgrades the existing
`AgentsPanel.jsx` + `SkillsPanel.jsx` (currently thin `PulseDataPanel`
wrappers) into a real read/write catalog — NOT a new parallel page. This phase
is backend-only; the Admin UI lands in W3-G.

**Files:** `backend/ai/catalog_service.py` (new), `backend/ai/catalog_api.py`
(new), `backend/ai/urls.py` (route), `backend/ai/tests/test_catalog.py` (new).

**Gate:** `pytest ai/tests/test_catalog.py`; `manage.py check`;
`makemigrations --check --dry-run` clean.

### W3-E — Durable execution: crash-resume / replay / observability (backend)

- **`POST /plans/{id}/resume/`** already re-enters execution; make it
  **crash-safe**: on `resume`, reconcile `RunStep` rows (mark any
  `running`/`awaiting_approval` steps correctly; skip completed steps).
- **`POST /plans/{id}/replay/`** — deterministic replay from the `RunStep`
  ledger + `Trajectory` rows. Replay is **read-only** (produces a timeline,
  never re-executes). Returns step-by-step `{step, status, started_at,
  finished_at, artifacts}`.
- **`GET /plans/{id}/timeline/`** — run timeline (start/end per step, Gantt-ready
  ranges) for W3-G.
- **`GET /runs/`** — list runs (resume/replay entry points) across plans.

**Files:** `backend/ai/plans_service.py` (modify), `backend/ai/plans_api.py`
(modify), `backend/ai/observability_api.py` (extend), `backend/ai/tests/
test_plans.py` (extend).

**Gate:** `pytest ai/tests/test_plans.py`; `manage.py check`; no new migrations.

### W3-F — AI Workspace: plan controls + live plan DAG (frontend, `shell/`)

User-facing **engagement** surface. Reuse existing d3 primitives — no new deps.

- **Extract `src/components/graph/ForceGraph.jsx`** from
  `KnowledgeGraphPanel.jsx` (d3-force + drag/zoom/pan + hover + click + legend),
  so it's shared by both surfaces.
- **Plan edit/pause/resume/fork controls** wired into `AITaskPlanCard.jsx` /
  `AITaskPanel.jsx` (W3-C endpoints), with the diff-review gate from
  `PATCH /plans/{id}/`.
- **`PlanDagGraph.jsx`** — live plan DAG: nodes=steps, edges=`depends_on`,
  node color=status (pending/running/completed/failed/awaiting). Polls the
  *current user's* plan during a run.
- **`PlanMermaidPreview.jsx`** — Mermaid `graph` preview of the plan DAG for the
  review card (reuses `MarkdownMessage` lazy mermaid rendering; `mermaid` is
  already a dependency).

**Files:** `carbon-frontend/src/components/graph/ForceGraph.jsx` (new,
extracted), `PlanDagGraph.jsx`, `PlanMermaidPreview.jsx` (new); wire into
`src/shell/AITaskPlanCard.jsx` + `AITaskPanel.jsx`.

**Gate:** `npx vitest run` workspace graph specs; `npm run lint`; `npm run build`.

### W3-G — AI Admin: catalog + topology + run timeline (frontend, `admin/ai/`)

Admin **manage & observe** surface. Reuses `ForceGraph.jsx`.

- **Catalog CRUD UI** — upgrade `AgentsPanel.jsx` + `SkillsPanel.jsx` (from thin
  `PulseDataPanel` wrappers) to a real table + detail drawer: agent role, edges,
  skills, status; admin-gated create/edit/remove (RULE_21).
- **`AgentTopologyGraph.jsx`** — renders `GET /catalog/topology/` (agents +
  declared handoffs) — the system's declared graph.
- **`RunTimeline.jsx`** — Gantt-style timeline from `GET /plans/{id}/timeline/`
  + `GET /runs/` — cross-user run observation for admins.

**Files:** `carbon-frontend/src/pages/admin/ai/AgentsPanel.jsx` (upgrade),
`SkillsPanel.jsx` (upgrade), `src/components/graph/AgentTopologyGraph.jsx`,
`RunTimeline.jsx` (new).

**Gate:** `npx vitest run` admin graph specs; `npm run lint`; `npm run build`.

---

## 5. Sequencing & dependencies

```
W3-C (plan lifecycle) ──┐
                        ├──► W3-E (resume/replay/timeline) ──► W3-G (admin observe)
W3-D (catalog backend) ─┘         ▲                             ▲
        │                         │                             │
        │                         │        (topology + timeline)
        │                         └─────────────────────────────┘
        └──────────────► W3-F (workspace plan controls + DAG)  ←── W3-C
```

- **Backend first:** W3-C and W3-D are independent — dispatch in parallel.
- **W3-E** depends on W3-C (resume/pause already exist there).
- **W3-F** (Workspace) depends on W3-C (plan endpoints) — no admin dependency.
- **W3-G** (Admin) depends on W3-D (catalog/topology) + W3-E (timeline).

---

## 6. What we deliberately do NOT do

- No LangGraph/LangChain/AutoGen dependency — ADR-001 + ADR-0004 hold.
- No new Django app — ADR-0008.
- No re-running of work for visualization — read refs only.
- No auto-approval of replans — RULE_21.
- No raw d3 in page components — go through `ForceGraph.jsx`.
