"""Catalog-metadata ESS read renderers (I4)."""
import json

from ai.engine.cognition.plan.export_bind import render_bound_catalog_read
from ai.engine.cognition.turn.catalog_render import (
    BALANCE_APIS,
    honest_unsummarized_fallback,
    render_catalog_read,
    should_honest_fallback,
)
from ai.engine.cognition.turn.grounding import ungrounded_numbers


SIX_ROW_ENTITLEMENTS = [
    {"leave_type": "annual", "entitled_days": 30, "used_days": 0, "carried_forward": 0},
    {"leave_type": "sick", "entitled_days": 15, "used_days": 2, "carried_forward": 0},
    {"leave_type": "emergency", "entitled_days": 5, "used_days": 0, "carried_forward": 0},
    {"leave_type": "unpaid", "entitled_days": 0, "used_days": 0, "carried_forward": 0},
    {"leave_type": "maternity", "entitled_days": 70, "used_days": 0, "carried_forward": 0},
    {"leave_type": "paternity", "entitled_days": 3, "used_days": 0, "carried_forward": 0},
]


def test_balance_apis_alias_same_renderer():
    assert "list_leave_entitlements" in BALANCE_APIS
    assert "get_my_leave_balance" in BALANCE_APIS


def test_list_leave_entitlements_six_row_render_en():
    rendered = render_catalog_read(
        {"result": json.dumps(SIX_ROW_ENTITLEMENTS)},
        "list_leave_entitlements",
        "en",
    )
    assert rendered
    assert "Your leave balance" in rendered
    assert "**Your leave balance**" not in rendered
    assert "- annual entitled 30" in rendered
    assert "sick entitled 15 (used 2)" in rendered
    assert "call_host_api" not in rendered
    assert ungrounded_numbers(rendered, [SIX_ROW_ENTITLEMENTS]) == []


def test_org_entitlements_name_each_employee_instead_of_repeating_your_balance():
    rows = []
    for name, no, used in (
        ("Bilagot Panta", "1067", 8),
        ("Mohammad Bolto", "1712", 0),
    ):
        rows.append({
            "employee_name": name,
            "employee_no": no,
            "year": 2026,
            "leave_type": "annual",
            "entitled_days": 30,
            "used_days": used,
        })
    rendered = render_catalog_read(
        {"result": rows}, "list_leave_entitlements", "en",
    )
    assert "Your leave balance" not in rendered
    assert "Leave balances" in rendered
    assert "Bilagot Panta (1067), 2026" in rendered
    assert "Mohammad Bolto (1712), 2026" in rendered
    assert "annual entitled 30 (used 8)" in rendered
    assert rendered.count("annual entitled 30") == 2


def test_list_leave_entitlements_six_row_render_ar():
    rendered = render_catalog_read(
        {"result": SIX_ROW_ENTITLEMENTS},
        "list_leave_entitlements",
        "ar",
    )
    assert rendered
    assert "رصيد إجازاتك" in rendered
    assert "**رصيد إجازاتك**" not in rendered
    assert "annual" in rendered
    assert "المستحق 30" in rendered
    assert ungrounded_numbers(rendered, [SIX_ROW_ENTITLEMENTS]) == []


def test_get_my_leave_balance_uses_your_scope_en():
    rendered = render_bound_catalog_read(
        {"result": [{"leave_type": "annual", "entitled": 30, "remaining": 30}]},
        "get_my_leave_balance",
        "en",
    )
    assert rendered == (
        "Your leave balance\n\n"
        "- annual remaining 30 (entitled 30)"
    )


def test_honest_unsummarized_fallback_has_no_tool_names():
    en = honest_unsummarized_fallback("en")
    assert "call_host_api" not in en
    assert "Retrieved" not in en
    assert "Open My" in en


LOAN_ROWS = [
    {"id": 7, "loan_type": "emergency", "principal": 9600, "term_months": 12, "status": "active"},
]


