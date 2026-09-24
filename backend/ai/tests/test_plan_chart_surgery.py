"""Plan 'add a chart' surgery — on-screen vs export PNG paths."""
from __future__ import annotations

from ai.plans_service import PlansService


def _spine():
    return [
        {
            "step_id": 0,
            "intent": "Read leave balance (read only)",
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "get_my_leave_balance"},
            "depends_on": [],
            "is_mutation": False,
            "dry_run_supported": False,
        },
    ]


def test_add_chart_without_export_uses_envelope_not_matplotlib():
    steps = PlansService._surgical_incremental_steps(_spine(), "add a chart please")
    tools = [s.get("tool_name") for s in steps]
    assert "code_execute" not in tools
    assert "export_document" not in tools
    chartish = [s for s in steps if "visual" in (s.get("intent") or "").lower()
                or "chart" in (s.get("intent") or "").lower()
                or "mermaid" in (s.get("intent") or "").lower()]
    assert chartish
    assert chartish[0].get("tool_name") in (None, "")
    assert "code_execute" not in (chartish[0].get("instructions") or "").lower() or (
        "do not call code_execute" in (chartish[0].get("instructions") or "").lower()
    )


def test_add_chart_with_existing_export_uses_code_execute_png():
    spine = _spine() + [
        {
            "step_id": 1,
            "intent": "Export the Word report",
            "tool_name": "export_document",
            "tool_args": {"format": "docx"},
            "depends_on": [0],
            "is_mutation": False,
            "dry_run_supported": False,
        },
    ]
    steps = PlansService._surgical_incremental_steps(spine, "add charts")
    assert any(s.get("tool_name") == "code_execute" for s in steps)
    export = next(s for s in steps if s.get("tool_name") == "export_document")
    assert "chart" in (export.get("intent") or "").lower()


def test_add_chart_and_word_export_appends_png_and_docx():
    steps = PlansService._surgical_incremental_steps(
        _spine(),
        "add a chart and export to word",
    )
    tools = [s.get("tool_name") for s in steps]
    assert "code_execute" in tools
    assert "export_document" in tools


def test_leave_balance_envelope_charts_without_saying_chart():
    from ai.envelope_service import deterministic_envelope_blocks

    usable = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_my_leave_balance"},
        "result": {
            "results": [
                {"leave_type": "Annual", "remaining": 12},
                {"leave_type": "Sick", "remaining": 5},
            ],
        },
    }]
    blocks = deterministic_envelope_blocks(usable, user_message="What is my leave balance?")
    assert blocks["charts"]
    assert blocks["charts"][0].title == "Leave balance"
    assert blocks["charts"][0].series[0]["data"][0] == ["Annual", 12]
