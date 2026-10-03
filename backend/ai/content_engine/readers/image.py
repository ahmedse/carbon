"""Raster-image reader backed by the OCR runtime.

If a runtime exists, verbatim OCR text is returned as a citable ``kind='ocr'``
unit. If not, the result is ``status='no_runtime'`` naming the exact missing
dependency; no text is invented. The non-citable vision-description hook lives
in :mod:`ai.content_engine.ocr` and is default-OFF; this reader never calls it.
"""

from __future__ import annotations

from pathlib import Path

from .. import ocr


def read(path: str, mime: str | None = None) -> dict:
    if not Path(path).is_file():
        return {"units": [], "status": "unreadable", "reader": "image", "error": "missing_file"}
    result = ocr.run_ocr(path)
    result["reader"] = "image"
    return result
