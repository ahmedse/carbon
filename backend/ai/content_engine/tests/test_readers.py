"""Reader tests. Binary fixtures are generated, never committed.

Every test writes a tiny fixture into ``tmp_path`` and asserts the frozen
``ReaderResult`` / ``TextUnit`` shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.content_engine import ocr
from ai.content_engine.readers import registry

# Frozen field names.
_UNIT_FIELDS = {
    "text",
    "kind",
    "source_ref",
    "locator",
    "citable",
    "course",
    "activity_ref",
    "status",
}
_RESULT_FIELDS = {"units", "status", "reader", "error"}


def _check_result(result: dict) -> dict:
    assert set(result) == _RESULT_FIELDS, result
    assert result["status"] in {"ok", "empty", "unreadable", "no_runtime"}, result
    for unit in result["units"]:
        assert set(unit) == _UNIT_FIELDS, unit
    return result


# --- text family ----------------------------------------------------------


def test_txt_read_citable(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("First sentence. Second sentence.\nThird line.", encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), "text/plain"))
    assert result["status"] == "ok"
    assert result["reader"] == "text"
    unit = result["units"][0]
    assert unit["kind"] == "txt"
    assert unit["citable"] is True
    assert "First sentence." in unit["text"]
    assert unit["locator"] == "n/a"


def test_md_read(tmp_path: Path) -> None:
    path = tmp_path / "readme.md"
    path.write_text("# Title\n\nA paragraph.", encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "ok"
    assert result["units"][0]["kind"] == "md"


def test_json_stringifies_leaves_keeping_structure(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{"a": "alpha", "nested": {"list": ["x", "y"]}}', encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), "application/json"))
    assert result["status"] == "ok"
    text = result["units"][0]["text"]
    assert "a: alpha" in text
    assert "nested.list[0]: x" in text
    assert "nested.list[1]: y" in text


def test_csv_read(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("name,role\nAda,engineer\n", encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "ok"
    assert result["units"][0]["kind"] == "csv"


def test_empty_text_file_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "blank.txt"
    path.write_text("   \n", encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "empty"
    assert result["units"] == []


# --- html -----------------------------------------------------------------


def test_html_strips_tags_keeps_text(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><style>.x{}</style></head><body>"
        "<h1>Heading</h1><p>Body sentence.</p><script>bad()</script>"
        "</body></html>",
        encoding="utf-8",
    )
    result = _check_result(registry.dispatch(str(path), "text/html"))
    assert result["status"] == "ok"
    unit = result["units"][0]
    assert unit["kind"] == "html"
    assert unit["citable"] is True
    assert "Body sentence." in unit["text"]
    assert "Heading" in unit["text"]
    assert "bad()" not in unit["text"]
    assert ".x{}" not in unit["text"]


# --- pdf ------------------------------------------------------------------


def _write_text_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF sentence one. PDF sentence two.")
    doc.save(str(path))
    doc.close()


def _write_blank_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


def test_pdf_text_layer_citable(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    _write_text_pdf(path)
    result = _check_result(registry.dispatch(str(path), "application/pdf"))
    assert result["status"] == "ok"
    assert result["reader"] == "pdf"
    unit = result["units"][0]
    assert unit["kind"] == "pdf"
    assert unit["citable"] is True
    assert unit["locator"] == "1"
    assert "PDF sentence one." in unit["text"]


def test_scanned_pdf_flags_ocr_needed(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    _write_blank_pdf(path)
    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "empty"
    assert result["error"] == "ocr_needed"
    assert result["units"] == []


# --- office ---------------------------------------------------------------


def test_pptx_slide_and_speaker_notes_are_citable(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    path = tmp_path / "deck.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    box.text_frame.text = "Slide body sentence."
    slide.notes_slide.notes_text_frame.text = "Speaker note sentence."
    prs.save(str(path))

    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "ok"
    assert result["reader"] == "office"
    kinds = {unit["kind"] for unit in result["units"]}
    assert kinds == {"pptx"}
    assert all(unit["citable"] is True for unit in result["units"])
    bodies = {unit["locator"]: unit["text"] for unit in result["units"]}
    assert "Slide body sentence." in bodies["1"]
    assert "Speaker note sentence." in bodies["notes 1"]


def test_docx_paragraphs_and_tables(tmp_path: Path) -> None:
    from docx import Document

    path = tmp_path / "doc.docx"
    doc = Document()
    doc.add_paragraph("Paragraph sentence.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Left cell"
    table.rows[0].cells[1].text = "Right cell"
    doc.save(str(path))

    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "ok"
    unit = result["units"][0]
    assert unit["kind"] == "docx"
    assert unit["citable"] is True
    assert "Paragraph sentence." in unit["text"]
    assert "Left cell" in unit["text"]
    assert "Right cell" in unit["text"]


def test_legacy_ppt_non_ole2_is_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "old.ppt"
    path.write_bytes(b"this is not an OLE2 compound file")
    result = _check_result(registry.dispatch(str(path), None))
    assert result["status"] == "unreadable"
    assert result["error"]


# --- image / OCR ----------------------------------------------------------


def _write_png(path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (32, 32), "white").save(str(path))


def test_image_reflects_ocr_runtime(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    _write_png(path)
    result = _check_result(registry.dispatch(str(path), "image/png"))
    assert result["reader"] == "image"
    available, _detail = ocr.available()
    if available:
        # A blank raster yields no verbatim text: empty, never fabricated.
        assert result["status"] == "empty"
        assert result["units"] == []
    else:
        assert result["status"] == "no_runtime"
        assert result["error"]
        assert "missing:" in result["error"]
        assert result["units"] == []


def test_ocr_availability_reports_exact_reason() -> None:
    available, detail = ocr.available()
    assert isinstance(available, bool)
    if not available:
        assert detail.startswith("missing:")
        assert any(name in detail for name in ("pytesseract", "tesseract", "easyocr"))


def test_vision_hook_default_off_and_never_citable() -> None:
    off = ocr.vision_description("/nonexistent.png")
    assert off["status"] == "no_runtime"
    assert off["error"] == "vision_disabled"
    assert off["units"] == []

    described = ocr.vision_description(
        "/nonexistent.png", enabled=True, describe=lambda _p: "A scanned form."
    )
    assert described["status"] == "ok"
    unit = described["units"][0]
    assert unit["citable"] is False
    assert unit["kind"] == "image"


# --- registry -------------------------------------------------------------


def test_unknown_type_is_unreadable_not_silent_empty(tmp_path: Path) -> None:
    path = tmp_path / "thing.xyz"
    path.write_bytes(b"data")
    result = _check_result(registry.dispatch(str(path), "application/x-unknown"))
    assert result["status"] == "unreadable"
    assert result["units"] == []
    assert result["error"]


def test_dispatch_uses_mime_over_extension(tmp_path: Path) -> None:
    path = tmp_path / "page.html"
    path.write_text("<p>Hello HTML.</p>", encoding="utf-8")
    result = _check_result(registry.dispatch(str(path), "text/html; charset=utf-8"))
    assert result["reader"] == "html"


def test_registry_table_covers_required_formats() -> None:
    rows = registry.table()
    values = set(rows.values())
    assert {"text", "html", "pdf", "office", "image"} <= values
    assert rows["ext:.pptx"] == "office"
    assert rows["mime:application/pdf"] == "pdf"


# --- default-OFF guard ----------------------------------------------------


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_content_engine_is_not_referenced_by_any_turn_path() -> None:
    backend = _backend_root()
    engine_root = backend / "ai" / "engine"
    watched = list(engine_root.rglob("*.py")) + [
        backend / "ai" / "moodle_page.py",
        backend / "ai" / "moodle_host.py",
    ]
    assert engine_root.is_dir()
    offenders = [
        str(path)
        for path in watched
        if path.is_file() and "content_engine" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders
