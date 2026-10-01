"""Topic teaching door: named topic → this course’s bank, or an explicit miss."""
from pathlib import Path

import yaml

from ai.moodle_ask_state import (
    PASSAGE_IDS,
    RESOLVED_TOPIC,
    clear_ask_state,
    get_ask_state,
    put_ask_state,
    set_resolved_topic,
)
from ai.moodle_host import door_answer, page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_bank import load_c4_drive, load_c4_files
from ai.moodle_page import _topic_from_message, _topic_spec, topic_answer

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_TOPIC = _PACK / "topic_asks.yaml"

# Frozen gold reply for MED520 course-home “educate me about alopecia”.
# Span is capped by topic_asks cite_span; ellipsis matches lecture-door style.
ALOPECIA_REPLY = (
    "Section 4: alopecia. Activities: alopecia; PPT: alopecia.\n"
    "MED520:file:1111:alopecia.pdf\n"
    "No Alopecia SLOs By the end of this lecture, students will be able to 1. "
    "Explain the etiology, pathogenesis, and clinical manifestations , "
    "associations, diagnosis, treatment lines of alopecia areata…\n"
    "Also openable on this topic: PPT: alopecia."
)

# Frozen gold for MED520 course-home “herpes?” (title activities 1127/1128).
HERPES_REPLY = (
    "Section 12: herpes. Activities: PPT: Herpes updated; herpes Updated.\n"
    "MED520:file:1127:herpes.pptx\n"
    "Herpes Clinical Features: Genital Often asymptomatic Primary infection: "
    "painful erosive balanitis/vulvitis Recurrent: limited number of vesicles "
    "reappear on the genitalia or buttocks , with…\n"
    "Also openable on this topic: herpes Updated."
)

_MISS = "This is not in this course."
_ALOPECIA_PASSAGES = [
    "MED520:file:1111:alopecia.pdf",
    "MED520:google:1112:1tdof3py-n4A-D6b8lEZFdDyiUfKQhT8b",
]


def _page(snapshot: dict) -> dict:
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def _med520_home() -> dict:
    return {
        "course": {
            "id": 74,
            "shortname": "MED520",
            "fullname": "Dermatology",
            "visible_to_user": True,
        },
        "sections": [
            {"number": 3, "name": "Basic skin lesions", "visible": True},
            {"number": 4, "name": "alopecia", "visible": True},
            {"number": 6, "name": "Fungal infections", "visible": True},
            {"number": 12, "name": "herpes", "visible": True},
        ],
    }


def _assert_no_parametric_essay(got: str) -> None:
    """Words from the parametric LLM essay must not appear unless quoted."""
    for word in ("androgenetic", "telogen effluvium", "minoxidil"):
        if word not in got.casefold():
            continue
        bank = {**load_c4_files("MED520"), **load_c4_drive("MED520")}
        joined = "\n".join(
            str((bank.get(pid) or {}).get("text") or "") for pid in _ALOPECIA_PASSAGES
        ).casefold()
        assert word in joined
        assert any(word in line.casefold() for line in got.splitlines() if "MED520:" not in line)


def test_topic_pack_miss_sentence_is_distinct():
    pack = yaml.safe_load(_TOPIC.read_text(encoding="utf-8"))
    assert pack["miss"] == _MISS
    assert pack["miss"] != "This is not in this lecture."
    assert "not on this page" not in pack["miss"].casefold()
    assert "tell me more about " in [str(p).casefold() for p in pack["prefixes"]]
    short = pack.get("short_query") or {}
    assert int(short.get("max_tokens") or 0) >= 1
    assert "herpes" not in [str(w).casefold() for w in (short.get("stopwords") or [])]
    assert "hi" in [str(w).casefold() for w in (short.get("greetings") or [])]


def test_t0_absent_topic_refuses_on_med520():
    """T0 — bartter syndrome is absent from every pack bank."""
    restored = _page(_med520_home())
    got = door_answer("educate me about bartter syndrome", restored)
    assert got == _MISS
    assert "not on this page" not in got.casefold()
    assert "not in this lecture" not in got.casefold()


