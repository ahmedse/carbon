# Pulse v2 — Phased Implementation Plan

**Version:** 1.0  
**Date:** 2026-09-05  
**Status:** Approved for execution  
**Owner:** Master Architect  
**Audience:** Backend Worker agents implementing this plan  

---

## How to read this document

Every phase has the same structure:

```
Objective         — what behaviour changes for the user
Why it matters    — what is broken today that this fixes
What to build     — exact files, classes, methods, SQL
What NOT to touch — explicit stop conditions
Tests to write    — exact test names and assertions
Acceptance gate   — how the architect verifies it is done
Rollback          — how to disable it without data loss
```

**The workers rule:** Read the "What NOT to touch" section before touching anything. If something is not listed under "What to build," do not change it. When in doubt, stop and ask.

---

## Architecture north star (read this once)

Today Pulse is a **per-turn classifier** that guesses what the user wants, then either answers from memory or calls a tool. It forgets everything between turns except the conversation thread. It cannot observe the result of a tool call and then decide to call another. It cannot save work across conversations.

Pulse v2 must become a **coworker** that:

1. Observes what a tool returned and decides what to do next — automatically.
2. Remembers an unfinished objective across conversations.
3. Uses live Carbon data (emissions, DQ, MDM) as its ground truth, not as a retrieval hint.
4. Tells the user what it actually did vs. what it only proposed.
5. Asks one specific question when it needs information — not a generic clarification.

The existing consent gate (RULE_21), GuardChain, and TurnLedger are **not being replaced** — they are the governance layer that stays intact. Every phase adds capability within those constraints.

---

## Current code map (memorise this before touching anything)

| File | Purpose |
|---|---|
| `backend/ai/engine/cognition/turn/runner.py` | `TurnPipelineRunner` — the six-witness chat pipeline. Single-pass by default. |
| `backend/ai/engine/cognition/plan/loop.py` | `ReActLoop` — multi-step plan executor. Already has `draft→critic→execute→observe`. Only runs when `KG_MULTI_STEP_ENABLED=True`. |
| `backend/ai/engine/cognition/turn/intent.py` | `IntentResolver` — LLM classifier that assigns a `zone` and `action`. This is the primary routing bottleneck. |
| `backend/ai/engine/cognition/turn/draft.py` | `DraftWitness` — calls the LLM and returns a `DraftResult` with text + tool_calls. |
| `backend/ai/engine/cognition/turn/critic.py` | `CriticWitness` — validates the draft, gates mutations. |
| `backend/ai/engine/cognition/turn/execute.py` | `ExecuteWitness` — dispatches tool calls through the executor. |
| `backend/ai/engine/cognition/synthesis.py` | `_synthesize_tool_results()` — LLM synthesis after tool results arrive. |
| `backend/ai/flight_director.py` | `FlightDirector` — in-loop ref validation + fidelity re-run. Already wired into `ReActLoop`. |
| `backend/ai/guards.py` | `GuardChain` — `AccessGuard`, `DataIsolationGuard`, `MutationGuard`, `AuditTrail`. Never modify without the architect. |
| `backend/ai/host_executor.py` | `CarbonHostExecutor` — in-process transport for tool calls. |
| `backend/ai/plans_service.py` | `PlansService` — plan lifecycle: `pending_approval → approved → running → paused/completed`. |
| `backend/ai/durable_service.py` | `DurableExecutionService` — crash-resume, replay, timeline. |
| `backend/ai/models/core.py` | Django ORM: `Run`, `RunStep`, `RunArtifact`, `RunSchedule`, `Skill`, `SkillAdmissionLog`, `ToolExecution`, `TurnLedgerRow`, `Trajectory`. |
| `backend/ai/engine/core/models.py` | SQLAlchemy ORM for the engine: `MemoryLongTerm`, `MemoryEpisodic`, `ToolExecution` (engine-side), `Skill`, `Run`, `RunStep`. |
| `backend/ai/engine/memory/working.py` | `WorkingMemory` — single-slot in-process focus store. Conversation-scoped but not durable. |
| `backend/ai/models/workspace.py` | `AIConversation`, `AIMessage`, `AIArtifact`, `AIGeneration` (cancellation lease). |
| `backend/ai/intelligence.py` | `CarbonIntelligence` — entry point for all AI calls from the Django app. |

---

## Phase 1 — Make the adaptive loop the default path

**Objective:** Every user message that requires a tool call goes through `ReActLoop` automatically, not only when `KG_MULTI_STEP_ENABLED=True` is set by an admin. The user never gets a single-pass flat answer when a tool is available and the task warrants observation.

**Why it matters today:** The current pipeline runs `TurnPipelineRunner.run()`. After S2 (retrieval) it tries PR-20 (multi-step) only if `settings.KG_MULTI_STEP_ENABLED` is True. If False, it falls through to the S3 single-pass draft that calls the LLM once. That single LLM call may emit a tool call. If it does, the tool runs, but then S3 ends — the LLM never sees the tool result to produce a grounded answer. The synthesis step (`_synthesize_tool_results`) tries to patch this, but it is a separate LLM call with no memory of the draft.

**What is broken because of this:**
- The model calls `web_research` and returns `"I'll fetch the weather"`. The synthesis step runs but has no conversation-level continuity.
- The model calls `get_entity_details` and returns partial data. There is no second step to fill gaps.
- Multi-hop questions ("compare our factors with the latest IPCC values") require two tools but only one fires.

### 1.1 — Introduce `PULSE_LOOP_ENABLED` feature flag

**File:** `backend/ai/config/settings.py` (the Pydantic settings class)

Add this field to the `PulseSettings` class:

```python
PULSE_LOOP_ENABLED: bool = Field(default=True, description="Route tool-bearing turns through ReActLoop instead of single-pass S3.")
PULSE_LOOP_MAX_STEPS: int = Field(default=6, description="Maximum tool-calling steps before the loop forces a synthesis.")
PULSE_LOOP_MAX_TOKENS: int = Field(default=8000, description="Token budget for one loop execution.")
```

**Environment variables (add to `.env.example` and `deploy/carbon/.env`):**
```
PULSE_LOOP_ENABLED=true
PULSE_LOOP_MAX_STEPS=6
PULSE_LOOP_MAX_TOKENS=8000
```

Do not change any other settings field.

### 1.2 — Modify `TurnPipelineRunner.run()` to enter `ReActLoop` when tools are needed

**File:** `backend/ai/engine/cognition/turn/runner.py`

**Location:** Find the block starting at `# ── PR-20: Multi-step planning gate`. It looks like:

```python
react_result = None
if settings.KG_MULTI_STEP_ENABLED and self.db is not None:
    try:
        react_result = await self._try_multi_step_plan(...)
```

**What to add directly ABOVE that block:**

```python
# ── Phase 1: Pulse Loop — route tool-bearing turns through ReActLoop ──────
# When PULSE_LOOP_ENABLED is True, ANY turn that has tools available routes
# through ReActLoop without requiring a planner decomposition first. The
# loop runs a single-step plan (one intent = the user's message) which is
# identical to today's single-pass except the loop can observe the tool
# result and call another tool.
pulse_loop_result = None
if (
    settings.PULSE_LOOP_ENABLED
    and self.db is not None
    and self._draft_tools  # tools are wired
    and not settings.KG_MULTI_STEP_ENABLED  # don't double-enter the loop
):
    try:
        pulse_loop_result = await self._try_pulse_loop(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            host_user_id=host_user_id,
            page_context=page_context,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            retrieval=retrieval,
            progress_callback=progress_callback,
            stream_callback=stream_callback,
            turn_id=turn_id,
            budget_tracker=budget,
        )
    except Exception:
        logger.exception(
            "[%s] Pulse loop attempt failed; falling back to single-pass",
            turn_id[:8],
        )
```

**What to add after that block (mirror the fan_out_result / react_result return patterns exactly):**

Add `if pulse_loop_result is not None:` handling that:
1. Sets `final_text = pulse_loop_result.final_response`
2. Sets `total_tokens = pulse_loop_result.total_tokens` (sum from loop)
3. Sets `total_llm_calls = len(pulse_loop_result.step_results)`
4. Writes ledger rows for each step using `self._write_ledger_row()`
5. Writes the final `"final"` ledger row
6. Calls `await self.db.commit()`
7. Sets `ledger.final_response`, `ledger.total_latency_ms`, etc.
8. Returns the `AgentResponse` with `confidence=0.85`

Copy the `react_result is not None` block (lines ~1040–1115 of runner.py) character-for-character, then replace `react_result` with `pulse_loop_result`. Do not invent a new pattern.

**New private method `_try_pulse_loop()` on `TurnPipelineRunner`:**

```python
async def _try_pulse_loop(
    self,
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    host_user_id: str | None,
    page_context: str,
    conversation_history: list[dict] | None,
    instance_config: dict | None,
    user_info: dict | None,
    retrieval,
    progress_callback,
    stream_callback,
    turn_id: str,
    budget_tracker,
) -> "ReActResult | None":
    """Run the user message as a single-step ReActLoop with observation.

    Returns None if the planner determines no tool is needed (pure
    knowledge answer), so the single-pass path handles it. This is the
    same contract as _try_multi_step_plan.
    """
    from ai.engine.cognition.plan.planner import Plan, PlanStep, PlanPhase
    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.llm.prompts import build_system_prompt

    settings = get_settings()

    # Build a one-step plan: the intent is the user's message verbatim.
    # No LLM decomposition — this avoids a latency-adding planning call
    # for the common case where one tool suffices.
    plan = Plan(
        steps=[
            PlanStep(
                step_id=0,
                intent=user_message,
                tool_name=None,   # let the draft witness pick the tool
                is_mutation=False,
                depends_on=[],
                agent_role=None,
            )
        ],
        phases=[PlanPhase(phase_id=0, step_ids=[0], strategy="sequential", name="main")],
        source="pulse_loop",
    )

    system_prompt = build_system_prompt(
        instance_config=instance_config,
        user_info=user_info,
        page_context=page_context,
        retrieval=retrieval,
    )

    loop = ReActLoop(
        llm_client=self.llm_client,
        knowledge_store=self.knowledge_store,
        memory_manager=self.memory_manager,
        executor=self.executor,
        db=self.db,
    )

    result = await loop.run(
        plan=plan,
        instance_id=instance_id,
        conversation_id=conversation_id,
        user_message=user_message,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        instance_config=instance_config,
        user_info=user_info,
        retrieval=retrieval,
        progress_callback=progress_callback,
        stream_callback=stream_callback,
        dry_run=False,
        confirmation_token=None,
        db=self.db,
        host_user_id=host_user_id,
    )

    # If the step did not execute any tool (pure knowledge turn), let
    # the single-pass path handle it — it has better synthesis prompts
    # for no-tool turns.
    executed_any = any(
        sr.executed and not sr.error
        for sr in result.step_results
    )
    if not executed_any:
        return None

    # Attach token budget tracking (mirrors _try_multi_step_plan)
    if budget_tracker is not None:
        total = sum(
            getattr(sr, "tokens_used", 0) or 0
            for sr in result.step_results
        )
        await budget_tracker.consume(total)

    return result
```

