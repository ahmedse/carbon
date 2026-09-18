# ADR-0041 — Pulse Ops Canvas (Job Map)

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** Master Architect (Pulse Master)
- **Area:** frontend + backend (cross-cutting)

## Context

Cursor Canvas proved that agents should emit **durable visual boards** beside
chat — not walls of markdown. Enterprise peers go further: ServiceNow attaches
AI activity to the **work record**; SAP Joule Work uses goal **Spaces**; Palantir
grounds agentic work in an **ontology** of objects, actions, and processes.

Pulse already has graph primitives (`EnterpriseGraph` / `PlanDagGraph`), typed
answers (`AnswerEnvelope`), WorkObjectives (API + orphaned panel), and
FlightDirector (backend-only). It does **not** have a reopenable artifact host
that answers: *what is this task about, what does it require, and where is it?*

Without that surface, Chat stays prose-heavy, Agent stays stage-bound cockpit
tabs, and ops users (People / Leave / EduOS GradeVance) never see a job map on
the record they already work in.

Research board: workspace canvas `pulse-ops-canvas-research.canvas.tsx`.

## Decision

### 1. Product name: **Pulse Ops Canvas** (primary template: **Job Map**)

A durable, reopenable board sibling to Chat/Agent conversation — not a
replacement for either mode (ADR-0014 stands).

### 2. Closed component kit — never free model HTML/JS

The agent emits **typed blocks** only (extend AnswerEnvelope + graph nodes):
stats, tables, charts, DAG, gates, CBAC chips, caveats, sources, todos/diffs.
Same safety posture as envelope synthesis. No Claude-style arbitrary sandbox.

### 3. Five Job Map layers (same template; mode changes rights)

| Layer | Content |
|-------|---------|
| **Intent** | Ask · success criteria · Chat vs Agent contract |
| **Job map** | Steps · deps · owners · CBAC · entities/tools touched |
| **Live run** | Progress · FlightDirector QoS · blockers · consent |
| **Evidence** | Envelope tables/charts · sources · audit ids |
| **Outcome** | Result · SoR links · canvas id for reopen/rerun |

- **Chat Job Brief** = layers Intent + Job map + Evidence + Outcome — **read-only**.
- **Agent Job Map** = all layers — runnable with **RULE_21** consent rails.

### 4. Artifact host (workspace)

1. Promote `AIArtifactBrowser` into a real **canvas shelf** (list · reopen ·
   rerun metadata).
2. Primary render host: docked pane on `EnterpriseGraph` / Agent Run·Review
   **or** a workspace-level side column sibling to the main Chat/Agent area
   (choose one in Phase 1 implementation; do not fork two hosts).
3. Wire **WorkObjectives** into the shelf (goal list → open Job Map).
4. Surface **FlightDirector** QoS / acceptance on the Agent Job Map Live-run
   layer (no steward-only-only placement).

### 5. Attach to work objects (ops users)

Job Maps may open from domain records (ServiceNow pattern), not only Pulse:
Employee, Leave, PayrollRun, Correspondence, GradeVance assessment — via
Inspector / record action, CBAC-scoped. Admin Command Center (ADR-0036) remains
**steward** IA; it is not the coworker Job Map.

### 6. When-to-canvas (skill / policy)

Emit or open a Job Map when the turn is multi-hop, plan/run, authz-sensitive
synthesis, audit, or ops briefing. **Do not** canvas short lookups (mirrors
Cursor canvas skill discipline).

### 7. Ontology-lite grounding

Map nodes bind to **ECF entities**, `instance.yaml` catalog tools, and CBAC —
not a second Palantir Foundry. No new charting deps (ADR-0011 / 0012).

### 8. Phasing (implementation order)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | This ADR + non-goals locked | **DONE** |
| 1 | Host shell + canvas shelf | **DONE** (`OpsCanvasShelf`) |
| 2 | Agent Job Map template (plan loop emit) | **DONE** (`create_plan` emit) |
| 3 | Chat Job Brief (advisory) | **DONE** (`_maybe_emit_chat_job_brief`) |
| 4 | Record attach (People / EduOS) | **DONE** (Employee 360; EduOS same pattern) |
| 5 | Instance skills for layouts + CBAC-gated share/snapshot | **DONE** (skill md + share API) |

Evidence: `docs/pulse/evidence/OPS-CANVAS-ADR-0041-2026-09-18.md`

### Follow-through (same ADR, post-MVP)

| Item | Status |
|------|--------|
| FlightDirector QoS → `live_run.qos` | **DONE** (`patch_live_run_qos`) |
| EduOS GradeVance attach | **DONE** (Run workbench) |
| Agent run Job Map button | **DONE** (`AgentRunSurface`) |
| SkillRegistry DB admission | N/A — filesystem skill + auto-emit hooks; guidance packs remain F1a deferred |

## Alternatives Considered

- **Free HTML/JS artifacts (Claude Artifacts)** — rejected; CBAC/audit/RULE_21
  require a closed kit.
- **ChatGPT-style document canvas only** — rejected; ops need process/job maps,
  not just editable prose.
- **Fold everything into Admin Control Plane** — rejected; steward ≠ coworker
  (ADR-0036).
- **Replace Agent cockpit with canvas only** — rejected; Brief/Plan/Run lifecycle
  (ADR-0014) stays; canvas is the durable board *alongside*.
- **New React Flow / Recharts canvas stack** — rejected; ADR-0011/0012.

## Consequences

- **Positive:** higher information bandwidth; legible task requirements; FlightDirector
  and WorkObjectives finally have a home; Chat and Agent share one map language;
  ops users see AI work on the record.
- **Negative / trade-off:** new host + typed schema work; risk of over-canvasing
  simple Q&A (mitigated by when-to-canvas policy).
- **Do NOT re-try:** arbitrary model HTML; putting Job Map only in admin; merging
  Chat and Agent modes to “get a canvas”; second graph library.

## References

- Research: `~/.cursor/projects/home-ahmed-ws-carbon/canvases/pulse-ops-canvas-research.canvas.tsx`
- ADR-0012 Enterprise Graph · ADR-0014 Chat/Agent split · ADR-0019 Inspector ·
  ADR-0032 ECF · ADR-0034 resilient workflow graph · ADR-0036 control plane IA
- `carbon-frontend/src/shell/{AIWorkspace,AgentRunSurface,EnvelopeMessage,AIArtifactBrowser}.jsx`
- `carbon-frontend/src/components/{graph/EnterpriseGraph,ai/WorkObjectivesPanel}.jsx`
- `backend/ai/{envelope.py,flight_director.py,work_objectives_api.py}`
- Market: Cursor Canvas · ServiceNow Now Assist panel · SAP Joule Work Spaces ·
  Palantir AIP Ontology
