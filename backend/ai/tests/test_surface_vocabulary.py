"""One vocabulary for where a turn runs (ADR-0014 · ADR-0046).

Regression bank for the "Open in Agent while the dial already reads Plan"
class of bug: three disagreeing representations of the mode, a bare ``"plan"``
that meant both a Chat dial and an Agent loop, and a ``surface`` argument that
silently defaulted to Chat before the dial could be consulted.
"""
from __future__ import annotations

import pytest

from ai.engine.agent.chat_surface import (
    assert_handoff_is_honest,
    build_chat_handoff_result,
    build_handoff_actions,
    cta_target_surface,
    handoff_problems,
    handoff_spec_for_api,
    is_chat_surface,
    is_host_mutation_tool,
)
from ai.engine.agent.guardrails import HookContext, chat_surface_hook
from ai.engine.agent.surface import HandoffLoopError, Surface


# ── the vocabulary itself ──────────────────────────────────────────────────


def test_chat_and_agent_plan_are_different_surfaces():
    """The collision that caused the bug: one word, two write permissions."""
    assert Surface.CHAT_PLAN.is_chat
    assert not Surface.CHAT_PLAN.may_host_mutate
    assert Surface.AGENT_PLAN.may_host_mutate
    assert Surface.CHAT_PLAN is not Surface.AGENT_PLAN


def test_dial_decides_when_the_engine_path_is_unspecified():
    assert Surface.resolve(None, process_mode="plan") is Surface.CHAT_PLAN
    assert Surface.resolve(None, process_mode="ask") is Surface.CHAT_ASK
    # Agent is representable now; it used to be flattened into "ask".
    assert Surface.resolve(None, process_mode="agent") is Surface.AGENT_RUN


def test_unset_surface_is_not_silently_chat_before_the_dial_is_read():
    """The original defect: ``surface or "chat"`` outranked process_mode."""
    assert Surface.resolve(surface=None, process_mode="plan") is Surface.CHAT_PLAN
    assert Surface.resolve(surface="", process_mode="plan") is Surface.CHAT_PLAN


def test_unknown_surface_fails_closed_to_the_most_restrictive():
    for value in (None, "", "   ", "nonsense", "plan_mode_v3"):
        assert Surface.resolve(value) is Surface.CHAT_ASK
        assert is_chat_surface(value) is True


def test_agent_path_outranks_the_chat_dial():
    """A brief typed on the Plan dial still runs the Agent loop as Agent."""
    resolved = Surface.resolve("agent_plan", process_mode="plan")
    assert resolved is Surface.AGENT_PLAN
    assert resolved.may_host_mutate


def test_legacy_surface_names_keep_their_write_permission():
    assert is_chat_surface("chat") is True
    assert is_chat_surface(None) is True
    assert is_chat_surface("agent") is False
    assert is_chat_surface("plan") is False  # legacy = Agent plan loop
    assert is_chat_surface("agent_discovery") is False


def test_surface_renders_as_its_value_in_logs_and_fstrings():
    assert str(Surface.CHAT_PLAN) == "chat.plan"
    assert f"{Surface.AGENT_RUN}" == "agent.run"


# ── the invariant: never advise the surface you are already on ─────────────


def test_cta_targets_are_known():
    assert cta_target_surface({"type": "open_panel", "panel": "tasks"}) is Surface.AGENT_RUN
    assert cta_target_surface({"type": "open_panel", "panel": "plan"}) is Surface.CHAT_PLAN
    # My / Team are host apps, not Pulse surfaces — they can never loop.
    assert cta_target_surface({"type": "navigate", "route": "/my/leave"}) is None


def test_open_in_agent_is_dropped_when_already_in_agent():
    spec = handoff_spec_for_api("submit_my_leave")
    actions = build_handoff_actions(spec, surface=Surface.AGENT_RUN)
    assert all(cta_target_surface(a) is not Surface.AGENT_RUN for a in actions)
    assert [a["route"] for a in actions] == ["/my/leave"]


def test_switch_to_plan_is_dropped_when_already_on_the_plan_dial():
    result = build_chat_handoff_result(
        "plan_task", {"brief": "x"}, surface=Surface.CHAT_PLAN,
    )
    panels = {a.get("panel") for a in result["actions"]}
    assert "plan" not in panels
    assert panels == {"tasks"}
    assert "Agent" in (result["envelope"]["headline"] or "")


