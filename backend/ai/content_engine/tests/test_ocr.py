"""OCR provisioning tests.

These tests prove the raster/OCR path with a synthetic, test-time-generated PNG
(no committed binary, no network). They are runtime-aware: when an OCR runtime
is available the reader must return a real, citable ``kind='ocr'`` unit whose
text is the verbatim OCR output; when none is available the gap must be locked
as ``no_runtime`` naming the exact missing dependency.
"""

from __future__ import annotations

from pathlib import Path

from ai.content_engine import ocr
from ai.content_engine.readers import registry

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

# A token that survives OCR of a small synthetic render.
_KNOWN_DIGITS = "12345"


def _draw_text_png(path: Path) -> None:
    """Render known English text into a PNG using PIL (test-time only)."""
    from PIL import Image, ImageDraw, ImageFont

    try:  # Pillow >= 10.1: scalable built-in font.
        font = ImageFont.load_default(size=48)
    except TypeError:  # pragma: no cover - older Pillow.
        font = ImageFont.load_default()

    image = Image.new("RGB", (640, 140), "white")
    drawer = ImageDraw.Draw(image)
    drawer.text((20, 40), f"HELLO WORLD {_KNOWN_DIGITS}", fill="black", font=font)
    image.save(str(path))


def _check_result(result: dict) -> dict:
    assert set(result) == _RESULT_FIELDS, result
    assert result["status"] in {"ok", "empty", "unreadable", "no_runtime"}, result
    for unit in result["units"]:
        assert set(unit) == _UNIT_FIELDS, unit
    return result


def test_synthetic_image_ocr_is_verbatim_and_citable(tmp_path: Path) -> None:
    """A synthetic PNG of known English text becomes a citable OCR unit."""
    path = tmp_path / "synthetic.png"
    _draw_text_png(path)

    available, backend = ocr.available()
    if not available:
        # Runtime gap: lock the exact missing-deps string so it stays visible.
        result = _check_result(registry.dispatch(str(path), "image/png"))
        assert result["status"] == "no_runtime", result
        assert result["reader"] == "image"
        assert result["error"] and result["error"].startswith("missing:"), result
        assert any(
            name in result["error"]
            for name in ("pytesseract", "tesseract", "easyocr")
        ), result
        assert result["units"] == []
        return

    result = _check_result(registry.dispatch(str(path), "image/png"))
    assert result["status"] == "ok", (backend, result)
    assert result["reader"] == "image"
    assert result["error"] is None

    unit = result["units"][0]
    assert unit["kind"] == "ocr"
    assert unit["citable"] is True
    assert isinstance(unit["locator"], str) and unit["locator"]
    # Verbatim OCR output: the known digits must be present.
    assert _KNOWN_DIGITS in unit["text"], unit["text"]
    assert "hello" in unit["text"].lower() or "world" in unit["text"].lower(), unit["text"]


def test_run_ocr_locator_uses_page(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.png"
    _draw_text_png(path)
    available, _backend = ocr.available()
    if not available:
        result = _check_result(ocr.run_ocr(str(path), page=3))
        assert result["status"] == "no_runtime"
        return
    result = _check_result(ocr.run_ocr(str(path), page=3, source_ref="doc#3"))
    assert result["status"] == "ok", result
    unit = result["units"][0]
    assert unit["locator"] == "page 3"
    assert unit["source_ref"] == "doc#3"
    assert unit["kind"] == "ocr"
    assert unit["citable"] is True


def test_scanned_pdf_path_ocr_is_page_located_and_citable(tmp_path: Path) -> None:
    """An image-only PDF (no text layer) OCRs page-by-page via ``ocr_pdf``."""
    import pymupdf

    png = tmp_path / "synthetic.png"
    _draw_text_png(png)
    pdf = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=640, height=140)
    page.insert_image(pymupdf.Rect(0, 0, 640, 140), filename=str(png))
    doc.save(str(pdf))
    doc.close()

    # The plain pdf reader must still flag this as needing OCR (no text layer).
    plain = _check_result(registry.dispatch(str(pdf), "application/pdf"))
    assert plain["status"] == "empty"
    assert plain["error"] == "ocr_needed"

    available, _backend = ocr.available()
    if not available:
        result = _check_result(ocr.ocr_pdf(str(pdf)))
        assert result["status"] == "no_runtime"
        return

    result = _check_result(ocr.ocr_pdf(str(pdf), source_ref="scanned#1"))
    assert result["status"] == "ok", result
    assert result["reader"] == "ocr"
    unit = result["units"][0]
    assert unit["kind"] == "ocr"
    assert unit["citable"] is True
    assert unit["locator"] == "page 1"
    assert unit["source_ref"] == "scanned#1"
    assert _KNOWN_DIGITS in unit["text"], unit["text"]


def test_missing_language_pack_is_reported_not_degraded(tmp_path: Path) -> None:
    """An absent requested language pack is a reported status, not a fallback."""
    path = tmp_path / "synthetic.png"
    _draw_text_png(path)
    available, backend = ocr.available()
    if not available or backend != "pytesseract" or not ocr.languages():
        return  # nothing to assert when the pack set is unknown.
    result = _check_result(ocr.run_ocr(str(path), lang="zzz_not_a_lang"))
    assert result["status"] == "no_runtime", result
    assert "missing_language:zzz_not_a_lang" in (result["error"] or "")
    assert result["units"] == []


def test_languages_reports_known_packs() -> None:
    """When a pytesseract runtime exists, its pack list is discoverable."""
    available, backend = ocr.available()
    if not available or backend != "pytesseract":
        assert isinstance(ocr.languages(), list)
        return
    langs = ocr.languages()
    assert isinstance(langs, list)
    # A working tesseract always ships eng in a standard install.
    assert "eng" in langs, langs


def test_vision_hook_stays_default_off_and_never_citable() -> None:
    """The description hook never produces a citable fact and is OFF by default."""
    off = _check_result(ocr.vision_description("/nonexistent.png"))
    assert off["status"] == "no_runtime"
    assert off["error"] == "vision_disabled"
    assert off["units"] == []

    on = _check_result(
        ocr.vision_description(
            "/nonexistent.png", enabled=True, describe=lambda _p: "A scanned form."
        )
    )
    assert on["status"] == "ok"
    assert on["units"][0]["citable"] is False


def test_content_engine_is_not_imported_by_any_turn_path() -> None:
    """Default-OFF: no engine turn path may import the content_engine."""
    backend = Path(__file__).resolve().parents[3]
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
