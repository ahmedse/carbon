"""PDF reader: text-layer extraction, one citable unit per page.

Matches the repo's existing ingest pattern (``pypdf.PdfReader`` +
``page.extract_text()``), so there is no second PDF stack. A PDF with no text
layer (a scan) is reported as ``status='empty'`` with ``error='ocr_needed'``;
this reader never fabricates text and never calls OCR itself.
"""

from __future__ import annotations

import io
from pathlib import Path


def _result(units: list[dict], status: str, error: str | None) -> dict:
    return {"units": units, "status": status, "reader": "pdf", "error": error}


def _unit(text: str, page: int) -> dict:
    return {
        "text": text,
        "kind": "pdf",
        "source_ref": "",
        "locator": str(page),
        "citable": True,
        "course": None,
        "activity_ref": None,
        "status": "ok",
    }


def read(path: str, mime: str | None = None) -> dict:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")
    if not raw.strip():
        return _result([], "unreadable", "empty_file")

    try:
        from pypdf import PdfReader
    except ImportError:
        return _result([], "no_runtime", "missing: pypdf")

    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            return _result([], "unreadable", "encrypted")
        pages = list(reader.pages)
    except Exception as exc:  # noqa: BLE001 - a bad PDF is a status, not a crash.
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")

    units: list[dict] = []
    for index, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one bad page must not sink the file.
            text = ""
        text = _tidy(text)
        if text:
            units.append(_unit(text, index))

    if not units:
        # Zero text layer across the whole document: a scan. Flag for OCR.
        return _result([], "empty", "ocr_needed")
    return _result(units, "ok", None)


def _tidy(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
