# Sprint 25 — R2: Engine systemic empty replies on tool-requiring turns (F-04)

**Owner:** Master Architect · **Worker Role:** backend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (root-caused by Master — implement to spec)
**Source:** `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` finding F-04
**Priority:** P1 — systemic, ×5 repro (AGT-08, QUERY-02, KB-03, MNT-03, OPS-07).

## Goal
Stop the pipeline from returning **empty replies** on turns where the model emits a tool call
with zero accompanying text. Currently such turns spend 2.0–2.4K tokens and return `''`.

## Root cause (verified in source — implement exactly this)

The single-pass path (`backend/ai/engine/cognition/turn/runner.py`) does:

1. **S3 Draft** — model returns `draft.text = ""` (text_len=0) with `draft.tool_calls = [<tool>]`.
2. **S4 Critic** (`backend/ai/engine/cognition/turn/critic.py:73-81`) — the citation-grounding
   check runs on the **empty** text:
   ```python
   if has_retrieval_results and not has_citations and not has_inline_citations:
       flags.append("ungrounded_claim")
   ```
   Empty text has no citations → `ungrounded_claim` flagged → LLM critic returns `veto` with no
   `rewritten_text`.
3. **Final text** (`runner.py:511`):
   ```python
   final_text = critic.rewritten_text if critic.rewritten_text else draft.text
   ```
   → `final_text = ""`.
4. **S5 Execute** runs the tool, but the response is built from `final_text` (still `""`), so the
   user sees an empty bubble.

The fingerprint the QA captured is exact: `draft(text_len=0) → critic(VETO, ungrounded_claim)
→ execution(tools_executed=1) → final('')`.

## Files to Change
- `backend/ai/engine/cognition/turn/critic.py` — MODIFY: skip citation-grounding when the draft
  is a **tool-call-only turn** (text empty, tool_calls present).
- `backend/ai/engine/cognition/turn/runner.py` — MODIFY: post-execution synthesis so tool-only
  turns produce text from tool results instead of the empty pre-tool draft.
- `backend/ai/tests/test_tool_turn_finalization.py` — ADD.

## Tasks

### 1. Critic: don't veto a tool-only draft for grounding (critic.py)
In `CriticWitness.review`, before the citation-grounding check, add a guard: a draft that has
`tool_calls` but empty/whitespace `text` is a **work-in-progress tool turn**, not an ungrounded
claim. It should NOT receive the `ungrounded_claim` flag (and must not be LLM-vetoed for that
reason). Example:
```python
is_tool_only = bool(draft.tool_calls) and not (draft.text or "").strip()
# only apply citation grounding when there is text to ground:
if not is_tool_only and has_retrieval_results and not has_citations and not has_inline_citations:
    flags.append("ungrounded_claim")
```
Mutation gating (S4 rules #3/#4) and all other critic rules still apply unchanged.

### 2. Runner: synthesize final text after tool execution (runner.py)
After S5 `ExecuteWitness.execute(...)` returns `execution` with `execution.completed_tools`,
when `final_text.strip() == ""` AND at least one tool completed, synthesize a short text summary
from the tool results (do NOT leave it empty). Minimum viable:
- If a tool produced a result payload, emit a plain-language one-liner describing the outcome
  (e.g. "I ran `<tool>` — it returned N rows / status `…`."). Reuse any existing synthesis
  helper in `backend/ai/engine/cognition/synthesis.py` if it fits; otherwise a small local
  `_summarize_tool_turn(execution)` is acceptable.
- On tool error/failed result, emit the error plainly (already a grounding rule; ensure it's
  surfaced as text, not swallowed).
- Do NOT spend an extra LLM call for the summary unless one already exists in the path — a
  deterministic summary is sufficient to meet the acceptance bar.

### 3. Tests
`test_tool_turn_finalization.py`:
- A draft with `tool_calls` and empty `text` is NOT flagged `ungrounded_claim` and is not
  LLM-vetoed.
- A tool-only turn with a successful tool result produces a non-empty `final_text` (no `''`).
- A tool-only turn with a failed tool produces non-empty text containing the error.
- The control case (non-tool, ungrounded text) is STILL vetoed as before (no regression).

## DO NOT TOUCH
- Frontend files.
- The fan-out path (runner.py ~213-355) and the ReAct loop (`cognition/plan/loop.py`) — the
  single-pass S3→S5 path only.
- `draft.py` / `execute.py` / `ledger.py` (consume their outputs, don't fork them).

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_tool_turn_finalization.py -q
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```
Acceptance repro: send "Create a DQ rule that flags negative emission values" (or any
tool-requiring prompt) and confirm a non-empty reply.

## Hard rules
- `python -m pytest`, never `manage.py test`. Venv `/home/ahmed/aast/carbon/.venv`.
- Timezone-aware datetimes. Engine stays stateless (RULE_6). No new Django apps.

## Output contract
Append an `R2` section to `TASK-RESULTS.md`.

## Notes for the Master
- The "wrong tool" sub-symptom (model picks `search_knowledge` instead of the domain tool) is a
  **separate** tool-selection issue — out of scope here. This task only fixes the empty-reply
  finalization. Log the wrong-tool observation but do not chase it.
- Acceptance bar: no empty `final_text` on any tool-requiring turn; control non-tool grounding
  veto still fires.
