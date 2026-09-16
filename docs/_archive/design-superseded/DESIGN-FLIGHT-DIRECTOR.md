# DESIGN — Flight Director: Supervisor Layer for the Plan-Execution Pipeline

**Author:** Master Architect
**Date:** 2026-08-24
**Status:** READY — Phase 25-A..25-E spec'd in `TASKS.md`; dispatch per phase with the QA gate between phases.
**Source of truth for implementation:** this doc + the `Phase 25-*` entries in `TASKS.md`.
**Scope:** backend only (25-A..25-E). Phase 26 (frontend QoS report panel) is optional.

---

## 0. Problem (verified against the tree)

The Pulse plan pipeline (`SkillAwarePlanner.decompose` → `ReActLoop` → durable
`Run`/`RunStep`) executes steps in isolation. Evidence from a real
water-consumption run: step 3's worker created rule **#129**, a later step
staged a binding referencing stale rule **#125** → FK failure on confirm.
Nothing reconciles created IDs across steps; nothing asserts the brief was
actually met; closure is prose only.

Verified code facts (file:line):

| Fact | Location |
|------|----------|
| `_execute_step` runs draft→critic→execute per step; no cross-step state | `backend/ai/engine/cognition/plan/loop.py` (~540–780) |
| `_replan_step` only rebuilds the failed step (retry, same args) | `loop.py` `_replan_step` |
| `succeeded` = every critic verdict `pass/pass_with_flag` and no error — NOT brief fulfillment | `loop.py` `run()` |
| `step_contexts` carries prior step text, but nothing validates created IDs | `loop.py` `_build_step_prompt` |
| Retry loop re-queues only `STEP_FAILED` steps, transient-only | `backend/ai/plans_service.py` `_run_plan_frames` (`RETRY_MAX_ATTEMPTS=3`) |
| `_rule_assignments_in_process` duplicate-guards, but FK 500s on stale rule ids are not caught/validated | `backend/ai/host_executor.py` `_rule_assignments_in_process` |
| `RuleFieldAssignmentSerializer.validate` rejects nonexistent rules at staging time — but the LLM stages with stale ids because nothing rewrites them | `backend/dq/serializers.py` (~360–390) |
| `final_response` is narrative; `_finalize_run` stores only status/latency/llm_calls | `loop.py` `_finalize_run` |
| Learning flywheel only updates skill stats for skill-sourced plans; no prompt/playbook auto-update, no learning-job enqueue | `backend/ai/feedback/skill_flywheel.py` |
| `DraftWitness.draft(model=...)` accepts a per-call model override (enables per-step escalation) | `backend/ai/engine/cognition/turn/draft.py:29–39` |
| `ExecutionResult.completed_tools` is the full executed list (fidelity signal) | `backend/ai/engine/cognition/turn/execute.py` + `witnesses.py` |
| `DraftResult.tool_calls` is the full declared list (fidelity signal) | `witnesses.py` |

Correction to the brief: `/memories/repo/*.md` **does not exist** in this
workspace. Conventions live in `.ai-toolkit/shared/*.md` (base-rules,
qa-framework, testing, api-contract, data-layer) and `docs/`. The
`LearningJobsPanel.jsx` frontend panel exists but is a **stub** (read-only
`PulseDataPanel` with no backend endpoint); there is **no `LearningJob`
model**. This design adds the missing durable models.

---

## 1. Architecture

A **`FlightDirector`** supervisor (Carbon-side, `backend/ai/flight_director.py`)
implements a `FlightDirectorWitness` protocol with four surfaces:

```
contract_gate(plan, brief)                     # pre-run (plans_service)
prepare_step(step, ledger, attempts) -> StepPrep   # pre-draft (loop hook)
on_step_completed(step, draft, execution, result, ledger) -> StepFlightVerdict  # post-execute (loop hook)
run_acceptance_checks(run, steps, executor) -> AcceptanceReport                 # post-run (plans_service)
finalize_report(...) + enqueue_learning_from_report(report)                      # post-run (plans_service)
```

**Engine footprint is additive-only.** `ReActLoop` gains one optional
constructor arg `flight_director=None` plus guarded call sites. When `None`
(zero config), behavior is byte-identical to today — existing plan-lifecycle
tests must pass unmodified. Everything else lives Carbon-side in
`flight_director.py` and `plans_service.py`.

