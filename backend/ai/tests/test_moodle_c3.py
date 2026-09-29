"""C3: NMD1103 page, label, and book text is stored under its activity id."""
import json
from pathlib import Path

import yaml

from ai.moodle_bank import cite, load_c3, passages_for, retrieve

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c3.yaml"

_BANK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "bank" / "course-meat-13"
_NMD1103 = _BANK / "NMD1103.jsonl"


def _export_c3(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") in {"page", "label", "book"} and str(row.get("text") or "").strip():
            rows.append(row)
    return rows


def test_every_nmd1103_page_label_and_book_is_stored_verbatim():
    export = _export_c3(_NMD1103)
    assert export, "NMD1103 export has no page, label, or book text"
    bank = load_c3("NMD1103")
    assert len(bank) == len(export)
    for row in export:
        activity = int(str(row["ref"]).split(":", 1)[1])
        found = passages_for("NMD1103", activity, bank)
        assert len(found) == 1
        assert found[0]["text"] == str(row["text"]).strip()
        assert found[0]["course"] == "NMD1103"
        assert "MED213" not in found[0]["id"]


def test_every_listed_course_keeps_its_own_pages():
    for path in sorted(_BANK.glob("*.jsonl")):
        export = _export_c3(path)
        bank = load_c3(path.stem)
        assert len(bank) == len(export)
        assert all(row["course"] == path.stem for row in bank.values())


def test_nmd1103_matches_the_frozen_gold():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = load_c3(gold["course"])
    assert sorted(bank) == sorted(gold["passages"])
    assert len(bank) == gold["count"]
    assert retrieve(gold["course"], 1008, bank) == ["NMD1103:page:1008"]
    assert retrieve(gold["course"], 999999, bank) == []
    assert cite(gold["course"], 999999, bank) == gold["miss"]


def test_a_file_or_another_course_is_not_a_c3_hit():
    bank = load_c3("NMD1103")
    assert all(row["kind"] in {"page", "label", "book"} for row in bank.values())
    assert passages_for("MED213", 1008, bank) == []
