# TASK — Pulse Memory Phase M0: Trust Repair (P0)

**Role:** backend-worker
**Domain:** `backend/ai/engine/` + `backend/ai/engine/instances/carbon/instance.yaml` ONLY
**Model:** DeepSeek V4-Flash
**Parent plan:** `tasks/TASK-PULSE-MEMORY-NEXTGEN.md` (read §1b, §2b, §4 Phase M0)
**Constraint:** Do NOT break the 1,015 existing tests. Do NOT touch the GAP-1..GAP-6 fixes that are working (fallback, anaphora, entity extractor, working memory, preferences, terminology).

---

## WHY (context — read once)

Live session transcript (2026-08-24) exposed three trust-breaking failures:

- **GAP-M5:** Pulse claimed "I can store information permanently" then, 6 turns later, said "I don't have memory enabled." Root cause verified: the `learn_fact` / `forget_fact` tools EXIST and are fully executable (`engine/agent/tools.py` → `execute_learn_fact`/`execute_forget_fact`, registered in `TOOL_EXECUTORS`), but they are **absent from the `_draft_tools` allow list in `engine/cognition/turn/runner.py`**. So the chat LLM never sees the memory tools, and instead *describes* memory in prose that it cannot back up.
- **GAP-M6:** Pulse asked "shall I store this?" in prose → user said "yes" → the pipeline treated "yes" as a fresh decontextualized query → FallbackHandler fired → capability table dumped.
- **GAP-M7:** on confusion, `list_my_capabilities` fires and dumps the "Your Access" work-areas table, even though the user never asked about capabilities.

**Non-negotiable principle (§2b of plan):** Pulse may only claim a capability that a tool result or deterministic engine behaviour can demonstrate **in the same turn**. Native LLM abilities (prose generation, world knowledge, arithmetic, in-context recall) are NEVER marketed as Pulse's own capabilities.

---

## FILES TO READ FIRST (before writing anything)

1. `backend/ai/engine/cognition/turn/runner.py` — the `_draft_tools` `allow` set (~line 66), the S1→S6 `run()` flow, the GROUNDING RULES block (~line 410), the S3 single-pass path and pre-S1 hook point (top of `run()`).
2. `backend/ai/engine/agent/tools.py` — `learn_fact`/`forget_fact` tool defs (~line 167, 193), `execute_learn_fact` (~997), `execute_forget_fact` (~1054), `TOOL_EXECUTORS` (~1426).
3. `backend/ai/engine/agent/executor.py` — `create_pending_execution`, `cancel_pending_learn_facts`, `confirm_execution`, `decline_execution` (the engine-side propose→confirm flow).
4. `backend/ai/host_executor.py` — `confirm_execution` (~503): the CARBON-side executor that actually writes confirmed `learn_fact` to `MemoryLongTerm`. READ THIS to understand where the durable write happens.
5. `backend/ai/workspace_api.py` — `confirm_tool_execution` (~442): the API endpoint the UI confirm button calls.
6. `backend/ai/engine/instances/carbon/instance.yaml` — the `persona` string.
7. `backend/ai/engine/cognition/dialogue/entity_extractor.py` — the domain-agnostic regex-extraction pattern to mirror.
8. `backend/ai/tests/test_gap1_fallback.py`, `backend/ai/tests/test_gap3_anaphora.py` — test conventions for the gap suite.
9. `backend/ai/engine/plugins/` — note `list_my_capabilities` is a plugin (`backend/ai/plugins/list_capabilities.py`), surfaced via `get_tool_definitions()`.

---

## FIX 1 — Wire `learn_fact` + `forget_fact` into the chat tool set (GAP-M5)

**File:** `backend/ai/engine/cognition/turn/runner.py`

In `TurnPipelineRunner.__init__`, extend the `allow` set (currently):
```python
allow = {
    "create_dq_rule", "search_knowledge", "get_entity_details",
    "list_my_capabilities", "plan_task",
    "edit_plan", "approve_plan",
    "web_research", "export_document",
}
```
to include `"learn_fact"` and `"forget_fact"`.

Do NOT remove any existing entries. Do NOT change the executor instantiation.

**File:** `backend/ai/engine/instances/carbon/instance.yaml`