**Why loop-level and not purely post-hoc:** fidelity detection needs
`draft.tool_calls` (declared) vs `execution.completed_tools` (executed) at
execution time — only the first completed tool is persisted to `RunStep`.
Stale-reference repair needs the rewrite to happen *before* the LLM stages the
binding. Both are only reachable with an in-loop hook. Acceptance re-queries
and the QoS report are purely Carbon-side post-run.

---

## 2. New durable models (`backend/ai/models/core.py`, one migration `0022`)

### `AcceptanceReport(AppScopeMixin)` — one row per finalized run
| field | type | notes |
|-------|------|-------|
| `id` | CharField(36, PK) | `generate_uuid` |
| `run` | FK `Run` (CASCADE, related_name=`acceptance_reports`) | |
| `status` | TextField | `met` \| `partial` \| `missed` |
| `report_json` | JSONField | per-requirement `{step_id, intent, criterion, verdict, evidence, repairs, escalated}` |
| `metrics_json` | JSONField | `{retries, rewrites, vetoes, escalations, fidelity_failures, total_latency_ms, total_llm_calls, steps_total, steps_met, steps_partial, steps_missed}` |
| `narrative` | TextField | the run's `final_response` |
| `created_at` | DateTimeField(auto_now_add) | |

### `LearningOutcome(AppScopeMixin)` — outcome→learning mapping
| field | type | notes |
|-------|------|-------|
| `id` | CharField(36, PK) | `generate_uuid` |
| `run` | FK `Run` (CASCADE) | |
| `pattern` | TextField | e.g. `"planner: always emit acceptance_criteria"` |
| `target` | TextField | `playbook` \| `prompts` |
| `payload_json` | JSONField | guidance text + provenance |
| `status` | TextField | `queued` \| `applied` \| `skipped` |
| `applied_at` | DateTimeField(null) | |
| `created_at` | DateTimeField(auto_now_add) | |
| constraint | `UniqueConstraint(run, pattern)` | dedup — one outcome per run+pattern |

**FlightDirector state** needs no new table: live in `Run.working_notes["flight"]`
(JSON), alongside the existing `working_notes["audit"]`:

```json
{
  "ledger": {"created": [{"kind": "rule", "id": 129, "name": "Water consumption > 0", "step": 3}],
             "repaired_refs": [{"step": 4, "kind": "rule", "from": 125, "to": 129, "ts": "..."}]},
  "fidelity": {"step": 3, "declared": 2, "executed": 1, "escalated": false},
  "escalations": [{"step": 5, "reason": "acceptance_missed_2_attempts"}],
  "contract": {"ok": true, "findings": [], "suggested_criteria": [{"step_id": 2, "criterion": {...}}]}
}
```

Register both models in `backend/ai/models/__init__.py` and `backend/ai/admin.py`.

---

## 3. FlightDirector behavior

### 3.1 Contract gate (pre-run, `plans_service._run_plan_frames`)
- Extract artifact nouns from the brief (deterministic: look for "table",
  "rule", "field(s)", "binding", "report", "export" + quoted/backticked names
  like `water_volume_m3`).
- If any noun has no covering step (no step whose `intent`/`tool_args` mention
  it) → `findings.append({kind, noun, missing: true})`.
- **Auto-suggest `acceptance_criteria`** per step when the plan omits them,
  using deterministic templates (see 3.4). Store in
  `working_notes.flight.contract.suggested_criteria` and merge into
  `plan_json.steps[i]["acceptance_criteria"]` (service-owned key the engine
  ignores, exactly like `instructions`).
- The gate **never blocks** execution — it records. Blocking is product
  decision; recording is the supervisor's job.

### 3.2 Working-memory ledger + stale-reference validation (in-loop)
- `parse_output(tool_output)` extracts created entities from common shapes:
  `{"id": N}`, `{"data": {"id": N}}`, `{"status_code": 201, "data": {...}}`,
  `{"bindings": [{"id": ...}]}`, `{"table": {...}}`, `{"artifact_id": ...}`,
  keyed by `kind` inferred from the endpoint/tool (`dq/rules`→rule,
  `dataschema/tables`→table, `rule-assignments`→binding, `export_document`→artifact).
