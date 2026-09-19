# ADR-0043 — Agent Four-View Cockpit (Plan · Run · Canvas · Output)

- **Status:** Implemented (V1–V4)
- **Date:** 2026-09-19
- **Deciders:** Master Architect (Pulse seat)
- **Area:** frontend | cross-cutting (Pulse Agent UI)
- **Extends:** ADR-0014 (Chat/Agent split), ADR-0034 (workflow + cockpit segments), ADR-0041 (Ops Canvas / Job Map)
- **Does not touch:** Nibras / EduOS product UIs (EduOS may *attach* Job Maps per ADR-0041 §5)
- **Screen Spec:** `docs/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`

## Context

ADR-0034 collapsed six Agent tabs into a cockpit with segments
**Plan · Steps · Output · Metrics**. ADR-0041 then introduced the durable
**Ops Canvas Job Map** (intent · job map · live run · evidence · outcome).

Live remake glued the Job Map **under** the DAG on the same scroll as live
progress and the step list. Operators now see the **same job three times**
(graph nodes ≈ step list ≈ Job Map steps) plus QoS/consent chrome. That violates
ADR-0034 §6.1 progressive disclosure and makes ADR-0041 look like “more Chat
artifacts” instead of a durable board.

Master evaluation (2026-09-19): density is an **IA bug**, not a missing feature.

## Decision

### 1. Four exclusive views (one primary surface at a time)

Replace the shipped segment set with:

| View | Owns this question | Primary surface | Forbidden on this view |
|------|--------------------|-----------------|------------------------|
| **Plan** | What will we do? | `PlanDagGraph` (+ edit/approve/fork affordances) | Full Job Map board; consent banners; artifact downloads |
| **Run** | Where are we *now*? | Progress · blockers · RULE_21 consent CTA · `StepToolbar` · active-step I/O | Full five-layer Job Map; historical evidence tables |
| **Canvas** | What’s the durable story of this job? | `OpsCanvasHost` Job Map (ADR-0041 layers) | Play/pause chrome; per-step toolbar clutter |
| **Output** | What did we produce? | Run artifacts · envelope/tables · SoR links · ledger summary | Re-listing every tool as a second DAG |

Exactly **one** of Plan / Run / Canvas / Output is the hero body. A thin
**status chip** (e.g. `8/10 · consent needed`) stays in the run header so
orientation survives view switches.

### 2. Lifecycle defaults (progressive disclosure)

| Plan / run state | Default view | Why |
|------------------|--------------|-----|
| `pending_approval` / discovery | **Plan** | Review graph before RULE_21 execute |
| `running` / `paused` / step `awaiting_approval` | **Run** | Operator console + consent CTA |
| `completed` / `completed_with_gaps` / `failed` | **Output** | Deliverables first; Canvas one click away |
| User explicitly opens board / Artifacts / record attach | **Canvas** | Durable Job Map (ADR-0041) |

Defaults are soft — user segment choice persists (RULE_17) after first manual switch.

### 3. Mapping from today’s code (no second graph library)

| Today | Becomes |
|-------|---------|
| Cockpit segment `plan` | **Plan** |
| Segment `steps` + live strip glued under DAG | **Run** (absorb; remove Job Map from `AgentRunSurface` default body) |
| Segment `metrics` | **Demote** — QoS chips live on **Run** header; deep acceptance report on **Output** / Canvas live_run |
| Segment `output` | **Output** |
| `OpsCanvasHost` under DAG / Artifacts shelf | **Canvas** view + Artifacts shelf + record attach (unchanged hosts) |
| ADR-0034 “Steps” name | Renamed **Run** in product copy |

ADR-0011 / 0012 still bind: reuse `PlanDagGraph` / `EnterpriseGraph` — **no new chart stack**.

### 4. Canvas contract (ADR-0041 unchanged; placement fixed)

- Chat may still emit **Job Brief** (advisory). Agent emits **Job Map**.
- Canvas view renders the conversation/plan’s Agent Job Map; if none exists yet,
  empty state: “Job Map appears when a plan is created.”
- **Do not** auto-open Canvas during consent — **Run** owns the grant moment.
- Record attach (People / GradeVance) remains ADR-0041 §5 — opens Canvas, not Run.

### 5. Non-goals (binding)

- Do **not** show DAG + Job Map + full step list on one scroll.
- Do **not** invent a fifth always-visible pane.
- Do **not** merge Chat and Agent to “get a canvas” (ADR-0014).
- Do **not** put Job Map only in Admin Control Plane (ADR-0036 steward ≠ coworker).
- Do **not** free-form model HTML on Canvas (ADR-0041 closed kit).

### 6. Implementation phasing (workers — Master does not implement)

| Phase | Deliverable | Gate |
|-------|-------------|------|
| **V0** | This ADR + design board accepted | COMMS DECISION + canvas — **DONE** |
| **V1** | Segment rename + exclusive hero; remove Job Map from default `AgentRunSurface` stack | Vitest: one hero test-id; no dual board — **DONE** |
| **V2** | Lifecycle default routing + status chip | Soft defaults + `agent-status-chip` — **DONE** |
| **V3** | Canvas segment wires `OpsCanvasHost` by `plan_id`; Artifacts shelf stays | `AgentCanvasSurface` — **DONE** |
| **V4** | Metrics demotion + Output polish (acceptance / artifacts) | Run health accordion on Output — **DONE** |

Frontend worker required Screen Spec (`docs/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`) before V1 code — **DONE**.

## Alternatives Considered

- **Keep stacking DAG + Job Map** — rejected; triple encoding; fails progressive disclosure.
- **Canvas replaces Plan graph** — rejected; graph is for edit/approve topology; Job Map is durable narrative (ADR-0041).
- **Keep Metrics as peer segment** — rejected as peer of Canvas; QoS belongs on Run; deep metrics on Output/Canvas live_run.
- **Return to six classic tabs** — rejected; ADR-0034 U-1 stands; this ADR refines segments only.
- **New DAG library for Canvas** — rejected; ADR-0011/0012.

## Consequences

- **Positive:** one question per view; Consent visible; Job Map readable; ADR-0034 + ADR-0041 stop fighting.
- **Negative / trade-off:** one more product rename (Steps→Run); Metrics no longer a top segment.
- **Do NOT re-try:** gluing Ops Canvas under the live DAG; dual always-on plan lists.

## References

- Design narrative: `docs/DESIGN-AGENT-WORKFLOW-AND-UI.md` §6 (amended), §10
- Board: `~/.cursor/projects/home-ahmed-ws-carbon/canvases/pulse-agent-four-view-ia.canvas.tsx`
- ADR-0014 · ADR-0034 · ADR-0041 · ADR-0011 · ADR-0012 · ADR-0036
- Code today: `AITaskPanel.jsx` (segments), `AgentRunSurface.jsx`, `OpsCanvasHost.jsx`, `OpsCanvasShelf.jsx`
