"""OCR runtime detection, verbatim OCR, and a default-OFF vision hook.

If an OCR runtime (``pytesseract`` + the ``tesseract`` binary, or ``easyocr``)
is present it is used; otherwise callers get ``status='no_runtime'`` naming the
exact missing dependency. A requested language pack that is absent is reported
the same way. Nothing is fabricated when the runtime is absent.

The vision hook is a *description* path, never a fact: its ``TextUnit`` is
always ``citable=False``, and it is off unless explicitly enabled.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

#: Opt-in switch for the non-citable vision-description hook (default OFF).
VISION_ENV = "CONTENT_ENGINE_ENABLE_VISION"

#: Language packs requested by :func:`ocr_pdf` for a scanned document, in the
#: order they are combined when present (Arabic source, Latin script/numbers).
PDF_LANGS = ("ara", "eng")


def _result(units: list[dict], status: str, reader: str, error: str | None) -> dict:
    return {"units": units, "status": status, "reader": reader, "error": error}


def available() -> tuple[bool, str]:
    """Return ``(True, backend)`` if an OCR runtime is usable, else the reason.

    The reason names the exact missing dependency so a caller can report it
    without guessing.
    """
    has_tesseract_py = _module_present("pytesseract")
    has_tesseract_bin = shutil.which("tesseract") is not None
    has_easyocr = _module_present("easyocr")

    if has_tesseract_py and has_tesseract_bin:
        return True, "pytesseract"
    if has_easyocr:
        return True, "easyocr"

    missing: list[str] = []
    if not has_tesseract_py:
        missing.append("pytesseract (python)")
    if not has_tesseract_bin:
        missing.append("tesseract (binary)")
    if not has_easyocr:
        missing.append("easyocr (python)")
    return False, "missing: " + ", ".join(missing)


def _module_present(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def languages() -> list[str]:
    """Language packs the active OCR runtime can read, or ``[]`` if unknown.

    For the ``pytesseract`` backend these are the tesseract tessdata packs
    (e.g. ``ara``, ``eng``). An empty list means the pack set could not be
    determined, so callers must not silently assume a language exists.
    """
    if shutil.which("tesseract") is None:
        return []
    try:
        proc = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    found: list[str] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of available"):
            continue
        found.append(line)
    return sorted(found)


def _lang_missing(lang: str) -> tuple[bool, str]:
    """Return ``(is_missing, detail)`` for a tesseract ``lang`` expression.

    ``lang`` may be a ``+``-joined expression (``ara+eng``). When the pack set
    is unknown (``languages() == []``) nothing is reported as missing; the
    runtime decides. When it is known, a requested pack that is absent is
    reported instead of silently degrading.
    """
    have = set(languages())
    if not have:
        return False, ""
    wanted = [part for part in lang.split("+") if part]
    missing = [part for part in wanted if part not in have]
    if not missing:
        return False, ""
    return True, "missing_language:" + "+".join(missing) + " (have: " + ",".join(sorted(have)) + ")"


def _unit(text: str, locator: str, kind: str = "ocr", citable: bool = True) -> dict:
    return {
        "text": text,
        "kind": kind,
        "source_ref": "",
        "locator": locator,
        "citable": citable,
        "course": None,
        "activity_ref": None,
        "status": "ok",
    }


def run_ocr(
    path: str,
    *,
    page: int | None = None,
    source_ref: str = "",
    lang: str | None = None,
) -> dict:
    """OCR a raster image (or one rendered page) into a verbatim TextUnit.

    Returns a ``ReaderResult``. When no runtime is available the result is
    ``status='no_runtime'`` and carries the missing dependency in ``error``.
    When a requested language pack is absent, that fact is reported in
    ``error`` instead of silently degrading to another language.
    """
    ok, backend = available()
    if not ok:
        return _result([], "no_runtime", "ocr", backend)
    if lang and backend == "pytesseract":
        missing, detail = _lang_missing(lang)
        if missing:
            return _result([], "no_runtime", "ocr", detail)

    try:
        text = _ocr_text(path, backend, lang)
    except Exception as exc:  # noqa: BLE001 - a bad image is a status, not a crash.
        return _result([], "unreadable", "ocr", f"{type(exc).__name__}: {exc}")
    text = " ".join(text.split())
    if not text:
        return _result([], "empty", "ocr", "no_text")
    locator = f"page {page}" if page else "n/a"
    unit = _unit(text, locator)
    unit["source_ref"] = source_ref
    return _result([unit], "ok", "ocr", None)


def _ocr_text(path: str, backend: str, lang: str | None = None) -> str:
    if backend == "pytesseract":
        import pytesseract
        from PIL import Image

        with Image.open(path) as image:
            return pytesseract.image_to_string(image, lang=lang or "eng")
    import easyocr  # type: ignore

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    chunks = reader.readtext(str(path), detail=0, paragraph=True)
    return "\n".join(str(chunk) for chunk in chunks)


def ocr_pdf(path: str, *, source_ref: str = "") -> dict:
    """OCR every page of a scanned PDF (rendered locally via PyMuPDF).

    The default ``pdf`` reader does not call this; it flags ``ocr_needed``.
    This is the explicit opt-in path for a scanned document.
    """
    ok, backend = available()
    if not ok:
        return _result([], "no_runtime", "ocr", backend)
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return _result([], "no_runtime", "ocr", "missing: pymupdf")

    # A scanned document is typically Arabic; combine with Latin for numerals
    # and Latin-script fragments. Report (do not hide) a missing Arabic pack.
    have = set(languages())
    note: str | None = None
    if backend == "pytesseract" and have:
        if "ara" not in have:
            note = "missing_language:ara (have: " + ",".join(sorted(have)) + ")"
        lang = "+".join(part for part in PDF_LANGS if part in have) or None
    else:
        lang = "ara+eng" if backend == "pytesseract" else None

    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        return _result([], "unreadable", "ocr", f"{type(exc).__name__}: {exc}")

    units: list[dict] = []
    try:
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(dpi=200)
            tmp = Path(path).with_suffix(f".page{index}.png")
            try:
                pixmap.save(str(tmp))
                result = run_ocr(str(tmp), page=index, source_ref=source_ref, lang=lang)
            finally:
                tmp.unlink(missing_ok=True)
            if result["status"] == "ok":
                units.extend(result["units"])
    finally:
        doc.close()

    if not units:
        return _result([], "empty", "ocr", note or "no_text")
    return _result(units, "ok", "ocr", note)


def vision_enabled() -> bool:
    """Whether the default-OFF vision description hook is turned on."""
    return os.environ.get(VISION_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def vision_description(
    path: str,
    *,
    describe=None,
    enabled: bool | None = None,
    source_ref: str = "",
) -> dict:
    """Non-citable description hook. Default OFF.

    A description is never a fact, so any unit produced here carries
    ``citable=False``. No model or network lives in this module: the caller
    supplies ``describe(path) -> str``. With the hook off, or without a
    describer, nothing is produced.
    """
    if enabled is None:
        enabled = vision_enabled()
    if not enabled:
        return _result([], "no_runtime", "vision", "vision_disabled")
    if describe is None:
        return _result([], "no_runtime", "vision", "no_vision_model")
    try:
        text = " ".join(str(describe(path) or "").split())
    except Exception as exc:  # noqa: BLE001
        return _result([], "unreadable", "vision", f"{type(exc).__name__}: {exc}")
    if not text:
        return _result([], "empty", "vision", "no_description")
    unit = _unit(text, "n/a", kind="image", citable=False)
    unit["source_ref"] = source_ref
    return _result([unit], "ok", "vision", None)
