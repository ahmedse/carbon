"""C4-file: four NMD1103 resources are stored under their activity id."""
import json
from pathlib import Path

import yaml

from ai.moodle_bank import load_c4_files

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c4.yaml"
_MEAT = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-meat-13" / "NMD1103.jsonl"


def test_four_nmd1103_files_match_the_export():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = load_c4_files(gold["course"])
    assert len(gold["passages"]) == gold["count"]
    for pid in gold["passages"]:
        assert pid in bank
        row = bank[pid]
        assert row["course"] == "NMD1103"
        assert row["text"]
        filename = pid.rsplit(":", 1)[-1]
        assert len(row["text"]) > len(filename)
        meat = _meat_text(row["source"])
        assert row["text"] == meat
        assert "MED213" not in row["id"]


def test_google_intros_and_unlinked_ids_are_absent():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = load_c4_files(gold["course"])
    sources = {row["source"] for row in bank.values()}
    ids = set(bank)
    for source in gold["drive_refs_not_passages"] + gold["absent"]:
        assert source not in sources
        assert all(source not in pid for pid in ids)
    assert all(row["kind"] == "file" for row in bank.values())


def test_a_course_without_keys_has_no_file_passages():
    assert load_c4_files("MED213") == {}


def _meat_text(ref: str) -> str:
    for line in _MEAT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        if row.get("ref") == ref and row.get("kind") == "file":
            return str(row.get("text") or "").strip()
    raise AssertionError(ref)
