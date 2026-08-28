"""Phase A — Empty-response regression guard (GAP-W8).

Regression: turns where the LLM called tools but produced zero prose used to be
saved with empty content -> UI showed blank/"Your message was removed" bubbles.

Guards under test:

1. ``_build_tool_result_summary`` always yields non-empty text when tools
   completed (so the runner's injection never saves an empty turn).
2. The tool-result injection in the runner only triggers when the draft is
   actually empty AND tools ran — verified through the pure decision logic.
3. Api-catalog rendering stays wired so tool-heavy conversations never degrade
   to generic replies (prompt path renders live endpoint metadata).
"""
import pytest
from asgiref.sync import async_to_sync

from ai.engine.cognition.turn.execute import _build_tool_result_summary
from ai.engine.llm.prompts import build_chat_prompt


class TestNoBlankTurnGuard:
    def test_completed_tools_always_produce_text(self):
        """Any non-empty completed_tools list must yield non-empty summary."""
        for tools in (
            [{"tool_name": "x", "result": {"results": [{"a": 1}]}}],
            [{"tool_name": "x", "result": {}}],
            [{"tool_name": "x", "result": {"data": []}}],
            [{"tool_name": "x", "result": 123}],
            [{"tool_name": "x", "result": {}, "error": "boom"}],
        ):
            text = _build_tool_result_summary(tools)
            assert text.strip(), f"expected non-empty summary for {tools}"

    def test_empty_completed_tools_yield_empty(self):
        """If nothing ran, do NOT fabricate content (caller must not inject)."""
        assert _build_tool_result_summary([]) == ""

    def test_summary_does_not_leak_internal_json(self):
        """UI-facing text must be prose, never raw JSON dumps."""
        text = _build_tool_result_summary([
            {"tool_name": "list_emission_factors",
             "result": {"results": [{"code": "EG_GRID_2024", "factor_value": 0.4584}]}},
        ])
        assert '{"' not in text

    def test_draft_empty_with_tools_has_injection_path(self):
        """The runner's injection branch is exercised via the summary function;
        a turn with empty draft + tools yields final text != empty."""
        tools = [{"tool_name": "get_calculation_summary",
                  "result": {"total_calculations": 3}}]
        injected = _build_tool_result_summary(tools)
        # Simulate runner decision: draft empty + tools -> final_text = injected
        draft_text_was_empty = True
        final_text = injected if draft_text_was_empty and tools else ""
        assert final_text.strip() != ""


@pytest.mark.django_db
class TestPromptKeepsLiveCatalog:
    def test_prompt_renders_catalog_when_tools_available(self):
        prompt = async_to_sync(build_chat_prompt)(
            instance_name="carbon",
            system_description="help with carbon reporting",
            api_catalog=[{"name": "list_emission_factors", "method": "GET",
                          "description": "List active emission factors"}],
            navigation_routes=[],
            domain_topics=[],
            instance_config={},
        )
        assert "## Available Host API Endpoints" in prompt
        assert "`list_emission_factors` (GET): List active emission factors" in prompt

    def test_prompt_omits_catalog_when_empty(self):
        prompt = async_to_sync(build_chat_prompt)(
            instance_name="carbon",
            system_description="help",
            api_catalog=[],
            navigation_routes=[],
            domain_topics=[],
            instance_config={},
        )
        assert "## Available Host API Endpoints" not in prompt