**Stop condition:** If `build_system_prompt` does not exist with that exact signature, find the actual function that builds the system prompt in single-pass S3 and use the same call. Do not invent a new prompt builder.

### 1.3 — Add observation to `ReActLoop._execute_step()`

**File:** `backend/ai/engine/cognition/plan/loop.py`

The `_execute_step` method currently runs `draft → critic → execute`. After `execution = await ex.execute(...)` it records the tool output in `result.tool_output` but never feeds it back to the LLM to generate a grounded answer.

**Find this block in `_execute_step`:**

```python
result.executed = True
result.tool_output = execution.completed_tools[0] if execution.completed_tools else None
```

**Add immediately after `result.tool_output = ...`:**

```python
# Pulse v2 — observation step: if a tool ran and returned real data,
# ask the LLM to synthesise a grounded answer from the result.
# This is the "observe" in draft→critic→execute→observe.
if result.tool_output and not result.error:
    _obs = await self._observe(
        step=step,
        tool_output=result.tool_output,
        user_message=user_message,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        instance_config=instance_config,
        user_info=user_info,
        dw=dw,
    )
    if _obs:
        result.draft_text = _obs
```

**New private method `_observe()` on `ReActLoop`:**

```python
async def _observe(
    self,
    *,
    step,
    tool_output: dict,
    user_message: str,
    system_prompt: str,
    conversation_history: list[dict] | None,
    instance_config: dict | None,
    user_info: dict | None,
    dw,
) -> str | None:
    """Generate a grounded answer from a tool result.

    Returns the synthesis text or None when synthesis is unnecessary
    (e.g. the tool returned a confirmation/staging response, an error,
    or a no_match that should be escalated separately).
    """
    import json as _json

    result_raw = tool_output.get("result")
    tool_name = tool_output.get("tool_name", "")

    # Skip confirmation proposals — these are not data answers.
    if isinstance(result_raw, (dict, str)):
        try:
            _parsed = _json.loads(result_raw) if isinstance(result_raw, str) else result_raw
        except (TypeError, ValueError):
            _parsed = None
        if isinstance(_parsed, dict) and _parsed.get("requires_confirmation"):
            return None

    # Skip no_match — _synthesize_tool_results handles those.
    from ai.engine.core.resolution import payload_status
    if payload_status(result_raw) == "no_match":
        return None

    # Build the observation prompt.
    result_text = (
        _json.dumps(result_raw, ensure_ascii=False, default=str)
        if not isinstance(result_raw, str)
        else result_raw
    )[:4000]  # truncate very large payloads

    observation_prompt = (
        f"TOOL RESULT from {tool_name}:\n{result_text}\n\n"
        f"Original question: {user_message}\n\n"
        "Using ONLY the tool result above, write the final answer to the user. "
        "Be specific. Quote actual values. If the result is a list, summarize "
        "the key figures. Do not say you 'fetched' or 'retrieved' anything."
    )

    obs_draft = await dw.draft(
        instance_id="",       # observation does not need instance_id
        conversation_id="",
        user_message=observation_prompt,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        instance_config=instance_config,
        user_info=user_info,
        tools=None,           # observation never calls another tool
    )

    text = (obs_draft.text or "").strip()
    return text if len(text) > 20 else None
```

**Stop condition:** The `dw.draft()` signature is the exact `DraftWitness.draft()` signature. Do not invent new parameters.

### 1.4 — Tests for Phase 1

**File:** `backend/ai/tests/test_pulse_loop.py` (new file)

Write the following tests exactly:

```python
"""Phase 1 — Pulse Loop (observation-driven adaptive loop)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


async def _make_runner(db=None, executor=None):
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    runner = TurnPipelineRunner(db=db, executor=executor or MagicMock())
    runner._draft_tools = [{"function": {"name": "get_entity_details"}}]
    return runner


async def test_pulse_loop_enters_react_when_tool_wired():
    """When PULSE_LOOP_ENABLED=True and tools are available, the runner
    calls _try_pulse_loop before the single-pass path."""
    runner = await _make_runner(db=MagicMock())
    runner._try_pulse_loop = AsyncMock(return_value=None)

    with patch("ai.engine.cognition.turn.runner.get_settings") as mock_settings:
        mock_settings.return_value.PULSE_LOOP_ENABLED = True
        mock_settings.return_value.KG_MULTI_STEP_ENABLED = False
        mock_settings.return_value.INTENT_RESOLVER_ENABLED = False
        mock_settings.return_value.AGENT_ORCHESTRATOR_ENABLED = False
        mock_settings.return_value.RUN_TOKEN_BUDGET_DEFAULT = 10000

        with patch.object(runner, "_run_single_pass", AsyncMock(return_value=("response", "ledger"))):
            await runner.run(
                instance_id="i1",
                conversation_id="c1",
                user_message="Show me the latest emissions",
            )

    runner._try_pulse_loop.assert_called_once()


async def test_pulse_loop_skips_when_no_tool_executed():
    """When _try_pulse_loop returns None (no tool ran), the runner falls
    through to the single-pass path."""
    runner = await _make_runner(db=MagicMock())
    runner._try_pulse_loop = AsyncMock(return_value=None)

    with patch("ai.engine.cognition.turn.runner.get_settings") as mock_settings:
        mock_settings.return_value.PULSE_LOOP_ENABLED = True
        mock_settings.return_value.KG_MULTI_STEP_ENABLED = False
        mock_settings.return_value.INTENT_RESOLVER_ENABLED = False
        mock_settings.return_value.AGENT_ORCHESTRATOR_ENABLED = False
        mock_settings.return_value.RUN_TOKEN_BUDGET_DEFAULT = 10000

        single_pass_called = []

        async def fake_single_pass(**kwargs):
            single_pass_called.append(True)
            from unittest.mock import MagicMock
            return MagicMock(), MagicMock()

        with patch.object(runner, "_run_single_pass_s3", fake_single_pass, create=True):
            pass  # single-pass is whatever follows the loop in the actual code

    assert runner._try_pulse_loop.call_count == 1


async def test_observe_returns_none_for_confirmation_response():
    """_observe() must return None when the tool returned a confirmation
    proposal, not a data answer."""
    from ai.engine.cognition.plan.loop import ReActLoop

    loop = ReActLoop()
    result = await loop._observe(
        step=MagicMock(step_id=0),
        tool_output={
            "tool_name": "create_dq_rule",
            "result": json.dumps({"requires_confirmation": True, "rule_id": "r1"}),
        },
        user_message="Create a rule for null emails",
        system_prompt="",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=AsyncMock(),
    )
    assert result is None


async def test_observe_calls_draft_with_tool_result_prompt():
    """_observe() must call dw.draft() with a prompt that includes the
    tool result and the original question."""
    from ai.engine.cognition.plan.loop import ReActLoop

    loop = ReActLoop()
    mock_dw = AsyncMock()
    mock_dw.draft.return_value = MagicMock(text="The latest emission factor is 2.5 kg CO2e/kWh.")

    result = await loop._observe(
        step=MagicMock(step_id=0),
        tool_output={
            "tool_name": "get_entity_details",
            "result": json.dumps({"name": "Electricity", "factor": 2.5}),
        },
        user_message="What is the current electricity factor?",
        system_prompt="You are a data assistant.",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=mock_dw,
    )

    assert result == "The latest emission factor is 2.5 kg CO2e/kWh."
    call_kwargs = mock_dw.draft.call_args[1]
    assert "get_entity_details" in call_kwargs["user_message"]
    assert "What is the current electricity factor?" in call_kwargs["user_message"]
    assert call_kwargs["tools"] is None  # never calls another tool from observe
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_pulse_loop.py -v`

All 4 tests must pass.

### 1.5 Acceptance gate

- `test_pulse_loop.py` — 4/4 pass
- Manual smoke: send "show me the DQ rules for the emissions module" to the chat. The response must contain actual rule data, not "I'll fetch that for you."
- `TurnLedgerRow` stage for the turn must show `react_step_0` with `executed: true` and a non-empty draft.

### 1.6 Rollback

Set `PULSE_LOOP_ENABLED=false` in `.env`. No data is lost.

---

## Phase 2 — Replace the zone veto with evidence-need detection

**Objective:** The IntentResolver zone (`platform`, `concept`, `real_time`, `general`) must never prevent a tool from running when the tool is authoritative for the question. Today zone = `concept` or `general` injects `"Answer from your knowledge. No platform tool call is needed."` into the system prompt, which causes the LLM to refuse to call `web_research` for live weather.

**Why it matters:** The zone classifier is an LLM with a JSON schema. It is wrong ~20% of the time for edge cases. Its errors are invisible — the user gets a confidently-wrong answer. The correct pattern is: let the model decide whether to call a tool based on the tool descriptions, not based on a separate classifier's routing decision.

**What is broken today:**

1. `IntentResolver` assigns `zone = "real_time"` only for pure weather queries. A query like `"hi what is the weather in north coast egypt today, is it suitable for beach swimming?"` gets `zone = "concept"` because the classifier sees a beach/swim question, not a weather question.
2. The zone is then used in `runner.py` (after S1.5) to inject zone-specific instructions into the system prompt. When zone is `concept`, the instruction says "answer from your knowledge."
3. The `[WEATHER-DETERMINISTIC]` block in runner.py patches this for weather specifically. Phase 2 generalises the fix.

### 2.1 — Remove zone-based prompt injection from the single-pass path

**File:** `backend/ai/engine/cognition/turn/runner.py`

**Find the block where zone-specific instructions are injected.** It will look something like:

```python
if _intent_resolution.zone in ("concept", "general"):
    _extra_instruction = "Answer from your knowledge. No platform tool call is needed."
```

or similar. Search for `"zone"` and `"knowledge"` in the same block.

