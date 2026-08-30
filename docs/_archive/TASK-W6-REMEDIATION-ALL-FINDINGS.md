# TASK — W6 Remediation: Solve All Remaining QA Findings

**Role:** Master Architect
**Scope:** Close every finding left open by the W5 QA report
(`docs/TASK-RESULTS-QA-W5-CHAT-AGENT-MODE.md`) and the residual enterprise gaps
from ADR-0013 / the W5 scorecard.

**Status:** PLAN — not yet dispatched.

---

## 0. Findings Register (final truth, re-derived from current code)

Before anything is "fixed", the code was re-inspected. Two P2 findings the QA
report left *open* are actually **already implemented in the tree**. The plan
therefore opens with a cheap **re-verify gate**, not a re-fix.

| ID | Severity | QA claim | Current code reality | Action |
|----|----------|----------|----------------------|--------|
| F-W5-C-01 | P2 | `step.output_type` always `None`; `export_document` missing `store_artifact` | `_infer_output_type` (`plans_service.py:158`) + `_with_output_type` (`:213`) wired into serialization (`:379-380`, `:1644-1645`); `store_artifact` (`:256`) exists; `export_document.py:179` already calls it; `test_artifacts.py` covers store/list/download/CBAC/serialization | **Re-verify live**, add regression test if gap |
| F-W5-RUN-01 | P2 | `GET /ai/runs/compare/` 404 — URL not routed | `durable_urls.py` registers `compare/` (`RunViewSet.as_view({"get": "compare"})`), mounted at `config/urls.py:86` (`ai/runs/` → `durable_urls`); `compare_runs` service exists (`durable_service.py:215`) | **Re-verify live**; fix reload/mount only if still 404 |
| F-25 | Enterprise | Artifact delivery unproven | Full chain present (`store_artifact` + `export_document` + tests) | **End-to-end run** to produce a real downloadable artifact |
| F-W5-TST-01 | P3 | No unit tests for `StepOutputRenderer` / `DiscoveryComposer` | No test files found (confirmed) | Add tests |
| F-W5-TST-02 | P3 | No Monitor/Results tab assertions | Missing (confirmed) | Add assertions |
| F-PRE-01 | P3 | 9 pre-existing FE failures (AIArtifacts×2, AIMessageBubble.feedback×3, AISharedThreads×4) | Still failing | Fix |
| F-PRE-02 | P3 | `LoadoutSheetPage` flaky under parallel runner | Flaky (isolation) | Fix isolation |
| F-26 | Enterprise | Multi-agent coordination | `agent_role` exists; no parallel execution semantics | Implement |
| F-28 | Enterprise | Mid-execution edits | Not in scope | Implement |
| F-29 | Enterprise | Scheduling/triggers | Templates exist; no cron/event triggers | Implement |
| F-21 | P1 (prior) | Migration dependency `integrations.turnkey` → `turnkey` | Backend runs clean (PID alive, `manage.py check` clean) | Re-verify in final gate |
| F-22 | P1 (prior) | Duplicate `datahub.Dataset*` models | Backend runs clean | Re-verify in final gate |

**Guardrail:** F-W5-C-01 and F-W5-RUN-01 are **not to be re-implemented blind**.
They must be *proven* green or *proven* broken first, because the code is
already ahead of the QA snapshot.

---

## Phase W6-A — Re-verify + lock the two P2 findings (BACKEND)

**Worker:** backend-worker (with qa-validator confirming).
**Goal:** Turn "probably fixed in code" into "proven fixed, with a regression
test guarding it."

### A1 — Prove `compare/` is live (F-W5-RUN-01)
1. Hit the live endpoint with a valid admin token:
   `GET /carbon-api/ai/runs/compare/?a=<id>&b=<id>`.
   - **400** = route is live, only missing/invalid IDs → finding closed.
   - **404** = route truly not mounted → check `config/urls.py:86` and restart
     backend (`./manage.sh restart`) — do **not** edit URL files unless the
     mount line is genuinely absent.