Extend the `persona` string (append, don't rewrite the whole thing) with a truthful memory directive, e.g.:

> "You do NOT have a standalone persistent memory. When a user asks you to remember or store something, propose it with the learn_fact tool; it is only saved after the user confirms the proposal. Never claim you have already remembered or permanently stored something unless a learn_fact result confirmed it. Never describe in-context recall of earlier turns as 'my memory system'."

Keep the existing persona text intact (it already says "Never claim an action succeeded unless a tool result confirmed it").

**File:** `backend/ai/engine/cognition/turn/runner.py` — GROUNDING RULES block (~line 410)

Append two bullet rules (before the final bullet about capability-list):
- A memory-truthfulness rule: "Never claim you remembered or permanently stored anything. When the user asks you to remember/store something, call learn_fact; it only proposes — the user confirms before it is saved. Never say 'I have memory' or 'I don't have memory' — describe the learn_fact propose→confirm flow instead."
- A capability-separation rule: "Only claim a capability that a tool result in this turn just demonstrated. Your native abilities (writing prose, general knowledge, arithmetic) are NOT 'Pulse capabilities' and must not be listed as such. Use the capability-list tool only when the user asks what you/they can do or access — never as a fallback when you are unsure."

---

## FIX 2 — PendingActionStore for yes/no confirmations (GAP-M6)

**New file:** `backend/ai/engine/cognition/dialogue/pending_action.py`

Domain-agnostic, thread-safe, in-process store (mirror the singleton + `_lock` pattern in `engine/memory/working.py`). Scope it to MEMORY proposals only for M0 (do not attempt to auto-execute arbitrary host mutations — that stays on the existing RULE_21 propose→confirm path).

```python
class PendingActionStore:
    """Tracks Pulse's open 'shall I remember/store X?' proposal awaiting a yes/no.

    In-process, per-conversation, thread-safe. Memory-only in M0.
    """
    def set_pending(self, conv_id, fact, category="observation", expires_turns=2) -> None
    def get_pending(self, conv_id) -> dict | None
    def check_confirmation(self, conv_id, user_message) -> dict | None  # returns the pending action if message is an affirmation
    def clear(self, conv_id) -> None
    def detect_proposal(self, response_text) -> dict | None  # {"fact": ..., "category": ...} | None
```

- **Confirmation signals (short messages only):** `yes`, `yeah`, `yep`, `ok`, `okay`, `sure`, `do it`, `go ahead`, `please`, `store it`, `remember it`, `yes please`. Treat as confirmation ONLY when a pending action exists for that conversation AND the message is ≤ 4 words. Never confirm on a long message.
- **Proposal detection** (`detect_proposal`, applied to the assistant's FINAL text): regexes like `(shall|should|would you like me to|want me to|can I)\s+(store|remember|memorize|save|note)\s+(.+)` — capture the fact and infer category (`identity` if it matches `I am|my name is|I'm`, `preference` if it matches `prefer|want|like|always`, else `observation`). Keep it purely regex — no domain terms, no LLM.

**File:** `backend/ai/engine/cognition/turn/runner.py`

- **Pre-S1 hook** (very top of `run()`, right after the ledger is built and BEFORE the S1 salience block): call `check_confirmation(conversation_id, user_message)`. If it returns a pending action, SHORT-CIRCUIT the whole pipeline:
  1. Call `execute_learn_fact(fact=..., category=..., instance_id=instance_id, executor=self.executor, conversation_id=conversation_id)` (import from `ai.engine.agent.tools`) so the durable write stays on the audited propose→confirm path.
  2. `clear(conversation_id)`.
  3. Return an `AgentResponse` with a truthful confirmation message (e.g. "Done — I've prepared a memory card. Click confirm to save it permanently.") and an empty/turn-minimal ledger (write a `final` ledger row with verdict `pass` and a `pending_confirmation_shortcircuit: True` flag). DO NOT fabricate "saved" — the card is the confirmation.
  4. Broadcast `run.started` / `run.completed` so observers don't hang.
  - If no executor or the action is not memory, fall through to the normal pipeline (never crash).
- **Post-response hook** (before each `return response, ledger` at the end of the single-pass path): call `detect_proposal(final_text)`; if it returns a fact, `set_pending(conversation_id, fact, category)`.

Wrap every hook in try/except that logs and continues — a memory-hook failure must NEVER block the turn.

---

## FIX 3 — `list_my_capabilities` salience guard (GAP-M7)

**File:** `backend/ai/engine/cognition/turn/runner.py` — S3 single-pass path

Before the `draft_witness.draft(...)` call, compute a per-turn `draft_tools` from `self._draft_tools` that EXCLUDES `list_my_capabilities` unless BOTH of the following are false:
- `salience.domain != "identity"`, AND
- the user message does NOT match an explicit capability query (`what can you do`, `what do you have access to`, `what features`, `show me capabilities`, `your capabilities`, `what are you able to do`, `what can I use`).

```python
draft_tools = self._draft_tools
if draft_tools and not _is_capability_query(user_message) and salience.domain != "identity":
    draft_tools = [d for d in draft_tools if d.get("function", {}).get("name") != "list_my_capabilities"]
```

Add a small module-level helper `_is_capability_query(text) -> bool` (regex, domain-agnostic). The `draft_tools` variable already exists and is passed to `draft(...)` — repoint it to the filtered list. Do not filter any other tool.

---

## DO NOT TOUCH

- `engine/cognition/dialogue/fallback.py`, `anaphora.py`, `entity_extractor.py` (working GAP-1..GAP-6 fixes)
- `engine/memory/working.py`, `learning/preferences.py`, `knowledge/terminology.py`
- `engine/cognition/turn/critic.py` (knowledge-gap routing already fixed)
- `backend/ai/host_executor.py`, `backend/ai/workspace_api.py` (the confirmed-write path — READ ONLY; do not modify in M0)
- `backend/ai/engine/agent/tools.py` `execute_learn_fact`/`execute_forget_fact` bodies (they work; only call them)
- Any Django migration or model — M0 adds NO new DB model, NO migration.

---

## TESTS (all new tests must be domain-agnostic — use "Alpha Table", "Widget", "Dataset", never carbon/DQ/emission terms)

New files under `backend/ai/tests/`:

1. `test_gap7_pending_action.py`
   - `detect_proposal` recognizes "Would you like me to store that your name is Alex?" / "Shall I remember that you prefer weekly reports?"
   - `detect_proposal` returns None for non-proposal text.
   - `check_confirmation` returns the pending action for `yes`/`ok`/`do it`/`store it` when pending exists.
   - `check_confirmation` returns None for a long message even if it contains "yes".
   - `check_confirmation` returns None when no pending action exists (bare "yes" must NOT short-circuit a fresh query).
   - store → check → clear round-trips cleanly.

2. `test_gap8_capability_guard.py`
   - `_is_capability_query` matches "what can you do", "what do you have access to", "show me capabilities"; returns False for "yes", "what is a table", "explain GHG".
   - A filtered `draft_tools` list excludes `list_my_capabilities` for a non-capability message; includes it for a capability message.
   - The `_draft_tools` allow set includes `learn_fact` and `forget_fact`.

Use pytest + the existing gap-test fixtures/conventions. If a test needs the Django DB, use the same `@pytest.mark.django_db` + user fixture pattern as `test_gap1_fallback.py` / `test_gap3_anaphora.py`.

---

## VERIFICATION GATES (run ALL, paste full output into TASK-RESULTS.md)

```bash
cd /home/ahmed/aast/carbon/backend

# 1. New + existing gap tests
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_gap7_pending_action.py ai/tests/test_gap8_capability_guard.py ai/tests/test_gap1_fallback.py ai/tests/test_gap2_entity_extractor.py ai/tests/test_gap3_anaphora.py ai/tests/test_gap4_preferences.py -q

# 2. Full AI suite (must stay green — do not regress the 1,015)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q

# 3. Django check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check

# 4. Anti-pattern gate
cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh antipatterns
```

Gate 2 must show the same (or better) pass count as before. If any pre-existing test now fails, that is a BLOCKER — report it, do not paper over it.

---

## REPORT BACK (append to `tasks/TASK-RESULTS-M0-TRUST-REPAIR.md`)

- Task-by-task pass/fail table (Fix 1 / 2 / 3 + tests).
- Files changed (action, path, what).
- Full verification output (all four gates).
- Deviations + issues found (do NOT fix adjacent bugs — log them).