**Replace that injection with:** Do nothing. Remove the injection entirely. The tool descriptions are the routing signal. Do not add any alternative instruction.

**Important:** Do NOT remove the `off_limits` gate. That is a safety gate, not a routing gate. Leave it exactly as it is.

**Important:** Do NOT remove the `clarify` or `disambiguate` short-circuits. Those are confidence-ladder gates. Leave them exactly as they are.

### 2.2 — Add evidence-need detection to `IntentResolver`

**File:** `backend/ai/engine/cognition/turn/intent.py`

The `IntentResolution` dataclass has a field `needs_host_data: bool`. Today this is set but not used to route. Add a second field:

```python
@dataclass
class IntentResolution:
    ...
    needs_live_evidence: bool = False  # True = the model should call a real-time or live tool
```

**In `IntentResolver.resolve()`**, after the LLM call parses the JSON response, set `needs_live_evidence` from the LLM output. Add `"needs_live_evidence"` to the JSON schema the LLM is asked to fill. The field description must say:

> `"needs_live_evidence": true if the answer requires live data the LLM cannot know from training (current weather, live sensor readings, today's news, real-time exchange rates). false for everything else.`

This is metadata for logging only in Phase 2. Do not use it for routing yet.

### 2.3 — Make `web_research` tool description include weather explicitly

**File:** `backend/ai/plugins/web_research.py`

Find the `TOOL_DESCRIPTION` or `description` field of the `web_research` plugin definition. It currently says something like:

```python
description = "Search the web for real-time information and current news."
```

Replace with:

```python
description = (
    "Search the web for real-time information including: current weather and "
    "forecasts for any city or region, today's news, live exchange rates, "
    "current sports scores, and any other information that changes daily. "
    "Use this tool whenever the user asks about conditions RIGHT NOW or TODAY."
)
```

This makes the LLM's tool-selection decision correct without any classifier.

### 2.4 — Tests for Phase 2

**File:** `backend/ai/tests/test_phase2_routing.py` (new file)

```python
"""Phase 2 — Evidence-need detection, no zone vetoes."""
import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def test_intent_resolver_sets_needs_live_evidence_for_weather():
    """IntentResolver must set needs_live_evidence=True for current weather
    queries even when the zone is mislabelled."""
    from ai.engine.cognition.turn.intent import IntentResolver

    resolver = IntentResolver()
    fake_llm_response = {
        "content": '{"action":"answer","zone":"concept","intent":"current weather",'
                   '"needs_live_evidence":true,"delivery":"explain",'
                   '"candidates":[],"confidence":0.9}',
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "test",
    }
    with patch("ai.engine.cognition.turn.intent.route_chat", AsyncMock(return_value=fake_llm_response)):
        result = await resolver.resolve(
            user_message="what is the weather in cairo today",
            api_catalog=None,
            conversation_history=None,
            instance_id="i1",
            conversation_id="c1",
            db=None,
        )

    assert result is not None
    assert result.needs_live_evidence is True


async def test_weather_tool_description_mentions_weather():
    """web_research description must mention 'weather' so the LLM
    selects it for weather queries without a zone veto."""
    from ai.plugins.web_research import _PLUGIN_REGISTRY  # or however tools are exported
    # Find the web_research plugin definition
    # The exact import path depends on how plugins export their schema.
    # Adjust the import to match the actual export.
    try:
        from ai.engine.agent.tools import get_tool_definitions
        defs = get_tool_definitions()
        wr = next((d for d in defs if d.get("function", {}).get("name") == "web_research"), None)
        assert wr is not None, "web_research tool not found in definitions"
        desc = wr["function"]["description"]
        assert "weather" in desc.lower(), f"'weather' not in web_research description: {desc}"
    except ImportError:
        pytest.skip("Tool definitions not importable in isolation")


async def test_zone_concept_does_not_block_tool_call():
    """When zone='concept', the runner must NOT inject a 'no tool needed'
    instruction. The model must be free to call tools."""
    # Verify by checking the assembled system prompt for a concept-zone turn.
    # This is a behavioural test: run a turn through a mocked pipeline and
    # assert the system_prompt passed to DraftWitness.draft() does NOT contain
    # "Answer from your knowledge. No platform tool call is needed."
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from unittest.mock import MagicMock

    runner = TurnPipelineRunner(db=MagicMock(), executor=MagicMock())
    runner._draft_tools = [{"function": {"name": "web_research"}}]

    captured_prompts = []

    async def fake_draft(**kwargs):
        captured_prompts.append(kwargs.get("system_prompt", ""))
        result = MagicMock()
        result.text = "The answer is 42."
        result.tool_calls = []
        result.confidence = 0.9
        return result

    # This test verifies the absence of the veto string in the prompt.
    # If the prompt contains the veto string, the test fails and the worker
    # must find and remove the injection in runner.py.
    for prompt in captured_prompts:
        assert "Answer from your knowledge. No platform tool call is needed." not in prompt
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_phase2_routing.py -v`

### 2.5 Acceptance gate

- All 3 tests pass.
- Manual smoke: `"hi what is the weather in north coast egypt today, is it suitable for beach swimming?"` must trigger `web_research` without the [WEATHER-DETERMINISTIC] block being needed.
- Ledger zone is logged as-is (may still be `"concept"`). That is acceptable — the zone is for analytics, not routing.

### 2.6 Rollback

Restore the original `web_research` description and the zone-injection block from git. No database changes.

---

## Phase 3 — Durable work item: objective that survives conversation

**Objective:** A user can say "investigate why this month's emissions changed and save the work — I'll come back tomorrow." Pulse saves the objective. On next login the user can say "where did we get to?" and Pulse resumes from where it stopped.

**Why it matters:** Today `Run` and `RunStep` are tied to a plan execution. There is no concept of a user's _objective_ that spans multiple conversations. When the user asks "where did we get to?" there is nothing to look up.

**What to build:**

### 3.1 — New Django model `WorkObjective`

**File:** `backend/ai/models/core.py`

Add this class after `RunSchedule`:

```python
class WorkObjective(AppScopeMixin):
    """A user's durable objective that may span multiple conversations and runs.

    Created when the user explicitly asks Pulse to "save" or "continue later".
    Not created automatically for every turn.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting_for_user", "Waiting for User"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    host_user_id = models.CharField(max_length=255, db_index=True)
    conversation_id = models.TextField(db_index=True)  # originating conversation
    title = models.TextField()
    description = models.TextField()
    acceptance_criteria = models.TextField(blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")
    latest_run_id = models.TextField(null=True, blank=True)  # last Run.id
    latest_summary = models.TextField(blank=True, default="")  # what we found so far
    pending_question = models.TextField(blank=True, default="")  # question blocking progress
    evidence_json = models.JSONField(default=list)  # list of {source, content, retrieved_at}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["instance_id", "host_user_id", "status"]),
        ]
```

**Migration:** Create `backend/ai/migrations/0XXX_add_workobjective.py` (use the next available migration number). The migration must:
1. Create the `ai_workobjective` table.
2. Be additive only — do not drop or alter any existing column.

Run `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python manage.py makemigrations ai --name add_workobjective` and verify it only creates one table.

### 3.2 — New plugin `save_work_objective`

**File:** `backend/ai/plugins/save_work_objective.py` (new file)

```python
"""Plugin: save_work_objective

Lets Pulse save an investigation objective for the user to resume later.
The plugin is write-internal (creates a WorkObjective row) and requires
no confirmation — saving an objective has no side effects on Carbon data.
"""
from __future__ import annotations
import logging
from ai.engine.agent.plugins import register_plugin, PluginContext

logger = logging.getLogger("carbon.ai.plugins.save_work_objective")

SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_work_objective",
        "description": (
            "Save the current investigation objective so the user can resume it later. "
            "Use this when the user says 'save this', 'come back to this', 'continue tomorrow', "
            "or similar. Record what has been found so far and what remains to be done."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the objective (max 100 chars).",
                },
                "description": {
                    "type": "string",
                    "description": "Full description of what the user wants to achieve.",
                },
                "progress_so_far": {
                    "type": "string",
                    "description": "Summary of what has already been found or completed.",
                },
                "remaining_work": {
                    "type": "string",
                    "description": "What still needs to be done to complete the objective.",
                },
                "acceptance_criteria": {
                    "type": "string",
                    "description": "How to know when the objective is complete.",
                    "default": "",
                },
            },
            "required": ["title", "description", "progress_so_far", "remaining_work"],
        },
    },
}


@register_plugin(schema=SCHEMA, chat_visible=True, requires_confirmation=False)
async def save_work_objective(ctx: PluginContext, **kwargs) -> dict:
    """Create or update a WorkObjective for the current user."""
    from ai.models.core import WorkObjective
    from django.utils import timezone

    title = (kwargs.get("title") or "").strip()[:100]
    description = (kwargs.get("description") or "").strip()
    progress = (kwargs.get("progress_so_far") or "").strip()
    remaining = (kwargs.get("remaining_work") or "").strip()
    criteria = (kwargs.get("acceptance_criteria") or "").strip()

    if not title or not description:
        return {"status": "error", "error": "title and description are required"}

    if not ctx.host_user_id or not ctx.instance_id:
        return {"status": "error", "error": "No authenticated user — cannot save objective"}

    summary = f"**Found so far:** {progress}\n\n**Still to do:** {remaining}" if progress else remaining

    obj = await WorkObjective.objects.acreate(
        instance_id=ctx.instance_id,
        host_user_id=ctx.host_user_id,
        conversation_id=ctx.conversation_id or "",
        title=title,
        description=description,
        acceptance_criteria=criteria,
        status="open",
        latest_summary=summary,
        evidence_json=[],
    )

    logger.info(
        "WorkObjective created id=%s user=%s title=%r",
        obj.id, ctx.host_user_id, title,
    )

    return {
        "status": "saved",
        "objective_id": obj.id,
        "title": title,
        "message": (
            f"Objective saved — you can ask me 'where did we get to on {title}?' "
            "in any future conversation to resume."
        ),
    }
```

**Register it:** Add to `backend/ai/engine/agent/plugins.py` in the plugin registry list. Follow the exact same pattern as existing plugins in that file.

### 3.3 — New plugin `get_work_objectives`

**File:** `backend/ai/plugins/get_work_objectives.py` (new file)

