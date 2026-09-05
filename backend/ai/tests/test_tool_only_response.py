"""Phase A — Tool-only response injection (GAP-W8 regression).

When the LLM drafts a turn that ONLY calls tools (no prose text — a common
pattern for "show me the emission factors"), the turn must NOT be saved with
empty content (which rendered as blank/"removed" bubbles in the UI).

``_build_tool_result_summary`` converts executed tool results into deterministic
prose so the turn always has content.
"""
import pytest

from ai.engine.cognition.turn.execute import _build_tool_result_summary


class TestToolResultSummary:
    def test_empty_tools_returns_empty(self):
        assert _build_tool_result_summary([]) == ""

    def test_single_tool_with_data_list_counts_rows(self):
        summary = _build_tool_result_summary([
            {"tool_name": "list_emission_factors",
             "result": {"results": [{"code": "A"}, {"code": "B"}]}},
        ])
        assert "list_emission_factors" in summary
        assert "Retrieved 2 row(s)" in summary
        assert "Here's what I found" in summary

    def test_tool_with_error_is_reported(self):
        summary = _build_tool_result_summary([
            {"tool_name": "get_chairman_overview", "result": {},
             "error": "Calculation summary failed"},
        ])
        assert "get_chairman_overview" in summary
        assert "Error" in summary
        assert "Calculation summary failed" in summary

    def test_tool_with_dict_items_brief_summary(self):
        summary = _build_tool_result_summary([
            {"tool_name": "get_calculation_summary",
             "result": {"total_calculations": 42, "stale_count": 3}},
        ])
        assert "get_calculation_summary" in summary
        assert "total_calculations=42" in summary
        assert "stale_count=3" in summary

    def test_tool_with_empty_dict_flagged(self):
        summary = _build_tool_result_summary([
            {"tool_name": "list_reporting_periods", "result": {}},
        ])
        assert "(empty result)" in summary

    def test_multiple_tools_all_summarized(self):
        summary = _build_tool_result_summary([
            {"tool_name": "list_emission_factors",
             "result": {"results": [{"code": "A"}]}},
            {"tool_name": "list_gwp_gases",
             "result": {"results": [{"gas": "CO2"}, {"gas": "CH4"}]}},
        ])
        assert "list_emission_factors" in summary
        assert "list_gwp_gases" in summary
        assert "Retrieved 1 row(s)" in summary
        assert "Retrieved 2 row(s)" in summary

    def test_non_dict_result_truncated(self):
        long = "x" * 500
        summary = _build_tool_result_summary([
            {"tool_name": "export_document", "result": long},
        ])
        assert "export_document" in summary
        assert len(summary) < 400  # str is capped at 200 chars

    def test_json_string_result_real_pipeline_shape(self):
        """_execute_single_tool stores result as a JSON string — the summary
        must parse it and count rows, not dump raw JSON into the bubble."""
        result_str = '{"status_code": 200, "data": {"results": [{"code": "EG_GRID_2024"}, {"code": "DIESEL_2024"}]}}'
        summary = _build_tool_result_summary([
            {"tool_name": "list_emission_factors", "result": result_str},
        ])
        assert "Retrieved 2 row(s)" in summary
        assert '{"' not in summary

    def test_json_string_result_with_results_key(self):
        result_str = '{"results": [{"code": "A"}, {"code": "B"}, {"code": "C"}]}'
        summary = _build_tool_result_summary([
            {"tool_name": "list_gwp_gases", "result": result_str},
        ])
        assert "Retrieved 3 row(s)" in summary

    def test_deterministic_output(self):
        tools = [
            {"tool_name": "list_emission_factors", "result": {"results": [{"a": 1}]}},
        ]
        first = _build_tool_result_summary(tools)
        second = _build_tool_result_summary(tools)
        assert first == second

    def test_no_match_result_renders_clarification(self):
        summary = _build_tool_result_summary([
            {"tool_name": "get_weather",
             "result": {"status": "no_match", "reason": "unresolved_location",
                        "hint": "north coast egypt", "candidates": []}},
        ])
        assert "I couldn't resolve" in summary
        assert "north coast egypt" in summary
        # The tri-state dict must never be dumped as key=value prose.
        assert "status" not in summary
        assert "no_match" not in summary

    def test_no_match_json_envelope_renders_clarification(self):
        result_str = ('{"status_code": 200, "data": {"status": "no_match", '
                      '"reason": "unresolved_location", "hint": "north coast"}}')
        summary = _build_tool_result_summary([
            {"tool_name": "get_weather", "result": result_str},
        ])
        assert "I couldn't resolve" in summary
        assert "north coast" in summary
        assert "no_match" not in summary