2. Add a regression test in `backend/ai/tests/test_durable.py`:
   - `test_compare_runs_returns_aligned_diff` — two owned runs, diverging
     step status → assert `step_diff` entries + `status_changed` flags.
   - `test_compare_runs_rejects_missing_params` → 400.
   - `test_compare_runs_cross_user_denied` → 404 (CBAC).

### A2 — Prove `output_type` inference is live (F-W5-C-01)
1. Inspect a *completed* plan's `steps[].output_type` through the plans API
   (admin token). A step whose `tool_output_json` is structured (table/chart/
   artifact) must carry a non-`None` `output_type`.
   - If `tool_output_json` itself is empty for *all* completed steps, the bug
     is upstream (engine isn't persisting tool output) — escalate to
     `engine_runtime.py` write path, not `_infer_output_type`.
2. Add regression tests in `backend/ai/tests/test_artifacts.py`:
   - `test_infer_output_type_table` → `{"columns": [...], "rows": [...]}` ⇒ `table`
   - `test_infer_output_type_chart` → `{"series": [...]}` ⇒ `chart`
   - `test_infer_output_type_artifact` → `{"download_url": ...}` ⇒ `artifact`
   - `test_infer_output_type_empty_returns_none` → `None`
   - `test_serialize_run_injects_output_type` → step payload has both
     `output_type` and `tool_output._output_type`.

### A3 — Verification gate (W6-A)
- `pytest backend/ai/tests/test_artifacts.py backend/ai/tests/test_durable.py -q` → all green.
- Live `curl` for `compare/` returns **400** (not 404).
- Live plans payload shows a non-`None` `output_type` on a structured step.

### DO NOT TOUCH (W6-A)
- `plans_service.py` `_infer_output_type` / `_with_output_type` / `store_artifact`
  — already correct; only add tests.
- `durable_urls.py` + `config/urls.py:86` — already correct; only verify.
- Do **not** run `test_store_execute.py` (long-running; not part of this gate).

---

## Phase W6-B — Frontend test debt (FRONTEND + DEBUGGER)

**Worker:** frontend-worker (implementation), debugger-fixer (the 9 legacy
failures + flaky isolation).
**Goal:** 797/797 → 100% green (no `-t` skips) on `vitest run`.

### B1 — Add `StepOutputRenderer` tests (F-W5-TST-01)
- New `carbon-frontend/src/features/ai/test/StepOutputRenderer.test.jsx`:
  - table shape → renders a table (MUI Table / DataGrid, no raw `<pre>`).
  - chart shape → renders the chart primitive (no crash on empty series).
  - artifact shape → renders download link(s) with `href`.
  - json fallback → renders structured `<pre>`.
  - text fallback → renders prose.
- **DataGrid v8 hazard:** `valueFormatter` is **positional**, not destructured
  — do not write tests that assume destructured args.

### B2 — Add `DiscoveryComposer` tests (F-W5-TST-01)
- New `carbon-frontend/src/features/ai/test/DiscoveryComposer.test.jsx`:
  - empty conversation → shows starter suggestions.
  - `needs_input` status → renders the clarifying-question prompt.
  - `plan_ready` status → renders the generated 7-step plan preview.
  - calls `startDiscoveryPlan` / `advanceDiscovery` on the right actions.

### B3 — Add Monitor/Results tab assertions (F-W5-TST-02)
- Extend `AITaskPanel.w3c.test.jsx` (or the AI workspace panel test):
  - switching to **Monitor** tab renders the run ledger / status timeline.
  - switching to **Results** tab renders artifact list + step outputs.

### B4 — Fix the 9 pre-existing failures (F-PRE-01)
- `AIArtifacts` (2): align test selectors/roles with the component's real
  `aria-label`s.
- `AIMessageBubble.feedback` (3): align accept/reject button roles + callback
  mocks.
- `AISharedThreads` (4): align shared-chip / separator query semantics.
- Do **not** weaken assertions to make tests pass — fix the *selector* to match
  the component contract, unless the component genuinely needs an `aria-label`.

### B5 — Fix `LoadoutSheetPage` flakiness (F-PRE-02)
- Root-cause the parallel-runner pollution (likely shared module-level state,
  an un-awaited timer, or a leaked `window`/store mock). Convert to isolated
  per-test setup (`beforeEach` reset, no shared mutable module state).
- Verify by running the file in isolation **and** in the full parallel suite.

### B6 — Verification gate (W6-B)
- `vitest run` → **0 failures, 0 skips**.
- `npm run build` clean.
- `eslint` clean.

### DO NOT TOUCH (W6-B)
- No dependency additions (ADR-0011: no new viz libs).
- No inline `sx`/hex — use theme tokens.
- No raw `fetch()` — use the `apiFetch` wrapper.

---

## Phase W6-C — End-to-end artifact proof (F-25) — BACKEND

**Worker:** backend-worker.
**Goal:** Prove a real `export_document` run produces a downloadable artifact.

1. Drive one plan through a real `export_document` step (admin token).
2. Assert:
   - a `RunArtifact` row exists (step-scoped),
   - `steps[].output_type == "artifact"`,
   - `steps[].artifacts[]` carries `download_url`,
   - `GET {download_url}` → **200** with `Content-Disposition: attachment`.
3. If the artifact is absent, the fault is in the engine→`store_artifact`
   handoff (`get_current_plan_run()` contextvar / `resolve_export_step_index`)
   — fix there, not in `store_artifact` itself.

**Gate:** one manual `curl` of the download URL returning 200 + a written
evidence note in the QA report.

---

## Phase W6-D — F-26: Multi-agent parallel execution — BACKEND

**Worker:** backend-worker.
**Goal:** honor `agent_role` + `strategy: "parallel"` phases with true
concurrent step execution, still inside the consent/ledger envelope.

Scope (bounded — do not rebuild the engine):
1. Executor: when a phase declares `strategy: "parallel"`, fan out its
   independent steps (respect `depends_on`) concurrently with bounded
   concurrency (e.g. `ThreadPoolExecutor(max_workers=N)`).
2. Ledger: each step still writes its own `RunStep` row (status transitions),
   no cross-step writes.
3. Consent: mutation steps still gate on `is_mutation` + `requires_confirmation`
   — parallel fan-out must **not** bypass the consent gate.
4. Add tests: parallel phase → all steps reach terminal status; a failing step
   does not corrupt sibling step rows.

**Gate:** new tests in `test_durable.py` / a new `test_parallel.py` green;
no regression in the existing 74 backend tests.

---

## Phase W6-E — F-28 (mid-execution edits) + F-29 (scheduling) — BACKEND

**Worker:** backend-worker (F-28), backend-worker + devops-worker (F-29).

### E1 — F-28: mid-execution edits (pause → steer → resume)
1. Add a `pause` transition (run → `paused`) that halts at the next step
   boundary (never mid-step).
2. Allow editing *pending* steps' `instructions` (service-owned metadata, per
   `_serialize_run`) while paused.
