# DESIGN — Agent Execution Control & Scheduling (F-26 · F-28 · F-29)

**Author:** Product/UX Designer
**Date:** 2026-08-23
**Status:** READY — hand off to Master Architect for decomposition
**Feeds:** `docs/TASK-W6-REMEDIATION-ALL-FINDINGS.md` → Phase W6-D (F-26), W6-E (F-28, F-29)
**Source of truth for UX:** this doc. Backend builds the contract; Frontend composes against these acceptance criteria.

---

## 0. Users & Context

Three features, one surface (Agent mode, `src/shell/AITaskPanel.jsx`), one user type.

**Primary user:** a Carbon operator / analyst who turns a brief into a plan of
AI steps, reviews it, and lets it run against trusted data. They are not
engineers — they think in *outcomes*, not step internals (RULE_23).

**North star:** the user always knows (1) what is running and where it is,
(2) how to stop/steer it safely, and (3) what will happen next — with no
surprises (design-principle 10).

**Existing surface already in tree (reuse, do NOT rebuild):**
- Tabs: `tasks | run | monitor | results | templates` (localStorage key `carbon-ai-task-tab`, RULE_17)
- Plan DAG: `PlanDagGraph.jsx` (nodes = steps, edges = `depends_on`, status-colored)
- Plan controls: `pausePlan`, `resumePlanStream`, `stopPlan`, `forkPlan`, `editPlan`, `editPlanStep` (`src/api/aiWorkspace.js`)
- Consent gate: `PlanDiffReviewDialog.jsx` (diff-review), `confirmPlanStep` / `declinePlanStep` (per-step approve/decline)
- Step editing: `StepEditDialog.jsx` (title / instructions / depends_on)
- Templates: `listPlanTemplates`, `instantiatePlanTemplate`, `promotePlanTemplate`

---

## F-26 — Multi-Agent Parallel Execution

### Story
> As a Carbon operator, I want to see which plan steps are running in parallel
> and how each one is doing, so that I can trust that the plan is moving fast
> without losing the per-step consent controls.

### Acceptance

**Scenario: parallel phase visible in the plan (happy path)**
- Given a plan whose phase declares `strategy: "parallel"` with 3 independent steps,
- When I open the **Run** view during execution,
- Then the DAG renders those 3 steps as one visually-grouped **parallel lane**
  (a single "runs together" band, not 3 separate stacked cards),
- And each step still shows its own status chip (pending / working / done / failed / awaiting approval),
- And steps that complete independently update their own chip without disturbing siblings.

**Scenario: consent is never bypassed (permission edge)**
- Given a parallel step is flagged `is_mutation` + `requires_confirmation`,
- When the other parallel steps reach that step's boundary,
- Then that step stops at `awaiting approval` and shows the Approve/Decline action,
- And its sibling steps are NOT blocked by it — they continue and complete.

**Scenario: a step fails mid-parallel (error edge)**
- Given one parallel step fails while siblings succeed,
- Then the failed step shows a persistent `failed` chip with a one-line, outcome-worded reason and a Retry action,
- And the sibling steps keep their `done` status (no cascade reset),
- And the plan header shows "1 of 3 steps needs attention", not a blanket "failed".

**Scenario: nothing running yet (empty edge)**
- Given a plan is approved but not yet running,
- Then the parallel lanes render from the plan structure (gray/pending) with no live polling.

### Journey (single screen, no navigation)
```
Run view → plan DAG → parallel lane expands on click → per-step detail (status, output, actions)
```
Friction: parallel steps visually stacking under a single lane must not hide the
per-step Approve/Decline. Fix = lane expands inline (progressive disclosure),
consent action remains one click away, never behind two expansions.

### IA / placement
Lives in the **Run** tab of `AITaskPanel.jsx`. No new route, no new sidebar
entry. `PlanDagGraph.jsx` gains a `strategy` lane concept.

### Hand-off
- **Data:** plan/steps already carry `agent_role` (per W6-D) + phase `strategy`.
  Add a `strategy` (and optional `parallel_group`) field to the serialized step
  payload so the DAG can lane-group without a second round-trip.
- **Patterns:** `ux-patterns.md` → "Feedback & System State" (>1s = progress,
  keep rest interactive); "Data Tables & Lists" (status chip + label, never
  color alone).