def test_handoff_that_advises_its_own_surface_is_a_hard_error():
    looping = [{
        "type": "open_panel",
        "panel": "tasks",
        "label": "Open in Agent",
    }]
    assert handoff_problems(Surface.CHAT_ASK, looping) == []
    with pytest.raises(HandoffLoopError):
        assert_handoff_is_honest(Surface.AGENT_RUN, looping)


def test_a_write_handoff_on_an_agent_surface_is_itself_the_bug():
    """Agent can stage the write, so refusing it is a plumbing regression."""
    problems = handoff_problems(Surface.AGENT_PLAN, [])
    assert problems and "may stage the write itself" in problems[0]


def test_every_surface_can_build_a_handoff_without_advising_itself():
    spec = handoff_spec_for_api("submit_my_leave")
    for surface in Surface:
        actions = build_handoff_actions(spec, surface=surface)
        for action in actions:
            assert cta_target_surface(action) is not surface


# ── honest copy: name the dial the user can actually see ──────────────────


def test_plan_dial_copy_does_not_claim_the_user_is_in_chat():
    """The screenshot bug: 'cannot be submitted from Chat' on the Plan dial."""
    result = build_chat_handoff_result(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
        user_message="submit the leave",
        surface=Surface.CHAT_PLAN,
    )
    headline = result["envelope"]["headline"]
    assert "from Plan" in headline
    assert "Chat" not in headline
    assert "Plan only drafts" in result["message"]
    assert result["surface"] == "chat.plan"


def test_ask_dial_copy_still_names_chat():
    result = build_chat_handoff_result(
        "call_host_api",
        {"api_name": "submit_my_leave", "body": {"days": 1}},
        surface=Surface.CHAT_ASK,
    )
    assert "from Chat" in result["envelope"]["headline"]
    assert "Chat does not submit" in result["message"]


def test_handoff_copy_never_leaks_engine_jargon_on_any_surface():
    """RULE_23 holds for the new per-surface copy too."""
    for surface in (Surface.CHAT_ASK, Surface.CHAT_PLAN):
        result = build_chat_handoff_result(
            "call_host_api",
            {"api_name": "submit_my_loan", "body": {"principal": 500}},
            surface=surface,
        )
        blob = str(result["message"]) + str(result["envelope"])
        for jargon in ("ADR", "G2", "surface", "host mutation", "chat.plan"):
            assert jargon not in blob
        assert result["envelope"]["caveats"] == []


# ── the guardrail, with no per-tool special case ──────────────────────────


def test_plan_task_is_a_draft_on_the_plan_dial_and_a_write_on_ask():
    """Replaces the hand-carved ``if tool == "plan_task"`` escape hatch."""
    assert is_host_mutation_tool("plan_task", {}, surface=Surface.CHAT_PLAN) is False
    assert is_host_mutation_tool("plan_task", {}, surface=Surface.CHAT_ASK) is True
    # Committing a plan is Agent's job on every Chat surface.
    assert is_host_mutation_tool("approve_plan", {}, surface=Surface.CHAT_PLAN) is True


@pytest.mark.asyncio
async def test_structured_dial_alone_unblocks_plan_task_without_the_prose_prefix():
    """No ``[Pulse mode: …]`` in the message — process_mode is enough."""
    ctx = HookContext(
        tool_name="plan_task",
        tool_args={"brief": "loan 500 for 12 months"},
        instance_id="nibras",
        user_message="draft that for me",
        process_mode="plan",
    )
    assert (await chat_surface_hook(ctx)).action == "pass"


@pytest.mark.asyncio
async def test_plan_dial_still_cannot_submit_a_host_record():
    ctx = HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_loan", "body": {"principal": 500}},
        instance_id="nibras",
        user_message="submit it",
        process_mode="plan",
    )
    result = await chat_surface_hook(ctx)
    assert result.action == "cancel"
    assert "chat_no_host_mutation" in (result.flags or [])
    # The refusal names Plan, not Chat.
    assert "Plan" in (result.reason or "")
    assert "Chat" not in (result.reason or "")


@pytest.mark.asyncio
async def test_agent_dial_passes_the_write_through_to_consent():
    ctx = HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "submit_my_loan", "body": {"principal": 500}},
        instance_id="nibras",
        process_mode="agent",
    )
    assert (await chat_surface_hook(ctx)).action == "pass"