3. `resume` already exists (`durable_service.resume_run`) — wire it to honor
   edited pending steps.
4. Tests: pause→edit→resume preserves the edit; resume after crash still works.

### E2 — F-29: scheduling/triggers
1. Add a `RunSchedule` model (cron expression / one-off `run_at`, target plan
   template id, owner).
2. Add a `manage.py run_due_schedules` command (idempotent) that materializes
   due schedules into runs and enqueues them.
3. `manage.sh` gets a documented cron line (manual/CI-only; **no docker**).
4. Tests: due schedule → run created; future schedule → not run; owner scoping.

**Gate:** new tests green; `manage.py run_due_schedules --dry-run` clean.

---

## Phase W6-F — Final full-suite + F-21/F-22 re-verification — QA

**Worker:** qa-validator (independent), master-architect signs off.

1. Backend: `pytest backend -q` → 74 + all new tests green.
2. Frontend: `vitest run` → 100% green; build + lint clean.
3. Re-verify F-21/F-22: `manage.py check` + `manage.py showmigrations` with no
   missing/conflicting dependency errors.
4. Re-run the W5 QA "Round-2" smoke (discovery lifecycle end-to-end) once.
5. Write `docs/TASK-RESULTS-W6-REMEDIATION.md` with a per-finding CLOSED table.

