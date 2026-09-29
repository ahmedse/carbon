"""Onboarding how-to answers for the Moodle Ask door."""
from ai.moodle_host import prepare_ask
from ai.moodle_refusals import classify

_LISTED = {
    "audience": "staff",
    "courseid": 11,
    "enrolled": True,
    "course": {
        "id": 11,
        "shortname": "NMD1103",
        "fullname": "Secret Student",
        "visible_to_user": True,
    },
    "sections": [{"number": 1, "name": "Week 1", "visible": True}],
}

_HOWTO = [
    (
        "How do I open a goal?",
        "On Goals, a click on the row only highlights it. The eye opens the record.",
    ),
    (
        "How do I publish an office hour?",
        "Open Office Hours on this activity and create a slot. Students can book it only when they have an active pairing here.",
    ),
    (
        "How does a student book?",
        "The student opens Office Hours, chooses a published slot, and books it. Booking fails without an active pairing on this activity.",
    ),
    (
        "How do I submit a reflection?",
        "Open Reflections. A student submits only against a prompt on this activity. The eye opens the reflection. Pulse will not write it.",
    ),
    (
        "How do I give feedback on a reflection?",
        "A mentor opens the reflection with the eye and writes feedback there. The mentor must be paired with that student on this activity.",
    ),
    (
        "Where is the portfolio?",
        "Portfolio is in the MedMentor bar. It shows your own goals and flags. A student cannot open another student's portfolio.",
    ),
]

_CASELOAD = [
    "Who is my mentee this week?",
    "Book an office hour and set a mentoring pair.",
    "Show the medmentor goals",
    "List my mentees",
    "Change the mentoring pair",
]


def _ask(message: str):
    return prepare_ask({
        "pulse_mode": "ask",
        "message": message,
        "snapshot": _LISTED,
        "host_context": {"audience": "staff", "courseid": 11},
        "moodle_user_id": 7,
    })


def test_six_how_to_asks_return_fixed_answers():
    for message, expected in _HOWTO:
        decision = _ask(message)
        assert decision.answer == expected
        assert decision.refusal is None
        assert decision.chat is None


def test_how_to_answers_do_not_cite_snapshot_names():
    for message, _expected in _HOWTO:
        decision = _ask(message)
        assert "Secret Student" not in (decision.answer or "")


def test_caseload_phrases_refuse_as_mentorship_caseload():
    for message in _CASELOAD:
        assert classify(message) == "mentorship_caseload"
        decision = _ask(message)
        assert decision.refusal == "mentorship_caseload"
        assert decision.chat is None


def test_open_goal_is_not_a_caseload_refusal():
    message = "How do I open a goal?"
    assert classify(message) != "mentorship_caseload"
    assert classify(message) is None
    decision = _ask(message)
    assert decision.refusal is None
