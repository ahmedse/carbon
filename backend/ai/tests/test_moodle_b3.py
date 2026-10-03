"""B3 grounding/faithfulness gold (TEACHING-WAVE-SPEC §1.6).

Locks the authored gold ``domain_packs/aast-med/gold/teach-b3.yaml``:
≥50 ``(draft sentence) → passage id → verbatim span`` assertions across 13
courses, each a REAL sentence-bounded slice of the committed bank; 100% verbatim
and 0 fabricated spans. Out-of-scope cases must be refused: a topic with no
passage is the exact miss, a student audience and an off-list course are
refused, and an ungrounded claim is dropped, never printed.
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
from ai.moodle_host import page_context_from_snapshot, snapshot_from_page_context
from ai.moodle_page import _load_course_bank
from ai.moodle_teach import _grounded_spans, _spec, ground_sentence, lesson_draft, teach_answer
from ai.tests.test_moodle_topic import _med520_home, _page

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "teach-b3.yaml").read_text(encoding="utf-8"))
_CASES = _GOLD["cases"]
_OUT = _GOLD["out_of_scope"]
_MISS = _GOLD["miss"]


def _bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _page_for(shortname: str) -> dict:
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


def test_b3_gold_shape_and_coverage():
    assert len(_CASES) >= 50, len(_CASES)
    assert len({case["shortname"] for case in _CASES}) == 13
    assert len({case["id"] for case in _CASES}) == len(_CASES)
    assert _GOLD["thresholds"]["verbatim_ratio"] == 1.0
    assert _GOLD["thresholds"]["fabricated_spans"] == 0
    for case in _CASES:
        for key in ("id", "shortname", "topic", "passage_ref", "draft_sentence", "verbatim_span"):
            assert case.get(key) not in (None, ""), key


@pytest.mark.parametrize("case", _CASES, ids=[case["id"] for case in _CASES])
def test_b3_case_is_real_and_grounded(case: dict):
    bank = _bank(case["shortname"])
    pid = case["passage_ref"]
    # The passage id resolves in the open course bank, and both the sentence and
    # the claimed span are VERBATIM substrings of that passage's committed text.
    assert pid in bank, f"{pid} does not resolve"
    text = str(bank[pid]["text"])
    assert case["verbatim_span"] in text
    assert case["draft_sentence"] in text
    # The builder would emit the sentence for this topic (grounding pass).
    spec = _spec()
    spans = _grounded_spans(text, case["topic"], spec)
    assert case["draft_sentence"] in spans


def test_b3_is_100_percent_verbatim_zero_fabricated():
    graded = 0
    verbatim = 0
    for case in _CASES:
        bank = _bank(case["shortname"])
        pid = case["passage_ref"]
        graded += 1
        if pid not in bank:
            continue
        text = str(bank[pid]["text"])
        if case["verbatim_span"] in text and case["draft_sentence"] in text:
            verbatim += 1
    assert graded >= 50
    assert verbatim == graded, f"{verbatim}/{graded} verbatim"


def test_b3_no_passage_topic_is_the_exact_miss():
    for case in _OUT["no_passage"]:
        assert teach_answer(case["query"], _page_for(case["shortname"])) == _MISS


def test_b3_student_audience_is_refused():
    for case in _OUT["student_audience"]:
        student_page = snapshot_from_page_context(
            page_context_from_snapshot({"audience": "student"}, _med520_home())
        )
        assert teach_answer(case["query"], student_page) is None


def test_b3_off_list_is_refused():
    for case in _OUT["off_list"]:
        snapshot = {
            "course": {
                "id": 1,
                "shortname": case["shortname"],
                "fullname": case["shortname"],
                "visible_to_user": True,
            },
            "sections": [],
        }
        assert teach_answer(case["query"], _page(snapshot)) is None


def test_b3_ungrounded_claim_is_dropped_not_fabricated():
    spec = _spec()
    for case in _OUT["ungrounded_claim"]:
        text = str(_load_course_bank("MED520")[case["passage_ref"]]["text"])
        assert case["fabricated_sentence"] not in text
        assert not ground_sentence(text, case["fabricated_sentence"])
        assert case["fabricated_sentence"] not in _grounded_spans(text, "alopecia", spec)
        assert case["fabricated_sentence"] not in lesson_draft("alopecia", _page_for("MED520"))


def test_b3_full_drafts_emit_only_grounded_sentences():
    for shortname, topic in (("MED520", "alopecia"), ("MED213", "alcohol"), ("NMD3101", "immunology")):
        reply = lesson_draft(topic, _page_for(shortname))
        bank = _bank(shortname)
        saw = False
        current = None
        for line in reply.splitlines():
            if line in bank:
                current = line
            elif line.startswith("- ") and current is not None:
                saw = True
                assert line[2:] in str(bank[current]["text"])
        assert saw, f"no grounded sentence for {shortname}/{topic}"
