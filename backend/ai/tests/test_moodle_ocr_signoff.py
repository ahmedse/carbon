"""Arabic OCR sign-off mechanism locks.

The mechanism is the deliverable; the actual human sign-off is BY-REAL-WORLD and
must never be faked. These tests prove: unsigned Arabic stays non-citable; a
recorded sign-off (fixture) flips ONLY the signed passage ids; a sign-off cannot
cross to different text or a different course; and the staff Index job consumes
the record to expose the citable set.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ai import moodle_content_job as job

_ARABIC = "إجازة مرضية معتمدة"


def _pending_row(ref: str = "file:scan.pdf", locator: str = "page 1", text: str = _ARABIC) -> dict:
    return {"filename": "scan.pdf", "ref": ref, "locator": locator, "text": text, "signoff": "arabic"}


def _write_pending(tmp_path: Path, rows: list[dict], shortname: str = "MED5310") -> None:
    stored = job.record_ocr_pending(shortname, rows, root=tmp_path / "ocr")
    assert stored == len(rows)


def _pid(shortname: str, row: dict) -> str:
    return job.ocr_passage_id(shortname, row)


# ── unsigned stays non-citable ───────────────────────────────────────────────


def test_unsigned_arabic_stays_non_citable(tmp_path):
    row = _pending_row()
    _write_pending(tmp_path, [row])
    rows = job.signed_ocr_rows("MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff")
    assert len(rows) == 1
    assert rows[0]["citable"] is False
    assert rows[0]["status"] == "pending_signoff"
    status = job.ocr_signoff_status(
        "MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
    )
    assert status == {
        "course": "MED5310",
        "pending": 1,
        "signed_off": 0,
        "citable_passage_ids": [],
    }


# ── a recorded sign-off flips ONLY the signed ids ────────────────────────────


def test_recorded_signoff_makes_only_signed_ids_citable(tmp_path):
    one = _pending_row(ref="file:a.pdf", locator="page 1")
    two = _pending_row(ref="file:a.pdf", locator="page 2", text="نص عربي آخر تماما")
    _write_pending(tmp_path, [one, two])
    signed_id = _pid("MED5310", one)
    other_id = _pid("MED5310", two)

    out = job.record_ocr_signoff(
        "MED5310",
        passage_ids=[signed_id],
        source_doc="MED5310 scanned handout v1",
        who="reviewer.med",
        when="2026-10-03T00:00:00+00:00",
        root=tmp_path / "signoff",
        pending_root=tmp_path / "ocr",
    )
    assert out["ok"] is True and out["recorded"] == 1 and out["unknown"] == []

    rows = {
        r["passage_id"]: r
        for r in job.signed_ocr_rows(
            "MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
        )
    }
    assert rows[signed_id]["citable"] is True
    assert rows[signed_id]["status"] == "signed_off"
    assert rows[signed_id]["signoff_ref"]["who"] == "reviewer.med"
    # No cross-contamination: the second passage stays non-citable.
    assert rows[other_id]["citable"] is False
    assert rows[other_id]["status"] == "pending_signoff"

    status = job.ocr_signoff_status(
        "MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
    )
    assert status["signed_off"] == 1
    assert status["pending"] == 1
    assert status["citable_passage_ids"] == [signed_id]


def test_signoff_does_not_cross_courses(tmp_path):
    row = _pending_row()
    _write_pending(tmp_path, [row], shortname="MED5310")
    _write_pending(tmp_path, [row], shortname="MED520")
    pid_5310 = _pid("MED5310", row)
    out = job.record_ocr_signoff(
        "MED5310",
        passage_ids=[pid_5310],
        source_doc="MED5310 doc",
        who="reviewer.med",
        root=tmp_path / "signoff",
        pending_root=tmp_path / "ocr",
    )
    assert out["recorded"] == 1

    med520 = job.signed_ocr_rows(
        "MED520", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
    )
    assert med520[0]["citable"] is False


def test_signoff_of_a_changed_quote_is_invalidated(tmp_path):
    row = _pending_row()
    _write_pending(tmp_path, [row])
    pid = _pid("MED5310", row)
    job.record_ocr_signoff(
        "MED5310",
        passage_ids=[pid],
        source_doc="MED5310 doc",
        who="reviewer.med",
        root=tmp_path / "signoff",
        pending_root=tmp_path / "ocr",
    )
    # The stored quote changes after sign-off: the digest no longer matches.
    _write_pending(tmp_path, [_pending_row(text="نص مختلف تماما الآن")])
    rows = job.signed_ocr_rows(
        "MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
    )
    assert rows[0]["citable"] is False
    assert rows[0]["status"] == "pending_signoff"


# ── explicit, auditable, no auto-sign ────────────────────────────────────────


def test_signoff_requires_who_and_source_and_ids(tmp_path):
    _write_pending(tmp_path, [_pending_row()])
    pid = _pid("MED5310", _pending_row())
    base = {"passage_ids": [pid], "source_doc": "doc", "who": "reviewer.med", "root": tmp_path / "signoff", "pending_root": tmp_path / "ocr"}

    assert job.record_ocr_signoff("MED5310", **{**base, "who": ""})["error"] == "missing_who"
    assert (
        job.record_ocr_signoff("MED5310", **{**base, "source_doc": ""})["error"]
        == "missing_source_doc"
    )
    assert (
        job.record_ocr_signoff("MED5310", **{**base, "passage_ids": []})["error"]
        == "missing_passage_ids"
    )
    assert job.record_ocr_signoff("NOT_A_COURSE", **base)["error"] == "off_list"


def test_signoff_unknown_id_is_reported_and_not_recorded(tmp_path):
    _write_pending(tmp_path, [_pending_row()])
    out = job.record_ocr_signoff(
        "MED5310",
        passage_ids=["MED5310:ocr:file:ghost.pdf:page 9"],
        source_doc="doc",
        who="reviewer.med",
        root=tmp_path / "signoff",
        pending_root=tmp_path / "ocr",
    )
    assert out["ok"] is True
    assert out["recorded"] == 0
    assert out["unknown"] == ["MED5310:ocr:file:ghost.pdf:page 9"]
    rows = job.signed_ocr_rows(
        "MED5310", pending_root=tmp_path / "ocr", signoff_root=tmp_path / "signoff"
    )
    assert rows[0]["citable"] is False


# ── the staff Index job consumes the record ──────────────────────────────────


def test_run_index_consumes_signoff_and_indexes_only_signed_text(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "_OCR_ROOT", tmp_path / "ocr")
    monkeypatch.setattr(job, "_OCR_SIGNOFF_ROOT", tmp_path / "signoff")
    monkeypatch.setattr(job, "_INDEX_ROOT", tmp_path / "index")
    monkeypatch.setattr(job, "_GRAPH_ROOT", tmp_path / "graph")

    one = _pending_row(ref="file:a.pdf", locator="page 1")
    two = _pending_row(ref="file:a.pdf", locator="page 2", text="نص غير موقّع")
    job.record_ocr_pending("MED5310", [one, two])
    job.record_ocr_signoff(
        "MED5310",
        passage_ids=[job.ocr_passage_id("MED5310", one)],
        source_doc="MED5310 scanned handout v1",
        who="reviewer.med",
    )

    result = job.run_index("MED5310", {"build": ["ocr", "index"]})
    assert result["ok"] is True
    assert result["ocr"]["signed_off"] == 1
    assert result["ocr"]["pending"] == 1
    assert result["ocr"]["citable_passage_ids"] == [job.ocr_passage_id("MED5310", one)]

    from ai.content_engine import index as ce_index

    loaded = ce_index.load_index(result["index"]["path"])
    all_text = "\n".join(c["text"] for c in loaded.chunks)
    assert _ARABIC in all_text
    assert "نص غير موقّع" not in all_text


def test_run_index_without_signoff_never_indexes_pending_arabic(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "_OCR_ROOT", tmp_path / "ocr")
    monkeypatch.setattr(job, "_OCR_SIGNOFF_ROOT", tmp_path / "signoff")
    monkeypatch.setattr(job, "_INDEX_ROOT", tmp_path / "index")
    job.record_ocr_pending("MED5310", [_pending_row()])

    result = job.run_index("MED5310", {"build": ["ocr", "index"]})
    assert result["ocr"]["signed_off"] == 0
    from ai.content_engine import index as ce_index

    loaded = ce_index.load_index(result["index"]["path"])
    assert _ARABIC not in "\n".join(c["text"] for c in loaded.chunks)
