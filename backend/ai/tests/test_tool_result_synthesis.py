"""Phase A — Tool-result synthesis (GAP-W9 regression, ADR-0021).

When the S3 planner drafts a turn that only calls tools (no prose, or a short
"promise to fetch"), the pipeline must re-synthesize the final answer from the
ACTUAL tool results — not discard them. These tests cover the pure renderer
(``_render_tool_results_for_synthesis``) and the short-circuit branches of
``_synthesize_tool_results`` that return before any LLM call.
"""
import pytest
from unittest.mock import AsyncMock, patch

from ai.engine.cognition.turn.runner import (
    _render_tool_results_for_synthesis,
    _synthesize_tool_results,
)


class TestRenderToolResultsForSynthesis:
    def test_empty_returns_empty(self):
        assert _render_tool_results_for_synthesis([]).strip() == ""

    def test_unwraps_host_envelope(self):
        out = _render_tool_results_for_synthesis([
            {"tool_name": "list_emission_factors",
             "result": '{"status_code": 200, "data": {"results": [{"code": "A"}]}}'},
        ])
        assert "list_emission_factors" in out
        assert "total rows: 1" in out
        # The envelope keys must NOT leak into the render.
        assert "status_code" not in out

    def test_list_payload_counts_rows(self):
        out = _render_tool_results_for_synthesis([
            {"tool_name": "list_gwp_gases",
             "result": {"results": [{"gas": "CO2"}, {"gas": "CH4"}, {"gas": "N2O"}]}},
        ])
        assert "total rows: 3" in out

    def test_json_string_result_parsed(self):
        out = _render_tool_results_for_synthesis([
            {"tool_name": "get_calculation_summary",
             "result": '{"total_calculations": 115, "stale_count": 0}'},
        ])
        assert "115" in out  # JSON string parsed, not dumped raw

    def test_truncates_to_max_chars(self):
        big = {"results": [{"x": "y" * 1000} for _ in range(100)]}
        out = _render_tool_results_for_synthesis(
            [{"tool_name": "huge", "result": big}],
            max_chars=500,
        )
        assert len(out) <= 500 + 20  # header + truncated marker slack


class TestSynthesizeToolResultsShortCircuits:
    @pytest.mark.asyncio
    async def test_no_usable_tools_with_error_runs_recovery(self):
        # Errored tools → ADR-0021 failure recovery (deterministic fallback
        # when the recovery LLM is unavailable / mocked off).
        with patch(
            "ai.engine.llm.router.route_chat",
            AsyncMock(side_effect=RuntimeError("no llm")),
        ):
            result = await _synthesize_tool_results(
                instance_id="i", conversation_id="c", user_message="hi",
                completed_tools=[
                    {"tool_name": "create_dq_rule", "result": {},
                     "requires_confirmation": True},
                    {
                        "tool_name": "call_host_api:submit_my_leave",
                        "tool_args": {"api_name": "submit_my_leave", "method": "POST"},
                        "result": {
                            "status_code": 400,
                            "data": {
                                "detail": "Those dates overlap an existing emergency leave.",
                                "error_kind": "overlap",
                                "hints": {"suggestion": "Pick another day that is free."},
                            },
                        },
                        "error": "Those dates overlap an existing emergency leave.",
                    },
                ],
                draft_text="",
            )
        assert result is not None
        assert result.get("is_recovery") is True
        assert "overlap" in result["text"].lower() or "Pick another day" in result["text"]
        assert "invented" not in result["text"].lower()

    @pytest.mark.asyncio
    async def test_confirm_only_tools_returns_none(self):
        # Staging-only turn (no executed failure) → no recovery, no synthesis.
        result = await _synthesize_tool_results(
            instance_id="i", conversation_id="c", user_message="hi",
            completed_tools=[
                {"tool_name": "create_dq_rule", "result": {},
                 "requires_confirmation": True},
            ],
            draft_text="",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_completed_tools_returns_none(self):
        result = await _synthesize_tool_results(
            instance_id="i", conversation_id="c", user_message="hi",
            completed_tools=[],
            draft_text="",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_long_draft_returns_none(self):
        # A substantial answer already exists — never re-synthesize.
        result = await _synthesize_tool_results(
            instance_id="i", conversation_id="c", user_message="hi",
            completed_tools=[
                {"tool_name": "list_emission_factors",
                 "result": {"results": [{"code": "A"}]}},
            ],
            draft_text="A " * 300,
        )
        assert result is None


class TestSynthesizeToolResultsNoDataNet:
    @pytest.mark.asyncio
    async def test_long_no_data_draft_over_real_data_resynthesizes(self):
        """A long draft that falsely claims 'no data' while the tool returned
        calculations must NOT be kept — force the markdown re-synthesis path."""
        summary = '{"status_code": 200, "data": {"total_calculations": 115}}'
        with patch(
            "ai.engine.llm.router.route_chat",
            AsyncMock(return_value={"content": "115 calculations found.", "model": "test"}),
        ) as mock_route:
            result = await _synthesize_tool_results(
                instance_id="i", conversation_id="c", user_message="emissions 2026",
                completed_tools=[
                    {"tool_name": "call_host_api", "result": summary},
                ],
                draft_text="No carbon emissions data is available for AASTMT in 2026. " * 20,
            )

        # The synthesis LLM was invoked (instead of returning None to keep the draft).
        mock_route.assert_awaited_once()
        assert result is not None
        assert result["text"].startswith("115 calculations found.")

    @pytest.mark.asyncio
    async def test_long_no_data_draft_over_empty_data_kept(self):
        """When the tool genuinely returned 0 calculations, a 'no data' draft is
        correct and must NOT trigger a wasteful re-synthesis."""
        summary = '{"status_code": 200, "data": {"total_calculations": 0, "by_scope": {}, "by_module": []}}'
        with patch("ai.engine.llm.router.route_chat") as mock_route:
            result = await _synthesize_tool_results(
                instance_id="i", conversation_id="c", user_message="emissions 2026",
                completed_tools=[
                    {"tool_name": "call_host_api", "result": summary},
                ],
                draft_text="No carbon emissions data is available for AASTMT in 2026. " * 20,
            )

        mock_route.assert_not_awaited()
        assert result is None
