# Screen Spec: Agent — Four-View Cockpit (ADR-0043)

Owner: Master Architect (Pulse) · IA: Workspace → Agent · Route: in-shell `AITaskPanel` (chat-first)
Status: **APPROVED for implementation** · Date: 2026-09-19
Extends: ADR-0043 · ADR-0034 · ADR-0041 · `DESIGN-AGENT-WORKFLOW-AND-UI.md` §6/§10

---

### Story

As an operator, I want **one exclusive hero** at a time (Plan · Run · Canvas · Output)
so I can answer one question without triple-encoding the same job (DAG + steps + Job Map).

### Acceptance (Given / When / Then)

**Happy — exclusive heroes**
- Given an open Agent plan past discovery, When the cockpit mounts, Then exactly one of
  `agent-cockpit-hero-plan` | `agent-cockpit-hero-run` | `agent-cockpit-hero-canvas` |
  `agent-cockpit-hero-output` is in the DOM.
- Given Run is active, When Job Map was previously stacked under the DAG, Then
  `agent-run-job-map-board` is **absent** from the Run surface.

**Lifecycle defaults (soft)**
- Given `pending_approval`, When the plan opens and the user has not manually switched,
  Then segment = **Plan**.
- Given `running` / `paused` / step `awaiting_approval`, Then default = **Run**.
- Given `completed` / `completed_with_gaps` / `failed`, Then default = **Output**.
- Given the user switches segment, When status changes, Then their choice persists
  (RULE_17) until they open another plan.

**Canvas**
- Given a plan with an Agent Job Map (`artifact_type=job_map`, `plan_id`), When Canvas
  is selected, Then `OpsCanvasHost` renders that artifact.
- Given no Job Map yet, Then empty state: “Job Map appears when a plan is created.”
  with retry.
- Do **not** auto-open Canvas during consent — Run owns the grant moment.

**Status chip**
- Given a plan with steps, Then the run header shows a chip such as `3/5 · consent needed`
  (progress + blocker), not color alone (a11y).

**Metrics demotion**
- Metrics is **not** a peer segment. QoS chips live on Run progress; deep Monitor + Audit
  live under Output (collapsible “Run health”). When the run is settled
  (`finished` / `stopped` / `error`), Run health opens by default so audit is
  not hidden behind a click.

**Completed-plan actions (ADR-0043 aligned)**
- Given a settled plan, When the operator is on **Run**, Then a thin CTA strip
  offers Rerun · Edit on Plan · Open Output (no audit table on Run).
- Given Output Actions, Then Rerun · Fork · Edit plan are available for
  terminal statuses including `completed_with_gaps`.
- Given the activity bar **Tasks** icon, When the open plan is completed, Then
  the cockpit soft-defaults to **Output** (not forced onto Run).

**Plan brief verbs (rename vs replan — 2026-09-19)**
- Given Plan inspect chrome, Then affordances are **Rename** · **Replan…** ·
  **Fork** · **Discuss in Chat** (not a single “Edit brief” that replans).
- Given **Rename**, When the operator changes only the title/brief text, Then
  `PATCH` with `mode=rename` updates `user_message` only — no decompose, no
  step wipe, no status change, no diff dialog.
- Given **Replan…**, When confirmed in UI, Then `mode=replan` regenerates steps,
  returns a diff, drops non-pending plans to `pending_approval` (RULE_21), and
  **Cancel** restores the pre-edit snapshot (edits are not stranded on Cancel).
- Given **Discuss in Chat**, Then the Chat composer is seeded with a refine
  draft (plan id + brief; **no** prior final_response body). Chat must not
  silent-PATCH the plan, must not auto-run tools / `invoke_skill` / ReAct, and
  must answer in prose until the operator says Fork or Replan.

**Edges**
- Empty: no plan selected → idle composer hint (existing).
- Error: artifact load failure → human message + Retry on Canvas.
- Forbidden: 403 on artifacts → explain permission (notifyFromError).
- Classic `carbon-ai-cockpit=off` six-tab layout remains as debug escape hatch.

### Journey