def test_t1_alopecia_course_home_cites_title_activities():
    """T1 — title-matched 1111/1112, not a title-only refusal."""
    restored = _page(_med520_home())
    got = door_answer("educate me about alopecia", restored)
    assert got == ALOPECIA_REPLY
    assert "alopecia" in got.casefold()
    assert "1111" in got or "1112" in got
    assert "only lists the section name" not in got.casefold()
    assert "can't teach" not in got.casefold()
    assert "can’t teach" not in got.casefold()
    bank = {**load_c4_files("MED520"), **load_c4_drive("MED520")}
    body = got.split("\n", 2)[2].split("\n", 1)[0].rstrip("…")
    assert body in bank["MED520:file:1111:alopecia.pdf"]["text"]
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "educate me about alopecia",
        "snapshot": {
            "audience": "staff",
            "courseid": 74,
            "enrolled": True,
            **_med520_home(),
        },
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert decision.answer == ALOPECIA_REPLY


def test_tell_me_more_about_alopecia_hits_topic_door():
    """Live miss: tell me more about was a phrase miss, not a restart-only issue."""
    _topic_spec.cache_clear()
    restored = _page(_med520_home())
    got = door_answer("tell me more about alopecia", restored)
    assert got == ALOPECIA_REPLY
    assert "1111" in got
    assert "web search" not in got.casefold()
    assert "doesn't carry" not in got.casefold()
    assert "does not carry" not in got.casefold()
    assert "no alopecia content" not in got.casefold()
    _assert_no_parametric_essay(got)
    clear_ask_state()
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "tell me more about alopecia",
        "snapshot": {
            "audience": "staff",
            "courseid": 74,
            "enrolled": True,
            **_med520_home(),
        },
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 9,
    })
    assert decision.chat is None
    assert decision.answer == ALOPECIA_REPLY
    state = get_ask_state("moodle-9-74")
    assert state.get(RESOLVED_TOPIC) == "alopecia"
    assert "1111" in " ".join(state.get(PASSAGE_IDS) or [])


def test_t4_herpes_short_query_cites_title_activities():
    """T4 — bare “herpes?” is a short topic query, not an LLM clinical refusal."""
    _topic_spec.cache_clear()
    assert _topic_from_message("herpes?") == "herpes"
    restored = _page(_med520_home())
    got = door_answer("herpes?", restored)
    assert got == HERPES_REPLY
    assert "1127" in got
    assert "isn't on this page" not in got.casefold()
    assert "isn’t on this page" not in got.casefold()
    assert "clinical advice" not in got.casefold()
    assert "clinician" not in got.casefold()
    bank = load_c4_files("MED520")
    body = got.split("\n", 2)[2].split("\n", 1)[0].rstrip("…")
    assert body in bank["MED520:file:1127:herpes.pptx"]["text"]
    clear_ask_state()
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "herpes?",
        "snapshot": {
            "audience": "staff",
            "courseid": 74,
            "enrolled": True,
            **_med520_home(),
        },
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 14,
    })
    assert decision.chat is None
    assert decision.answer == HERPES_REPLY
    state = get_ask_state("moodle-14-74")
    assert state.get(RESOLVED_TOPIC) == "herpes"
    assert any("1127" in pid or "1128" in pid for pid in (state.get(PASSAGE_IDS) or []))


def test_t4_herpes_cross_course_misses():
    """Same short query on a course without herpes title/passages → miss."""
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    got = door_answer("herpes?", _page(snapshot))
    assert got == _MISS
    assert "MED520" not in got
    assert "1127" not in got
    assert "1128" not in got
    assert "clinical" not in got.casefold()


def test_t4_greeting_is_not_forced_into_topic_miss():
    """Greetings stay out of the topic door; the greet door answers."""
    _topic_spec.cache_clear()
    assert _topic_from_message("hi") is None
    assert _topic_from_message("hello") is None
    got = door_answer("hi", _page(_med520_home()))
    assert got != _MISS
    assert got is not None
    assert _MISS not in got
    assert "MED520" in got
    assert "Dermatology" in got
    assert "this page" not in got.casefold()
    assert "course page" not in got.casefold()
    assert "weeks" not in got.casefold()
    assert "exams" not in got.casefold()


def test_tell_me_more_about_lecture_10_stays_lecture_door():
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [
            {"number": 0, "name": "General", "visible": True},
            {"number": 19, "name": "L10: Terminology1", "visible": True},
        ],
    }
    restored = _page(snapshot)
    got = door_answer("tell me more about lecture 10", restored)
    assert got is not None
    assert "NMD1000:file:1278:Terminology 1.pdf" in got
    assert "alopecia" not in got.casefold()
    assert "Section 19: L10: Terminology1." in got


