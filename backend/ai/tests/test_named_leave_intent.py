"""Named leave intent override (SIM-20260919-N7 / N-CHAT-03)."""
from __future__ import annotations

from ai.engine.agent.tools import (
    extract_named_coworker_query,
    first_person_leave_ask,
    first_person_profile_ask,
    leave_balance_intent_asked,
    named_leave_balance_ask,
)
from ai.engine.cognition.turn.intent import (
    IntentCandidate,
    IntentResolution,
    _apply_named_coworker_override,
    _apply_named_leave_override,
)


def test_named_leave_detects_employee_number_ask():
    msg = "What is the annual leave remaining for employee 1001 Wellie?"
    assert leave_balance_intent_asked(msg)
    assert named_leave_balance_ask(msg)
    assert not first_person_leave_ask(msg)


def test_named_coworker_override_forces_resolve():
    resolution = IntentResolution(
        action="clarify",
        candidates=[],
        confidence=0.4,
        clarification="Who is Reena?",
    )
    out = _apply_named_coworker_override(
        resolution,
        user_message="Tell me about Reena",
        labels=[{"name": "get_my_profile"}],
    )
    assert out.action == "answer"
    assert out.candidates and out.candidates[0].name == "resolve_entity"


def test_first_person_profile_is_identity_not_salary():
    assert first_person_profile_ask("What is my employee number?")
    assert first_person_profile_ask("What department am I in?")
    assert first_person_profile_ask("And who is my manager?")
    assert first_person_profile_ask("My manager's name is?")
    assert not first_person_profile_ask("What department does she work in?")
    assert not first_person_profile_ask("Which department is he in?")
    assert not first_person_profile_ask("What number did you give me?")
    assert not first_person_profile_ask("What is my salary?")
    assert not first_person_profile_ask("What is my leave balance?")
    assert extract_named_coworker_query("Tell me about Reena") == "Reena"
    assert extract_named_coworker_query("Now tell me about Salman") == "Salman"
    assert extract_named_coworker_query("Back to Reena - is she a manager?") == "Reena"
    assert extract_named_coworker_query("What is my employee number?") is None
    assert extract_named_coworker_query("What department does she work in?") is None


def test_first_person_leave_not_named():
    msg = "What is my leave balance?"
    assert leave_balance_intent_asked(msg)
    assert first_person_leave_ask(msg)
    assert not named_leave_balance_ask(msg)


def test_named_leave_override_prefers_list_leave_entitlements():
    labels = [
        {"name": "resolve_entity"},
        {"name": "list_leave_entitlements"},
        {"name": "get_my_leave_balance"},
    ]
    resolution = IntentResolution(
        action="answer",
        candidates=[IntentCandidate(name="resolve_entity", confidence=0.85)],
        confidence=0.85,
        zone="platform",
    )
    out = _apply_named_leave_override(
        resolution,
        user_message="annual leave remaining for employee 1001 Wellie",
        labels=labels,
    )
    assert out.action == "answer"
    assert out.candidates[0].name == "list_leave_entitlements"
    assert out.confidence >= 0.9


def test_first_person_leave_override_prefers_get_my_leave_balance():
    labels = [
        {"name": "list_leave_entitlements"},
        {"name": "get_my_leave_balance"},
        {"name": "resolve_entity"},
    ]
    resolution = IntentResolution(
        action="answer",
        candidates=[IntentCandidate(name="resolve_entity", confidence=0.7)],
        confidence=0.7,
        zone="platform",
    )
    out = _apply_named_leave_override(
        resolution,
        user_message="What is my leave balance?",
        labels=labels,
    )
    assert out.candidates[0].name == "get_my_leave_balance"