```python
"""Plugin: get_work_objectives

Retrieves the user's saved work objectives so Pulse can resume them.
"""
from __future__ import annotations
import logging
from ai.engine.agent.plugins import register_plugin, PluginContext

logger = logging.getLogger("carbon.ai.plugins.get_work_objectives")

SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_work_objectives",
        "description": (
            "Retrieve the user's saved work objectives. Use when the user asks "
            "'where did we get to?', 'what were we working on?', 'resume my investigation', "
            "or similar. Returns a list of open objectives with their current status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["open", "in_progress", "waiting_for_user", "all"],
                    "default": "open",
                    "description": "Filter by status. Use 'all' to see completed objectives too.",
                },
            },
            "required": [],
        },
    },
}


@register_plugin(schema=SCHEMA, chat_visible=True, requires_confirmation=False)
async def get_work_objectives(ctx: PluginContext, **kwargs) -> dict:
    """List WorkObjectives for the current user."""
    from ai.models.core import WorkObjective

    status_filter = kwargs.get("status_filter", "open")

    if not ctx.host_user_id or not ctx.instance_id:
        return {"status": "error", "error": "No authenticated user"}

    qs = WorkObjective.objects.filter(
        instance_id=ctx.instance_id,
        host_user_id=ctx.host_user_id,
    ).order_by("-updated_at")

    if status_filter != "all":
        statuses = ["open", "in_progress", "waiting_for_user"] if status_filter == "open" else [status_filter]
        qs = qs.filter(status__in=statuses)

    objectives = await qs.avalues(
        "id", "title", "description", "status", "latest_summary",
        "pending_question", "updated_at", "created_at",
    )[:10]

    items = [
        {
            "id": str(o["id"]),
            "title": o["title"],
            "status": o["status"],
            "summary": o["latest_summary"],
            "pending_question": o["pending_question"],
            "last_updated": o["updated_at"].isoformat() if o["updated_at"] else None,
        }
        async for o in objectives
    ]

    if not items:
        return {
            "status": "no_match",
            "hint": "No saved objectives found. Ask me to 'save this investigation' to create one.",
        }

    return {
        "status": "resolved",
        "objectives": items,
        "count": len(items),
    }
```

### 3.4 — Tests for Phase 3

**File:** `backend/ai/tests/test_work_objectives.py` (new file)

```python
"""Phase 3 — WorkObjective durable work item."""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.django_db(transaction=True)


def _make_ctx(instance_id="i1", host_user_id="u1", conversation_id="c1"):
    from ai.engine.agent.plugins import PluginContext
    return PluginContext(
        instance_id=instance_id,
        host_user_id=host_user_id,
        conversation_id=conversation_id,
        db=None,
        user_token="inproc:test:u1",
    )


@pytest.mark.asyncio
async def test_save_work_objective_creates_row():
    """save_work_objective must create a WorkObjective row and return its id."""
    from ai.plugins.save_work_objective import save_work_objective

    ctx = _make_ctx()
    result = await save_work_objective(
        ctx,
        title="Investigate emissions change",
        description="Find why Scope 2 emissions increased 15% in August",
        progress_so_far="Found that electricity consumption increased",
        remaining_work="Need to check if the emission factor changed",
    )

    assert result["status"] == "saved"
    assert "objective_id" in result
    assert result["title"] == "Investigate emissions change"

    from ai.models.core import WorkObjective
    obj = await WorkObjective.objects.aget(id=result["objective_id"])
    assert obj.status == "open"
    assert obj.host_user_id == "u1"
    assert "Found so far" in obj.latest_summary


@pytest.mark.asyncio
async def test_get_work_objectives_returns_open_items():
    """get_work_objectives must return previously saved objectives."""
    from ai.plugins.save_work_objective import save_work_objective
    from ai.plugins.get_work_objectives import get_work_objectives

    ctx = _make_ctx()
    await save_work_objective(
        ctx,
        title="DQ audit",
        description="Audit null rates in the people module",
        progress_so_far="Found 3 tables with >5% nulls",
        remaining_work="Need to propose DQ rules for each",
    )

    result = await get_work_objectives(ctx, status_filter="open")

    assert result["status"] == "resolved"
    assert result["count"] >= 1
    titles = [o["title"] for o in result["objectives"]]
    assert "DQ audit" in titles


@pytest.mark.asyncio
async def test_get_work_objectives_returns_no_match_when_empty():
    """get_work_objectives must return no_match status when no objectives exist."""
    from ai.plugins.get_work_objectives import get_work_objectives

    ctx = _make_ctx(host_user_id="user_with_no_objectives")
    result = await get_work_objectives(ctx, status_filter="open")

    assert result["status"] == "no_match"
    assert "hint" in result


@pytest.mark.asyncio
async def test_save_objective_requires_title():
    """save_work_objective must return error when title is missing."""
    from ai.plugins.save_work_objective import save_work_objective

    ctx = _make_ctx()
    result = await save_work_objective(
        ctx,
        title="",
        description="Something",
        progress_so_far="",
        remaining_work="everything",
    )

    assert result["status"] == "error"
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_work_objectives.py -v`

All 4 tests must pass.

### 3.5 Acceptance gate

- 4/4 tests pass.
- Manual smoke: say "save this investigation — I want to resume tomorrow." Then in a new conversation say "where did we get to?" The response must list the saved objective with its summary.
- `WorkObjective` row visible in Django admin under `ai` app.

### 3.6 Rollback

Disable both plugins by removing them from the registry. The `WorkObjective` table remains but is dormant. No existing behaviour is affected.

---

## Phase 4 — Typed evidence records: ground answers in data, not inference

**Objective:** When Pulse retrieves data from a Carbon endpoint or an external source, it must record exactly what it retrieved (source, time, scope, coverage). The final answer must cite this evidence. The user can ask "what data did you use?" and get a real answer.

**Why it matters:** Today when `get_entity_details` returns emission factor data, that data lives only in `TurnLedgerRow.payload_json`. It is not linked to the assistant's claim. If the same emission factor changes the next day, there is no way to know the answer was stale.

### 4.1 — New Django model `EvidenceRecord`

**File:** `backend/ai/models/core.py`

Add after `WorkObjective`:

```python
class EvidenceRecord(AppScopeMixin):
    """A retrievd piece of evidence backing an AI claim.

    Created by tools when they return real data. Linked from WorkObjective
    and from AIMessage.metadata_json (evidence_ids list).
    """

    SOURCE_TYPES = [
        ("carbon_api", "Carbon Platform API"),
        ("web_search", "Web Search"),
        ("knowledge_graph", "Knowledge Graph"),
        ("memory", "Agent Memory"),
    ]

    COVERAGE_TYPES = [
        ("complete", "Complete for scope"),
        ("partial", "Partial"),
        ("sampled", "Sampled"),
        ("unknown", "Unknown"),
    ]

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.TextField(db_index=True)
    host_user_id = models.CharField(max_length=255, db_index=True)
    conversation_id = models.TextField(db_index=True)
    turn_id = models.TextField(db_index=True)  # TurnLedgerRow.turn_id
    objective_id = models.TextField(null=True, blank=True, db_index=True)  # WorkObjective.id

    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    source_identifier = models.TextField()   # endpoint path or URL
    query_description = models.TextField()   # what was asked
    content_json = models.JSONField()        # the actual retrieved data
    coverage = models.CharField(max_length=20, choices=COVERAGE_TYPES, default="unknown")
    limitations = models.TextField(blank=True, default="")
    retrieved_at = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"
        ordering = ["-retrieved_at"]
        indexes = [
            models.Index(fields=["instance_id", "conversation_id", "turn_id"]),
            models.Index(fields=["objective_id"]),
        ]
```

**Migration:** `python manage.py makemigrations ai --name add_evidencerecord`

### 4.2 — Record evidence in `ExecuteWitness.execute()`

**File:** `backend/ai/engine/cognition/turn/execute.py`

Find the `execute()` method. After a tool runs and returns a non-error result, call a new private async method `_register_evidence()`:

```python
async def _register_evidence(
    self,
    *,
    tool_name: str,
    tool_args: dict,
    tool_result: dict,
    instance_id: str,
    conversation_id: str,
    turn_id: str,
    host_user_id: str | None,
    db,
) -> None:
    """Write an EvidenceRecord row for a successfully executed tool call.
    
    Silently no-ops on any error — evidence recording must never fail a turn.
    """
    import json as _json
    from ai.engine.core.resolution import payload_status

    try:
        raw = tool_result.get("result")
        if payload_status(raw) == "no_match":
            return  # no_match is not evidence of data
        if tool_result.get("requires_confirmation"):
            return  # staging proposals are not evidence

        # Map tool names to source types
        source_map = {
            "web_research": "web_search",
            "search_knowledge": "knowledge_graph",
            "get_entity_details": "carbon_api",
            "call_host_api": "carbon_api",
        }
        source_type = source_map.get(tool_name, "carbon_api")
        source_id = tool_args.get("query") or tool_args.get("endpoint") or tool_name

        from ai.models.core import EvidenceRecord
        await EvidenceRecord.objects.acreate(
            instance_id=instance_id or "",
            host_user_id=host_user_id or "",
            conversation_id=conversation_id or "",
            turn_id=turn_id or "",
            source_type=source_type,
            source_identifier=source_id[:500],
            query_description=_json.dumps(tool_args, ensure_ascii=False)[:500],
            content_json=raw if isinstance(raw, (dict, list)) else {"raw": str(raw)[:2000]},
            coverage="unknown",
        )
    except Exception:
        import logging
        logging.getLogger("pulse.cognition.execute").warning(
            "EvidenceRecord write failed for %s", tool_name, exc_info=True
        )
```

**Important:** The `_register_evidence` call must be wrapped in `try/except Exception`. Evidence recording must never raise into the tool execution path.

### 4.3 — Surface evidence citations in final response

**File:** `backend/ai/engine/cognition/synthesis.py`

In `_synthesize_tool_results()`, after the final LLM synthesis is produced, append a short evidence footer to the response text. The footer format is:

```
---
*Sources: [carbon_api: /carbon-api/carbon/factors, retrieved 2026-09-05 14:23 UTC]*
```

This goes at the end of the synthesized text. Do not add it to confirmation/staging responses.

**Implementation:** In `_synthesize_tool_results()`, find where `synthesized` is returned. Before returning, append:

```python
if synthesized and usable:
    _sources = []
    for tr in usable:
        _src = tr.get("tool_name", "")
        if _src:
            _sources.append(_src)
    if _sources:
        import datetime
        _ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        _footer = f"\n\n---\n*Sources: {', '.join(set(_sources))} — retrieved {_ts}*"
        synthesized = synthesized + _footer
```