def test_fallback_never_replaces_a_catalog_render():
    """ADR-0049 invariant: forced call blanks the draft, render still wins."""
    tool_row = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_loans"},
        "result": LOAN_ROWS,
    }
    rendered = render_bound_catalog_read(tool_row, "list_my_loans", "en")
    assert rendered and "emergency" in rendered
    # Draft was empty (force_tool) but a render exists → no fallback.
    assert should_honest_fallback(rendered, [tool_row]) is False


_RUN_ENTRY = {
    "name": "list_payroll_runs",
    "kind": "list",
    "empty_render": "no_list_rows",
    "label": "Runs",
    "latest_by": "period_end",
    "returns": ["id", "org_unit", "period_start", "period_end", "status", "created_at"],
}
_DETAIL_ENTRY = {
    "name": "get_payroll_run",
    "kind": "detail",
    "empty_render": "no_detail_row",
    "returns": ["id", "org_unit", "period_start", "period_end", "status", "committed_at"],
}
_RUN_ROWS = [
    {
        "id": 57,
        "org_unit": 1,
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "status": "committed",
        "created_at": "2026-09-25T18:48:06.260434+03:00",
    },
    {
        "id": 56,
        "org_unit": 1,
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "status": "committed",
        "created_at": "2026-09-25T18:48:02.408376+03:00",
    },
]


def test_declared_list_restates_returns_and_latest_first():
    payload = {"status_code": 200, "data": {"count": 2, "results": _RUN_ROWS}}
    rendered = render_catalog_read(
        {"result": payload},
        "list_payroll_runs",
        "en",
        catalog_entry=_RUN_ENTRY,
    )
    assert rendered
    assert rendered.startswith("Runs (2):")
    assert rendered.index("id=56") < rendered.index("id=57")
    assert "period_end=2026-08-31" in rendered
    assert ungrounded_numbers(rendered, [payload]) == []


def test_declared_detail_restates_iso_commit_without_writer():
    row = {
        "id": 56,
        "org_unit": 1,
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "status": "committed",
        "committed_at": "2026-09-25T18:48:02.408376+03:00",
    }
    rendered = render_catalog_read(
        {"result": {"status_code": 200, "data": row}},
        "get_payroll_run",
        "en",
        catalog_entry=_DETAIL_ENTRY,
    )
    assert rendered
    assert "id=56" in rendered
    assert "committed_at=2026-09-25T18:48:02.408376+03:00" in rendered
    assert ungrounded_numbers(rendered, [row]) == []


def test_declared_list_empty_uses_pack_empty_render():
    rendered = render_catalog_read(
        {"result": {"results": []}},
        "list_payroll_runs",
        "en",
        catalog_entry=_RUN_ENTRY,
    )
    assert rendered == "No rows on record for that list."


def test_restate_last_view_copies_table_cells():
    from ai.engine.cognition.turn.catalog_render import restate_last_view

    text = restate_last_view({
        "tables": [{
            "title": "Committed at",
            "columns": ["Category", "Value"],
            "rows": [["2026-09-25T18:48:02.408376+03:00", 1]],
        }],
    })
    assert "2026-09-25T18:48:02.408376+03:00" in text
    assert "Value=1" in text
    assert ungrounded_numbers(text, [{
        "tables": [{"rows": [["2026-09-25T18:48:02.408376+03:00", 1]]}],
    }]) == []


def test_declared_kind_without_returns_does_not_guess():
    assert render_catalog_read(
        {"result": _RUN_ROWS},
        "list_payroll_runs",
        "en",
        catalog_entry={"name": "list_payroll_runs", "kind": "list", "empty_render": "no_list_rows"},
    ) is None


def test_fallback_only_when_tools_ran_and_nothing_rendered():
    tool_row = {"tool_name": "call_host_api", "tool_args": {"api_name": "x"}, "result": {}}
    assert should_honest_fallback("", [tool_row]) is True
    assert should_honest_fallback("   ", [tool_row]) is True
    assert should_honest_fallback("", []) is False
    assert should_honest_fallback("", None) is False
    assert should_honest_fallback("No payslip for this month.", [tool_row]) is False
