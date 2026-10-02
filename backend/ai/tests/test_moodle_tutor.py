"""Tutor rungs T2 Explain, T3 Quiz, T5 Staff coworker (frozen 2 Oct 2026).

Every span a door emits must be an exact substring of a selected passage. A
proposal that is not a substring is dropped, never printed. The excluded
modules (quiz, qbank, assign, forum, …) are never in the bank.
"""
from __future__ import annotations

from ai.moodle_bank import (
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
)
from ai.moodle_host import door_answer
from ai.moodle_page import (
    _keep_substrings,
    _quiz_spec,
    _staff_spec,
    _topic_spec,
    explain_answer,
    is_explain_ask,
    is_quiz_ask,
    quiz_answer,
    staff_answer,
)
from ai.tests.test_moodle_topic import _med520_home, _page

_MISS = "This is not in this course."
_EXCLUDED_KINDS = {
    "quiz",
    "qbank",
    "feedback",
    "lesson",
    "scorm",
    "h5pactivity",
    "assign",
    "workshop",
    "forum",
}


def _nmd1000_home() -> dict:
    return {
        "course": {
            "id": 2,
            "shortname": "NMD1000",
            "fullname": "Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 1, "name": "Welcome", "visible": True}],
    }


def _course_bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _spans_after_label(reply: str, label: str) -> list[str]:
    lines = reply.splitlines()
    spans: list[str] = []
    started = False
    for line in lines:
        if line.startswith(label):
            started = True
            continue
        if started and line.startswith("- "):
            spans.append(line[2:])
    return spans


# --------------------------------------------------------------------------
# T2 Explain
# --------------------------------------------------------------------------


def test_t2_explain_multi_span_are_substrings():
    reply = explain_answer("explain alopecia", _page(_med520_home()))
    assert reply is not None
    labels = [line for line in reply.splitlines() if line.startswith("Verbatim spans from ")]
    assert len(labels) == 1
    pid = labels[0].removeprefix("Verbatim spans from ").rstrip(":")
    bank = _course_bank("MED520")
    assert pid in bank
    passage_text = str(bank[pid]["text"])
    spans = _spans_after_label(reply, "Verbatim spans from ")
    # Benchmark: 2–3 spans, all from the same selected activity.
    assert 2 <= len(spans) <= 3
    for span in spans:
        assert span in passage_text
    assert "alopecia" in reply.casefold()


def test_t2_explain_caps_at_three():
    assert int(_quiz_spec()["max_items"]) >= 1
    from ai.moodle_page import _explain_spec

    assert int(_explain_spec()["max_spans"]) == 3
    reply = explain_answer("explain alopecia", _page(_med520_home()))
    assert reply is not None
    assert len(_spans_after_label(reply, "Verbatim spans from ")) <= 3


def test_t2_explain_non_substring_is_dropped():
    passage_text = "Explain the etiology, pathogenesis, and clinical manifestations of alopecia areata."
    kept = _keep_substrings(
        [
            "Explain the etiology",
            "This sentence is model prose that is not in the passage.",
        ],
        passage_text,
    )
    assert kept == ["Explain the etiology"]
    # Every span the door actually emits is contained by construction.
    reply = explain_answer("teach me about alopecia", _page(_med520_home()))
    assert reply is not None
    bank = _course_bank("MED520")
    pid = "MED520:file:1111:alopecia.pdf"
    for span in _spans_after_label(reply, "Verbatim spans from "):
        assert span in str(bank[pid]["text"])


def test_t2_explain_miss_is_exact():
    got = explain_answer("explain bartter syndrome", _page(_med520_home()))
    assert got == _MISS
    assert "not on this page" not in got.casefold()


def test_t2_explain_is_an_explain_ask_only():
    assert is_explain_ask("explain alopecia")
    assert is_explain_ask("teach me about alopecia")
    # A plain topic ask is not the explain door.
    assert not is_explain_ask("educate me about alopecia")
    assert not is_explain_ask("herpes?")


# --------------------------------------------------------------------------
# T3 Quiz
# --------------------------------------------------------------------------


def test_t3_quiz_answers_are_verbatim_spans():
    reply = quiz_answer("quiz me on alopecia", _page(_med520_home()))
    assert reply is not None
    bank = _course_bank("MED520")
    answers = [
        line.removeprefix("Answer: ")
        for line in reply.splitlines()
        if line.startswith("Answer: ")
    ]
    assert 1 <= len(answers) <= 3
    for answer in answers:
        assert "alopecia" in answer.casefold()
        owners = [row for row in bank.values() if answer in str(row.get("text") or "")]
        assert owners, answer
    # Every question is the answer with the topic blanked.
    questions = [
        line
        for line in reply.splitlines()
        if line and not line.startswith(("Q", "Answer:", "Section", "Practice"))
    ]
    assert questions
    for question in questions:
        assert "____" in question


def test_t3_quiz_marks_the_activity():
    reply = quiz_answer("quiz me on alopecia", _page(_med520_home()))
    assert reply is not None
    assert "Section 4: alopecia" in reply
    assert "MED520:file:1111:alopecia.pdf" in reply
    assert "from alopecia [MED520:file:1111:alopecia.pdf]" in reply


def test_t3_quiz_no_pack_answer_misses():
    got = quiz_answer("quiz me on bartter syndrome", _page(_med520_home()))
    assert got == _MISS
    other = quiz_answer("quiz me on herpes", _page({
        "course": {
            "id": 2,
            "shortname": "NMD1000",
            "fullname": "Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }))
    assert other == _MISS
    assert is_quiz_ask("quiz me on alopecia")
    assert not is_quiz_ask("educate me about alopecia")


def test_t3_quiz_excluded_mods_never_used():
    bank = _course_bank("MED520")
    kinds = {str(row.get("kind") or "") for row in bank.values()}
    assert not (kinds & _EXCLUDED_KINDS)
    reply = quiz_answer("quiz me on alopecia", _page(_med520_home()))
    assert reply is not None
    for kind in _EXCLUDED_KINDS:
        assert f":{kind}:" not in reply


# --------------------------------------------------------------------------
# T5 Staff coworker
# --------------------------------------------------------------------------


def test_t5_gap_report_lists_not_in_pack():
    reply = staff_answer("pack gaps", _page(_nmd1000_home()))
    assert reply is not None
    assert reply.startswith("Not in the pack on NMD1000:")
    assert "L15 PPT: Proteins" in reply
    lines = [line for line in reply.splitlines() if line.startswith("- ")]
    assert lines
    assert len(lines) <= int(_staff_spec()["gap_max"])


def test_t5_gap_report_clean_course():
    reply = staff_answer("pack gaps", _page(_med520_home()))
    assert reply == "No pack gaps found for this course."


def test_t5_gap_report_off_list_is_refused():
    snapshot = {
        "course": {
            "id": 1,
            "shortname": "AHFAD",
            "fullname": "AHFAD",
            "visible_to_user": True,
        },
        "sections": [],
    }
    assert staff_answer("pack gaps", _page(snapshot)) == "This is not on the course list."


def test_t5_ilo_finder_cites_passages():
    reply = staff_answer("which lectures cover hair follicle", _page(_med520_home()))
    assert reply is not None
    assert reply.startswith("Pack passages containing those terms (MED520):")
    assert "alopecia [MED520:file:1111:alopecia.pdf]" in reply
    bank = _course_bank("MED520")
    # Every non-label line is either a citation header or an exact passage span.
    for line in reply.splitlines()[1:]:
        if line.startswith("- "):
            pid = line.split("[", 1)[1].rstrip("]")
            assert pid in bank
        else:
            owners = [row for row in bank.values() if line in str(row.get("text") or "")]
            assert owners, line


def test_t5_ilo_finder_miss_is_exact():
    got = staff_answer("which lectures cover zzznosuchterm", _page(_med520_home()))
    assert got == "No pack passage contains those terms."


def test_t5_draft_note_is_proposal_only():
    reply = staff_answer("draft an extra note about alopecia", _page(_med520_home()))
    assert reply is not None
    assert reply.startswith("Draft extra note (proposal only")
    assert "No write was made. Paste and save it in the Extra tab." in reply
    bank = _course_bank("MED520")
    pid = "MED520:file:1111:alopecia.pdf"
    for span in _spans_after_label(reply, "Source:"):
        assert span in str(bank[pid]["text"])


def test_t5_student_audience_is_refused():
    from ai.moodle_host import page_context_from_snapshot, snapshot_from_page_context

    student_page = snapshot_from_page_context(
        page_context_from_snapshot({"audience": "student"}, _nmd1000_home())
    )
    assert staff_answer("pack gaps", student_page) is None
    assert staff_answer("which lectures cover hair", student_page) is None
    # A staff page on the same course is allowed.
    assert staff_answer("pack gaps", _page(_nmd1000_home())) is not None


def test_t5_dispatches_through_door_answer():
    got = door_answer("pack gaps", _page(_nmd1000_home()))
    assert got is not None
    assert got.startswith("Not in the pack on NMD1000:")
    # Existing doors do not regress.
    from ai.tests.test_moodle_topic import ALOPECIA_REPLY

    assert door_answer("educate me about alopecia", _page(_med520_home())) == ALOPECIA_REPLY