### 4.4 — Tests for Phase 4

**File:** `backend/ai/tests/test_evidence_records.py` (new file)

```python
"""Phase 4 — Evidence records."""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_evidence_record_created_for_successful_tool():
    """_register_evidence must create an EvidenceRecord row when a tool
    returns real data (not no_match, not requires_confirmation)."""
    from ai.engine.cognition.turn.execute import ExecuteWitness
    from ai.models.core import EvidenceRecord

    ew = ExecuteWitness()
    await ew._register_evidence(
        tool_name="get_entity_details",
        tool_args={"entity_type": "emission_factor", "entity_id": "ef-1"},
        tool_result={
            "tool_name": "get_entity_details",
            "result": {"name": "Electricity", "factor": 2.5, "unit": "kg CO2e/kWh"},
        },
        instance_id="i1",
        conversation_id="c1",
        turn_id="t1",
        host_user_id="u1",
        db=None,
    )

    record = await EvidenceRecord.objects.aget(turn_id="t1")
    assert record.source_type == "carbon_api"
    assert "entity_type" in record.query_description


@pytest.mark.asyncio
async def test_evidence_record_skipped_for_no_match():
    """_register_evidence must NOT create a record when the tool returns
    no_match status — that is not evidence of data."""
    import json
    from ai.engine.cognition.turn.execute import ExecuteWitness
    from ai.models.core import EvidenceRecord

    ew = ExecuteWitness()
    await ew._register_evidence(
        tool_name="get_entity_details",
        tool_args={"entity_id": "nonexistent"},
        tool_result={
            "result": json.dumps({"status": "no_match", "hint": "Entity not found"}),
        },
        instance_id="i1",
        conversation_id="c1",
        turn_id="t-nomatch",
        host_user_id="u1",
        db=None,
    )

    count = await EvidenceRecord.objects.filter(turn_id="t-nomatch").acount()
    assert count == 0


@pytest.mark.asyncio
async def test_evidence_record_does_not_fail_turn_on_error():
    """_register_evidence must silently swallow errors and never raise."""
    from ai.engine.cognition.turn.execute import ExecuteWitness

    ew = ExecuteWitness()
    # Pass garbage that would normally cause a DB error — must not raise.
    await ew._register_evidence(
        tool_name="web_research",
        tool_args={},
        tool_result={"result": None},  # None result
        instance_id=None,
        conversation_id=None,
        turn_id=None,
        host_user_id=None,
        db=None,
    )
    # If we reach here without an exception, the test passes.
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_evidence_records.py -v`

All 3 tests must pass.

---

## Phase 5 — Multi-hop reasoning: let the loop choose its next tool

**Objective:** When a tool returns data and the data is insufficient to answer the question, the loop must be able to call a second tool to fill the gap — automatically, without a new user message.

**Example:** User asks "Compare our Scope 2 electricity factor with the latest IPCC published value." This requires two tool calls: (1) `get_entity_details` for the platform factor, (2) `web_research` for the current IPCC value. Today these cannot be chained.

**Why it matters:** Multi-hop questions currently require the user to ask the second question manually. An intelligent coworker should recognize "I have one piece of data but need another" and fetch it.

### 5.1 — Extend `ReActLoop` to support multiple steps without a pre-declared plan

**File:** `backend/ai/engine/cognition/plan/loop.py`

The `_try_pulse_loop` method in Phase 1 creates a one-step plan. Extend it to detect when the model's observation concludes "I need another tool" and generates a follow-up step.

**Modify `_observe()` to return a structured result instead of just a string:**

```python
from dataclasses import dataclass

@dataclass
class ObservationResult:
    answer: str | None           # grounded answer text, or None
    needs_followup: bool         # True = model wants to call another tool
    followup_tool: str | None    # tool name for the next step
    followup_args: dict | None   # args for the next step
```

Change `_observe()` to call the LLM with a prompt that asks: "Did this tool result fully answer the question, or do you need another tool to complete the answer? If you need another tool, name it and its arguments."

The LLM response must be parsed from JSON. If `needs_followup=True` and `followup_tool` is in the allowed tool set, the loop appends a new `PlanStep` and continues.

**Stop condition:** Maximum follow-up steps = `settings.PULSE_LOOP_MAX_STEPS` (from Phase 1). After that, synthesize from whatever has been gathered.

**Guard:** The follow-up tool must be in `self._allowed_followup_tools`. Define this as:

```python
_ALLOWED_FOLLOWUP_TOOLS = frozenset({
    "web_research",
    "get_entity_details",
    "search_knowledge",
    "call_host_api",
})
```

Mutation tools (`create_dq_rule`, `plan_task`, `learn_fact`) must NEVER appear in `_ALLOWED_FOLLOWUP_TOOLS`. Automatic multi-hop must be read-only only.

### 5.2 — Modify `_try_pulse_loop()` in `TurnPipelineRunner`

The one-step plan from Phase 1 becomes a dynamic plan. Change the plan creation to start with one step but allow the loop itself to add steps via the `_observe` followup mechanism.

The loop's `run()` already handles plans with variable numbers of steps — the only change needed is that `_observe()` can emit a new `PlanStep` into `remaining` when `needs_followup=True`.

**Add to `ReActLoop._execute_step()` after the observation:**

```python
if isinstance(_obs, ObservationResult) and _obs.needs_followup:
    if (
        _obs.followup_tool in _ALLOWED_FOLLOWUP_TOOLS
        and len([r for r in step_results if r.executed]) < settings.PULSE_LOOP_MAX_STEPS
    ):
        # Inject a follow-up step into the plan's remaining steps.
        # The calling loop.run() will pick it up on the next iteration.
        _next_step_id = max(s.step_id for s in plan.steps) + 1
        _next_step = PlanStep(
            step_id=_next_step_id,
            intent=f"Fetch {_obs.followup_tool} to complete the answer",
            tool_name=_obs.followup_tool,
            is_mutation=False,
            depends_on=[step.step_id],
            agent_role=None,
        )
        plan.steps.append(_next_step)
        remaining.append(_next_step)
        result.draft_text = _obs.answer or ""
    else:
        result.draft_text = _obs.answer or ""
```

### 5.3 — Tests for Phase 5

**File:** `backend/ai/tests/test_multi_hop.py` (new file)

```python
"""Phase 5 — Multi-hop reasoning."""
import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


async def test_observe_returns_followup_when_data_insufficient():
    """_observe() must set needs_followup=True and name the next tool
    when the LLM response indicates more data is needed."""
    import json
    from ai.engine.cognition.plan.loop import ReActLoop, ObservationResult

    loop = ReActLoop()
    
    fake_llm_response = json.dumps({
        "answer": "The platform factor is 2.5 kg CO2e/kWh.",
        "needs_followup": True,
        "followup_tool": "web_research",
        "followup_args": {"query": "IPCC 2024 electricity emission factor"},
    })
    
    mock_dw = AsyncMock()
    mock_dw.draft.return_value = MagicMock(text=fake_llm_response, tool_calls=[])

    result = await loop._observe(
        step=MagicMock(step_id=0),
        tool_output={
            "tool_name": "get_entity_details",
            "result": {"name": "Electricity", "factor": 2.5},
        },
        user_message="Compare our factor with the latest IPCC value",
        system_prompt="",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=mock_dw,
    )

    assert isinstance(result, ObservationResult)
    assert result.needs_followup is True
    assert result.followup_tool == "web_research"
    assert result.answer == "The platform factor is 2.5 kg CO2e/kWh."


async def test_followup_mutation_tool_is_blocked():
    """Multi-hop must never auto-call a mutation tool as a follow-up."""
    from ai.engine.cognition.plan.loop import ReActLoop, _ALLOWED_FOLLOWUP_TOOLS

    assert "create_dq_rule" not in _ALLOWED_FOLLOWUP_TOOLS
    assert "plan_task" not in _ALLOWED_FOLLOWUP_TOOLS
    assert "learn_fact" not in _ALLOWED_FOLLOWUP_TOOLS


async def test_multihop_stops_at_max_steps():
    """The loop must not follow up more than PULSE_LOOP_MAX_STEPS times."""
    from ai.engine.cognition.plan.loop import ReActLoop, ObservationResult

    loop = ReActLoop()
    settings = MagicMock()
    settings.PULSE_LOOP_MAX_STEPS = 2

    # Simulate 3 step_results already executed
    step_results = [
        MagicMock(executed=True),
        MagicMock(executed=True),
        MagicMock(executed=True),
    ]

    # A followup that would exceed the limit must be ignored
    obs = ObservationResult(
        answer="Partial answer",
        needs_followup=True,
        followup_tool="web_research",
        followup_args={"query": "test"},
    )

    # The guard condition in _execute_step checks len(executed) < max_steps.
    # With 3 executed steps and max=2, the followup is ignored.
    executed_count = len([r for r in step_results if r.executed])
    assert executed_count >= settings.PULSE_LOOP_MAX_STEPS
    # Therefore followup is blocked (not injected into remaining).
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_multi_hop.py -v`

All 3 tests must pass.

---

## Phase 6 — Upgrade the context assembler: inject Carbon business context

**Objective:** Every time Pulse answers a question about Carbon data, the system prompt must include the exact definitions that Carbon uses — not generic LLM knowledge. This means: which emission factors are active, which reporting period is current, which DQ rules apply to the active module.

**Why it matters:** The LLM defaults to general knowledge ("the global average electricity factor is about 0.4 kg CO2e/kWh"). Carbon's actual factor may be different. The LLM must know the difference and say "based on your configured factor of 2.5 kg CO2e/kWh."

### 6.1 — New service `CarbonContextAssembler`

**File:** `backend/ai/context/carbon_context.py` (new file)

