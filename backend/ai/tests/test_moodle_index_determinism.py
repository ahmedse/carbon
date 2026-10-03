"""WS-7: the committed aast-med keyword index is a reproducible build artifact.

The topic door READS ``domain_packs/aast-med/index/<shortname>.jsonl`` at answer
time. This locks that a rebuild from the SAME pack bank is byte-identical and
that the committed bytes equal a fresh build, so regeneration by the staff Index
job is safe and cannot silently drift from the vendored artifact.
"""
from __future__ import annotations

from pathlib import Path

from ai.content_engine.ingest import build_course_index
from ai.moodle_bank import listed_shortnames

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_INDEX = _PACK / "index"

# Smallest committed course keeps the real-bank double build fast while still
# exercising the full bank -> chunker -> save_index path.
_COURSE = "MED5310"


def test_committed_index_file_exists_for_every_listed_course():
    for shortname in listed_shortnames():
        assert (_INDEX / f"{shortname}.jsonl").is_file(), shortname


def test_pack_index_rebuild_is_byte_identical_and_matches_committed(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    build_course_index(_COURSE, index_root=a)
    build_course_index(_COURSE, index_root=b)
    built_a = (a / f"{_COURSE}.jsonl").read_bytes()
    built_b = (b / f"{_COURSE}.jsonl").read_bytes()
    assert built_a == built_b, "index build is not deterministic"
    committed = (_INDEX / f"{_COURSE}.jsonl").read_bytes()
    assert built_a == committed, (
        "committed index is stale vs a fresh build; regenerate it with the "
        "staff Index job (run_index(..., {'build': ['index']}))"
    )
