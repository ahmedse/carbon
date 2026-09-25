"""Distribution / visual rendering — no raw payslip dumps."""
from __future__ import annotations

from ai.engine.cognition.turn.runner import (
    _cell_display,
    _is_distribution_ask,
    _render_tool_charts,
    _render_tool_tables,
    _salary_band_buckets,
    _wants_visual,
)


def test_distribution_ask_wants_visual_without_saying_chart():
    assert _wants_visual("tell me more about the salaries distributions")
    assert _is_distribution_ask("tell me more about the salaries distributions")
    assert not _wants_visual("what is my leave balance?")


def test_cell_display_never_dumps_dict_repr():
    assert _cell_display({"id": 101, "code": "gosi", "label": "GOSI / PIFSS"}) == "GOSI / PIFSS"
    assert "id" not in _cell_display("{'id': 101, 'code': 'gosi', 'label': 'Net'}")


def test_distribution_tables_bucket_not_dump_rows():
    usable = [{
        "tool_name": "call_host_api",
        "result": {
            "rows": [
                {"id": 1, "employee_name": "A", "amount": 170, "line_type": {"label": "Gross"}},
                {"id": 2, "employee_name": "B", "amount": 220, "line_type": {"label": "Gross"}},
                {"id": 3, "employee_name": "C", "amount": 900, "line_type": {"label": "Gross"}},
            ],
        },
    }]
    md = _render_tool_tables(
        usable,
        user_message="tell me more about the salaries distributions",
    )
    assert "employee_name" not in md.lower()
    assert "Salary band" in md
    assert "Manjar" not in md
    charts = _render_tool_charts(
        usable,
        user_message="tell me more about the salaries distributions",
    )
    assert "```mermaid" in charts
    assert "xychart-beta" in charts


def test_analyze_breakdown_renders_table_and_chart():
    usable = [{
        "tool_name": "call_host_api",
        "result": {
            "data": {
                "dimension": "gender",
                "suggested_chart_type": "bar",
                "breakdown": [
                    {"label": "male", "count": 80, "pct": 80.0},
                    {"label": "female", "count": 20, "pct": 20.0},
                ],
            },
        },
    }]
    md = _render_tool_tables(usable, user_message="headcount by gender")
    assert "male" in md and "80" in md
    charts = _render_tool_charts(usable, user_message="headcount by gender distribution")
    assert "```mermaid" in charts


def test_leave_balance_rows_chart_instead_of_a_sandbox_image():
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
    charts = _render_tool_charts(usable, user_message="create a report with charts")
    assert "```mermaid" in charts
    assert "Annual" in charts and "Sick" in charts
    assert "12" in charts and "5" in charts
    from ai.envelope_service import deterministic_envelope_blocks

    blocks = deterministic_envelope_blocks(usable, user_message="create a report with charts")
    assert blocks["charts"]
    assert blocks["charts"][0].title == "Leave balance"
    assert blocks["charts"][0].series[0]["data"][0] == ["Annual", 12]


def test_named_pie_is_drawn_when_the_shape_suggests_a_bar():
    usable = [{
        "tool_name": "call_host_api",
        "result": {
            "data": {
                "dimension": "gender",
                "suggested_chart_type": "bar",
                "breakdown": [
                    {"label": "(blank)", "count": 554, "pct": 99.8},
                    {"label": "female", "count": 1, "pct": 0.2},
                ],
            },
        },
    }]
    charts = _render_tool_charts(
        usable,
        user_message="give me a summary report with pie charts",
    )
    assert "pie showData" in charts
    assert "Drawn as a pie" in charts
    plain = _render_tool_charts(usable, user_message="summary report with charts")
    assert "xychart-beta" in plain
    assert "Drawn as a pie" not in plain


def test_salary_band_buckets():
    bands = dict(_salary_band_buckets([50, 150, 250, 350, 500, 800, 1500, 3000, 8000]))
    assert bands["≤100"] == 1
    assert bands["5k+"] == 1
