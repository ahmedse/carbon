# TASK-RESULTS — Uncertainty Provenance

## 2026-09-03 backend-worker — Phase 1: Boundary Audit (read-only)

### Seams found

| # | File | Function/location | Falsy value | States conflated | Verdict |
|---|------|-------------------|-------------|------------------|---------|
| 1 | ai/plugins/web_research.py | `_weather` (L245/257/260/265) | `None` | no_match vs empty vs error | conflates |
| 2 | ai/plugins/web_research.py | `execute` L200-203 fall-through to `_search` | `None` → search | no_match → fabricated answer | conflates |
| 3 | ai/engine/cognition/turn/intent.py | `IntentResolver.resolve` (L335/339/384/389) | `None` | error vs no_signal vs empty-catalog | conflates |
| 4 | ai/subagent_service.py | `SubagentService.run_subagent` L94 | `""` | error vs empty | conflates |
| 5 | ai/engine/knowledge_graph/context.py | `assemble_context` L264/269, L351/352 | `""` | no_match vs empty | conflates |
| 6 | ai/engine/memory/episodic.py | `get_relevant_episodes` L431/434 | `[]` | error vs empty | conflates |
| 7 | ai/engine/memory/episodic.py | `_find_predecessor` L157/160/174 | `None` | error vs no_match vs empty | conflates |
| 8 | ai/engine/agent/tools.py | `_resolve_entity_id_from_config` L856 + "Fallback: use the first item" | `entity_id` unchanged / first item | empty vs no_match (fabricates) | conflates |
| 9 | ai/engine/agent/tools.py | `_resolve_slug_to_id` (unresolved slug kept, L~495) | raw slug | no_match → raw value | conflates |
| 10 | ai/engine/agent/tools.py | `execute_open_entity` `if not entity_config:` generic-route fallback | generic route | no_match → fabricated route | conflates |
| 11 | ai/engine/cognition/turn/runner.py | `_synthesize_tool_results` L227 `if tr.get("result") is None: continue` + L231 | `None` | no_match vs error (silent drop) | conflates |

