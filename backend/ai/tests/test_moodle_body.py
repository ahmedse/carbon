"""B3 body-topic retrieval gold + B2 partial Index loop.

A course topic that lives only in a passage BODY is cited from this course’s
JSONL with a verbatim span around the word. Whole-word, occurrence-ranked,
deterministic. No embeddings, no model, no new network.
"""
from ai.moodle_bank import (
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
    write_extra_index,
)
from ai.moodle_host import door_answer, page_context_from_snapshot, snapshot_from_page_context
from ai.moodle_page import _topic_spec, topic_answer

_MISS = "This is not in this course."

_MED520_HOME = {
    "course": {
        "id": 74,
        "shortname": "MED520",
        "fullname": "Dermatology",
        "visible_to_user": True,
    },
    "sections": [
        {"number": 3, "name": "Basic skin lesions", "visible": True},
        {"number": 4, "name": "alopecia", "visible": True},
        {"number": 12, "name": "herpes", "visible": True},
    ],
}

_NMD1000_HOME = {
    "course": {
        "id": 25,
        "shortname": "NMD1000",
        "fullname": "NMD1000: Introduction to Medical School",
        "visible_to_user": True,
    },
    "sections": [{"number": 0, "name": "General", "visible": True}],
}

_NMD3101_HOME = {
    "course": {
        "id": 26,
        "shortname": "NMD3101",
        "fullname": "Principles of infection",
        "visible_to_user": True,
    },
    "sections": [{"number": 0, "name": "General", "visible": True}],
}

_TERBINAFINE_ID = "MED520:google:1116:17MCfM6hBkJGWrgcEMmQONv29QSmTIPvd"
_MINOXIDIL_ID = "MED520:google:1112:1tdof3py-n4A-D6b8lEZFdDyiUfKQhT8b"

# Frozen golds. Term is in the body of a google deck, not in a title.
TERBINAFINE_REPLY = (
    "Activities: PPT: Fungal infections.\n"
    "MED520:google:1116:17MCfM6hBkJGWrgcEMmQONv29QSmTIPvd\n"
    "Oral therapies like terbinafine, griseofulvin, and itraconazole is essential "
    "for scalp, nail infections, or when topical treatment is ineffective."
)

MINOXIDIL_REPLY = (
    "Activities: PPT: alopecia; alopecia.\n"
    "MED520:google:1112:1tdof3py-n4A-D6b8lEZFdDyiUfKQhT8b\n"
    "Topical minoxidil and anthralin (dithranol), have been advocated in patients "
    "with limited patchy alopecia.\n"
    "Also openable on this topic: alopecia."
)


def _page(snapshot: dict) -> dict:
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def _bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _span_after(got: str, passage_id: str) -> str:
    return got.split(passage_id, 1)[1].lstrip("\n").split("\n", 1)[0]


def test_body_only_term_cites_passage_with_verbatim_span():
    """B3 — a term only in a passage body cites that passage with a real span."""
    _topic_spec.cache_clear()
    bank = _bank("MED520")
    assert all("terbinafine" not in str(row.get("name") or "").casefold() for row in bank.values())
    got = door_answer("what is terbinafine", _page(_MED520_HOME))
    assert got == TERBINAFINE_REPLY
    span = _span_after(got, _TERBINAFINE_ID)
    assert "terbinafine" in span.casefold()
    assert span in bank[_TERBINAFINE_ID]["text"]
    assert len(span) <= 160
    assert "1111" not in got


def test_body_occurrence_preference_is_deterministic():
    """R-body3 — most occurrences wins (1112 has 5, 1111 has 1)."""
    _topic_spec.cache_clear()
    bank = _bank("MED520")
    got = door_answer("what is minoxidil", _page(_MED520_HOME))
    assert got == MINOXIDIL_REPLY
    assert _MINOXIDIL_ID in got
    assert "MED520:file:1111:alopecia.pdf" not in got
    span = _span_after(got, _MINOXIDIL_ID)
    assert "minoxidil" in span.casefold()
    assert span in bank[_MINOXIDIL_ID]["text"]
    assert len(span) <= 160


def test_body_word_boundary_miss_on_substring_collision():
    """R-body3/R-body5 — “flu” is inside fluid/influence, not a word. Miss exactly."""
    _topic_spec.cache_clear()
    for home in (_NMD1000_HOME, _NMD3101_HOME):
        got = door_answer("what is flu", _page(home))
        assert got == _MISS
        assert "1288" not in got


def test_body_cross_course_term_misses_on_other_course():
    """R-body1 — balanitis is in MED520 body only; NMD3101 must not cite it."""
    _topic_spec.cache_clear()
    got = door_answer("what is balanitis", _page(_NMD3101_HOME))
    assert got == _MISS
    assert "MED520" not in got
    assert "1127" not in got and "1128" not in got


def test_body_index_loop_extra_term_live_only_after_index(tmp_path, monkeypatch):
    """R-body8 — an extra-file body term misses before Index and cites after."""
    _topic_spec.cache_clear()
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    snapshot = _page(_MED520_HOME)
    assert topic_answer("what is pulsebodyterm", snapshot) == _MISS
    extra_text = "AASTMT Pulse-only tutor note. pulsebodyterm is the unique body term."
    written = write_extra_index(
        "MED520",
        [
            {
                "itemid": 42,
                "filename": "body-note.md",
                "title": "Body note",
                "sectionnum": -1,
                "passages": [{"text": extra_text}],
            }
        ],
        extra_root=tmp_path,
    )
    assert written == 1
    got = topic_answer("what is pulsebodyterm", snapshot)
    assert got is not None
    passage_id = "MED520:extra:42:body-note.md"
    assert passage_id in got
    span = _span_after(got, passage_id)
    assert "pulsebodyterm" in span.casefold()
    assert span in extra_text
    assert len(span) <= 160


def test_body_topic_sets_resolved_topic_for_reference_follow_up():
    """B4 — a body topic writes typed state; the reference door reads it, no web."""
    from ai.moodle_ask_state import RESOLVED_TOPIC, clear_ask_state, get_ask_state
    from ai.moodle_host import prepare_ask

    _topic_spec.cache_clear()
    clear_ask_state()
    snapshot = {"audience": "staff", "courseid": 74, "enrolled": True, **_MED520_HOME}
    first = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "what is terbinafine",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 21,
        }
    )
    assert first.chat is None
    assert _TERBINAFINE_ID in (first.answer or "")
    state = get_ask_state("moodle-21-74")
    assert state.get(RESOLVED_TOPIC) == "terbinafine"
    second = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "give me references",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 21,
        }
    )
    assert second.chat is None
    assert _TERBINAFINE_ID in (second.answer or "")
    assert "web" not in (second.answer or "").casefold()
    assert "external" not in (second.answer or "").casefold()


def test_body_capped_span_starts_on_a_word_not_punctuation():
    """R-body4 — a capped body window must begin on a word, not on a comma.

    ``itraconazole`` first appears mid-sentence after a comma; the 160-cap must
    not leave the span starting with ``", "``.
    """
    _topic_spec.cache_clear()
    got = door_answer("what is itraconazole", _page(_MED520_HOME))
    assert got is not None
    assert _TERBINAFINE_ID in got
    span = _span_after(got, _TERBINAFINE_ID)
    bank = _bank("MED520")
    assert "itraconazole" in span.casefold()
    assert span in bank[_TERBINAFINE_ID]["text"]
    assert span[0].isalnum()
    assert len(span) <= 160
    assert not bank[_TERBINAFINE_ID]["text"].strip().startswith(span)