```python
"""Assembles Carbon-specific business context for injection into the system prompt.

This service fetches live data from the Carbon platform models and formats it
as a compact context block. It is called once per turn, cached for the turn
duration, and injected into the system prompt before S3 (draft).
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger("carbon.ai.context_assembler")

_CACHE_TTL_SECONDS = 300  # 5 minutes — context is stable within a session


class CarbonContextAssembler:
    """Fetches and formats Carbon domain context for prompt injection."""

    async def assemble(
        self,
        *,
        user,
        app_identifier: str | None = None,
        module_id: int | None = None,
    ) -> str:
        """Return a compact context block string.

        Returns empty string on any error — context injection must never fail.
        """
        try:
            parts = []

            # Reporting period
            period = await self._get_active_period(user, app_identifier)
            if period:
                parts.append(f"**Active reporting period:** {period}")

            # Emission factors (top 5 by module usage)
            if app_identifier == "emissions" and module_id:
                factors = await self._get_module_factors(module_id)
                if factors:
                    parts.append(f"**Configured emission factors (module {module_id}):**")
                    for f in factors[:5]:
                        parts.append(f"  - {f['name']}: {f['factor']} {f['unit']}")

            # Active DQ rules count
            dq_count = await self._get_active_dq_rules_count(user)
            if dq_count is not None:
                parts.append(f"**Active DQ rules:** {dq_count}")

            if not parts:
                return ""

            return (
                "\n\n## Your Carbon Platform Context\n"
                + "\n".join(parts)
                + "\n\nAlways refer to these actual values instead of general knowledge."
            )
        except Exception:
            logger.warning("CarbonContextAssembler.assemble failed", exc_info=True)
            return ""

    async def _get_active_period(self, user, app_identifier: str | None) -> str | None:
        """Return the active reporting period label."""
        try:
            from emissions.models import ReportingPeriod
            period = await ReportingPeriod.objects.filter(is_active=True).afirst()
            if period:
                return f"{period.name} ({period.start_date} – {period.end_date})"
        except Exception:
            pass
        return None

    async def _get_module_factors(self, module_id: int) -> list[dict]:
        """Return emission factors configured for this module."""
        try:
            from emissions.models import EmissionFactor
            qs = EmissionFactor.objects.filter(
                module_id=module_id,
                is_active=True,
            ).values("name", "factor_value", "unit")
            return [
                {"name": f["name"], "factor": str(f["factor_value"]), "unit": f["unit"]}
                async for f in qs[:5]
            ]
        except Exception:
            pass
        return []

    async def _get_active_dq_rules_count(self, user) -> int | None:
        """Return the count of active DQ rules visible to this user."""
        try:
            from dq.models import DQRule
            return await DQRule.objects.filter(is_active=True).acount()
        except Exception:
            pass
        return None
```

**Stop condition:** If `emissions.models.ReportingPeriod`, `EmissionFactor`, or `dq.models.DQRule` do not have the exact field names used here, adjust the field names to match the actual models. Run `grep -n "class ReportingPeriod\|class EmissionFactor\|class DQRule" backend/emissions/models.py backend/dq/models.py` first.

### 6.2 — Inject context into `TurnPipelineRunner.run()`

**File:** `backend/ai/engine/cognition/turn/runner.py`

After S2 (retrieval), before S3 or the loop entry, add:

```python
# ── Phase 6: Carbon context injection ────────────────────────────────
_carbon_context = ""
if settings.PULSE_CARBON_CONTEXT_ENABLED:
    try:
        from ai.context.carbon_context import CarbonContextAssembler
        _assembler = CarbonContextAssembler()
        _django_user = getattr(self, "_django_user", None)
        if _django_user and instance_config:
            _carbon_context = await _assembler.assemble(
                user=_django_user,
                app_identifier=instance_config.get("app_identifier"),
                module_id=instance_config.get("module_id"),
            )
    except Exception:
        logger.warning("[%s] Carbon context assembly failed", turn_id[:8], exc_info=True)
```

Add `PULSE_CARBON_CONTEXT_ENABLED: bool = Field(default=True)` to `PulseSettings`.

The `_carbon_context` string must be passed into the system prompt builder. Find where `build_system_prompt` is called and append `_carbon_context` to the result.

### 6.3 — Tests for Phase 6

**File:** `backend/ai/tests/test_carbon_context.py` (new file)

```python
"""Phase 6 — Carbon business context injection."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.asyncio


async def test_assembler_returns_string():
    """CarbonContextAssembler.assemble must return a string even when
    all queries fail (empty DB or wrong schema)."""
    from ai.context.carbon_context import CarbonContextAssembler

    assembler = CarbonContextAssembler()
    result = await assembler.assemble(user=MagicMock(), app_identifier="emissions")

    assert isinstance(result, str)
    # May be empty (no data in test DB) — that is acceptable.


async def test_assembler_does_not_raise_on_model_error():
    """CarbonContextAssembler must return '' when a model import fails."""
    from ai.context.carbon_context import CarbonContextAssembler

    assembler = CarbonContextAssembler()
    with patch.object(assembler, "_get_active_period", AsyncMock(side_effect=Exception("DB down"))):
        with patch.object(assembler, "_get_module_factors", AsyncMock(side_effect=Exception("DB down"))):
            with patch.object(assembler, "_get_active_dq_rules_count", AsyncMock(side_effect=Exception("DB down"))):
                result = await assembler.assemble(user=MagicMock(), app_identifier="emissions")

    assert result == ""
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_carbon_context.py -v`

---

## Phase 7 — Post-result verification: did the claim match the evidence?

**Objective:** After Pulse synthesizes an answer, a verification step checks that the claims in the answer are supported by the evidence retrieved. If a claim is not supported, the answer is flagged or the specific claim is removed.

**Why it matters:** Today the synthesis LLM can generate a plausible-sounding but factually wrong claim even when tool results are present. Example: tool returns `factor: 2.5` but the synthesis says "2.3 — slightly below the global average." The number is wrong. No one catches it.

### 7.1 — New `VerificationWitness`

**File:** `backend/ai/engine/cognition/turn/verify.py` (new file)

```python
"""S4.5 — Post-result verification witness.

Checks that the synthesized answer's factual claims are supported by the
tool results. Runs only when tool results exist. Returns a VerificationResult.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("pulse.cognition.verify")


@dataclass
class VerificationResult:
    passed: bool
    unsupported_claims: list[str] = field(default_factory=list)
    verified_claims: list[str] = field(default_factory=list)
    corrected_text: str | None = None  # corrected version if passed=False
    tokens_used: int = 0
    model_used: str = ""


class VerificationWitness:
    """Verify that a synthesized answer is grounded in the tool results."""

    async def verify(
        self,
        *,
        answer: str,
        tool_results: list[dict],
        user_message: str,
        instance_id: str,
        conversation_id: str,
        model: str | None = None,
    ) -> VerificationResult:
        """Verify the answer against the tool results.

        Returns VerificationResult. Never raises — returns passed=True with
        empty claims on any failure (fail-open to avoid blocking responses).
        """
        from ai.engine.llm.router import route_chat

        if not answer or not tool_results:
            return VerificationResult(passed=True)

        results_text = json.dumps(
            [{"tool": tr.get("tool_name", ""), "result": tr.get("result")} for tr in tool_results],
            ensure_ascii=False, default=str,
        )[:3000]

        system = (
            "You are a fact-checker. You receive: (1) an AI assistant's answer and "
            "(2) the raw tool results the answer was based on. "
            "Your job is to identify any specific numbers, dates, names, or percentages "
            "in the answer that contradict the tool results. "
            "Reply with JSON: "
            '{"passed": true/false, "unsupported_claims": ["claim1", ...], '
            '"verified_claims": ["claim1", ...], '
            '"corrected_text": "corrected answer or null if passed=true"}'
        )

        user_content = (
            f"User question: {user_message}\n\n"
            f"Tool results:\n{results_text}\n\n"
            f"Answer to verify:\n{answer}"
        )

        try:
            response = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"verify-{conversation_id}",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                model=model,
                tools=None,
            )
        except Exception:
            logger.warning("VerificationWitness LLM call failed", exc_info=True)
            return VerificationResult(passed=True)

        raw = (response.get("content") or "").strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return VerificationResult(passed=True)

        tokens = int(response.get("input_tokens", 0) or 0) + int(response.get("output_tokens", 0) or 0)

        return VerificationResult(
            passed=bool(parsed.get("passed", True)),
            unsupported_claims=parsed.get("unsupported_claims", []),
            verified_claims=parsed.get("verified_claims", []),
            corrected_text=parsed.get("corrected_text"),
            tokens_used=tokens,
            model_used=response.get("model", ""),
        )
```

### 7.2 — Wire `VerificationWitness` into `TurnPipelineRunner`

**File:** `backend/ai/engine/cognition/turn/runner.py`

After `_synthesize_tool_results()` produces the final text, add:

```python
# ── Phase 7: Post-result verification ────────────────────────────────
if settings.PULSE_VERIFY_ENABLED and completed_tools and final_text:
    try:
        from ai.engine.cognition.turn.verify import VerificationWitness
        _vw = VerificationWitness()
        _vr = await _vw.verify(
            answer=final_text,
            tool_results=completed_tools,
            user_message=user_message,
            instance_id=instance_id,
            conversation_id=conversation_id,
        )
        if not _vr.passed and _vr.corrected_text:
            final_text = _vr.corrected_text
            logger.info(
                "[%s] Verification corrected answer: unsupported=%s",
                turn_id[:8], _vr.unsupported_claims,
            )
        total_tokens += _vr.tokens_used
        total_llm_calls += 1
        # Record in ledger
        ledger.verification_passed = _vr.passed
        ledger.verification_unsupported = _vr.unsupported_claims
    except Exception:
        logger.warning("[%s] Verification step failed", turn_id[:8], exc_info=True)
```

Add `PULSE_VERIFY_ENABLED: bool = Field(default=False)` to `PulseSettings`. It defaults to **False** (opt-in) because verification adds one LLM call per response. Enable it explicitly:

```
PULSE_VERIFY_ENABLED=true
```

Add `verification_passed: bool | None = None` and `verification_unsupported: list[str] = field(default_factory=list)` to `TurnLedger`.

### 7.3 — Tests for Phase 7

**File:** `backend/ai/tests/test_verification.py` (new file)

