# ADR-0043 — Agent Four-View Cockpit (Plan · Run · Canvas · Output)

- **Status:** Implemented (V1–V6) · **V6 Plan graph-structure** (2026-09-20)
- **Date:** 2026-09-19 · amended 2026-09-20 (V5 + V6)
- **Deciders:** Master Architect (Pulse seat)
- **Area:** frontend | cross-cutting (Pulse Agent UI)
- **Extends:** ADR-0014 (Chat/Agent split), ADR-0034 (workflow + cockpit segments), ADR-0041 (Ops Canvas / Job Map)
- **Does not touch:** Nibras / EduOS product UIs (EduOS may *attach* Job Maps per ADR-0041 §5)
- **Screen Spec:** `docs/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`
- **Remediation master:** `docs/pulse/PULSE-AGENTIC-UX-REMEDIATION-PLAN.md` Track E

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
| **Plan** | What will we do? | **`PlanDagGraph` structure mode** (graph hero) · tooltips · click → light drawer · Approve / Cancel / Discuss | Stage wall; Finished/run status; full Job Map; step consent banners; artifact downloads; wall of secondary verbs |
| **Run** | Where are we *now*? | **Chronicle** · progress · RULE_21 consent hero · transport · Step expand for I/O · **Run health** (Analyst) | Full Job Map; DAG; deliverable cards |
| **Canvas** | What’s the durable story of this job? | `OpsCanvasHost` **story-first** (goal → stages → here → outcome); tools/QoS progressive | Play/pause chrome; raw `RULE_` as Operator copy |
| **Output** | What did we produce? | Answer · artifact cards (Preview / Download / Delete) · Actions | Run health accordion; re-listing every tool as a second DAG |

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
| **V4** | Metrics demotion + Output polish (acceptance / artifacts) | Run health on Output — **DONE** (superseded placement by V5) |
| **V5** | Operator calm: Plan stage-first; Run chronicle + Run health; Canvas story-first; Output purity + file Delete | Track E · Vitest + Screen Spec — **DONE** |
| **V6** | Plan graph-only structure (no stage wall / no Finished); tooltips; click drawer | Vitest AgentReviewSurface + PlanDagGraph structure — **DONE** |

Frontend worker required Screen Spec (`docs/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`) before V1 code — **DONE**. V5 amends that Spec.

### V5 Operator calm (binding deltas)

1. **Plan primary chrome ≤3:** Approve plan · Cancel plan (was Decline) · Discuss in Chat. Fork / Rename / Replan live under **More**.
2. **Run health** moves from Output → **Run** (collapsible; auto-open when settled still allowed). Output stays Answer + filings only.
3. **Canvas** remains `OpsCanvasHost` (no new library) but Operator copy is story-first; tool / CBAC / QoS / rule ids demoted behind expand or Analyst density.
4. **Artifact Delete** on Output cards uses existing `DELETE ai/artifacts/:id/` with confirm (ux-patterns destructive).
5. Autonomy dial still density-only — never bypasses RULE_21.

### V6 Plan structure (binding — supersedes V5 Plan body)

1. **Plan hero = graph only** (`PlanDagGraph mode="structure"`). No stage list; no Show/Hide graph toggle.
2. **Do not mingle Run status on Plan:** no Finished / Running / Needs approval chips or status legend on Plan nodes. Run owns execution state.
3. **Tooltips** on nodes and edges. **Click** opens a **docked scrollable pane inside the graph** (never an overlay Drawer) with Operator-light markdown via **`RichContent`** (`MarkdownMessage` — the shared Chat-grade formatter for Agent surfaces and domain apps).
4. **Plan chrome is a toolbar under the cockpit tabs** (`AgentPlanToolbar`): read-only label · Approve / Cancel / Discuss · More for Fork / Replan. **Do not** edit the prompt/brief by clicking the label — changing the brief is **Replan** or **Discuss in Chat** only.
5. Execution-mode DAG (status + analyst dock) remains for classic hatch — not the Plan segment default.
6. **Structure layout is top→bottom** (parallel siblings side-by-side); fit-by-width so nodes stay readable and vertical space is used.
7. **Shapes follow BPMN / flowchart conventions** (`planGraphShapes.js`): roundedRect=orchestrator task, parallelogram=researcher, hexagon=domain specialist, chamfer=critic, stadium=planner; diamonds for choice/parallel; circles for wait/observe/end. Edges: solid sequence, dashed conditional, open arrowhead for guarded.

## Alternatives Considered

- **Keep stacking DAG + Job Map** — rejected; triple encoding; fails progressive disclosure.
- **Canvas replaces Plan graph** — rejected; graph is for edit/approve topology; Job Map is durable narrative (ADR-0041).
- **Keep Metrics as peer segment** — rejected as peer of Canvas; QoS belongs on Run; deep metrics on Run health / Canvas live_run (V5: not on Output).
- **Return to six classic tabs** — rejected; ADR-0034 U-1 stands; this ADR refines segments only.
- **New DAG library for Canvas** — rejected; ADR-0011/0012.
- **Hide Cancel plan behind More** — rejected; destructive cancel must stay one click from Approve (ux-patterns + UX-R2).
- **Remove Replan from product** — rejected; demote only (Discuss covers soft refine).

## Consequences

- **Positive:** one question per view; Consent visible; Job Map readable; Operator chrome calm (V5).
- **Negative / trade-off:** one more product rename (Steps→Run); Metrics no longer a top segment; Analyst must expand for DAG / Run health / tool args.
- **Do NOT re-try:** gluing Ops Canvas under the live DAG; dual always-on plan lists; Output-as-ops-console.

## References

- Design narrative: `docs/DESIGN-AGENT-WORKFLOW-AND-UI.md` §6 (amended), §10
- Board: `~/.cursor/projects/home-ahmed-ws-carbon/canvases/pulse-agent-four-view-ia.canvas.tsx`
- ADR-0014 · ADR-0034 · ADR-0041 · ADR-0011 · ADR-0012 · ADR-0036
- Code today: `AITaskPanel.jsx` (segments), `AgentRunSurface.jsx`, `OpsCanvasHost.jsx`, `OpsCanvasShelf.jsx`