- `prepare_step(step, ledger, attempts)`:
  1. For each reference arg key (`rule`, `rule_id`, `data_table`, `table_id`,
     `data_field`, `dq_rule_ids`, `module_id`) present in `step.tool_args`:
     - id **in ledger** → valid, no-op.
     - id **not in ledger** → authoritative existence check via read-only GET
       (list rules/tables). If the id exists on the host → pre-existing, valid.
       If it does not exist AND earlier steps created exactly one entity of
       that kind whose name overlaps the step's intent → **rewrite the arg to
       the actual id** (`repair_kind="stale_reference"`). Otherwise → append
       instruction "the referenced id N is invalid — list current
       {kind}s and use the real id of the entity created in step X" and mark
       the step for repair.
  2. Returns `StepPrep(corrected_tool_args, extra_instructions, model_override,
     repair_kind, repair_detail)`.
- `on_step_completed(...)` updates the ledger from `execution.completed_tools`
  (all of them), records `repaired_refs`, and runs the fidelity guard (3.3).

### 3.3 Worker-fidelity guard (in-loop)
- `declared = len(draft.tool_calls)`; `executed = len(execution.completed_tools)`.
- A step whose `tool_name` is set is expected to produce exactly ≥1 tool call.
  - `declared > executed` → fidelity failure:
    - attempt 1 (non-mutation step or idempotent reads): re-run the step with
      `extra_instructions = f"{declared - executed} declared action(s) did not run: <names>. Execute them all in this turn."`
    - attempt 2 still failing → escalate **that step only**:
      `model_override = getattr(settings, "AI_FLIGHT_DIRECTOR_ESCALATION_MODEL", "gpt-4o")`
      (threaded into `DraftWitness.draft(model=...)`), mark `escalated`, count metric.
    - mutation steps NEVER auto re-run (RULE_21) — fidelity failure on a
      mutation escalates straight to the report as `partial` + human-review flag.
  - `declared == 0 and executed == 0 and step.tool_name is not None` →
    orchestrator/no-op guard: record `fidelity.no_op`, force a re-draft once
    with instruction "call {tool_name} — do not answer in prose".

### 3.4 Acceptance criteria (deterministic templates, per `tool_name`)
| tool_name | default criterion |
|-----------|-------------------|
| `create_dq_rule` | `{"type": "created_entity", "kind": "rule", "expect_status": 201}` |
| `call_host_api` (POST) | `{"type": "created_entity", "kind": "host", "expect_status": 201}` |
| `call_host_api` (GET) | `{"type": "read_ok", "expect_status": 200}` |
| `export_document` | `{"type": "artifact", "expect_artifact": true}` |
| table-creating step (tool_args has `fields`) | `{"type": "table_fields", "fields": <args.fields names>}` |
| reasoning step (`tool_name` None) | none (skip) |

Explicit `acceptance_criteria` supplied by the planner/user override defaults.

### 3.5 Acceptance checks + repair (post-run, Carbon-side)
- `run_acceptance_checks(run, steps, executor)` re-queries read-only:
  - `created_entity` → GET rules/tables; assert entity exists with the id from
    the ledger; evidence = `{query, matches}`.
  - `table_fields` → GET table detail; assert **exact field set** vs criterion
    (brief: "exactly the 4 planned fields"); mismatch → `partial` + actual diff.
  - `artifact` → assert `RunArtifact` rows exist for the step.
- Verdict per requirement: `met | partial | missed`.
- **Repair loop**: `missed` → build `repair_instructions` with the actual diff
  → re-draft + re-execute the step (read-only-safe, non-mutation only) → up to
  `AI_FLIGHT_DIRECTOR_MAX_REPAIRS` (default 2) → still failing → escalate
  (step flagged, `escalations` metric +1), report `partial`.
- Overall status: all met → `met`; any partial → `partial`; any missed without
  repair → `missed`. Un-repaired `missed` requirements surface to the user,
  never silently.

### 3.6 QoS closure + grow loop (post-run, `plans_service`)
- `finalize_report(run, steps)` writes the `AcceptanceReport` row
  (requirements + metrics + narrative) and appends `flight` state to
  `working_notes`.
- `enqueue_learning_from_report(report)` — deterministic pattern matchers:
  - report has any step missing `acceptance_criteria` → `"planner: always emit acceptance_criteria"` (target `playbook`)
  - `metrics.fidelity_failures > 0` → `"worker: never stop before all declared calls run"` (target `playbook`)
  - `ledger.repaired_refs` non-empty → `"planner: resolve created ids from prior step outputs"` (target `playbook`)
