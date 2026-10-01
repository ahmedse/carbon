"""A3: Pulse-inactive sections are not title matches and are not cited."""
from ai.moodle_host import door_answer, page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_page import lecture_answer, topic_answer

from ai.tests.test_moodle_topic import ALOPECIA_REPLY, HERPES_REPLY, _MISS, _med520_home, _page


def _off_herpes() -> dict:
    snapshot = _med520_home()
    snapshot["audience"] = "staff"
    snapshot["pulse_off_sections"] = [12]
    snapshot["pulse_off_cmids"] = [1127, 1128]
    return snapshot


def test_pulse_off_herpes_section_is_a_topic_miss():
    snapshot = _off_herpes()
    answer = topic_answer("herpes?", snapshot)
    assert answer == _MISS
    assert "1127" not in (answer or "")
    assert "1128" not in (answer or "")
    assert "PPT: Herpes updated" not in (answer or "")
    alopecia = topic_answer("educate me about alopecia", snapshot)
    assert alopecia == ALOPECIA_REPLY
    assert "1111" in (alopecia or "")


def test_pulse_off_flags_survive_the_page_block():
    snapshot = _off_herpes()
    restored = _page(snapshot)
    assert restored.get("pulse_off_sections") == [12]
    assert 1127 in restored.get("pulse_off_cmids", [])
    assert 1128 in restored.get("pulse_off_cmids", [])
    answer = door_answer("herpes?", restored)
    assert answer == _MISS
    assert HERPES_REPLY not in (answer or "")


def test_prepare_ask_honors_pulse_off_section():
    snapshot = _off_herpes()
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "herpes?",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 7,
        }
    )
    assert decision.chat is None
    assert decision.answer == _MISS
    block = page_context_from_snapshot({"audience": "staff"}, snapshot)
    restored = snapshot_from_page_context(block)
    assert "Pulse-off sections: 12" in block
    assert restored["pulse_off_sections"] == [12]


def test_pulse_off_open_activity_has_no_lecture_to_cite():
    snapshot = _off_herpes()
    snapshot["activity"] = {
        "cmid": 1127,
        "name": "PPT: Herpes updated",
        "module": "resource",
        "section": 12,
    }
    answer = lecture_answer("What is this lecture?", snapshot)
    assert answer == "This page has no lecture to cite."
    assert "1127" not in (answer or "")
    assert "PPT: Herpes updated" not in (answer or "")
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "What is this lecture?",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 7,
        }
    )
    assert decision.chat is None
    assert decision.answer == "This page has no lecture to cite."