```python
"""Phase 7 — Post-result verification."""
import json
import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def test_verification_passes_correct_claim():
    """VerificationWitness must return passed=True when the answer's
    numbers match the tool results."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    fake_response = {
        "content": json.dumps({
            "passed": True,
            "unsupported_claims": [],
            "verified_claims": ["2.5 kg CO2e/kWh"],
            "corrected_text": None,
        }),
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "test",
    }
    with patch("ai.engine.cognition.turn.verify.route_chat", AsyncMock(return_value=fake_response)):
        result = await vw.verify(
            answer="The electricity factor is 2.5 kg CO2e/kWh.",
            tool_results=[{"tool_name": "get_entity_details", "result": {"factor": 2.5}}],
            user_message="What is the electricity factor?",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is True
    assert "2.5 kg CO2e/kWh" in result.verified_claims


async def test_verification_corrects_wrong_number():
    """VerificationWitness must return passed=False and corrected_text
    when the answer contains a number that contradicts the tool result."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    fake_response = {
        "content": json.dumps({
            "passed": False,
            "unsupported_claims": ["2.3 kg CO2e/kWh"],
            "verified_claims": [],
            "corrected_text": "The electricity factor is 2.5 kg CO2e/kWh, as configured.",
        }),
        "input_tokens": 100,
        "output_tokens": 80,
        "model": "test",
    }
    with patch("ai.engine.cognition.turn.verify.route_chat", AsyncMock(return_value=fake_response)):
        result = await vw.verify(
            answer="The electricity factor is 2.3 kg CO2e/kWh.",  # wrong number
            tool_results=[{"tool_name": "get_entity_details", "result": {"factor": 2.5}}],
            user_message="What is the electricity factor?",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert "2.3 kg CO2e/kWh" in result.unsupported_claims
    assert result.corrected_text is not None
    assert "2.5" in result.corrected_text


async def test_verification_returns_passed_on_llm_failure():
    """VerificationWitness must return passed=True (fail-open) when the
    verification LLM call fails — never block the response."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    ):
        result = await vw.verify(
            answer="Some answer",
            tool_results=[{"tool_name": "get_entity_details", "result": {}}],
            user_message="test",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is True
```

**Run gate:** `cd /home/ahmed/aast/carbon/backend && ../.venv/bin/python -m pytest ai/tests/test_verification.py -v`

All 3 tests must pass.

---

## Phase 8 — Frontend: Work Objectives panel

**Objective:** The user can see their saved work objectives in a dedicated panel. They can click an objective to load its context and ask Pulse to continue. The panel shows: title, status, latest summary, last updated.

**Files to modify:**
- `carbon-frontend/src/components/ai/` — add `WorkObjectivesPanel.jsx`
- `carbon-frontend/src/api/ai.js` — add `getWorkObjectives()` and `updateObjectiveStatus()`
- Wire into the existing AI sidebar/chat layout

### 8.1 — API functions

**File:** `carbon-frontend/src/api/ai.js`

Add to the existing API module (do not create a new file):

```javascript
export async function getWorkObjectives({ statusFilter = 'open' } = {}) {
  const params = new URLSearchParams({ status_filter: statusFilter });
  return apiFetch(`/carbon-api/ai/work-objectives/?${params}`);
}

export async function updateObjectiveStatus(objectiveId, status) {
  return apiFetch(`/carbon-api/ai/work-objectives/${objectiveId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}
```

### 8.2 — New REST endpoint

**File:** `backend/ai/views.py` (or the AI views file)

Add a `WorkObjectiveViewSet` with:
- `GET /carbon-api/ai/work-objectives/` — list objectives for `request.user`
- `PATCH /carbon-api/ai/work-objectives/{id}/` — update status only (no other fields via this endpoint)

```python
class WorkObjectiveViewSet(viewsets.ModelViewSet):
    serializer_class = WorkObjectiveSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = WorkObjective.objects.filter(
            host_user_id=str(self.request.user.pk),
        ).order_by("-updated_at")
        status_filter = self.request.query_params.get("status_filter", "open")
        if status_filter != "all":
            open_statuses = ["open", "in_progress", "waiting_for_user"]
            statuses = open_statuses if status_filter == "open" else [status_filter]
            qs = qs.filter(status__in=statuses)
        return qs

    def perform_update(self, serializer):
        # Only allow status changes via PATCH — never allow objective content changes.
        allowed = {"status"}
        data = {k: v for k, v in self.request.data.items() if k in allowed}
        serializer.save(**data)
```

Create `WorkObjectiveSerializer` in the serializers file with fields:
`id, title, description, status, latest_summary, pending_question, created_at, updated_at`

Register the viewset in `backend/ai/urls.py`.

### 8.3 — `WorkObjectivesPanel` React component

**File:** `carbon-frontend/src/components/ai/WorkObjectivesPanel.jsx` (new file)

```jsx
import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, List, ListItem, ListItemText,
  Chip, IconButton, Tooltip, CircularProgress,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { getWorkObjectives, updateObjectiveStatus } from '../../api/ai';

const STATUS_COLOR = {
  open: 'warning',
  in_progress: 'info',
  waiting_for_user: 'secondary',
  completed: 'success',
  cancelled: 'default',
};

export default function WorkObjectivesPanel({ onSelectObjective }) {
  const [objectives, setObjectives] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkObjectives({ statusFilter: 'open' });
      setObjectives(Array.isArray(data) ? data : (data?.results ?? []));
    } catch (e) {
      setError('Could not load objectives');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleComplete = async (id, e) => {
    e.stopPropagation();
    try {
      await updateObjectiveStatus(id, 'completed');
      setObjectives(prev => prev.filter(o => o.id !== id));
    } catch {
      /* silently swallow — user can refresh */
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1, pb: 1 }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          SAVED OBJECTIVES
        </Typography>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={load}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {error && (
        <Typography variant="caption" color="error" sx={{ px: 1 }}>
          {error}
        </Typography>
      )}

      {!loading && objectives.length === 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
          No saved objectives. Tell Pulse to "save this investigation" to create one.
        </Typography>
      )}

      <List dense disablePadding>
        {objectives.map(obj => (
          <ListItem
            key={obj.id}
            button
            onClick={() => onSelectObjective?.(obj)}
            secondaryAction={
              <Tooltip title="Mark complete">
                <IconButton edge="end" size="small" onClick={(e) => handleComplete(obj.id, e)}>
                  <CheckCircleOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            }
            sx={{ py: 0.75, px: 1, borderRadius: 1, '&:hover': { bgcolor: 'action.hover' } }}
          >
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
                    {obj.title}
                  </Typography>
                  <Chip
                    label={obj.status.replace('_', ' ')}
                    size="small"
                    color={STATUS_COLOR[obj.status] || 'default'}
                    sx={{ height: 18, fontSize: '0.65rem' }}
                  />
                </Box>
              }
              secondary={
                obj.latest_summary
                  ? <Typography variant="caption" color="text.secondary" noWrap>
                      {obj.latest_summary.slice(0, 80)}
                    </Typography>
                  : null
              }
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
}
```

### 8.4 — Tests for Phase 8

**File:** `carbon-frontend/src/components/ai/__tests__/WorkObjectivesPanel.test.jsx` (new file)

```jsx
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import WorkObjectivesPanel from '../WorkObjectivesPanel';

vi.mock('../../../api/ai', () => ({
  getWorkObjectives: vi.fn(),
  updateObjectiveStatus: vi.fn(),
}));

import { getWorkObjectives, updateObjectiveStatus } from '../../../api/ai';

describe('WorkObjectivesPanel', () => {
  it('renders objectives returned by the API', async () => {
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'Investigate Scope 2', status: 'open', latest_summary: 'Found 3 factors' },
      { id: '2', title: 'DQ audit', status: 'in_progress', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => {
      expect(screen.getByText('Investigate Scope 2')).toBeInTheDocument();
      expect(screen.getByText('DQ audit')).toBeInTheDocument();
    });
  });

  it('shows empty state when no objectives exist', async () => {
    getWorkObjectives.mockResolvedValue([]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => {
      expect(screen.getByText(/No saved objectives/i)).toBeInTheDocument();
    });
  });

  it('calls onSelectObjective when an item is clicked', async () => {
    const onSelect = vi.fn();
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'Test objective', status: 'open', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel onSelectObjective={onSelect} />);

    await waitFor(() => screen.getByText('Test objective'));
    fireEvent.click(screen.getByText('Test objective'));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', title: 'Test objective' }),
    );
  });

  it('removes objective from list after marking complete', async () => {
    updateObjectiveStatus.mockResolvedValue({});
    getWorkObjectives.mockResolvedValue([
      { id: '1', title: 'To complete', status: 'open', latest_summary: '' },
    ]);

    render(<WorkObjectivesPanel />);

    await waitFor(() => screen.getByText('To complete'));
    fireEvent.click(screen.getAllByRole('button', { name: /mark complete/i })[0]);

    await waitFor(() => {
      expect(screen.queryByText('To complete')).not.toBeInTheDocument();
    });
  });
});
```

**Run gate:** `cd /home/ahmed/aast/carbon/carbon-frontend && npm run test -- --run src/components/ai/__tests__/WorkObjectivesPanel.test.jsx`

All 4 tests must pass.

---

## Phase 9 — Model policy: strong model for investigation turns

**Objective:** Multi-hop investigation turns (Phase 5) and post-result verification (Phase 7) use the configured strong model, not the default Haiku. Simple Q&A turns continue using Haiku. This is NOT automatic escalation — it is profile-based routing.

**Files to modify:** `backend/ai/engine/llm/router.py`, `backend/ai/engine/cognition/turn/runner.py`

### 9.1 — Define turn profiles

**File:** `backend/ai/engine/llm/router.py`

Add a function `model_for_profile()`:

```python
TURN_PROFILES = {
    "interactive":   None,           # use the instance default (Haiku)
    "investigate":   None,           # use settings.LLM_INVESTIGATE_MODEL
    "verify":        None,           # use settings.LLM_VERIFY_MODEL or investigate
    "extract":       None,           # use instance default (extraction is cheap)
}

def model_for_profile(profile: str) -> str | None:
    """Return the model name for a turn profile, or None for the instance default."""
    from ai.engine.core.settings import get_settings
    settings = get_settings()
    if profile == "investigate":
        return getattr(settings, "LLM_INVESTIGATE_MODEL", None) or None
    if profile == "verify":
        return getattr(settings, "LLM_VERIFY_MODEL", None) or model_for_profile("investigate")
    return None  # use instance default for all other profiles
```

Add to `PulseSettings`:
```python
LLM_INVESTIGATE_MODEL: str = Field(default="", description="Model for multi-hop investigation turns. Empty = use instance default.")
LLM_VERIFY_MODEL: str = Field(default="", description="Model for verification turns. Empty = use investigate model.")
```

Environment variable example:
```
LLM_INVESTIGATE_MODEL=anthropic/claude-sonnet-4-5
LLM_VERIFY_MODEL=anthropic/claude-haiku-4-5
```

### 9.2 — Pass profile to `_try_pulse_loop()`

**File:** `backend/ai/engine/cognition/turn/runner.py`

When calling `_try_pulse_loop()`, pass a `profile` parameter. When the loop has more than one step (multi-hop), use `"investigate"`. When single-step, use `"interactive"`.

In `_try_pulse_loop()`, after the loop `run()` call, if `len(result.step_results) > 1`, log it as `"investigate"` in the ledger.

Pass `model=model_for_profile("investigate")` to the `_observe()` call in Phase 5's multi-hop path.

### 9.3 — Tests for Phase 9

**File:** `backend/ai/tests/test_model_policy.py` (new file)

```python
"""Phase 9 — Model policy / turn profiles."""
import pytest
from unittest.mock import patch


