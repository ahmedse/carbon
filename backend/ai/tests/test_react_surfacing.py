from types import SimpleNamespace
from unittest.mock import MagicMock

from ai.engine.cognition.state_store import ConversationState, update_state_from_turn
from ai.engine.cognition.turn.runner import _completed_tools_from_react


def make_step(tool_name, tool_result=None, error=None, latency_ms=50.0, executed=True, tool_args=None):
    sr = MagicMock()
    sr.tool_name = None
    sr.tool_result = None
    sr.tool_output = {
        "tool_name": tool_name,
        "tool_args": tool_args or {},
        "result": tool_result or {"status": "ok"},
    }
    sr.error = error
    sr.latency_ms = latency_ms
    sr.executed = executed
    sr.critic_flags = []
    sr.critic_verdict = "pass"
    sr.step_id = "s1"
    sr.intent = "test"
    return sr


def test_react_path_populates_completed_tools():
    """completed_tools must be set on ledger.execution after ReAct path."""
    execution = SimpleNamespace(completed_tools=[])
    ledger = SimpleNamespace(execution=execution)
    react_result = MagicMock()
    react_result.step_results = [
        make_step("search_knowledge"),
        make_step("get_entity_details"),
    ]

    ledger.execution.completed_tools = _completed_tools_from_react(
        react_result.step_results,
    )

    assert len(ledger.execution.completed_tools) == 2
    assert ledger.execution.completed_tools[0]["tool_name"] == "search_knowledge"
    assert "latency_ms" in ledger.execution.completed_tools[0]


def test_react_path_skips_unexecuted_steps():
    execution = SimpleNamespace(completed_tools=[])
    ledger = SimpleNamespace(execution=execution)
    react_result = MagicMock()
    react_result.step_results = [
        make_step("search_knowledge"),
        make_step("get_entity_details", executed=False),
    ]
    ledger.execution.completed_tools = _completed_tools_from_react(
        react_result.step_results,
    )
    assert len(ledger.execution.completed_tools) == 1
    assert ledger.execution.completed_tools[0]["tool_name"] == "search_knowledge"


def test_react_payslip_tools_stamp_identity_digest():
    """ReAct tool_output must flatten so last_results can recall net/gosi/loan."""
    sr = make_step(
        "call_host_api",
        tool_args={"api_name": "list_my_payslips"},
        tool_result={
            "status_code": 200,
            "data": {
                "count": 4,
                "results": [
                    {"line_type": {"code": "gross"}, "amount": "6500.000"},
                    {"line_type": {"code": "gosi"}, "amount": "1200.000"},
                    {"line_type": {"code": "loan_installment"}, "amount": "800.000"},
                    {"line_type": {"code": "net"}, "amount": "4500.000"},
                ],
            },
        },
    )
    tools = _completed_tools_from_react([sr])
    assert tools[0]["tool_args"]["api_name"] == "list_my_payslips"
    assert tools[0]["result"]["status_code"] == 200
    state = update_state_from_turn(
        ConversationState(),
        decision="answer",
        completed_tools=tools,
        response_text="Last month's committed net pay is 4500.",
    )
    blob = " ".join(str(row.get("digest") or "") for row in state.last_results)
    assert "list_my_payslips" in blob
    assert "net=4500" in blob
    assert "gosi=1200" in blob
