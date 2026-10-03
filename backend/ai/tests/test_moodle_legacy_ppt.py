"""Lock the legacy .ppt recovery path against the bank loader.

The extraction-gap report counted nine unread legacy ``.ppt`` resources with no
local reader. The recovery reads their text directly (OLE2 text atoms) and
appends a filled passage row; the empty placeholder row is never rewritten.
These tests pin the honesty rules that make that safe:

* a legacy ``.ppt`` row whose stored text exists reads loaded;
* a legacy ``.ppt`` row with no text stays unread (the loader drops it);
* an already-owned ref is never duplicated, and re-running the writer is a
  no-op.

They are pure-loader tests: no Docker, no host, no network.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from ai.moodle_bank import load_c4_files
from ai.moodle_extraction_gap import technique_for

REPO = Path(__file__).resolve().parents[3]
_SCRIPT = REPO / "scripts" / "ingest_aast_med_local_files.py"


def _row(**over) -> dict:
    base = {
        "course": "NMD2101",
        "sectionnum": 1,
        "section": "PBL 1",
        "visible": True,
        "kind": "file",
        "name": "Deck",
        "ref": "file:Deck.ppt",
        "text": "",
    }
    base.update(over)
    return base


def _key(**over) -> dict:
    base = {
        "course": "NMD2101",
        "cmid": 422,
        "sectionnum": 1,
        "kind": "file",
        "name": "Deck",
        "ref": "file:Deck.ppt",
    }
    base.update(over)
    return base


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def _legacy_module():
    spec = importlib.util.spec_from_file_location("ingest_local_under_test", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_ppt_row_with_extracted_text_reads_loaded(tmp_path: Path):
    meat, keys = tmp_path / "meat", tmp_path / "keys"
    meat.mkdir(), keys.mkdir()
    body = "Anatomy of vertebrae and spinal cord with clinical correlations for the lecture."
    _write(meat / "NMD2101.jsonl", [_row(text=body)])
    _write(keys / "NMD2101.jsonl", [_key()])
    bank = load_c4_files("NMD2101", meat_root=meat, keys_root=keys)
    assert len(bank) == 1
    row = next(iter(bank.values()))
    assert row["kind"] == "file"
    assert row["text"] == body
    assert row["activity_id"] == 422


def test_legacy_ppt_row_without_text_reads_unread(tmp_path: Path):
    meat, keys = tmp_path / "meat", tmp_path / "keys"
    meat.mkdir(), keys.mkdir()
    _write(meat / "NMD2101.jsonl", [_row(text="")])
    _write(keys / "NMD2101.jsonl", [_key()])
    assert load_c4_files("NMD2101", meat_root=meat, keys_root=keys) == {}
    # the classifier still counts the row as a legacy_ppt gap
    assert technique_for({"kind": "file", "name": "Deck.ppt", "source": "Deck.ppt"}) == "legacy_ppt"


def test_append_writer_never_duplicates_an_owned_ref(tmp_path: Path, monkeypatch):
    module = _legacy_module()
    pack, gold = tmp_path / "meat", tmp_path / "gold"
    pack.mkdir(), gold.mkdir()
    owned = _row(ref="file:Owned.ppt", text="An already owned passage body that is long enough.")
    placeholder = _row(ref="file:New.ppt", name="New Deck", text="")
    _write(pack / "NMD2101.jsonl", [owned, placeholder])
    monkeypatch.setattr(module, "_PACK", pack)
    monkeypatch.setattr(module, "_GOLD", gold)

    new_body = "A brand new passage body that is long enough to be stored once."
    written, reasons = module._append_course(
        "NMD2101",
        {"file:Owned.ppt": "A replacement body the writer must ignore.", "file:New.ppt": new_body},
    )
    assert written == 1
    assert any(reason.endswith(":already_owned") for reason in reasons)

    rows = [
        json.loads(line)
        for line in (pack / "NMD2101.jsonl").read_text(encoding="utf-8").splitlines()
        if line.startswith("{")
    ]
    owned_rows = [r for r in rows if r["ref"] == "file:Owned.ppt" and str(r["text"]).strip()]
    assert len(owned_rows) == 1  # the placeholder was appended to, never rewritten
    assert owned_rows[0]["text"] == owned["text"]
    new_rows = [r for r in rows if r["ref"] == "file:New.ppt" and str(r["text"]).strip()]
    assert [r["text"] for r in new_rows] == [new_body]

    # Re-running once the ref is owned is a no-op.
    written_again, _ = module._append_course("NMD2101", {"file:New.ppt": new_body})
    assert written_again == 0


def test_recovered_legacy_ppt_refs_read_loaded_in_the_real_bank():
    recovered = {
        "NMD2101": (
            "file:Anatomical terms.ppt",
            "file:L 2 for upload Understanding CNS functionsppt.ppt",
            "file:L 4 Anterior triangle.ppt",
            "file:L 6 anatomy of vertebral colomn and spinal corfd Lecture Power point.ppt",
            "file:this one L 20 memory (2).ppt",
            "file:this one L 20 memory.ppt",
        ),
        "NMD4201": (
            "file:CARCINOMA OF BREAST 6TH YR STUDENTS.ppt",
            "file:preoperative assessment and premedication ASA.ppt",
        ),
        "MED520": ("file:8 november.ppt",),
    }
    for shortname, refs in recovered.items():
        bank = load_c4_files(shortname)
        sources = {str(row.get("source") or "") for row in bank.values()}
        for ref in refs:
            assert ref in sources, (shortname, ref)
