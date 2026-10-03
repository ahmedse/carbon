"""WS-7: the topic door degrades SAFELY when the keyword index is ABSENT.

The topic-index fallback is recall-only. With no ``<course>.jsonl`` on disk the
door must return its EXACT miss sentence and raise nothing — never a traceback.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ai.moodle_bank import cite_topic_index, cite_topic_index_windowed
from ai.moodle_host import door_answer

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "retrieval-b3.yaml").read_text(encoding="utf-8"))
_MISS = _GOLD["miss"]
# A genuine R0 title-door miss that the committed index DOES answer.
_CASE = _GOLD["cases"][0]


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


def test_index_fallbacks_return_none_when_index_absent(tmp_path):
    bank = {
        f"{_CASE['shortname']}:file:{_CASE['open_activity']}:x.txt": {
            "id": f"{_CASE['shortname']}:file:{_CASE['open_activity']}:x.txt",
            "course": _CASE["shortname"],
            "kind": "file",
            "activity_id": int(_CASE["open_activity"]),
            "name": "x.txt",
            "text": "unrelated content that holds no query term",
            "world": "w",
        }
    }
    # No <course>.jsonl under tmp_path -> both fallbacks are a clean None.
    assert cite_topic_index(
        _CASE["query"], bank, course=_CASE["shortname"],
        activity_id=int(_CASE["open_activity"]), world="w", index_root=tmp_path,
    ) is None
    assert cite_topic_index_windowed(
        _CASE["query"], bank, course=_CASE["shortname"],
        activity_id=int(_CASE["open_activity"]), world="w", index_root=tmp_path,
    ) is None


def test_topic_door_returns_exact_miss_when_index_absent(tmp_path, monkeypatch):
    page = _page(_CASE)
    # Sanity: with the committed index present this R0 miss is answered.
    assert door_answer(_CASE["query"], page) != _MISS

    import ai.moodle_bank as moodle_bank

    # Point the door at an empty root: the index file simply is not there.
    monkeypatch.setattr(moodle_bank, "_INDEX", tmp_path)
    got = door_answer(_CASE["query"], page)
    assert got == _MISS
