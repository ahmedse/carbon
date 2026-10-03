"""B3 retrieval gold (L-R R1) — the keyword index wired behind a title-door miss.

The gold ``domain_packs/aast-med/gold/retrieval-b3.yaml`` is authored first
(TEACHING-WAVE-SPEC §1.2 / §1.6). Each case is a REAL question whose R0
whole-file title/body door returns the exact course miss, while exactly ONE
committed index chunk row answers it with a verbatim span.

This file locks:

* every gold case is a genuine R0 miss (``_topic_rows`` returns no row) and the
  R1 door answers it with the expected passage ref and a verbatim span;
* recall ≥ 0.90 and precision = 1.00 (0 fabricated spans, 0 non-unique);
* a miss still returns the exact course miss sentence;
* a non-unique hit is never emitted as a cite.

No existing golden is read or edited here.
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
from ai.moodle_host import door_answer
from ai.moodle_page import _topic_rows

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "retrieval-b3.yaml").read_text(encoding="utf-8"))
_CASES = _GOLD["cases"]
_MISS = _GOLD["miss"]


def _bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _page(case: dict) -> dict:
    return {
        "audience": "staff",
        "enrolled": True,
        "course": {
            "id": 1,
            "shortname": case["shortname"],
            "fullname": case["shortname"],
            "visible_to_user": True,
        },
        "sections": [],
        "activity": {"cmid": int(case["open_activity"]), "name": ""},
    }


def _topic(query: str) -> str:
    text = " ".join(query.casefold().split())
    return text.split("what is ", 1)[1] if "what is " in text else text


def _cite(reply: str) -> tuple[str, str]:
    """(passage id, span) from the topic door reply shape: head / id / span."""
    lines = reply.splitlines()
    assert len(lines) >= 3, f"short reply: {reply!r}"
    return lines[1], lines[2]


def test_gold_shape_and_coverage():
    assert len(_CASES) >= 40
    assert len({c["shortname"] for c in _CASES}) == 13
    for case in _CASES:
        for key in ("shortname", "open_activity", "query", "expected_passage_ref", "expected_span"):
            assert case.get(key) not in (None, ""), key


@pytest.mark.parametrize("case", _CASES, ids=[f"{c['shortname']}-{i}" for i, c in enumerate(_CASES)])
def test_retrieval_b3_case(case: dict):
    shortname = case["shortname"]
    bank = _bank(shortname)
    page = _page(case)

    # R0 is a genuine title-door miss: no title hit and no whole-file body hit.
    assert _topic_rows(bank, _topic(case["query"]), page=page)[0] == []

    reply = door_answer(case["query"], page)
    assert reply != _MISS, "R0 title door did not miss"
    pid, span = _cite(reply)

    # R1: unique passage, verbatim span, resolving in the bank for the open activity.
    assert pid == case["expected_passage_ref"]
    assert pid in bank
    assert int(bank[pid]["activity_id"]) == int(case["open_activity"])
    assert span and span in str(bank[pid]["text"])
    assert case["expected_span"] in str(bank[pid]["text"])


def test_recall_and_precision_meet_thresholds():
    correct = 0
    for case in _CASES:
        bank = _bank(case["shortname"])
        reply = door_answer(case["query"], _page(case))
        if reply == _MISS:
            continue
        pid, span = _cite(reply)
        if (
            pid == case["expected_passage_ref"]
            and pid in bank
            and span
            and span in str(bank[pid]["text"])
            and case["expected_span"] in str(bank[pid]["text"])
        ):
            correct += 1
    recall = correct / len(_CASES)
    assert len(_CASES) >= 40
    assert recall >= 0.90, f"recall {recall:.3f} ({correct}/{len(_CASES)})"
    assert correct == len(_CASES), f"precision < 1.00 ({correct}/{len(_CASES)})"


def test_miss_is_the_exact_course_sentence():
    page = _page({"shortname": "MED213", "open_activity": 859})
    assert door_answer("what is zzzq neverterm xxq", page) == _MISS


def test_non_unique_hit_is_never_emitted(tmp_path):
    """Two passages tie for the top keyword score => no cite (unique rule holds)."""
    from ai.content_engine.index import save_index
    from ai.moodle_bank import cite_topic_index

    course = "SYN1000"
    activity = 7
    text_a = "The aardvark forages at night and returns to its burrow before dawn."
    text_b = "The buffalo migrates across the grassland during the dry season."
    rows = {
        f"{course}:file:{activity}:a.txt": text_a,
        f"{course}:file:{activity}:b.txt": text_b,
    }
    bank = {
        pid: {"id": pid, "activity_id": activity, "world": "w", "text": text}
        for pid, text in rows.items()
    }
    chunks = [
        {
            "chunk_id": f"{course}:{activity}:file:{pid}:0",
            "source_ref": pid,
            "course": course,
            "activity_ref": str(activity),
            "locator": pid,
            "text": text,
        }
        for pid, text in rows.items()
    ]
    save_index(str(tmp_path / f"{course}.jsonl"), chunks)

    # Ambiguous: one term in each passage => a tie => None (never a cite).
    assert cite_topic_index(
        "aardvark buffalo", bank,
        course=course, activity_id=activity, world="w", index_root=tmp_path,
    ) is None
    # Unique: only one passage answers => that passage id.
    cite = cite_topic_index(
        "aardvark", bank,
        course=course, activity_id=activity, world="w", index_root=tmp_path,
    )
    assert cite is not None
    assert cite[0] == f"{course}:file:{activity}:a.txt"
    assert cite[1] in text_a