def test_references_after_topic_use_seeded_state_not_history():
    """Reference door reads resolved_topic from typed state — not a history scan."""
    clear_ask_state()
    restored = _page(_med520_home())
    state: dict = {}
    set_resolved_topic(
        state,
        topic="alopecia",
        shortname="MED520",
        passage_ids=list(_ALOPECIA_PASSAGES),
    )
    put_ask_state("moodle-11-74", state)
    seeded = get_ask_state("moodle-11-74")
    got = door_answer("give me references", restored, state=seeded)
    assert got is not None
    assert "Course materials for alopecia:" in got
    assert "MED520:file:1111:alopecia.pdf" in got
    assert "1112" in got
    assert "web search" not in got.casefold()
    assert "external" not in got.casefold()
    assert "retrieved" not in got.casefold()
    bank = {**load_c4_files("MED520"), **load_c4_drive("MED520")}
    for pid in _ALOPECIA_PASSAGES:
        assert pid in got
        after = got.split(pid, 1)[1].lstrip("\n").split("\n", 1)[0].rstrip("…")
        assert after
        assert after in bank[pid]["text"]


def test_reference_ask_with_empty_state_does_not_invent_cites():
    """Empty resolved_topic → pack no_topic. No MED520 invent; no web wording."""
    clear_ask_state()
    restored = _page(_med520_home())
    for message in ("give me references", "here from the course"):
        got = door_answer(message, restored, state={})
        assert got == "No course topic is in focus."
        assert "1111" not in got
        assert "1112" not in got
        assert "alopecia" not in got.casefold()
        assert "web search" not in got.casefold()
        assert "MED520" not in got


def test_page_context_round_trip_keeps_course_id_for_ask_state():
    """Live embed keys ask state by course id from the signed page block."""
    from ai.moodle_ask_state import ask_state_key
    from ai.moodle_host import page_context_from_snapshot

    text = page_context_from_snapshot({"audience": "staff"}, {
        "audience": "staff",
        "enrolled": True,
        **_med520_home(),
    })
    assert "id=74" in text
    restored = snapshot_from_page_context(text)
    assert restored["course"].get("id") == 74
    assert restored["course"].get("shortname") == "MED520"
    assert ask_state_key("9", restored["course"]["id"], shortname="MED520") == "moodle-9-74"


def test_here_from_the_course_with_state_cites_course_not_web():
    clear_ask_state()
    restored = _page(_med520_home())
    state: dict = {}
    set_resolved_topic(
        state,
        topic="alopecia",
        shortname="MED520",
        passage_ids=list(_ALOPECIA_PASSAGES),
    )
    got = door_answer("here from the course", restored, state=state)
    assert got is not None
    assert "1111" in got and "1112" in got
    assert "web search" not in got.casefold()
    assert "five external" not in got.casefold()
    assert "I gave you" not in got.casefold()


def test_prepare_ask_references_after_topic_turn():
    clear_ask_state()
    snapshot = {
        "audience": "staff",
        "courseid": 74,
        "enrolled": True,
        **_med520_home(),
    }
    first = prepare_ask({
        "pulse_mode": "ask",
        "message": "tell me more about alopecia",
        "snapshot": snapshot,
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 12,
    })
    assert first.chat is None
    assert first.answer == ALOPECIA_REPLY
    second = prepare_ask({
        "pulse_mode": "ask",
        "message": "give me references",
        "snapshot": snapshot,
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 12,
    })
    assert second.chat is None
    assert "1111" in (second.answer or "")
    assert "1112" in (second.answer or "")
    assert "web search" not in (second.answer or "").casefold()
    third = prepare_ask({
        "pulse_mode": "ask",
        "message": "here from the course",
        "snapshot": snapshot,
        "host_context": {"audience": "staff", "courseid": 74},
        "moodle_user_id": 12,
    })
    assert third.chat is None
    assert "1111" in (third.answer or "")
    assert "web search" not in (third.answer or "").casefold()


def test_t2_incidental_fungal_is_not_the_body_when_title_matches():
    """T2 — fungal decks mention alopecia; title match must win."""
    got = topic_answer("educate me about alopecia", _med520_home())
    assert got is not None
    assert "1115" not in got
    assert "1116" not in got
    assert "fungal" not in got.casefold()
    assert "MED520:file:1111:alopecia.pdf" in got
    assert "PPT: alopecia" in got


def test_t0_cross_course_alopecia_on_nmd1000_misses():
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    got = door_answer("educate me about alopecia", _page(snapshot))
    assert got == _MISS
    assert "MED520" not in got
    assert "1111" not in got
    assert "alopecia areata" not in got.casefold()


def test_absent_prefixed_topic_still_misses():
    """Prefix path unchanged: absent topic still exact miss."""
    got = door_answer("what is bartter syndrome", _page(_med520_home()))
    assert got == _MISS
