"""v21 follow-up reads: fields a read returns, a continue that re-reads, labelled breakdowns."""
import asyncio

from ai.engine.cognition.state_store import ConversationState, update_state_from_turn
from ai.engine.cognition.turn.capability import CapabilitySurface
from ai.engine.cognition.turn.catalog_render import render_breakdown_bind
from ai.engine.cognition.turn.decision import Command, Decision, validate_decision
from ai.engine.cognition.turn.pipeline_v21 import act_on_decision

_PROFILE = {
    "name": "read_me",
    "method": "GET",
    "kind": "detail",
    "returns": ["full_name", "code_no"],
    "field_labels": {"code_no": {"en": "Code number", "ar": "الرقم"}},
}


def _validate(fields):
    caps = CapabilitySurface(entries=(_PROFILE,))
    return validate_decision(
        Decision(commands=[Command(op="call_tool", name="read_me", fields=fields)], language="en"),
        allowed_tools=caps.names,
        field_gaps=caps.field_gaps,
    )


def test_a_field_the_read_does_not_return_is_rejected_with_what_it_returns():
    decided = _validate(["project_code"])
    assert decided.commands == []
    [rejection] = decided.rejections
    assert rejection.code == "unknown_field"
    assert "project_code" in rejection.detail and "full_name, code_no" in rejection.detail


def test_fields_named_by_key_or_label_stand():
    decided = _validate(["full_name", "Code number"])
    assert [c.op for c in decided.commands] == ["call_tool"]
    assert not decided.rejections


def test_a_continue_re_runs_the_last_read_with_its_args():
    state = ConversationState()
    update_state_from_turn(
        state,
        decision="answer",
        completed_tools=[{
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "count_things", "query_params": {"dimension": "status"}},
            "result": {"total": 7, "dimension": "status", "breakdown": [{"label": "on", "count": 7}]},
        }],
    )
    assert state.last_results[-1]["args"] == {"dimension": "status"}
    calls: list[tuple[str, dict]] = []

    async def execute_tool(api, args):
        calls.append((api, args))
        return {"total": 8, "dimension": "status", "breakdown": [{"label": "on", "count": 8}]}

    text = asyncio.run(act_on_decision(
        Decision(commands=[Command(op="continue")], language="en"),
        execute_tool=execute_tool,
        user_message="Same again.",
        state=state,
    ))
    assert calls == [("count_things", {"dimension": "status"})]
    assert "8" in (text or "")


def test_arabic_breakdown_uses_the_catalog_label_and_says_yes_no():
    text = render_breakdown_bind(
        {"total": 5, "dimension": "is_on", "breakdown": [{"label": "True", "count": 5}]},
        "ar",
        {"is_on": {"en": "On", "ar": "مفعّل"}},
    )
    assert text == "الإجمالي: 5\nحسب: مفعّل\nنعم: 5"
