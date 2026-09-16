# ADR-0034 — Resilient Agent Workflow Graph (typed nodes + guards)

- **Status:** Accepted
- **Date:** 2026-09-16
- **Deciders:** Master Architect (Pulse seat)
- **Area:** backend | frontend | cross-cutting

## Context
Agent plans were a linear `depends_on` list (+ optional parallel phases). Live QA
and `docs/DESIGN-AGENT-WORKFLOW-AND-UI.md` require branching, loops, catch/heal,
and partial completion without replacing the durable journal or fail-closed
boundary. Shipping a second runtime (Temporal/Camunda) was rejected for the pilot.

## Decision
1. Adopt a **declarative JSON workflow graph** under `backend/ai/engine/workflow/`
   (RULE_20 pure): `graph.py` (schema + old→graph compile), `guards.py` (sandboxed
   boolean expressions — no `eval`), `driver.py` (eligibility + XOR `choose_edge`).
2. Persist compiled graph on `plan_json.workflow_graph` alongside legacy steps
   (backward compatible; old clients ignore the key).
3. Node taxonomy: `task|choice|parallel|map|loop|wait|human|subflow|observe|
   succeed|fail`. Per-node retry/catch/timeout and `observe` heal land in later
   W-4/W-5 phases; driver is additive — ReActLoop remains the executor until
   W-3 is fully wired.
4. Cancel/Stop must never be clobbered by `_finalize_run` (see PB-51).
5. Briefs that ask for Word/Excel get an `export_document` deliverable step
   (`_ensure_export_deliverable`) so Results is not empty by accident.

## Alternatives Considered
- **Temporal / Camunda** — rejected for pilot; keep Django journal + in-process engine.
- **LangGraph as runtime** — patterns only (conditional edges/cycles); no new dep.
- **Replace ReActLoop immediately** — too large; compile/driver first, wire later.

## Consequences
- **Positive:** typed control flow without DB migration; replay-ready journal kinds
  can be added; UI can render choice/parallel from `workflow_graph`.
- **Negative / trade-off:** dual representation (steps + graph) until driver owns
  execution; graph UI lags engine.
- **Do NOT re-try:** clobbering `cancelled`/`paused` in `_finalize_run`; arbitrary
  Python in guards; marking `export_document` tool-less so no file is produced.

## References
- `docs/DESIGN-AGENT-WORKFLOW-AND-UI.md` (W-1…W-7, U-1…U-4)
- `backend/ai/engine/workflow/{graph,guards,driver}.py`
- `backend/ai/tests/test_workflow_graph.py`, `test_react_cancel_finalize.py`
- ADR-0014 (Chat/Agent mode split), ADR-0012 (Enterprise graph canvas)
