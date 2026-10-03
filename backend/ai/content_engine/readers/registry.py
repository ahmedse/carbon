"""Format registry: MIME type + extension -> reader.

``dispatch(path, mime)`` is the only entry point. A known type routes to its
reader; an unknown type is ``status='unreadable'`` with an explicit reason,
never a silent empty result.

No reader performs network I/O. Nothing here is imported by a turn path.
"""

from __future__ import annotations

from pathlib import Path

from . import html as _html
from . import image as _image
from . import office as _office
from . import pdf as _pdf
from . import text as _text

# MIME -> reader. Parameters such as ``; charset=utf-8`` are stripped first.
_BY_MIME = {
    "text/plain": _text,
    "text/markdown": _text,
    "text/x-markdown": _text,
    "application/json": _text,
    "text/csv": _text,
    "application/csv": _text,
    "application/x-json": _text,
    "text/html": _html,
    "application/xhtml+xml": _html,
    "application/pdf": _pdf,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": _office,
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow": _office,
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow.macroEnabled.12": _office,
    "application/vnd.ms-powerpoint": _office,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _office,
    "application/msword": _office,
    "image/png": _image,
    "image/jpeg": _image,
    "image/jpg": _image,
    "image/tiff": _image,
    "image/bmp": _image,
    "image/x-ms-bmp": _image,
}

# Extension -> reader (used when the MIME is absent, generic, or unknown).
_BY_EXT = {
    ".txt": _text,
    ".text": _text,
    ".md": _text,
    ".markdown": _text,
    ".json": _text,
    ".csv": _text,
    ".html": _html,
    ".htm": _html,
    ".xhtml": _html,
    ".pdf": _pdf,
    ".pptx": _office,
    ".pptm": _office,
    ".ppsx": _office,
    ".ppsxm": _office,
    ".ppt": _office,
    ".docx": _office,
    ".png": _image,
    ".jpg": _image,
    ".jpeg": _image,
    ".tif": _image,
    ".tiff": _image,
    ".bmp": _image,
}

# MIMEs that carry no format information and should defer to the extension.
_GENERIC_MIME = {"application/octet-stream", "binary/octet-stream", ""}


def _normalise_mime(mime: str | None) -> str:
    if not mime:
        return ""
    return mime.split(";", 1)[0].strip().lower()


def dispatch(path: str, mime: str | None = None) -> dict:
    """Route ``path`` (and optional ``mime``) to its reader.

    Returns a ``ReaderResult``. Unknown types are ``unreadable`` with a reason.
    """
    clean_mime = _normalise_mime(mime)
    reader = None
    if clean_mime not in _GENERIC_MIME:
        reader = _BY_MIME.get(clean_mime)
    if reader is None:
        suffix = Path(path).suffix.lower()
        reader = _BY_EXT.get(suffix)
    if reader is None:
        suffix = Path(path).suffix.lower()
        reason = f"unknown_type:mime={clean_mime or 'none'},ext={suffix or 'none'}"
        return {"units": [], "status": "unreadable", "reader": "registry", "error": reason}

    try:
        result = reader.read(path, clean_mime or None)
    except Exception as exc:  # noqa: BLE001 - a reader crash is a status.
        return {
            "units": [],
            "status": "unreadable",
            "reader": reader.__name__.rsplit(".", 1)[-1],
            "error": f"{type(exc).__name__}: {exc}",
        }
    return _normalise_result(result)


def _normalise_result(result: dict) -> dict:
    """Guarantee the frozen ReaderResult shape."""
    return {
        "units": list(result.get("units") or []),
        "status": str(result.get("status") or "unreadable"),
        "reader": str(result.get("reader") or "unknown"),
        "error": result.get("error"),
    }


def table() -> dict[str, str]:
    """The dispatch table, for documentation and tests: ``type -> reader``."""
    rows: dict[str, str] = {}
    for mime, module in _BY_MIME.items():
        rows[f"mime:{mime}"] = module.__name__.rsplit(".", 1)[-1]
    for ext, module in _BY_EXT.items():
        rows[f"ext:{ext}"] = module.__name__.rsplit(".", 1)[-1]
    return rows
