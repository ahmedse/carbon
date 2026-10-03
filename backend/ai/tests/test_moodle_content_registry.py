"""Lock the read-only content-format registry with no behavior change.

These tests pin the dispatcher (one reader per format), the exact per-format
row counts, and the honesty invariants: every raw bank row lands in exactly one
format, the total is not vacuous, and an unclassified row is a bug. They also
prove the module is inert: Django-free, not imported by a turn path, and leaving
the bank and gold bytes untouched.

No count here is a claim about a rung. The registry names readers; it adds no
OCR, no network, no vector store, and no graph.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ai.moodle_content_registry import (
    BY_ID,
    READERS,
    YIELDS,
    format_for_extension,
    join_techniques,
    matrix,
    summary,
    totals,
    unclassified_rows,
)

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent

#: The exact committed-bank matrix (Deliverable 1). A deliberate bank change
#: must update this lock; a silent drift must fail.
_EXPECTED = {
    "pdf": (318, 317),
    "pptx": (166, 166),
    "pptm": (1, 1),
    "ppsx": (2, 2),
    "ppt": (18, 9),
    "docx": (57, 57),
    "media": (4, 0),
    "page": (59, 58),
    "label": (80, 80),
    "section": (9, 9),
    "moodle_intro": (269, 269),
    "google_slides": (99, 92),
    "google_docs": (7, 3),
    "google_drive": (28, 27),
    "docs_link": (35, 0),
    "youtube": (78, 61),
}

#: The seven narrow reader functions the registry names (S0).
_READER_FUNCTIONS = {
    "scripts/ingest_aast_med_external.py::_pdf_text",
    "scripts/ingest_aast_med_external.py::_office_text",
    "scripts/ingest_aast_med_external.py::_legacy_ppt_text",
    "scripts/ingest_aast_med_external.py::google_presentation",
    "scripts/ingest_aast_med_external.py::google_document",
    "scripts/ingest_aast_med_external.py::google_file",
    "scripts/ingest_aast_med_external.py::youtube_caption",
}


def test_every_format_is_registered_once_with_a_valid_shape():
    ids = [fmt.format_id for fmt in READERS]
    assert len(ids) == len(set(ids))
    for fmt in READERS:
        assert fmt.yields in YIELDS, fmt.format_id
        assert isinstance(fmt.routed, bool)
        if fmt.yields != "text":
            assert fmt.citable is False, fmt.format_id


def test_matrix_covers_every_registered_format_in_order():
    assert [row.format_id for row in matrix()] == [fmt.format_id for fmt in READERS]


def test_every_raw_row_lands_in_exactly_one_format():
    assert unclassified_rows() == []
    rows = matrix()
    assert sum(row.total for row in rows) == summary()["raw_rows"]
    for row in rows:
        assert 0 <= row.with_text <= row.total, row.format_id


def test_the_matrix_matches_the_committed_bank_lock():
    seen = {row.format_id: (row.total, row.with_text) for row in matrix() if row.total}
    assert seen == _EXPECTED
    assert totals() == {name: total for name, (total, _text) in _EXPECTED.items()}


def test_summary_is_derived_and_names_seven_readers():
    data = summary()
    assert data["raw_rows"] == 1230
    assert data["rows_with_text"] == 1151
    assert data["citable_rows"] == 882
    assert data["reader_functions"] == 7


def test_reader_functions_are_the_seven_narrow_extractors():
    named = {row.reader for row in matrix() if row.reader in _READER_FUNCTIONS}
    assert named == _READER_FUNCTIONS


def test_citable_rule_is_text_only():
    for row in matrix():
        if row.yields == "text" and row.citable:
            assert row.citable_rows == row.with_text, row.format_id
        else:
            assert row.citable_rows == 0, row.format_id


def test_no_reader_formats_are_explicit_not_silent():
    # An image, an arbitrary web page, an HTML file, a folder, and a
    # docs.google.com link with no id have no reader and no citable text.
    for format_id in ("image", "web", "html", "folder", "docs_link", "moodle_intro"):
        assert BY_ID[format_id].reader == "none", format_id
        assert BY_ID[format_id].citable is False, format_id
    # The scanned-PDF gap is real: exactly one pdf row has no text.
    pdf = BY_ID["pdf"]
    assert pdf.reader.endswith("::_pdf_text") and pdf.citable
    row = next(r for r in matrix() if r.format_id == "pdf")
    assert row.total - row.with_text == 1


def test_ppsx_reader_is_now_routed_by_the_dispatcher():
    # The ingest gap is closed: the shared content-engine registry routes
    # .ppsx to the office reader, so the dispatcher accepts it.
    ppsx = BY_ID["ppsx"]
    assert ppsx.reader.endswith("::_office_text")
    assert ppsx.routed is True
    row = next(r for r in matrix() if r.format_id == "ppsx")
    assert row.with_text == row.total == 2


def test_media_has_a_status_not_a_body():
    media = next(r for r in matrix() if r.format_id == "media")
    assert media.with_text == 0
    assert media.citable is False


def test_extension_dispatch_is_total():
    assert format_for_extension(".pdf") == "pdf"
    assert format_for_extension("PDF") == "pdf"
    assert format_for_extension(".pptx") == "pptx"
    assert format_for_extension(".png") == "image"
    assert format_for_extension(".txt") == "extra"
    assert format_for_extension(".nope") == "unclassified"
    assert format_for_extension("") == "unclassified"


def test_join_view_matches_the_gap_reporter():
    join = join_techniques()
    assert sum(join.values()) == 74
    assert join == {
        "external_web": 40,
        "remote_youtube": 17,
        "remote_google": 12,
        "media": 4,
        "scanned_pdf": 1,
    }


def test_the_report_is_deterministic():
    assert matrix() == matrix()
    assert summary() == summary()
    assert join_techniques() == join_techniques()


def test_report_leaves_the_bank_and_gold_untouched():
    watched = [
        REPO / "domain_packs" / "aast-med" / "bank" / "course-meat-13" / "MED5310.jsonl",
        REPO / "domain_packs" / "aast-med" / "bank" / "course-ext-13" / "MED213.jsonl",
        REPO / "domain_packs" / "aast-med" / "gold" / "l5.yaml",
    ]
    before = {path: path.read_bytes() for path in watched}
    matrix()
    join_techniques()
    unclassified_rows()
    totals()
    for path, blob in before.items():
        assert path.read_bytes() == blob, path


def test_module_is_not_imported_by_a_turn_path():
    seams = [
        BACKEND / "ai" / "moodle_host.py",
        BACKEND / "ai" / "moodle_page.py",
        BACKEND / "ai" / "moodle_host_api.py",
        BACKEND / "ai" / "moodle_bank.py",
        BACKEND / "ai" / "moodle_integrity.py",
        BACKEND / "ai" / "moodle_refusals.py",
        BACKEND / "ai" / "moodle_onboarding.py",
    ]
    for path in seams:
        assert "moodle_content_registry" not in path.read_text(encoding="utf-8"), path
    for path in (BACKEND / "ai" / "engine").rglob("*.py"):
        assert "moodle_content_registry" not in path.read_text(encoding="utf-8"), path


def test_module_is_django_free():
    code = (
        "import sys, ai.moodle_content_registry as r; "
        "r.matrix(); r.summary(); "
        "assert 'django' not in sys.modules, 'content registry pulled Django in'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
