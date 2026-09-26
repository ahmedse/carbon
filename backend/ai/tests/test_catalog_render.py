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


def test_breakdown_restate_names_only_the_applied_dimension():
    payload = {
        "dimension": "is_active",
        "applied_filters": {},
        "total": 555,
        "breakdown": [{"label": True, "count": 555}],
    }
    rendered = render_catalog_read(
        {"result": payload},
        "analyze_employees",
        "en",
        catalog_entry={"name": "analyze_employees", "kind": "breakdown"},
    )
    assert rendered == "Total: 555\nBy: is_active\nTrue: 555"
    assert "Ali" not in rendered
    assert ungrounded_numbers(rendered, [payload]) == []


def test_metric_restate_quotes_the_host_citation():
    payload = {
        "metric": "headcount",
        "value": 555,
        "citation": "headcount = count where is_active=True",
    }
    rendered = render_catalog_read({"result": payload}, "aggregate_entity", "en")
    assert rendered == "555. headcount = count where is_active=True"
    assert ungrounded_numbers(rendered, [payload]) == []


def test_own_profile_restate_includes_basic_salary_when_the_host_sent_it():
    payload = {
        "id": 17,
        "employee_no": "2378",
        "full_name": "Ali Mohamed Saad AlAjmi",
        "job_title": "Director of Shared Services",
        "basic_salary": "2407.622",
    }
    rendered = render_catalog_read(
        {"result": payload},
        "get_my_profile",
        "en",
        catalog_entry={
            "name": "get_my_profile",
            "kind": "detail",
            "returns": ["full_name", "employee_no", "job_title", "basic_salary"],
        },
    )
    assert rendered is not None
    assert "basic_salary=2407.622" in rendered
    assert "not available" not in rendered.lower()
    assert ungrounded_numbers(rendered, [payload]) == []


def test_fallback_only_when_tools_ran_and_nothing_rendered():
    tool_row = {"tool_name": "call_host_api", "tool_args": {"api_name": "x"}, "result": {}}
    assert should_honest_fallback("", [tool_row]) is True
    assert should_honest_fallback("   ", [tool_row]) is True
    assert should_honest_fallback("", []) is False
    assert should_honest_fallback("", None) is False
    assert should_honest_fallback("No payslip for this month.", [tool_row]) is False


_PROFILE_ENTRY = {
    "name": "get_my_profile",
    "kind": "detail",
    "returns": ["full_name", "employee_no", "job_title", "basic_salary"],
    "field_labels": {
        "full_name": {"en": "Name", "ar": "الاسم"},
        "employee_no": {"en": "Employee number", "ar": "الرقم الوظيفي"},
        "job_title": {"en": "Job title", "ar": "المسمى الوظيفي"},
        "basic_salary": {"en": "Basic salary", "ar": "الراتب الأساسي"},
    },
}
_PROFILE = {
    "id": 17,
    "employee_no": "2378",
    "full_name": "Ali Mohamed Saad AlAjmi",
    "job_title": "Director of Shared Services",
    "basic_salary": "2407.622",
}


def test_sensitive_pay_stays_off_a_profile_dump():
    entry = {**_PROFILE_ENTRY, "sensitive_fields": ["basic_salary"]}
    dumped = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "en", catalog_entry=entry,
    )
    asked_all = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "en",
        catalog_entry=entry,
        fields=["full_name", "employee_no", "job_title", "basic_salary"],
    )
    pay = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "en",
        catalog_entry=entry, fields=["basic_salary"],
    )
    assert dumped and "2407" not in dumped
    assert asked_all and "2407" not in asked_all
    assert pay == "Basic salary: 2407.622"


def test_detail_restate_shows_only_the_fields_asked():
    rendered = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "en",
        catalog_entry=_PROFILE_ENTRY, fields=["name", "employee_no"],
    )
    assert rendered == "Name: Ali Mohamed Saad AlAjmi · Employee number: 2378"
    assert "2407" not in rendered


def test_detail_restate_uses_the_pack_labels_in_arabic():
    rendered = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "ar",
        catalog_entry=_PROFILE_ENTRY, fields=["basic_salary"],
    )
    assert rendered == "الراتب الأساسي: 2407.622"


def test_an_ask_no_declared_field_holds_goes_to_the_writer():
    rendered = render_catalog_read(
        {"result": _PROFILE}, "get_my_profile", "en",
        catalog_entry=_PROFILE_ENTRY, fields=["tes_score"],
    )
    assert rendered is None


def test_metric_restate_speaks_arabic_to_an_arabic_ask():
    payload = {"metric": "kuwaiti", "value": 89, "citation": "kuwaiti = count where nationality__code=KWT"}
    rendered = render_catalog_read({"result": payload}, "aggregate_entity", "ar")
    assert rendered.startswith("العدد: 89")
    assert ungrounded_numbers(rendered, [payload]) == []
