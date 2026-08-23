# ADR-0013 — Next-Gen AI Agent Platform Gap Closure (5 gaps)

- **Status:** Accepted
- **Date:** 2026-08-21
- **Deciders:** Master Architect
- **Area:** cross-cutting

## Context

The "next-gen AI agent platform" proposal was assessed against the existing
Carbon AI Workspace. ~90% already mapped to shipped code (durable execution,
manifest-driven domain apps, enterprise graph canvas, KG provenance). Five
gaps remained and were implemented as one workstream:

1. **Output-quality drift** — no observability for how agent outputs trend over
   time or drift below an acceptable threshold.
2. **Bounded retry/backoff** — a failed plan step either ran once or failed
   permanently; no bounded, deterministic retry that still respects consent.
3. **Plan templates** — settled plans could be re-run but not promoted into a
   reusable, durable template.
4. **Run comparison** — no way to diff two runs of the same plan side-by-side.
5. **Non-data domain adapters** — the domain-protocol seam only hosted
   *data-trust* domains (emissions/water/mdm/data_product); finance/HR/customer
   operations verticals had no surface.

Binding constraints (unchanged): no edits under `backend/ai/engine/**` (call
public seams only), no new Django apps (ADR-0008), migrations only when
justified, and the two-surface split (user-facing Workspace vs admin-facing
`/admin/ai/*`).

## Decision

1. **Output-quality drift (Gap 1).** Read-only admin panel over
   `KgQualityScore`, `KgFeedbackRecord`, and `DqFeedbackEvent`, surfaced via
   `OutputQualityTrendView` (`ai/observability_api.py`) and
   `OutputQualityPanel.jsx` at `/admin/ai/output-quality`. `DqFeedbackEvent` is
   *not* `AppScopeMixin`, so it is scoped manually on `user_id`/`org_unit_id`.
2. **Bounded retry (Gap 2).** Retry logic lives in `plans_service.py` (NOT the
   engine). `_execute_plan_once` extracts one ReAct-loop pass with a fresh
   SQLAlchemy session per attempt; `_run_plan_frames` retries failed steps up to
   3 times with deterministic exponential backoff (no jitter) and **never
   bypasses the consent gate** — if any step is `awaiting_approval`, retry stops.
3. **Plan templates (Gap 3).** New `PlanTemplate` model in the existing `ai`
   app (ADR-0008 forbids new *apps*, not new models). `promote_template` /
   `list_templates` / `create_from_template` on `PlansService`; literal
   `templates/` routes are declared **before** `"<str:pk>/"` so they win.
4. **Run comparison (Gap 4).** `DurableExecutionService.compare_runs` aligns two
   runs' `RunStep` ledgers by `step_index`; `GET /ai/runs/compare/?a=&b=` and a
   `RunTimelinePanel.jsx` diff view render diverging steps (status/error/added/
   removed).
5. **Non-data domain adapters (Gap 5).** `finance.py`, `hr.py`, `customer.py`
   are **manifest-only** `DomainAIOperations` subclasses — advisory/drafting
   only (`chat` + `report_draft`), no table-bound types, `validate_task_payload`
   rejects `table_id`. Registered in `register_builtin_domains()`.

## Alternatives Considered

- **Rewrite the agent engine for each gap** — rejected; the no-engine-edit rule
  and the existing public seams (plans service, durable service, domain
  protocol, observability registry) already express every capability.
- **A generic "job" abstraction for finance/HR/customer** — rejected; these are
  non-data verticals, so a full data app (tables, DQ, isolation prefixes) would
  add surface with no data to guard.
- **Per-run diff via raw timeline event diffing** — rejected; aligning by
  `step_index` on `RunStep` rows is deterministic and matches the durable facts,
  unlike timestamp-fragile event-log diffing.

## Consequences

- **Positive:** five capabilities closed without touching the engine, without a
  new app, and with only one justified migration (`0019_plan_template`).
- **Negative / trade-off:** retry re-uses the existing `RunStep` statuses
  (pending/failed) rather than a bespoke attempt ledger; non-data domains are
  advisory-only by design and will need their own storage if they ever gain
  tables.
- **Do NOT re-try:** diffing two runs by diffing serialized timeline event lists
  (timestamp drift makes it noisy); putting retry/backoff inside the engine;
  registering a data-bound task type (dq_*/nl_query) on a non-data vertical.

## References

- `backend/ai/observability_api.py`, `backend/ai/plans_service.py`,
  `backend/ai/durable_service.py`, `backend/ai/domain/{finance,hr,customer}.py`
- `backend/ai/migrations/0019_plan_template.py`
- `carbon-frontend/src/pages/admin/ai/{OutputQualityPanel,RunTimelinePanel}.jsx`
- `carbon-frontend/src/shell/AITaskPanel.jsx` (Templates tab)
- ADR-0008 (no new apps), ADR-0016 (domain-neutral manifest seam),
  ADR-0012 (thin domain adapters)
