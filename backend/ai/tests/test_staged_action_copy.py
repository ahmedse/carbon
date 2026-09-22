"""A staged mutation is described by the system, never by the model.

Regression cover: the model kept reporting the confirm card as a blocker
("لا يمكنني تقديم طلب الإجازة ... يُرجى إكمال خطوات التأكيد في النظام، ثم أعد
المحاولة") and rewording it every turn, sending the user to a screen that does
not exist.
"""
from __future__ import annotations

import pytest

from ai.engine_runtime import (
    _grounded_outcome_note,
    _has_staged_host_action,
    _human_action_label,
    _staged_body_summary,
)

STAGED_TOOL = {
    "tool_name": "call_host_api",
    "tool_args": {"api_name": "submit_my_leave"},
    "result": {
        "requires_confirmation": True,
        "execution_id": "e1",
        "method": "POST",
        "endpoint": "/carbon-api/people/me/leave/",
        "body": {
            "leave_type": "annual",
            "start_date": "2026-09-22",
            "end_date": "2026-09-22",
            "days": 1,
        },
    },
}


def test_staged_note_says_what_will_be_submitted():
    note = _grounded_outcome_note([STAGED_TOOL])
    assert "Your leave" in note
    assert "leave type annual" in note
    assert "start date 2026-09-22" in note
    assert "Nothing has been submitted yet" in note


def test_staged_note_leaks_no_method_or_path():
    note = _grounded_outcome_note([STAGED_TOOL])
    assert "POST" not in note
    assert "/carbon-api" not in note


def test_staged_note_points_at_this_turn_not_elsewhere():
    note = _grounded_outcome_note([STAGED_TOOL]).lower()
    assert "confirm below" in note
    assert "try again" not in note
    assert "in the system" not in note


@pytest.mark.parametrize("body,expected", [
    ({"leave_type": "annual", "days": 1}, "leave type annual, days 1"),
    ({"leave_type": "", "days": 2}, "days 2"),
    ({"nested": {"a": 1}, "days": 2}, "days 2"),
    ({}, ""),
    (None, ""),
])
def test_body_summary_is_plain_text(body, expected):
    assert _staged_body_summary(body) == expected


def test_host_staged_detection():
    assert _has_staged_host_action([{"kind": "host", "execution_id": "e1"}]) is True
    assert _has_staged_host_action([{"kind": "memory", "execution_id": "e1"}]) is False
    assert _has_staged_host_action([]) is False


def test_action_label_reads_as_words():
    assert _human_action_label(
        {"tool_name": "call_host_api", "tool_args": {"api_name": "submit_my_leave"}}
    ) == "Your leave"
