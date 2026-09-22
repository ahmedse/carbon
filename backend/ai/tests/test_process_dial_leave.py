"""Process-dial hybrid — personal leave materializes leave.request.lifecycle."""
from __future__ import annotations

from datetime import date

import pytest

from ai.engine.cognition.plan.process_dial import (
    PROCESS_LEAVE,
    is_personal_leave_brief,
    materialize_leave_request_plan,
)


@pytest.mark.parametrize("text,expect", [
    ("اريد اجازة، ليوم واحد غدا، عادي.", True),
    ("I want one day of annual leave tomorrow", True),
    ("leave compliance board pack for October", False),
    ("analyze salary distribution", False),
    ("", False),
])
def test_personal_leave_brief_detection(text, expect):
    assert is_personal_leave_brief(text) is expect


@pytest.mark.django_db
def test_leave_dial_plan_spine_and_slots():
    from mdm.models import ReferenceSet, ReferenceValue
    from people.leave_type_resolve import ensure_leave_type_aliases

    rs, _ = ReferenceSet.objects.get_or_create(
        name="leave_type", defaults={"description": "Leave types"},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=rs, code="annual",
        defaults={"label": "Annual Leave", "metadata": {"aliases": ["عادي", "عادية"]}},
    )
    ensure_leave_type_aliases()

    plan = materialize_leave_request_plan(
        "اريد اجازة، ليوم واحد غدا، عادي.",
        today=date(2026, 9, 22),
    )
    assert plan.source == "process_dial"
    assert plan.skill_name == PROCESS_LEAVE
    assert plan.pattern == "leave_request"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_args.get("api_name") == "get_my_leave_balance"
    assert plan.steps[0].is_mutation is False
    submit = plan.steps[1]
    assert submit.tool_args.get("api_name") == "submit_my_leave"
    assert submit.is_mutation is True
    assert submit.depends_on == [0]
    body = submit.tool_args.get("body") or {}
    assert body.get("leave_type") == "annual"
    assert body.get("start_date") == "2026-09-23"
    assert body.get("days") == 1
    meta = submit.tool_args.get("_process") or {}
    assert meta.get("process_id") == PROCESS_LEAVE
    assert meta.get("process_step") == "submit"
    assert len(plan.phases) == 2


def test_planner_imports_process_dial_helpers():
    """Decompose short-circuit depends on these exports."""
    from ai.engine.cognition.plan.process_dial import (
        is_personal_leave_brief,
        materialize_leave_request_plan,
    )
    assert callable(is_personal_leave_brief)
    assert callable(materialize_leave_request_plan)
    assert is_personal_leave_brief("اريد اجازة غدا عادي") is True