Entry (composer / picker) → Clarify (discovery) → **Plan** (approve) → **Run**
(consent / progress) → **Output** (deliverables) ↔ **Canvas** (durable Job Map, optional).

### Composition (Artifact 4)

```
AITaskPanel (chat-first)
 ├─ Header: AgentTaskPicker · status chip · RunToolbar
 ├─ DiscoveryComposer (idle / discovering only)
 └─ AgentCockpit                    ← segments Plan · Run · Canvas · Output
      ├─ Plan  → AgentReviewSurface | PlanDagGraph   data-testid=agent-cockpit-hero-plan
      ├─ Run   → AgentRunSurface (list-first, QoS strip; no Job Map / no DAG / no artifact cards)
      │            data-testid=agent-cockpit-hero-run
      │            (artifact count in progress strip; handoff CTA → Output when finished;
│             post-done CTAs: Rerun · Edit on Plan · Open Output — no ledger table on Run)
      ├─ Canvas → AgentCanvasSurface → OpsCanvasHost
      │            data-testid=agent-cockpit-hero-canvas
      └─ Output → Answer (prose; tool JSON behind Technical details) ·
         artifact cards · Actions (Rerun · Fork · Edit plan · …)
         Empty artifacts: explain that files need an export step.
                   · Run health (Monitor + Audit; auto-open when run settled)
                   data-testid=agent-cockpit-hero-output
```

**Reuse audit**
- [x] Reuse `PlanDagGraph`, `OpsCanvasHost`, `OpsCanvasShelf`, `AgentReviewSurface`, `StepCard`
- [x] No new chart library (ADR-0011 / 0012)
- [x] Feedback via `NotificationProvider` — no `alert()`
- [x] Dialogs: existing `SystemDialog` / MUI Dialog for Library only

### State Matrix (Artifact 5)

| Surface | idle | loading | empty | loaded | error | forbidden |
|---------|------|---------|-------|--------|-------|-----------|
| Cockpit | composer hint | skeleton “Loading task…” | picker empty | four segments | notify + retry | notify |
| Plan | — | — | no steps caption | DAG / review / inspect (Edit brief · Fork when completed) | — | — |
| Run | — | progress “Starting…” | no steps | StepCards + QoS (+ post-done CTAs when settled) | step error chips | — |
| Canvas | — | CircularProgress | empty copy + CTA | OpsCanvasHost | Retry | notify |
| Output | — | artifacts spinner | “Run the plan…” | artifacts + Actions + Run health | notify | — |

Component: segment ToggleButton `default|selected|focus-visible|disabled`.

### Data Contract (Artifact 6)

- `GET /carbon-api/ai/plans/` · `GET /carbon-api/ai/plans/:id/` (existing)
- `GET /carbon-api/ai/artifacts/?artifact_type=job_map&plan_id=` → list; pick `mode=agent` prefer
- `GET /carbon-api/ai/plans/:id/artifacts/` · ledger (existing Output)
- `POST /carbon-api/ai/plans/:id/rerun/` — allowed for `completed` · `completed_with_gaps` · `failed` · `cancelled`
- Errors: network → notifyFromError; 403 → permission copy

### A11y (Artifact 7)

- [x] Segment control `aria-label="Run cockpit view"`; each toggle `aria-label`
- [x] Status chip = text label + color (never color alone)
- [x] Icon buttons keep `aria-label`
- [x] Focus-visible on segment toggles (MUI default)

### Performance (Artifact 8)

- Canvas fetches Job Map only when Canvas segment active (or soft prefetch once plan_id set — max 1 list call, poll ≤2.5s while Run live only if Canvas open)
- No second graph library; PlanDagGraph only on Plan
- Bundle: shell components only; no new deps

### i18n / RTL (Artifact 9)

- [x] Keys in `en/ai.json` + `ar/ai.json`: `cockpitPlan`, `cockpitRun`, `cockpitCanvas`,
  `cockpitOutput`, `jobMapEmpty`, `runHealth`, `statusConsentNeeded`, …
- [x] Directional icons OK (tree/play/map/article) — no chevrons that need mirror for segments