- Apply = upsert `PlaybookBlock(block_type="flight_director", title=pattern,
  content=guidance, version=N+1 if exists, provenance=run.id)` and mark the
  `LearningOutcome` `applied` with `applied_at`. Dedup via the
  `(run, pattern)` unique constraint; non-terminal runs no-op (mirrors
  `feed_run_feedback`).

---

## 4. New API endpoints (all owner-scoped, CBAC via `host_user_id`)

| Route | Action | Returns |
|-------|--------|---------|
| `GET /carbon-api/ai/plans/{id}/qos/` | `PlansService.get_qos_report` | `{"report": {status, requirements[], metrics, final_response, supervision}}` — from `AcceptanceReport` row, computed on the fly for legacy runs without one |
| `GET /carbon-api/ai/plans/{id}/flight/` | `PlansService.get_flight_state` | `{"supervision": {ledger, repairs, escalations, fidelity, contract}}` from `working_notes.flight` |

RULE_23: endpoint payloads and UI copy describe outcomes
("acceptance report", "3 of 4 requirements met"), never engine terms.

---

## 5. Files

### Create
- `backend/ai/flight_director.py` — FlightDirector + dataclasses + ledger + gates + checks + report + learning
- `backend/ai/tests/test_flight_models.py` — model defaults/constraints (Phase 25-A)
- `backend/ai/tests/test_flight_director.py` — unit: ledger parse/validate/rewrite, contract gate, criteria templates, fidelity (Phase 25-B)
- `backend/ai/tests/test_flight_director_integration.py` — stale-id repair journey, no 500; loop default unchanged (Phase 25-B)
- `backend/ai/tests/test_flight_acceptance.py` — acceptance pass/fail/repair/escalate (Phase 25-C)
- `backend/ai/tests/test_flight_api.py` — qos/flight endpoints + RBAC (Phase 25-C)
- `backend/ai/tests/test_flight_learning.py` — learning dedup + playbook upsert (Phase 25-D)

### Modify (additive-only for engine)
- `backend/ai/models/core.py` — 2 models; `backend/ai/models/__init__.py`; `backend/ai/admin.py`
- `backend/ai/migrations/0022_flight_director.py` — generated
- `backend/ai/engine/cognition/plan/loop.py` — optional `flight_director=None` + guarded hooks only
- `backend/ai/plans_service.py` — contract gate, pass FD into `_execute_plan_once`, finalize report, `get_qos_report`/`get_flight_state`
- `backend/ai/plans_api.py` + `backend/ai/plans_urls.py` — `qos/`, `flight/` routes
- `backend/config/settings.py` or `backend/ai/engine/core/config.py` — settings are optional; defaults live in `flight_director.py` via `getattr(settings, ..., default)` — **no settings change required**

### DO NOT TOUCH
- `backend/ai/engine/**` except the single additive `loop.py` hook (no behavior change when `flight_director=None`)
- `backend/dq/**`, `backend/dataschema/**` — read-only via existing serializers + `CarbonHostExecutor`
- `docker-compose.yml`, `manage.sh`, DB engine (PostgreSQL localhost:5432 stays), `backend/ai/feedback/skill_flywheel.py`

---

## 6. Settings (optional, defaults in code)
- `AI_FLIGHT_DIRECTOR_ESCALATION_MODEL` (default `"gpt-4o"`)
- `AI_FLIGHT_DIRECTOR_MAX_REPAIRS` (default `2`)

---

## 7. QA gates per phase (see TASKS.md Phase 25-* for the exact commands)

Per-phase green gate (worker-verified, Master-Architect-reviewed before the
next dispatch): phase tests pass + `pytest dq -q --maxfail=5` (38 tests) +
`pytest ai -q --maxfail=5` still green + `makemigrations --check --dry-run`
clean + `manage.py check`.

Formal 4-layer evidence (qa-validator, Phase 25-E): L1 structural (check,
migrations) → L2 security (qos/flight outsider 403 + unauth 401 with real
JWT) → L3 functional (integration journey: water-consumption brief with a
stale rule reference → reference repaired → QoS report `met`) → L4 (UI only
if Phase 26 ships). Every claim carries terminal output + evidence ids.

---

## 8. Deferred / out of scope
- Frontend QoS panel (Phase 26, optional) — depends on Phase 25-C endpoints.
- Full-plan replan on acceptance failure (this design repairs per-step).
- Auto-updating planner/worker *prompts* from outcomes — the grow loop updates
  Playbook blocks; prompt injection is a follow-up (playbook blocks are the
  curated seam).