- **Primitives:** `PlanDagGraph.jsx` (extend, not fork), `Chip`, `Stack`,
  `Collapse` (lane expand), theme `status` colors (design-system RULE 5).
- **RULE_23:** lane/step copy = outcome words ("Gathering the data", "Drafting
  the report"), never "thread pool", "fan-out", "concurrency".

---

## F-28 — Mid-Execution Edits (pause → steer → resume)

### Story
> As a Carbon operator, I want to pause a running plan and adjust what the
> *not-yet-run* steps will do, so that I can course-correct without throwing
> away the work already completed.

### Acceptance

**Scenario: pause a running plan (happy path)**
- Given a plan is running with 5 steps and 2 are complete,
- When I press **Pause**,
- Then the run halts at the next step boundary (never mid-step) and the header shows a `paused` status,
- And the 2 completed steps are locked (read-only, status preserved),
- And the 1 in-flight step is marked `stopped` with its partial output retained,
- And the remaining pending steps become editable.

**Scenario: steer a paused plan (happy path continued)**
- Given the plan is paused,
- When I edit a pending step's instructions (via the existing `StepEditDialog`),
- Then the edit opens the `PlanDiffReviewDialog` consent gate before it is saved (RULE_21),
- And the diff shows exactly the before/after instruction change,
- And saving re-approves only that step — completed steps are untouched.

**Scenario: resume after steering (happy path continued)**
- Given a paused plan with an edited pending step,
- When I press **Resume**,
- Then execution continues from the first pending step,
- And the edited step runs with its new instructions,
- And completed steps are NOT re-run.

**Scenario: pause with a consent step pending (permission edge)**
- Given a step is already `awaiting approval` when I press Pause,
- Then the plan pauses and that step remains at `awaiting approval` (its consent
  is preserved, not auto-approved or auto-declined).

**Scenario: nothing editable (boundary edge)**
- Given a plan has 0 pending steps (all complete or running),
- When paused,
- Then the edit affordance is disabled with a tooltip: "No upcoming steps to adjust."

**Scenario: resume fails (error edge)**
- Given I press Resume and the service cannot continue,
- Then the plan returns to `paused` with an actionable, outcome-worded error and a Retry action — never a dead end.

### Journey
```
Run view (working) → Pause → [steer: edit pending step → diff review → save] → Resume → Run view (working)
```
Drop-off risk: user forgets they are paused and leaves. Mitigation = the
`paused` status is a persistent chip + the Run view shows a "Paused — 2 steps
completed, 2 to go" banner until resume or stop.

### IA / placement
Same Run tab. Pause/Resume/Stop already exist as plan controls; this design
adds *per-pending-step* edit affordances (edit icon on pending step rows) and a
lock/read-only state for completed steps. No new route.

### Hand-off
- **Data:** `pausePlan` already exists. W6-E1 adds a `paused` run transition and
  the ability to `editPlanStep` on *pending* steps while paused (backend). The
  serialized step needs a `runnable_state` (`completed | in_flight | pending`)
  so the UI can lock/edit correctly without inferring from status strings.
- **Patterns:** `ux-patterns.md` → "Destructive & Irreversible" (pause is
  reversible, no confirm needed; stop may ask if work is unsaved); "Forms"
  (preserve input on error).
- **Primitives:** `StepEditDialog.jsx`, `PlanDiffReviewDialog.jsx`, `Chip`,
  `Banner`/`Alert` (paused banner), `IconButton` + tooltip (edit on pending).
- **RULE_21:** every edit still passes the diff-review consent gate; nothing
  auto-applies.

---

## F-29 — Scheduling & Triggers

### Story
> As a Carbon operator, I want to schedule a settled plan to run later (once or
> on a recurring cadence), so that routine work happens without me being there
> to press Run.

### Acceptance

**Scenario: schedule a one-off run (happy path)**
- Given a plan template exists,
- When I choose **Schedule** on it and pick a future date/time,
- Then the schedule is saved and appears in a **Scheduled** list with its
  next-run time, owner, and status (`scheduled`),
- And a human-readable "Runs in X" relative time is shown, not a raw cron string.

**Scenario: schedule a recurring run (happy path continued)**
- Given the schedule form,
- When I pick a recurring cadence (e.g. daily at 09:00, weekly on Monday),
- Then the form shows a plain-language preview ("Every day at 9:00 AM Cairo"),
- And the stored value is a cron expression the backend can execute.

**Scenario: scheduled run materializes (happy path outcome)**
- Given a schedule becomes due,
- Then a run is created and appears in the plan's Run history with the same
  consent/ledger behavior as a manual run,
- And any mutation step still stops at `awaiting approval` — scheduling does NOT
  auto-approve (RULE_21).

**Scenario: no schedules yet (empty edge)**
- Given the user has no schedules,
- Then the Scheduled list shows an empty state with a next action:
  "Schedule a plan to run on its own."

**Scenario: invalid or past time (error/boundary edge)**
- Given I pick a time in the past for a one-off schedule,
- Then the form shows an inline validation error and disables Save (with why),
  never silently accepts it.

**Scenario: ownership scope (permission edge)**
- Given a user views the Scheduled list,
- Then they see only schedules they own (or their org-unit scope), never another
  user's schedule.

### Journey
```
Templates tab → Schedule action → Schedule dialog (once | recurring + time/cadence) → Saved
   → Scheduled list (manage: edit | pause schedule | delete with confirm)
```
Friction: cron is hostile to non-engineers. Mitigation = a preset cadence picker
(daily/weekly/monthly) + plain-language preview; raw cron is progressive-disclosed
for power users only.

### IA / placement
Two touch points in `AITaskPanel.jsx`:
1. **Templates tab** — a "Schedule" action per template row.
2. **A new "Scheduled" list** — either a 6th tab or a section inside Templates.
   **Recommendation:** a 6th tab `scheduled` (RULE_17 — persist to the same
   `carbon-ai-task-tab` key) because schedules are a first-class object, not a
   template attribute.

### Hand-off
- **Data (backend W6-E2):** `RunSchedule` model (cron or one-off `run_at`,
  target template id, owner, org-unit scope), `run_due_schedules` management
  command. New API surface needed for the UI:
  - `listSchedules`, `createSchedule`, `editSchedule`, `deleteSchedule`,
    `pauseSchedule` (a schedule can be disabled without deletion).
  - Each returns a plain-language `preview` string OR the raw cron + enough to
    render the preview client-side (prefer server-side preview to keep one
    source of truth).
- **Patterns:** `ux-patterns.md` → "Forms" (label above, inline validation on
  blur, preserve input); "Destructive" (delete schedule = confirm naming the
  consequence); "Feedback" (save = toast).
- **Primitives:** `Dialog` + `TextField` (or a date/time picker), `Autocomplete`
  for cadence presets, `Chip` for status, `Stack`, theme tokens (RULE_8).
- **RULE_23:** "Runs in 2 days" / "Every weekday at 9:00 AM" — never a bare
  `0 9 * * 1-5` in the default view.
- **No docker** (project rule): cron is documented + run via `manage.sh`, not
  container orchestration.

---

## 3. Cross-feature consistency rules

1. All three features live in the **Agent mode Run/Templates surface** — no new
   routes, no new sidebar entries (ux-patterns: one nav model).
2. Status = **chip + label**, never color alone (design-system RULE 5).
3. Every list/section handles the **4 data states** (loading / error / empty /
   loaded) (design-system RULE 4).
4. **Consent is never auto-bypassed** — parallel fan-out, mid-execution edits,
   and scheduled runs all still stop at `awaiting approval` for mutation steps
   (RULE_21).
5. **Outcome copy only** — no "thread", "fan-out", "cron", "concurrency" in
   user-facing text (RULE_23).

## 4. Definition of Ready (for Master Architect decomposition)

- [x] User role + goal + value — Carbon operator; trust fast, steerable, self-running plans
- [x] Acceptance criteria (happy + empty + error + permission + boundary) per feature
- [x] Journeys mapped (F-26 single-screen, F-28 pause→steer→resume, F-29 schedule→list)
- [x] IA placement — Agent mode tabs only, no new routes
- [x] Data/endpoints identified (see each Hand-off)
- [x] Patterns + primitives identified (existing `PlanDagGraph`, `StepEditDialog`, `PlanDiffReviewDialog`, templates API)