### Notable clean seams (no conflation)
- `ai/engine/knowledge/semantic_layer.py` — `enrich_schema` / `_call_llm_for_descriptions`: raises `SemanticEnrichmentError`, docstring "No fallbacks: if the LLM fails, the error propagates". One state only (error → raise).
- `ai/plugins/web_research.py` `_search` L435 `if not results:` — returns an explicit `{"results": [], "message": "No results were returned…"}` dict; genuinely-empty is surfaced, not coerced.
- `ai/plugins/web_research.py` `_weather` forecast HTTP error (~L270) — returns explicit `{"error": "Could not fetch current weather…"}` dict (error state surfaced; the *geocoder* side is the conflating part in #1).
- `ai/engine/cognition/turn/execute.py` `_execute_single_tool` — returns `{"result": None, "error": …}` distinguishing error from result; nested `{"error":…}` promotion (L383-393) and null-output guard (L361-372) both fail *honestly*.
- `ai/engine/agent/tools.py` `execute_get_entity_details` — returns `{"entity": None, "message": "Entity '…' not found"}` (explicit not-found message, not bare falsy).
- `ai/engine/agent/tools.py` `execute_search_knowledge` — returns `{"entities": [], "message": "Knowledge store not available"}` and `count`; empty vs unavailable are distinct.
- `ai/engine/cognition/turn/intent.py` `_parse_json` (L214/227/231) — returns `None` only for unparseable JSON (single unambiguous error state).
- `ai/engine/cognition/turn/runner.py` `_try_multi_step_plan` L1556 and `_try_fan_out` L1666/1673/1737/1747/1754/1758/1770 — documented `None` = "fall through to single-pass / not applicable" (control-flow, not entity absence).
- `ai/engine/agent/tools.py` `_get_slug_resolution` / `_get_param_resolution` / `_find_entity_config` (L381/385/392/401/405/408/821/825) — return `None` for "not configured" (single config-absence state).
- `ai/engine/knowledge_graph/context.py` `_normalize_scores` L38 and `rerank_with_llm` L101 `if not candidates: return []` — pure normalizer / empty-in → empty-out.

### Grep evidence

```bash
cd /home/ahmed/aast/carbon/backend
grep -rn "return None" ai/plugins ai/engine/cognition/turn ai/engine/agent
```
```
ai/plugins/web_research.py:245:            return None
ai/plugins/web_research.py:257:            return None
ai/plugins/web_research.py:260:            return None
ai/plugins/web_research.py:265:            return None
ai/engine/cognition/turn/intent.py:335:            return None
ai/engine/cognition/turn/intent.py:339:            return None
ai/engine/cognition/turn/intent.py:384:            return None
ai/engine/cognition/turn/intent.py:389:            return None
ai/engine/cognition/turn/runner.py:231:        return None
ai/engine/agent/tools.py:821:        return None
```

```bash
grep -rniE "fall.?back|still gets something|fall through|fallthrough" ai/
```
```
ai/plugins/web_research.py:202:                    # Location couldn't be resolved — fall back to search so
ai/plugins/web_research.py:203:                    # the user still gets something rather than a refusal.
ai/engine/knowledge_graph/context.py:194:        # Fallback: return top_k by fused score
ai/engine/knowledge_graph/context.py:195:        return candidates[:top_k]
ai/engine/agent/tools.py:864:        # Fallback: use the first item
ai/engine/cognition/turn/runner.py:1735:            # Orchestrator chose not to fan out — fall through
```

```bash
grep -rnE "if not (results|matches|hits|data|rows|items)\b" ai/
```
```
ai/plugins/web_research.py:259:        if not matches:
ai/plugins/web_research.py:435:        if not results:
ai/engine/agent/tools.py:537:            if not items:
ai/engine/agent/tools.py:856:        if not items:
ai/engine/memory/episodic.py:159:        if not results["ids"] or not results["ids"][0]:
ai/engine/memory/episodic.py:433:        if not results["ids"] or not results["ids"][0]:
ai/engine/knowledge_graph/context.py:38:    if not items:
ai/engine/knowledge_graph/context.py:264:    if not seed_nodes:
```

```bash
grep -rn "return None" ai/engine/knowledge ai/engine/memory ai/engine/knowledge_graph
```
```
ai/engine/memory/episodic.py:157:            return None
ai/engine/memory/episodic.py:160:            return None
ai/engine/memory/episodic.py:174:        return None
ai/engine/memory/episodic.py:348:            return None
ai/engine/memory/episodic.py:405:            return None
ai/engine/memory/episodic.py:431:            return []
ai/engine/memory/episodic.py:434:            return []
ai/engine/knowledge_graph/context.py:269:        return "No relevant knowledge found for this query."
ai/engine/knowledge_graph/context.py:352:        return "No relevant knowledge found for this query."
```

Note: `return None` hits inside `ai/tests/**` and `ai/engine/knowledge_graph/{bm25,cache_store,path_finder,recovery_pipeline,schema_analyzer,session_store,store,synthesis,context_merger,multi_step_planner,plan_synthesizer}.py` were sampled; most are single-state internal helpers (parser/config/cache miss). Tests assert current behavior; migrations/historical modules are out-of-scope. `ai/engine/agent/{api_discipline,executor}.py` `return None` are config-lookup single-state.

### Summary

N = 20 seams classified, M = 11 conflating, K = 9 clean. Rank-1 next target: `ai/plugins/web_research.py` `_weather` → `execute` fall-through (seam #1+#2, the canonical "north coast egypt" case) — it is the reference implementation of the tri-state contract and the Phase 3 conversion point.

---

## 2026-09-03 backend-worker — Phase 2: Tri-state helper

**Created `backend/ai/engine/core/resolution.py`** (stdlib-only, RULE_20): `resolved()`, `no_match()`, `error()`, `is_resolved()`, `is_no_match()`, `is_error()`, `min_confidence()`, `truthiness_guard()`, `_clamp()`. Dict-based, no `__bool__`/`__len__` magic — callers branch on `status`, never `if result:`.

**Created `backend/ai/tests/test_resolution.py`** — 14 tests.

**Gate:** 14 passed.

---

## 2026-09-03 backend-worker — Phase 3: Convert the exemplar seam (weather)

**Modified `backend/ai/plugins/web_research.py`**: `_weather` now returns `no_match("missing_location"/"unresolved_location", hint=...)` when the location is empty/unresolvable, `error(...)` on geocode/forecast HTTP failures, `resolved(...)` on success (confidence placeholder 1.0). `execute` branches on `status`: `resolved` → return `data`; `no_match`/`error` → return the structured result (fall-through to `_search` REMOVED).

**Modified `backend/ai/tests/test_web_search_tool.py`**: `test_weather_region_returns_no_match` (asserts `status=="no_match"`, `hint` present, NO Wikipedia fallback).

**Gate:** 25 passed (web_search_tool + resolution).

---

## 2026-09-03 backend-worker — Phase 4: Escalation seam (no_match routes UP)

**Modified `backend/ai/engine/core/resolution.py`**: added `payload_status(raw)` — returns `resolved|no_match|error|None` from a raw tool-result payload (dict, JSON string, or host-envelope).

**Modified `backend/ai/engine/cognition/turn/runner.py`**:
- Added `_no_match_hints(no_matches)` and `_clarify_no_matches(...)` (dedicated `route_chat` that emits ONE disambiguating question; may suggest 2-3 normalized candidates; never fabricates).
- `_synthesize_tool_results` now partitions `usable` vs `no_matches` (via `payload_status`). Precedence: (1) `no_matches and not usable` → clarify (fires even when draft is a bare "I'll fetch…" promise); (2) `not usable` → None; (3) `>=300` draft guard (usable-only); (4) `no_matches and usable` → synthesize from usable + honesty directive listing unresolved hints.

**Modified `backend/ai/engine/cognition/turn/execute.py`**: `_build_tool_result_summary` detects `no_match` and renders `"I couldn't resolve \"{hint}\". Could you clarify what you meant?"` instead of dumping the tri-state dict.

**Modified tests**: `test_resolution.py` (+7 `payload_status` tests), `test_tool_only_response.py` (+2 no_match clarification tests).

**Gate:** 39 passed (resolution + tool_only_response + empty_response_regression).

---

## 2026-09-03 backend-worker — Phase 5: Confidence conservation surfacing

**Modified `backend/ai/engine_runtime.py`**:
- Added `_min_input_confidence(completed_tools) -> float | None` — min confidence across RESOLVED tool results only (no_match/error impose none); `None` = "no constraint".
- Added `_conserved_confidence(answer_conf, min_input_conf) -> (capped, violated)`.
- In `_run_chat`, after the veto `if/else`, compute `min_input_conf`, cap `answer_conf`, and on violation log `WARNING "confidence-amplifying junction"` + downgrade `confidence_label` + set `honest_uncertainty=True`.
- Surfaced `"min_input_confidence"` and `"confidence_conserved"` in the returned metadata.

**Modified `backend/ai/tests/test_confidence_surface.py`**: +10 unit tests for the two helpers.

**Gate:** 39 passed (confidence_surface + resolution).

**Deferred (explicitly):** real `confidence` derivation in `_weather` (currently `1.0` placeholder); end-to-end integration assertion on the new surface keys (no existing test produces a resolved-tool confidence lower than the draft's).
