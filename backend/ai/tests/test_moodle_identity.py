"""Identity and off-course doors on a Moodle course snapshot."""
from pathlib import Path

import yaml

from ai.moodle_host import door_answer, page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_page import _identity, _topic_from_message, closed_answer, identity_answer, is_greet_ask

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_IDENTITY = _PACK / "identity_asks.yaml"
_MISS = "This is not in this course."
_WHO = "I am Pulse for this course. I answer from this course's lectures and files."
_NMD3101 = "This course is NMD3101: priniciples of infection. This is not in this course."
_MED520 = "This course is MED520: Dermatology. This is not in this course."
_FORBIDDEN = (
    "page block",
    "Moodle page",
    "assistant on this Moodle",
    "Current page block",
    "Open My",
    "web search",
    "greenhouse",
    "Scope 1",
)


def _page(snapshot: dict) -> dict:
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def _nmd3101() -> dict:
    return {
        "audience": "staff",
        "courseid": 25,
        "enrolled": True,
        "course": {
            "id": 25,
            "shortname": "NMD3101",
            "fullname": "priniciples of infection",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }


def _med520() -> dict:
    return {
        "audience": "staff",
        "courseid": 74,
        "enrolled": True,
        "course": {
            "id": 74,
            "shortname": "MED520",
            "fullname": "Dermatology",
            "visible_to_user": True,
        },
        "sections": [
            {"number": 4, "name": "alopecia", "visible": True},
            {"number": 12, "name": "herpes", "visible": True},
        ],
    }


def _assert_clean(answer: str) -> None:
    folded = answer.casefold()
    for needle in _FORBIDDEN:
        assert needle.casefold() not in folded, needle
    assert "page block" not in folded


def test_identity_pack_owns_expert_prefixes():
    _identity.cache_clear()
    pack = yaml.safe_load(_IDENTITY.read_text(encoding="utf-8"))
    prefixes = [str(p).casefold() for p in (pack.get("expert_prefixes") or [])]
    assert "are you expert in " in prefixes
    assert pack["answer"] == _WHO
    assert pack["miss"] == _MISS
    assert "page" not in pack["answer"].casefold()
    assert "moodle" not in pack["answer"].casefold()


def test_who_are_you_is_the_course_tutor():
    restored = _page(_nmd3101())
    assert identity_answer("who are you", restored) == _WHO
    assert door_answer("who are you ?", restored) == _WHO
    _assert_clean(_WHO)


def test_expert_in_carbon_emissions_misses_on_nmd3101():
    restored = _page(_nmd3101())
    assert is_greet_ask("are you expert in carbon emissions?") is False
    assert _topic_from_message("are you expert in carbon emissions?") is None
    got = door_answer("are you expert in carbon emissions?", restored)
    assert got == _NMD3101
    _assert_clean(got)
    typo = door_answer("are you expert in carbon emissioons?", restored)
    assert typo == _NMD3101
    _assert_clean(typo)
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "are you expert in carbon emissioons?",
        "snapshot": _nmd3101(),
        "host_context": {"audience": "staff", "courseid": 25},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert decision.answer == _NMD3101


def test_expert_in_carbon_emissions_misses_on_med520():
    restored = _page(_med520())
    got = door_answer("are you expert in carbon emissions?", restored)
    assert got == _MED520
    assert "alopecia" not in got.casefold()
    assert "herpes" not in got.casefold()
    _assert_clean(got)


def test_herpes_short_query_stays_topic():
    restored = _page(_med520())
    got = door_answer("herpes?", restored)
    assert got != _MISS
    assert _MISS not in (got or "")
    assert "herpes" in got.casefold()


def test_hi_stays_greet_and_which_course_stays_identity():
    restored = _page(_nmd3101())
    greet = door_answer("hi", restored)
    assert greet.startswith("Hi. This course is NMD3101:")
    assert _MISS not in greet
    course = door_answer("which course", restored)
    assert course == "This course is NMD3101: priniciples of infection."
    assert _WHO not in (course or "")


def test_ordinary_off_course_chat_misses_closed():
    restored = _page(_nmd3101())
    got = door_answer("can you help me plan a weekend trip to the beach?", restored)
    assert got == _NMD3101
    assert closed_answer(restored) == _NMD3101
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "can you help me plan a weekend trip to the beach?",
        "snapshot": _nmd3101(),
        "host_context": {"audience": "staff", "courseid": 25},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert decision.answer == _NMD3101
    _assert_clean(got)
