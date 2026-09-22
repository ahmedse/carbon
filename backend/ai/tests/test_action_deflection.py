"""A write request must never be answered with "do it elsewhere, then retry".

Regression cover for the exact replies Nibras produced to a complete leave
request, each a reworded version of the same dead end.
"""
from __future__ import annotations

import types

import pytest

from ai.engine.cognition.turn.action_deflection import (
    build_forced_action_message,
    is_action_deflection,
)
from ai.engine_runtime import _should_force_action, _staged_or_acted

DEFLECTIONS = [
    "لا يمكنني تقديم طلب الإجازة مباشرةً. يُرجى التأكد من إكمال خطوات التأكيد "
    "المطلوبة في النظام الأساسي أولاً، ثم المحاولة مرة أخرى.",
    "يبدو أن هناك خطوة تأكيد مطلوبة من النظام الأساسي قبل تقديم طلب الإجازة. "
    "يُرجى إكمال عملية التأكيد المطلوبة أولاً، ثم المحاولة مرة أخرى.",
    "لا يمكنني تقديم طلب الإجازة لأن النظام يتطلب تأكيدًا منك أولاً. "
    "يُرجى إكمال خطوات التأكيد المطلوبة في النظام، ثم أعد المحاولة.",
    "It seems that submitting your leave request requires additional "
    "confirmation through the system. Please complete the confirmation "
    "process there first, and then try again.",
    "I cannot submit the request directly — please complete the confirmation "
    "steps in the system first, then try again.",
]


@pytest.mark.parametrize("text", DEFLECTIONS)
def test_deflections_are_detected(text):
    assert is_action_deflection(text) is True


@pytest.mark.parametrize("text", [
    "Your leave is ready to go — leave type annual, start date 2026-09-22. "
    "Nothing has been submitted yet: confirm below to proceed.",
    "You have 23 days of annual leave remaining.",
    "أي نوع إجازة تريد: سنوية أم مرضية؟",
    "",
])
def test_good_answers_are_not_deflections(text):
    assert is_action_deflection(text) is False


def _ledger(completed_tools):
    return types.SimpleNamespace(
        execution=types.SimpleNamespace(completed_tools=completed_tools)
    )


def test_staged_turn_is_not_retried():
    staged = _ledger([{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "submit_my_leave"},
        "result": {"requires_confirmation": True, "execution_id": "e1"},
    }])
    assert _staged_or_acted(staged) is True
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا, عادي.",
        types.SimpleNamespace(text=DEFLECTIONS[0]),
        staged,
    ) is False


def test_deflected_write_request_triggers_the_backstop():
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا, عادي.",
        types.SimpleNamespace(text=DEFLECTIONS[0]),
        _ledger([]),
    ) is True


def test_read_request_never_triggers_the_backstop():
    assert _should_force_action(
        "كم رصيد اجازاتي؟",
        types.SimpleNamespace(text=DEFLECTIONS[0]),
        _ledger([]),
    ) is False


def test_one_clarifying_question_is_a_valid_ending():
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا.",
        types.SimpleNamespace(text="أي نوع إجازة تريد: سنوية أم مرضية؟"),
        _ledger([]),
    ) is False


def test_read_only_answer_that_drops_the_request_triggers_the_backstop():
    # The exact live failure: a complete request answered with the balance
    # table and nothing staged.
    balance_answer = (
        "You have sufficient annual leave balance to take a one-day leave "
        "tomorrow. You have 23 days of annual leave remaining."
    )
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا, عادي.",
        types.SimpleNamespace(text=balance_answer),
        _ledger([{
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "get_my_leave_balance"},
            "result": {"status_code": 200, "data": []},
        }]),
    ) is True


def test_host_refusal_is_not_retried():
    # submit_my_leave ran and the host denied it — that is a grounded answer.
    denied = _ledger([{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "submit_my_leave"},
        "result": {"status_code": 400, "error_kind": "insufficient_balance"},
    }])
    assert _should_force_action(
        "اريد اجازة, ليوم واحد غدا, عادي.",
        types.SimpleNamespace(text="لا يوجد رصيد كافٍ لهذا النوع."),
        denied,
    ) is False


def test_forced_message_states_the_contract_and_keeps_the_request():
    forced = build_forced_action_message("اريد اجازة, ليوم واحد غدا, عادي.")
    assert "اريد اجازة" in forced
    assert "stages the action" in forced
    assert "ONE short question" in forced
