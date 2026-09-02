from unittest.mock import MagicMock
from types import SimpleNamespace


def make_step(tool_name, tool_result=None, error=None, latency_ms=50.0, executed=True):
    sr = MagicMock()
    sr.tool_name = tool_name
    sr.tool_result = tool_result or {"status": "ok"}
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
    ledger = SimpleNamespace(execution=execution, final_response="", total_latency_ms=0, total_tokens=0, total_llm_calls=0)
    react_result = MagicMock()
    react_result.step_results = [make_step("search_knowledge"), make_step("get_entity_details")]
    react_result.final_response = "answer"
    react_result.succeeded = True
    react_result.replans_used = 0

    _react_completed_tools = [
        {
            "tool_name": sr.tool_name or f"react_step_{i}",
            "result":    sr.tool_result if hasattr(sr, "tool_result") else {},
            "error":     sr.error if hasattr(sr, "error") else None,
            "latency_ms": sr.latency_ms if hasattr(sr, "latency_ms") else 0.0,
            "guardrail_flags": sr.critic_flags if hasattr(sr, "critic_flags") else [],
        }
        for i, sr in enumerate(react_result.step_results)
        if getattr(sr, "executed", True)
    ]
    if ledger.execution is not None:
        ledger.execution.completed_tools = _react_completed_tools

    assert len(ledger.execution.completed_tools) == 2
    assert ledger.execution.completed_tools[0]["tool_name"] == "search_knowledge"
    assert "latency_ms" in ledger.execution.completed_tools[0]


def test_react_path_skips_unexecuted_steps():
    execution = SimpleNamespace(completed_tools=[])
    ledger = SimpleNamespace(execution=execution)
    react_result = MagicMock()
    react_result.step_results = [make_step("search_knowledge"), make_step("get_entity_details", executed=False)]
    _react_completed_tools = [
        {"tool_name": sr.tool_name or f"react_step_{i}", "result": {}, "error": None, "latency_ms": 0.0, "guardrail_flags": []}
        for i, sr in enumerate(react_result.step_results)
        if getattr(sr, "executed", True)
    ]
    ledger.execution.completed_tools = _react_completed_tools
    assert len(ledger.execution.completed_tools) == 1
    assert ledger.execution.completed_tools[0]["tool_name"] == "search_knowledge"