---

## Dispatch order & dependencies

```
W6-A (backend, cheap, unblocks truth) ─┬─► W6-C (needs A2's live run context)
                                       └─► W6-D ─► W6-E
W6-B (frontend, independent) ──────────────────────────┘
                                                          ▼
                                              W6-F (qa-validator)
```

- **W6-A and W6-B are parallel** (different workers, disjoint files).
- **W6-D/E depend on W6-A** only insofar as they share the plans engine; they
  can start once A1/A2 confirm the durable surface is stable.
- **W6-F is the final gate** and is the only phase qa-validator executes.

---

## Master sign-off checklist

- [ ] W6-A: `compare/` returns 400; `output_type` non-`None` on structured steps; tests added.
- [ ] W6-B: `vitest run` 100% green; build/lint clean.
- [ ] W6-C: download URL returns 200 with attachment.
- [ ] W6-D: parallel phase test green; consent gate intact.
- [ ] W6-E: pause/edit/resume + scheduling tests green; cron documented.
- [ ] W6-F: full backend + frontend green; F-21/F-22 confirmed fixed; results doc written.

---

## Activation prompts (copy per worker)

### backend-worker — W6-A
> Run Phase W6-A only. Verify (do not blindly re-fix) F-W5-RUN-01 and
> F-W5-C-01. First curl `GET /carbon-api/ai/runs/compare/?a=<id>&b=<id>` with an
> admin token — 400 means live. Then confirm a completed plan's `steps[].output_type`
> is non-None for structured outputs. Add regression tests only (compare diff +
> CBAC; infer_output_type table/chart/artifact/empty; serialize injects output_type).
> Do NOT edit `_infer_output_type`, `_with_output_type`, `store_artifact`,
> `durable_urls.py`, or `config/urls.py` unless a mount line is genuinely absent.
> Do NOT run `test_store_execute.py`. Report pass/fail + exact curl status codes.

### backend-worker — W6-C/D/E
> Implement W6-C (prove export_document → downloadable artifact end-to-end),
> W6-D (parallel phase fan-out honoring consent + depends_on), W6-E (pause/edit/
> resume + RunSchedule + run_due_schedules command). Keep consent gates intact.
> No docker. Add tests per phase. Report green counts + any engine surprises.

### frontend-worker — W6-B (B1-B3)
> Add StepOutputRenderer.test.jsx, DiscoveryComposer.test.jsx, and Monitor/Results
> tab assertions. Remember MUI DataGrid v8 valueFormatter is positional. No new
> deps, no inline sx, no raw fetch. Report test counts.

### debugger-fixer — W6-B (B4-B5)
> Fix the 9 legacy FE failures (AIArtifacts, AIMessageBubble.feedback,
> AISharedThreads) and the LoadoutSheetPage flakiness. Fix selectors/roles or
> component contracts — never weaken assertions. Verify the flaky file in
> isolation AND in the full parallel suite.

### qa-validator — W6-F
> Independently run the full suite (backend pytest + frontend vitest + build +
> lint). Re-verify F-21/F-22 via manage.py check/showmigrations. Re-run the
> discovery lifecycle smoke once. Write TASK-RESULTS-W6-REMEDIATION.md with a
> per-finding CLOSED table and 4-layer evidence.
