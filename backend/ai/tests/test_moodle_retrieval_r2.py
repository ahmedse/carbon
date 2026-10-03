"""B3 retrieval gold, R2 rung (L-R R2) — hybrid keyword + overlap windows.

``domain_packs/aast-med/gold/retrieval-r2.yaml`` is the ADDITIVE R2 gold. Each
case is a real question whose

* R0 whole-file title/body door misses (the topic phrase is not a title and not
  a contiguous body phrase), and
* R1 rule — the single-chunk unique top score over the ``DEFAULT_K`` retrieval
  window only (``cite_topic_index(..., allow_window=False)``) — has no in-scope
  winner, and
* R2 rule — the same query with the adjacent-chunk overlap window enabled
  (``cite_topic_index(..., allow_window=True)``) — resolves to exactly ONE
  passage with a verbatim span of that passage's stored text.

The test proves the R2 gold *fails at R1 and passes at R2* and re-locks that the
R1 gold ``retrieval-b3.yaml`` is still fully answered (100% recall, precision
1.00). No existing golden is read for mutation or edited.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai.moodle_bank import (
    cite_topic_index,
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
    listed_world,
)
from ai.moodle_host import door_answer
from ai.moodle_page import _topic_rows

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "retrieval-r2.yaml").read_text(encoding="utf-8"))
_CASES = _GOLD["cases"]
_MISS = _GOLD["miss"]
_B3 = yaml.safe_load((_PACK / "gold" / "retrieval-b3.yaml").read_text(encoding="utf-8"))
_B3_CASES = _B3["cases"]


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


def test_r2_gold_shape_and_thresholds():
    assert len(_CASES) >= 6
    assert _GOLD["thresholds"]["recall_min"] >= 0.95
    assert _GOLD["thresholds"]["precision"] == 1.0
    for case in _CASES:
        for key in ("shortname", "open_activity", "query", "expected_passage_ref", "expected_span"):
            assert case.get(key) not in (None, ""), key


@pytest.mark.parametrize("case", _CASES, ids=[f"{c['shortname']}-{i}" for i, c in enumerate(_CASES)])
def test_r2_case_passes_at_r2_and_fails_at_r1(case: dict):
    shortname = case["shortname"]
    bank = _bank(shortname)
    activity = int(case["open_activity"])
    world = listed_world(shortname)
    page = _page(case)

    # R0 is a genuine title/body miss.
    assert _topic_rows(bank, _topic(case["query"]), page=page)[0] == []

    # R1 (single-chunk, top DEFAULT_K only) has no in-scope winner => miss.
    assert (
        cite_topic_index(
            _topic(case["query"]), bank, course=shortname,
            activity_id=activity, world=world, allow_window=False,
        )
        is None
    )

    # R2 (adjacent-chunk overlap window) resolves a unique passage.
    r2 = cite_topic_index(
        _topic(case["query"]), bank, course=shortname,
        activity_id=activity, world=world, allow_window=True,
    )
    assert r2 is not None, "R2 must answer an R2 gold case"
    pid, span = r2
    assert pid == case["expected_passage_ref"]
    assert pid in bank
    assert int(bank[pid]["activity_id"]) == activity
    assert span and span in str(bank[pid]["text"])

    # The door emits that cite (verbatim, unique) and still keeps the exact
    # miss for anything it cannot resolve.
    reply = door_answer(case["query"], page)
    assert reply != _MISS
    head, did, dspan = reply.splitlines()[:3]
    assert did == pid
    assert dspan in str(bank[pid]["text"])


def test_r2_recall_and_precision_are_one():
    correct = 0
    for case in _CASES:
        bank = _bank(case["shortname"])
        r2 = cite_topic_index(
            _topic(case["query"]), bank, course=case["shortname"],
            activity_id=int(case["open_activity"]), world=listed_world(case["shortname"]),
            allow_window=True,
        )
        if r2 is None:
            continue
        pid, span = r2
        if (
            pid == case["expected_passage_ref"]
            and pid in bank
            and span
            and span in str(bank[pid]["text"])
        ):
            correct += 1
    recall = correct / len(_CASES)
    assert recall >= 0.95, f"recall {recall:.3f} ({correct}/{len(_CASES)})"
    assert correct == len(_CASES), f"precision < 1.00 ({correct}/{len(_CASES)})"


def test_r2_is_additive_and_r1_gold_still_full():
    """R1's retrieval-b3 gold keeps 65/65 recall under the production door."""
    correct = 0
    for case in _B3_CASES:
        bank = _bank(case["shortname"])
        reply = door_answer(case["query"], _page(case))
        if reply == _MISS:
            continue
        pid, span = reply.splitlines()[1:3]
        if (
            pid == case["expected_passage_ref"]
            and pid in bank
            and span in str(bank[pid]["text"])
        ):
            correct += 1
    assert correct == len(_B3_CASES), f"B3 gold regressed: {correct}/{len(_B3_CASES)}"
