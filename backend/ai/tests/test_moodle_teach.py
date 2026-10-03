"""L-T T1 — grounded multi-passage lesson DRAFT (TEACHING-WAVE-SPEC §1.1).

Locks: the draft is labelled ``draft`` and claims no Moodle write (R11); every
emitted sentence is an exact substring of the passage it cites (the B3 pass); a
non-substring candidate is dropped, never printed; the door is staff-only; a
miss is the exact course sentence; existing doors do not regress.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai.moodle_bank import (
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
)
from ai.moodle_host import door_answer, page_context_from_snapshot, snapshot_from_page_context
from ai.moodle_page import is_explain_ask
from ai.moodle_teach import _grounded_spans, _spec, ground_sentence, is_teach_ask, lesson_draft, teach_answer
from ai.tests.test_moodle_topic import ALOPECIA_REPLY, _med520_home, _page

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "teach-b3.yaml").read_text(encoding="utf-8"))
_MISS = "This is not in this course."


def _course_bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _draft_pairs(reply: str, bank: dict[str, dict]) -> list[tuple[str, str]]:
    """(passage id, span) pairs from the draft: a bank id header, then '- ' lines."""
    pairs: list[tuple[str, str]] = []
    current = None
    for line in reply.splitlines():
        if line in bank:
            current = line
        elif line.startswith("- ") and current is not None:
            pairs.append((current, line[2:]))
    return pairs


def _staff_page(shortname: str) -> dict:
    return _page(
        {
            "course": {
                "id": 1,
                "shortname": shortname,
                "fullname": shortname,
                "visible_to_user": True,
            },
            "sections": [],
        }
    )


# --------------------------------------------------------------------------
# T1 door — grounded, labelled, no write
# --------------------------------------------------------------------------


def test_t1_draft_is_labelled_and_claims_no_write():
    reply = teach_answer("draft a lesson about alopecia", _page(_med520_home()))
    assert reply is not None
    assert reply.startswith("Draft lesson (proposal only")
    assert "No write was made. Paste and save it in the Extra tab." in reply


def test_t1_every_draft_sentence_is_a_verbatim_span():
    reply = teach_answer("draft a lesson about alopecia", _page(_med520_home()))
    assert reply is not None
    bank = _course_bank("MED520")
    pairs = _draft_pairs(reply, bank)
    assert pairs, "draft emitted no grounded sentence"
    for pid, span in pairs:
        assert pid in bank, f"unresolved passage id {pid}"
        assert span in str(bank[pid]["text"]), f"ungrounded sentence: {span!r}"


def test_t1_draft_is_multi_passage():
    reply = lesson_draft("alopecia", _staff_page("MED520"))
    bank = _course_bank("MED520")
    pids = {pid for pid, _span in _draft_pairs(reply, bank)}
    assert len(pids) >= 2, f"expected a multi-passage lesson, got {pids}"


def test_t1_non_substring_is_dropped_not_printed():
    passage_text = "Alopecia areata is a common autoimmune disorder of the hair follicle."
    fabricated = "Alopecia is caused by a rare fungal enzyme absent from every lecture."
    assert ground_sentence(passage_text, "Alopecia areata is a common autoimmune disorder of the hair follicle.")
    assert not ground_sentence(passage_text, fabricated)
    spans = _grounded_spans(passage_text, "alopecia", _spec())
    assert fabricated not in spans
    assert all(span in passage_text for span in spans)


def test_t1_draft_never_contains_the_fabricated_claim():
    claim = _GOLD["out_of_scope"]["ungrounded_claim"][0]
    bank = _course_bank("MED520")
    text = str(bank[claim["passage_ref"]]["text"])
    assert claim["fabricated_sentence"] not in text
    reply = lesson_draft("alopecia", _staff_page("MED520"))
    assert claim["fabricated_sentence"] not in reply


def test_t1_miss_is_the_exact_course_sentence():
    got = teach_answer("draft a lesson about zzznosuchtermqq", _page(_med520_home()))
    assert got == _MISS


def test_t1_student_audience_is_refused():
    student_page = snapshot_from_page_context(
        page_context_from_snapshot({"audience": "student"}, _med520_home())
    )
    assert teach_answer("draft a lesson about alopecia", student_page) is None


def test_t1_off_list_is_refused():
    snapshot = {
        "course": {"id": 1, "shortname": "AHFAD", "fullname": "AHFAD", "visible_to_user": True},
        "sections": [],
    }
    assert teach_answer("draft a lesson about alopecia", _page(snapshot)) is None


def test_t1_prefix_is_not_stolen_by_explain_or_topic():
    assert is_teach_ask("draft a lesson about alopecia")
    assert not is_explain_ask("draft a lesson about alopecia")
    # A plain explain ask is untouched.
    assert is_explain_ask("teach me about alopecia")


def test_t1_dispatches_through_door_answer_without_regressing():
    got = door_answer("draft a lesson about alopecia", _page(_med520_home()))
    assert got is not None
    assert got.startswith("Draft lesson (proposal only")
    assert door_answer("educate me about alopecia", _page(_med520_home())) == ALOPECIA_REPLY


# --------------------------------------------------------------------------
# R11 — the draft contract is labelled draft and writes nothing (4/4)
# --------------------------------------------------------------------------


def test_r11_four_draft_cases_are_proposal_only():
    gold = yaml.safe_load((_PACK / "gold" / "l5-r11.draft.yaml").read_text(encoding="utf-8"))
    cases = gold["cases"]
    assert len(cases) == 4
    for case in cases:
        reply = door_answer(case["ask"], _staff_page(case["course"]))
        assert reply is not None, case["id"]
        assert reply.startswith(case["expect_label"]), case["id"]
        assert case["expect_no_write"] in reply, case["id"]
        assert case["claims_moodle_write"] is False
        assert case["host_effect"] == "none"