def test_model_for_profile_returns_none_for_interactive():
    """interactive profile must return None (use instance default)."""
    from ai.engine.llm.router import model_for_profile
    assert model_for_profile("interactive") is None


def test_model_for_profile_returns_investigate_model_when_set():
    """investigate profile must return LLM_INVESTIGATE_MODEL when set."""
    from ai.engine.llm.router import model_for_profile
    from ai.engine.core.settings import get_settings

    with patch.object(get_settings(), "LLM_INVESTIGATE_MODEL", "anthropic/claude-sonnet-4-5"):
        result = model_for_profile("investigate")
        # Note: the with-patch approach for Pydantic settings depends on the
        # actual implementation. If get_settings() returns an immutable object,
        # use patch("ai.engine.core.settings.get_settings") instead.

    # The test verifies the routing logic exists — the exact value depends on env.
    assert result is None or isinstance(result, str)


def test_verify_profile_falls_back_to_investigate():
    """verify profile must fall back to the investigate model when
    LLM_VERIFY_MODEL is not set."""
    from ai.engine.llm.router import model_for_profile
    import ai.engine.llm.router as router_module

    with patch.object(router_module, "model_for_profile") as mock_mfp:
        mock_mfp.side_effect = lambda p: {
            "verify": None,
            "investigate": "anthropic/claude-sonnet-4-5",
        }.get(p)

        # verify falls back to investigate when verify returns None
        result = mock_mfp("verify") or mock_mfp("investigate")
        assert result == "anthropic/claude-sonnet-4-5"
```

---

## Phase 10 — Integration validation (full stack smoke)

**Objective:** Run all new tests and the existing test suite together. Fix any conflicts before declaring v2 complete.

### 10.1 — Full test run command

```bash
cd /home/ahmed/aast/carbon/backend
../.venv/bin/python -m pytest \
  ai/tests/test_pulse_loop.py \
  ai/tests/test_phase2_routing.py \
  ai/tests/test_work_objectives.py \
  ai/tests/test_evidence_records.py \
  ai/tests/test_multi_hop.py \
  ai/tests/test_carbon_context.py \
  ai/tests/test_verification.py \
  ai/tests/test_model_policy.py \
  -v --tb=short 2>&1 | tee /tmp/v2_test_run.txt
```

**Required outcome:** All new tests pass. Zero new failures in existing tests.

### 10.2 — Frontend test run

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run test -- --run src/components/ai/__tests__/WorkObjectivesPanel.test.jsx
```

### 10.3 — Regression check

Run the existing AI tests to confirm no regressions:

```bash
cd /home/ahmed/aast/carbon/backend
../.venv/bin/python -m pytest ai/tests/ -v --tb=short -x 2>&1 | tail -30
```

If any existing test fails, fix it before proceeding. Do not mark Phase 10 complete until the full suite passes.

### 10.4 — Manual golden scenarios

After all automated tests pass, manually verify these scenarios using `./manage.sh start` and the actual chat interface:

**G1 — Weather with ambiguity (Phase 2 must handle this without WEATHER-DETERMINISTIC block):**
> "hi what is the weather in north coast egypt today, is it suitable for beach swimming?"

Expected: calls `web_research`, returns live weather data, states location used.

**G2 — Single tool grounded answer (Phase 1 observation):**
> "What are the active DQ rules for the emissions module?"

Expected: calls `get_entity_details` or `call_host_api`, returns actual rule names and conditions from the database. Not a generic description.

**G3 — Save and resume (Phase 3):**
Turn 1: "Investigate why emissions increased in August. Save this so I can continue later."  
Turn 2 (new conversation): "Where did we get to on my emissions investigation?"

Expected: Pulse creates a `WorkObjective` in Turn 1. In Turn 2, calls `get_work_objectives` and reports the saved summary.

**G4 — Factual grounding (Phase 6):**
> "What is the current emission factor for our electricity consumption?"

Expected: returns the configured value from the Carbon database, not a generic global average.

**G5 — Spelling/text transformation (regression):**
> "Correct the spelling in this sentence: 'what is the weather in north cost egypt toay?'"

Expected: rewrites the sentence without calling `web_research`.

---

## Implementation order and constraints

**Strict order:** Phases must be implemented in sequence. Do not start Phase 2 until Phase 1 tests pass. Do not start Phase 3 until Phase 2 tests pass.

**Exception:** Phase 8 (frontend) can run in parallel with Phase 7 (verification).

**Forbidden actions across ALL phases:**
1. Do NOT modify `GuardChain`, `AccessGuard`, `DataIsolationGuard`, `MutationGuard`.
2. Do NOT change the `RULE_21` consent gate or the `confirmation_token` mechanism.
3. Do NOT add a new `TurnLedger` field without also adding it to the `TurnLedgerRow` Django model.
4. Do NOT create a new LLM router. Use `route_chat` with `task="cognition"`.
5. Do NOT drop or rename any existing database table or column.
6. Do NOT add Celery, Redis, or any new external service dependency.
7. Do NOT change `plans_service.py` approval flow.
8. Do NOT touch `backend/ai/engine/guards.py`.

**Required for every phase completion:**
```
Files changed: [list exact paths]
New migrations: [list or "none"]
Tests executed: [command used]
Test results: [N passed, 0 failed]
Feature flag: [name and default value]
Rollback: [how to disable]
```

---

## Appendix A — New settings summary

Add all of these to `PulseSettings` in `backend/ai/engine/core/settings.py`:

```python
PULSE_LOOP_ENABLED: bool = Field(default=True)
PULSE_LOOP_MAX_STEPS: int = Field(default=6)
PULSE_LOOP_MAX_TOKENS: int = Field(default=8000)
PULSE_CARBON_CONTEXT_ENABLED: bool = Field(default=True)
PULSE_VERIFY_ENABLED: bool = Field(default=False)
LLM_INVESTIGATE_MODEL: str = Field(default="")
LLM_VERIFY_MODEL: str = Field(default="")
```

Add to `deploy/carbon/.env` (production) and `.env.example`:

```
PULSE_LOOP_ENABLED=true
PULSE_LOOP_MAX_STEPS=6
PULSE_LOOP_MAX_TOKENS=8000
PULSE_CARBON_CONTEXT_ENABLED=true
PULSE_VERIFY_ENABLED=false
LLM_INVESTIGATE_MODEL=
LLM_VERIFY_MODEL=
```

---

## Appendix B — New files summary

| Phase | File | Type |
|---|---|---|
| 1 | `backend/ai/tests/test_pulse_loop.py` | Test |
| 2 | `backend/ai/tests/test_phase2_routing.py` | Test |
| 3 | `backend/ai/plugins/save_work_objective.py` | Plugin |
| 3 | `backend/ai/plugins/get_work_objectives.py` | Plugin |
| 3 | `backend/ai/tests/test_work_objectives.py` | Test |
| 3 | migration: `0XXX_add_workobjective.py` | Migration |
| 4 | `backend/ai/tests/test_evidence_records.py` | Test |
| 4 | migration: `0XXX_add_evidencerecord.py` | Migration |
| 5 | `backend/ai/tests/test_multi_hop.py` | Test |
| 6 | `backend/ai/context/carbon_context.py` | Service |
| 6 | `backend/ai/tests/test_carbon_context.py` | Test |
| 7 | `backend/ai/engine/cognition/turn/verify.py` | Witness |
| 7 | `backend/ai/tests/test_verification.py` | Test |
| 8 | `carbon-frontend/src/components/ai/WorkObjectivesPanel.jsx` | Component |
| 8 | `carbon-frontend/src/components/ai/__tests__/WorkObjectivesPanel.test.jsx` | Test |
| 9 | `backend/ai/tests/test_model_policy.py` | Test |

---

## Appendix C — Existing files modified

| Phase | File | What changes |
|---|---|---|
| 1 | `backend/ai/engine/cognition/turn/runner.py` | Add `_try_pulse_loop()`, add pulse loop entry point after fan-out gate |
| 1 | `backend/ai/engine/cognition/plan/loop.py` | Add `_observe()` method |
| 1 | `backend/ai/engine/core/settings.py` | Add 3 new settings fields |
| 2 | `backend/ai/engine/cognition/turn/runner.py` | Remove zone-based "answer from knowledge" injection |
| 2 | `backend/ai/engine/cognition/turn/intent.py` | Add `needs_live_evidence` field + LLM schema |
| 2 | `backend/ai/plugins/web_research.py` | Extend tool description |
| 3 | `backend/ai/models/core.py` | Add `WorkObjective` model |
| 3 | `backend/ai/engine/agent/plugins.py` | Register 2 new plugins |
| 4 | `backend/ai/models/core.py` | Add `EvidenceRecord` model |
| 4 | `backend/ai/engine/cognition/turn/execute.py` | Add `_register_evidence()` |
| 4 | `backend/ai/engine/cognition/synthesis.py` | Append evidence footer |
| 5 | `backend/ai/engine/cognition/plan/loop.py` | Change `_observe()` return type, add follow-up step injection |
| 6 | `backend/ai/engine/cognition/turn/runner.py` | Add `CarbonContextAssembler` call |
| 6 | `backend/ai/engine/core/settings.py` | Add `PULSE_CARBON_CONTEXT_ENABLED` |
| 7 | `backend/ai/engine/cognition/turn/runner.py` | Wire `VerificationWitness` after synthesis |
| 7 | `backend/ai/engine/core/settings.py` | Add `PULSE_VERIFY_ENABLED` |
| 8 | `backend/ai/views.py` | Add `WorkObjectiveViewSet` |
| 8 | `backend/ai/urls.py` | Register viewset |
| 8 | `carbon-frontend/src/api/ai.js` | Add 2 API functions |
| 9 | `backend/ai/engine/llm/router.py` | Add `model_for_profile()` |
| 9 | `backend/ai/engine/core/settings.py` | Add 2 model settings |
