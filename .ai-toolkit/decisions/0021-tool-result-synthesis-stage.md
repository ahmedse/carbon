# ADR-0021 — Tool-Result Synthesis Stage (execute → synthesize → finalize)

**Date:** 2026-08-28
**Status:** Accepted
**Author:** Master Architect
**Extends:** ADR-0007 (in-hand stateless engine), ADR-0008 (six-witness pipeline), ADR-0017 (instance.yaml catalog seam)

---

## Context

Behavioral eval of the live chat pipeline (31 scenarios) exposed two grounding
signatures when the S3 draft witness emits **tool calls with little or no prose**:

1. **Promise-only answers** — the planner drafts "I'll fetch the emission factors…"
   plus a tool call; S5 executes the tool, but S6 "finalize" only stamped the
   ledger — it never re-drafted the answer from the tool results. The user saw the
   pre-tool promise, and the fetched data was silently discarded.
2. **Wrong-tool fallback / hallucinated tool names** — `call_host_api` (the only
   planner tool that reaches live host data) was missing from the chat tool set,
   so the planner fell back to `search_knowledge` (KG-only) or hallucinated the
   endpoint name (`get_calculation_summary`) as a raw tool call.

The six-witness pipeline was designed as *route → retrieve → draft → critic →
execute → finalize*, but "finalize" was a ledger step, not a **re-synthesis** step.
The gap: nothing converts executed tool results back into grounded prose.

## Decision

1. **`call_host_api` is a spine tool, not a Carbon peripheral.** It is the generic,
   domain-neutral host-interface executor that reads `instance.yaml`'s `api_catalog`
   (ADR-0017) and dispatches to the project's `host_executor.py`. As a brain
   capability it belongs in `_CHAT_STATIC_TOOLS` (the frozen spine) alongside
   `search_knowledge`/`get_entity_details`/`learn_fact`/`forget_fact`. Its
   description points at the "Available Host API Endpoints" section of the system
   prompt (built from `api_catalog`) — never at `search_knowledge`.

2. **Add a synthesis step between S5 (execute) and S6 (finalize).** After tools
   execute, if any tool returned usable data AND the draft prose is empty or a
   short "promise" (< 300 chars), re-invoke the LLM to write the final answer from
   the actual tool results (`_synthesize_tool_results` in `turn/runner.py`).
   - LLM synthesis first (clean prose + real values).
   - Deterministic `_build_tool_result_summary` (GAP-W8) is the fallback when the
     LLM synthesis is unavailable — the "never return blank content" safety net.
   - `requires_confirmation` and errored tools are excluded from synthesis; they
     flow through the existing confirmation/anti-hallucination path unchanged.

## Consequences

### Positive
- A tool-only turn now returns the data the user asked for (prose + values), not a
  discarded promise or a raw JSON envelope.
- The seam is honest: synthesis lives in the cognition runner (domain-neutral); the
  domain terms come only from `instance.yaml` (ADR-0017).
- The fallback ordering is explicit and testable.

### Negative / Tradeoffs
- One extra LLM call per tool-only turn (bounded by the existing budget gate in
  `route_chat`).
- The < 300-char heuristic is a signal, not a guarantee; a pathological short draft
  with a good answer would still trigger synthesis (low risk — synthesis re-reads the
  tool results and answers the same question).

### Mitigation
- `_render_tool_results_for_synthesis` caps rendered results at 20k chars to bound
  token cost.
- Regression tests cover the pure renderer and the short-circuit branches of
  `_synthesize_tool_results` (no LLM call for no-usable-tools / long-draft).

## Files Changed

| File | Change |
|------|--------|
| `backend/ai/engine/cognition/turn/runner.py` | `call_host_api` in `_CHAT_STATIC_TOOLS`; `_render_tool_results_for_synthesis` + `_synthesize_tool_results`; GAP-W8/W9 reorder |
| `backend/ai/engine/agent/tools.py` | `call_host_api` description points at the catalog seam |
| `backend/ai/serializers.py` | `SendMessageSerializer.content` allows blank |
| `backend/ai/intelligence.py` | blank message normalized to a greeting |
| `backend/ai/tests/test_tool_result_synthesis.py` | regression tests |
