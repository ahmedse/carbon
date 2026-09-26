"""A plan step that collects an answer pauses the run. Later steps wait."""

from ai.engine.cognition.plan.loop import pause_for_user_answer, resume_answered_clarification
from ai.engine.cognition.plan.planner import PlanStep


def test_ask_clarification_pauses_before_later_steps():
    step = PlanStep(step_id=0, intent="Own slips or the org?", tool_name="ask_clarification")
    result = pause_for_user_answer(step)
    assert result is not None
    assert result.paused is True
    assert result.executed is False
    assert result.draft_text == "Own slips or the org?"
    assert result.tool_output["type"] == "clarification"


def test_clarification_payload_pauses_even_when_the_tool_name_was_lost():
    step = PlanStep(step_id=1, intent="scope")
    result = pause_for_user_answer(
        step,
        {"type": "clarification", "question": "Own or org?", "choices": ["own", "org"]},
    )
    assert result is not None
    assert result.paused is True
    assert result.draft_text == "Own or org?"
    assert result.tool_output["choices"] == ["own", "org"]


def test_an_answered_clarification_finishes_instead_of_asking_again():
    step = PlanStep(step_id=2, intent="Confirm the draft", tool_name="ask_clarification")
    result = resume_answered_clarification(step, "token-1")
    assert result is not None
    assert result.paused is False
    assert result.executed is True
    assert result.tool_output["answered"] is True
    assert resume_answered_clarification(step, None) is None
    assert resume_answered_clarification(
        PlanStep(step_id=3, intent="submit", tool_name="call_host_api"),
        "token-1",
    ) is None


def test_a_plain_read_does_not_pause():
    step = PlanStep(step_id=2, intent="list slips", tool_name="call_host_api")
    assert pause_for_user_answer(step, {"ok": True}) is None
