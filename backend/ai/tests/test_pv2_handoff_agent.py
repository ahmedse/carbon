"""PV2-3B — Chat ``handoff_agent`` (ADR-0046 · F-LIVE-2 / F-LIVE-4).

Chat must never execute a mutating ``call_host_api`` plan (no ReAct consent
pause, no Run/RunStep staging). Enough bound slots → ``handoff_agent`` with
slots persisted on ConversationState. The Chat prompt never says
``CALL THE TOOL`` for a host write.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.state_store import ConversationState
from ai.engine.cognition.turn.handoff_agent import (
    ChatHandoffOutcome,
    build_chat_write_handoff,
    chat_grounding_rules_block,
    combine_user_brief,
    enough_slots_for_chat_handoff,
    extract_plan_write,
    is_ess_write_utterance,
    merge_slots,
    plan_has_mutating_host_api,
    seed_slots_into_state,
)
from ai.engine.cognition.turn.witnesses import TurnLedger
from ai.engine_runtime import _should_force_action

_LOAN_CATALOG = [
    {
        "name": "submit_my_loan",
        "method": "POST",
        "requires_confirmation": True,
    },
    {
        "name": "list_my_payslips",
        "method": "GET",
    },
]


def _loan_step(**body) -> PlanStep:
    payload = {
        "loan_type": "emergency",
        "principal": 3000,
        "term_months": 12,
        "start_date": "2026-09-23",
    }
    payload.update(body)
    return PlanStep(
        step_id=1,
        intent="Submit emergency loan",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_loan", "body": payload},
        is_mutation=True,
    )


def _read_step() -> PlanStep:
    return PlanStep(
        step_id=1,
        intent="List payslips",
        tool_name="call_host_api",
        tool_args={"api_name": "list_my_payslips"},
        is_mutation=False,
    )


def _mutating_plan(*steps: PlanStep, source: str = "skill") -> Plan:
    return Plan(
        pattern="custom",
        steps=list(steps),
        synthesis_instruction="",
        source=source,
    )


# ── Pure helpers ───────────────────────────────────────────────────────────


def test_plan_has_mutating_host_api():
    assert plan_has_mutating_host_api(
        _mutating_plan(_loan_step()), api_catalog=_LOAN_CATALOG,
    )
    assert not plan_has_mutating_host_api(
        _mutating_plan(_read_step()), api_catalog=_LOAN_CATALOG,
    )
    orphan = PlanStep(
        step_id=1,
        intent="create",
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_leave", "body": {"days": 1}},
    )
    assert plan_has_mutating_host_api(_mutating_plan(orphan), api_catalog=[])
    dq = PlanStep(step_id=1, intent="dq", tool_name="create_dq_rule")
    assert plan_has_mutating_host_api(_mutating_plan(dq), api_catalog=[])


def test_extract_and_enough_slots():
    plan = _mutating_plan(_loan_step())
    api, body = extract_plan_write(plan)
    assert api == "submit_my_loan"
    assert body["loan_type"] == "emergency"
    assert body["principal"] == 3000
    assert enough_slots_for_chat_handoff(api, body) is True
    assert enough_slots_for_chat_handoff("submit_my_loan", {"loan_type": "emergency"}) is False
    assert enough_slots_for_chat_handoff("submit_my_leave", {"leave_type": "annual"}) is False
    assert enough_slots_for_chat_handoff(
        "submit_my_leave",
        {"leave_type": "annual", "start_date": "2026-10-01"},
    ) is True
    assert enough_slots_for_chat_handoff("submit_my_other", {"x": 1}) is True
    assert enough_slots_for_chat_handoff("submit_my_other", {}) is False


def test_merge_slots_and_brief():
    merged = merge_slots(
        {"loan_type": "emergency"},
        {"principal": 3000, "loan_type": ""},
        {"principal": 5000},
    )
    assert merged == {"loan_type": "emergency", "principal": 5000}
    brief = combine_user_brief(
        "I need 3000 SAR",
        [
            {"role": "user", "content": "I want to apply for a loan"},
            {"role": "assistant", "content": "What type?"},
            {"role": "user", "content": "An emergency loan"},
        ],
        {"loan_type": "emergency"},
    )
    assert "I want to apply for a loan" in brief
    assert "An emergency loan" in brief
    assert "I need 3000 SAR" in brief
    assert "loan_type=emergency" in brief


def test_seed_slots_into_state_and_api_switch():
    state = ConversationState()
    ctx = SimpleNamespace(state=state)
    seed_slots_into_state(ctx, "submit_my_loan", {"loan_type": "emergency", "principal": 3000})
    assert state.intent.get("api") == "submit_my_loan"
    assert state.slots["loan_type"] == "emergency"
    assert state.slots["principal"] == 3000
    seed_slots_into_state(ctx, "submit_my_leave", {"leave_type": "annual"})
    assert state.intent.get("api") == "submit_my_leave"
    assert "principal" not in state.slots
    assert state.slots["leave_type"] == "annual"


def test_handoff_copy_en_and_ar_lists_slots():
    en = build_chat_write_handoff(
        api_name="submit_my_loan",
        slots={"loan_type": "emergency", "principal": 3000, "term_months": 12},
        user_message="I need 3000 SAR for an emergency loan",
    )
    assert isinstance(en, ChatHandoffOutcome)
    assert "emergency" in en.text.lower()
    assert "3000" in en.text
    assert "switch to Agent" in en.text
    assert "Chat does not submit" in en.text
    assert "approval" not in en.text.lower()
    assert en.tool_result.get("action") == "chat_handoff"
    assert en.tool_result.get("requires_confirmation") is False

    ar = build_chat_write_handoff(
        api_name="submit_my_loan",
        slots={"loan_type": "emergency", "principal": 5000},
        user_message="أريد قرض طارئ ٥٠٠٠",
    )
    assert "الوكيل" in ar.text or "Agent" in ar.text
    assert "قرض" in ar.text or "emergency" in ar.text.lower() or "5000" in ar.text
    assert "approval" not in ar.text.lower()
    assert "أتابع تقديم" not in ar.text


def test_chat_grounding_never_says_call_the_tool_for_writes():
    block = chat_grounding_rules_block()
    assert "CALL THE TOOL" not in block
    assert "call the tool" not in block.lower()
    assert "HOST WRITES" in block
    assert "switch to Agent" in block
    assert "learn_fact" in block


def test_is_ess_write_utterance():
    assert is_ess_write_utterance("I want to apply for an emergency loan of 3000 SAR")
    assert is_ess_write_utterance("أريد إجازة سنوية غدا")
    assert not is_ess_write_utterance("what is my net pay")


# ── force_action is a logged fallback ──────────────────────────────────────


def test_should_force_action_skips_when_chat_handoff_already_fired():
    ledger = SimpleNamespace(
        execution=SimpleNamespace(
            completed_tools=[
                {
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "submit_my_loan"},
                    "result": {"action": "chat_handoff"},
                }
            ]
        )
    )
    response = SimpleNamespace(text="I have: emergency; 3000. Switch to Agent.")
    assert _should_force_action("I want an emergency loan of 3000", response, ledger) is False


def test_should_force_action_fires_on_approval_bait():
    ledger = SimpleNamespace(execution=SimpleNamespace(completed_tools=[]))
    response = SimpleNamespace(
        text="I need your approval before I can proceed. Shall I submit?"
    )
    assert _should_force_action(
        "I want to apply for an emergency loan of 3000 SAR",
        response,
        ledger,
    ) is True


# ── Runner seams ───────────────────────────────────────────────────────────


class _StateCtx:
    def __init__(self):
        self.state = ConversationState()
        self.owner_user_id = "u1"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_try_chat_write_handoff_complete_loan():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    ctx = _StateCtx()
    outcome = await runner._try_chat_write_handoff(  # noqa: SLF001
        user_message="I need 3000 SAR for an emergency loan",
        conversation_history=[
            {"role": "user", "content": "I want to apply for a loan"},
            {"role": "user", "content": "An emergency loan"},
        ],
        state_ctx=ctx,
        instance_config={"api_catalog": _LOAN_CATALOG},
    )
    assert isinstance(outcome, ChatHandoffOutcome)
    assert outcome.api_name == "submit_my_loan"
    assert ctx.state.slots.get("loan_type")
    assert ctx.state.slots.get("principal") in (3000, "3000", 3000.0)
    assert "3000" in outcome.text or "3,000" in outcome.text or "emergency" in outcome.text.lower()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_try_chat_write_handoff_incomplete_seeds_state():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    ctx = _StateCtx()
    outcome = await runner._try_chat_write_handoff(  # noqa: SLF001
        user_message="I want to apply for a loan",
        conversation_history=[],
        state_ctx=ctx,
        instance_config={"api_catalog": _LOAN_CATALOG},
    )
    assert outcome is None


@pytest.mark.asyncio
async def test_return_chat_handoff_does_not_stage_host_runs():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    runner.db = None
    ledger = TurnLedger()
    outcome = build_chat_write_handoff(
        api_name="submit_my_loan",
        slots={"loan_type": "emergency", "principal": 3000},
        user_message="I need 3000 SAR for an emergency loan",
    )
    with (
        patch(
            "ai.engine.cognition.notifier.broadcast_run_event",
            new_callable=AsyncMock,
        ),
        patch("ai.models.core.Run.objects") as run_objects,
        patch("ai.models.core.RunStep.objects") as step_objects,
    ):
        response, out_ledger = await runner._return_chat_handoff(  # noqa: SLF001
            outcome=outcome,
            ledger=ledger,
            meter=SimpleNamespace(by_stage=lambda: {}, total=0),
            turn_id="t1",
            instance_id="nibras",
            conversation_id="c1",
            host_user_id="u1",
            t0=0.0,
        )
    assert out_ledger.force_action_fired is False
    assert out_ledger.turn_decision == "handoff_agent"
    tools = out_ledger.execution.completed_tools or []
    assert tools
    assert "chat_no_host_mutation" in (tools[0].get("guardrail_flags") or [])
    assert tools[0]["result"].get("action") == "chat_handoff"
    assert tools[0]["result"].get("requires_confirmation") is False
    assert "switch to Agent" in (response.text or "")
    assert "approval" not in (response.text or "").lower()
    run_objects.create.assert_not_called()
    step_objects.create.assert_not_called()
    run_objects.filter.assert_not_called()


@pytest.mark.asyncio
async def test_try_multi_step_plan_skips_react_for_mutation():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    runner.llm_client = MagicMock()
    runner.db = MagicMock()
    ctx = _StateCtx()
    plan = _mutating_plan(_loan_step(), source="skill")

    class _FakePlanner:
        def __init__(self, **_kw):
            pass

        async def decompose(self, **_kw):
            return plan

    with (
        patch("ai.engine.cognition.plan.planner.SkillAwarePlanner", _FakePlanner),
        patch("ai.engine.cognition.plan.loop.ReActLoop") as react_cls,
        patch("ai.engine.skills.registry.SkillRegistry"),
        patch(
            "ai.engine.cognition.plan.planner._is_agent_discuss_context",
            return_value=False,
        ),
        patch(
            "ai.engine.cognition.plan.planner._wants_explicit_task_creation",
            return_value=False,
        ),
    ):
        result = await runner._try_multi_step_plan(  # noqa: SLF001
            instance_id="nibras",
            conversation_id="c1",
            user_message="I need 3000 SAR for an emergency loan",
            host_user_id="u1",
            page_context="",
            conversation_history=[],
            instance_config={"api_catalog": _LOAN_CATALOG},
            user_info={"language": "en"},
            retrieval=SimpleNamespace(knowledge_chunks=[], memory_chunks=[]),
            state_ctx=ctx,
        )
    assert isinstance(result, ChatHandoffOutcome)
    react_cls.assert_not_called()
    assert ctx.state.slots.get("loan_type") == "emergency"
    assert ctx.state.intent.get("api") == "submit_my_loan"


@pytest.mark.asyncio
async def test_try_multi_step_plan_runs_readonly():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    runner.llm_client = MagicMock()
    runner.db = MagicMock()
    runner.knowledge_store = MagicMock()
    runner.memory_manager = MagicMock()
    runner.executor = MagicMock()
    plan = _mutating_plan(_read_step(), source="skill")
    loop_instance = MagicMock()
    loop_instance.run = AsyncMock(return_value=SimpleNamespace(final_response="ok"))

    class _FakePlanner:
        def __init__(self, **_kw):
            pass

        async def decompose(self, **_kw):
            return plan

    retrieval = SimpleNamespace(knowledge_chunks=[], memory_chunks=[])
    with (
        patch("ai.engine.cognition.plan.planner.SkillAwarePlanner", _FakePlanner),
        patch(
            "ai.engine.cognition.plan.loop.ReActLoop",
            return_value=loop_instance,
        ) as react_cls,
        patch("ai.engine.skills.registry.SkillRegistry"),
        patch(
            "ai.engine.llm.prompts.build_chat_prompt",
            new_callable=AsyncMock,
            return_value="sp",
        ),
        patch("ai.engine.cognition.turn.draft.DraftWitness"),
        patch("ai.engine.cognition.turn.critic.CriticWitness"),
        patch(
            "ai.engine.cognition.plan.planner._is_agent_discuss_context",
            return_value=False,
        ),
        patch(
            "ai.engine.cognition.plan.planner._wants_explicit_task_creation",
            return_value=False,
        ),
    ):
        result = await runner._try_multi_step_plan(  # noqa: SLF001
            instance_id="nibras",
            conversation_id="c1",
            user_message="show my payslips",
            host_user_id="u1",
            page_context="",
            conversation_history=[],
            instance_config={"api_catalog": _LOAN_CATALOG},
            user_info={"language": "en"},
            retrieval=retrieval,
        )
    react_cls.assert_called()
    assert getattr(result, "final_response", None) == "ok"


def test_assembled_prompt_never_says_call_the_tool_for_ess_write():
    """Assembled Chat Identity + grounding must not coax CALL THE TOOL for writes."""
    from ai.engine.cognition.context_pack import CHAT_AUTONOMY, IdentityBlock

    identity = IdentityBlock(
        surface="chat",
        language="en",
        audience={"ess"},
        autonomy=CHAT_AUTONOMY,
        date_line="Today's date: 2026-09-23 (Africa/Cairo).",
    )
    assembled = f"{identity.render()}\n\n{chat_grounding_rules_block()}"
    assert "CALL THE TOOL" not in assembled
    assert "call the tool" not in assembled.lower()
    assert "submit_my_" in assembled or "HOST WRITES" in assembled
    assert "switch to Agent" in assembled or "hand off" in assembled.lower()
