"""WS-7: the packed keyword index must be a DETERMINISTIC build artifact.

The topic door reads ``domain_packs/aast-med/index/<shortname>.jsonl`` at
answer time, so two builds from the SAME pack bank must be BYTE-IDENTICAL:
the same chunk ids in the same order and the same postings. This file locks
that with a fast synthetic bank (no pack, no Django), exercising the full
``ingest.build_course_index`` -> ``chunk_units`` -> ``index.save_index`` path.
"""
from __future__ import annotations

import json

from ai.content_engine.index import load_index
from ai.content_engine.ingest import build_course_index

_COURSE = "DET101"


def _bank() -> dict[str, dict]:
    """A small bank in a deliberately NON-alphabetical insertion order.

    Determinism means "same input -> same bytes", not "sorted", so the exact
    insertion order below must reproduce the exact same artifact every time.
    """
    rows = {
        "d2": "The heart pumps blood through arteries and veins during systole.",
        "a1": "Cell division produces two identical daughter cells in mitosis.",
        "c3": "Photosynthesis converts light energy into chemical energy in plants.",
        "b2": "The Krebs cycle oxidises acetyl coenzyme A inside mitochondria.",
        "e4": "Osmoregulation balances water and salts along the kidney nephron.",
    }
    return {
        f"{_COURSE}:file:{100 + i}:{name}.txt": {
            "id": f"{_COURSE}:file:{100 + i}:{name}.txt",
            "course": _COURSE,
            "kind": "file",
            "activity_id": 100 + i,
            "name": f"{name}.txt",
            "text": text,
            "world": "det",
        }
        for i, (name, text) in enumerate(rows.items())
    }


def test_index_build_is_byte_identical_twice(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_course_index(_COURSE, index_root=first, bank=_bank())
    build_course_index(_COURSE, index_root=second, bank=_bank())
    assert (first / f"{_COURSE}.jsonl").read_bytes() == (
        second / f"{_COURSE}.jsonl"
    ).read_bytes()


def test_index_rebuild_over_same_path_is_idempotent(tmp_path):
    path = tmp_path / f"{_COURSE}.jsonl"
    build_course_index(_COURSE, index_root=tmp_path, bank=_bank())
    before = path.read_bytes()
    build_course_index(_COURSE, index_root=tmp_path, bank=_bank())
    assert path.read_bytes() == before


def test_chunk_ids_and_postings_are_stable_and_ordered(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_course_index(_COURSE, index_root=first, bank=_bank())
    build_course_index(_COURSE, index_root=second, bank=_bank())
    ia = load_index(str(first / f"{_COURSE}.jsonl"))
    ib = load_index(str(second / f"{_COURSE}.jsonl"))
    # Same chunk ids in the same retrieval order, and identical postings.
    assert [c["chunk_id"] for c in ia.chunks] == [c["chunk_id"] for c in ib.chunks]
    assert ia.postings == ib.postings
    # Posting lines are written in sorted-term order (not hash/insertion order).
    lines = (first / f"{_COURSE}.jsonl").read_text(encoding="utf-8").splitlines()
    terms = [json.loads(ln)["term"] for ln in lines if json.loads(ln).get("type") == "posting"]
    assert terms == sorted(terms)
