"""Ingest adapters: bytes -> shared readers -> citable passages / index / graph.

This module is the single seam the scripts and the staff Index job use so that
extraction, OCR, chunking, the keyword index, and the knowledge graph all route
through the same committed engines (``readers.registry``, ``chunk``, ``index``,
``graph``, ``ocr``) instead of a second ad-hoc stack.

Hard boundaries, identical to the rest of ``content_engine``:

* Nothing here is imported by ``ai/engine/**`` or by a Chat turn. Builders import
  ``ai.moodle_bank`` lazily (function-local) so importing this module never pulls
  Django and never opens the pack on import.
* OCR runs only where a caller asks for it (the staff Index path / local ingest),
  never on a Chat turn. Arabic OCR output is stored ``citable=False`` with
  ``status='pending_signoff'`` until the existing human sign-off clears it.
* Drive acquisition is delegated to :mod:`ai.content_engine.acquire`, which is
  default-OFF and refuses anything that is not a staff Index job.
"""
from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

from . import chunk as _chunk
from . import graph as _graph
from . import index as _index
from . import ocr as _ocr
from .readers import registry as _registry

#: Pack root for the aast-med default artifact paths (callers may override).
_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"

#: Extensions this adapter knows the shared registry can route.
ROUTED_SUFFIXES = frozenset(
    {
        ".txt",
        ".text",
        ".md",
        ".markdown",
        ".json",
        ".csv",
        ".html",
        ".htm",
        ".xhtml",
        ".pdf",
        ".pptx",
        ".pptm",
        ".ppsx",
        ".ppt",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }
)

#: A video has no local reader; keep the exact legacy status token.
_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


def default_index_root() -> Path:
    return _PACK / "index"


def default_graph_root() -> Path:
    return _PACK / "graph"


def default_ocr_pending_root() -> Path:
    return _PACK / "bank" / "ocr-pending"


# ─────────────────────────────────────────────────────────────────────────────
# Bytes -> ReaderResult -> text
# ─────────────────────────────────────────────────────────────────────────────


def _temp_file(data: bytes, filename: str) -> str:
    """Write ``data`` to a suffix-preserving temp file and return the path."""
    suffix = Path(filename).suffix.lower()
    fd, path = tempfile.mkstemp(prefix="ce-ingest-", suffix=suffix)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return path


def read_bytes(data: bytes, filename: str, mime: str | None = None) -> dict:
    """Dispatch stored bytes through the shared reader registry.

    The bytes are written to a temporary file that keeps the original suffix so
    extension-based routing is exact; the temp file is always removed.
    """
    if not data:
        return {"units": [], "status": "empty", "reader": "registry", "error": "empty_file"}
    path = _temp_file(data, filename)
    try:
        return _registry.dispatch(path, mime)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def units_text(result: dict) -> str:
    """Join the verbatim text of every unit in a ``ReaderResult``."""
    return "\n".join(
        str(unit.get("text") or "") for unit in (result.get("units") or []) if unit.get("text")
    )


def read_path(path: str, mime: str | None = None) -> dict:
    """Read a local path through the shared registry (the acquire reader seam).

    ``read_bytes`` takes bytes; acquisition hands a path, so this adapter reads
    the file first. It is the reader an Index job injects into
    ``acquire.drive_acquire`` / ``acquire.web_acquire``.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        return {
            "units": [],
            "status": "unreadable",
            "reader": "registry",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return read_bytes(data, path, mime)


def _has_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in text or "")


def ocr_bytes(data: bytes, filename: str, *, source_ref: str = "") -> dict:
    """OCR a scanned PDF or a raster image, flagging Arabic as non-citable.

    Returns a ``ReaderResult``. Any unit whose text contains Arabic is marked
    ``citable=False`` with ``status='pending_signoff'`` so it can never be a
    verbatim cite before the recorded human sign-off. English OCR text is
    returned citable.
    """
    ok, backend = _ocr.available()
    if not ok:
        return {"units": [], "status": "no_runtime", "reader": "ocr", "error": backend}
    suffix = Path(filename).suffix.lower()
    if suffix not in ROUTED_SUFFIXES:
        return {"units": [], "status": "unreadable", "reader": "ocr", "error": f"no_ocr:{suffix}"}
    path = _temp_file(data, filename)
    try:
        if suffix == ".pdf":
            result = _ocr.ocr_pdf(path, source_ref=source_ref)
        else:
            result = _ocr.run_ocr(path, source_ref=source_ref)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    for unit in result.get("units") or []:
        if _has_arabic(str(unit.get("text") or "")):
            unit["citable"] = False
            unit["status"] = "pending_signoff"
    return result


def extract_text(data: bytes, filename: str, mime: str | None = None) -> tuple[str, str]:
    """Mirror the legacy ``_extract`` ``(status, text)`` contract.

    A scanned PDF/image falls back to OCR: English yields ``ok``; Arabic yields
    ``signoff:arabic`` with the verbatim text (the caller stores it non-citable).
    """
    suffix = Path(filename).suffix.lower()
    if suffix in _VIDEO_SUFFIXES:
        return "unavailable:legacy_video", ""
    result = read_bytes(data, filename, mime)
    status = str(result.get("status") or "unreadable")
    error = result.get("error")
    text = units_text(result)
    if status == "ok" and text:
        return "ok", text
    if status == "empty" and error == "ocr_needed":
        ocr_result = ocr_bytes(data, filename)
        ocr_text = units_text(ocr_result)
        if not ocr_text:
            return "empty:no_text", ""
        if any(not unit.get("citable", True) for unit in ocr_result.get("units") or []):
            return "signoff:arabic", ocr_text
        return "ok", ocr_text
    if status == "empty":
        return f"empty:{error or 'no_text'}", ""
    if status == "no_runtime":
        return f"unavailable:{error or 'no_runtime'}", ""
    return f"unavailable:{error or 'unreadable'}", ""


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Extra files -> extra passage payload (verbatim, one passage per file)
# ─────────────────────────────────────────────────────────────────────────────


def _decode(content: object) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, str):
        try:
            return base64.b64decode(content, validate=True)
        except Exception:  # noqa: BLE001 - a non-base64 string is raw text bytes
            return content.encode("utf-8")
    return b""


def extra_payload_from_files(files: list[dict]) -> list[dict]:
    """Turn uploaded extra file bytes into ``write_extra_index`` payload rows.

    Each file becomes exactly one verbatim passage (the extra passage id is
    ``course:extra:itemid:filename``, so one row per file keeps a single owner).
    A file the shared readers cannot read is skipped, never faked.
    """
    out: list[dict] = []
    for item in files or []:
        if not isinstance(item, dict):
            continue
        try:
            itemid = int(item.get("itemid") or 0)
        except (TypeError, ValueError):
            continue
        filename = str(item.get("filename") or "").strip()
        if itemid <= 0 or not filename:
            continue
        data = _decode(item.get("content"))
        if not data:
            continue
        result = read_bytes(data, filename, item.get("mime"))
        text = units_text(result)
        if result.get("status") != "ok" or not text:
            continue
        out.append(
            {
                "itemid": itemid,
                "filename": filename,
                "title": str(item.get("title") or filename),
                "sectionnum": int(item.get("sectionnum") or -1),
                "passages": [{"text": text}],
            }
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Pack bank -> chunk index / knowledge graph (staff Index job)
# ─────────────────────────────────────────────────────────────────────────────


def _course_bank(shortname: str) -> dict[str, dict]:
    from ai import moodle_bank  # lazy: keeps this module Django-free on import

    bank: dict[str, dict] = {}
    bank.update(moodle_bank.load_c3(shortname))
    bank.update(moodle_bank.load_c4_files(shortname))
    bank.update(moodle_bank.load_c4_drive(shortname))
    bank.update(moodle_bank.load_c5_youtube(shortname))
    bank.update(moodle_bank.load_extra(shortname))
    return bank


def _unit_for(passage: dict, shortname: str) -> dict:
    return {
        "text": str(passage.get("text") or ""),
        "kind": str(passage.get("kind") or "passage"),
        "source_ref": str(passage.get("id") or ""),
        "locator": str(passage.get("name") or passage.get("id") or ""),
        "citable": True,
        "course": shortname,
        "activity_ref": str(passage.get("activity_id") or ""),
        "status": "ok",
    }


def build_course_index(
    shortname: str,
    *,
    index_root: str | os.PathLike[str] | None = None,
    bank: dict[str, dict] | None = None,
    extra_passages: dict[str, dict] | None = None,
) -> dict:
    """Chunk the course passage bank and persist the keyword index to JSONL.

    ``extra_passages`` are additive rows (e.g. Arabic OCR passages a recorded
    human sign-off has cleared). They join the keyword index only; they never
    reach a door or the citable bank.
    """
    bank = _course_bank(shortname) if bank is None else bank
    if extra_passages:
        bank = {**bank, **extra_passages}
    units = [
        _unit_for(passage, shortname)
        for passage in bank.values()
        if str(passage.get("text") or "").strip()
    ]
    chunks = _chunk.chunk_units(units)
    root = Path(index_root) if index_root is not None else default_index_root()
    path = root / f"{shortname}.jsonl"
    index = _index.save_index(str(path), chunks, semantic_status="default_off")
    return {
        "course": shortname,
        "chunks": len(index.chunks),
        "path": str(path),
        "keyword": _index.KEYWORD_DEFAULT_ON,
        "semantic_status": "default_off",
    }


def build_course_graph(
    shortname: str,
    *,
    graph_root: str | os.PathLike[str] | None = None,
) -> dict:
    """Build the passage-grounded knowledge graph from the loaded pack bank.

    The loader rows already carry a real ``activity_id`` (the raw meat ``cmid``
    is often null), so the graph is built from the same passage dicts a door
    serves — never from filenames.
    """
    bank = _course_bank(shortname)
    graph = _graph.build_course_graph(shortname, bank.values())
    root = Path(graph_root) if graph_root is not None else default_graph_root()
    path = root / f"{shortname}.jsonl"
    graph.save(path)
    stats = graph.stats()
    return {
        "course": shortname,
        "nodes": stats["nodes"],
        "edges": stats["edges"],
        "path": str(path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Drive refs for a course (default-OFF; only the staff Index job calls these)
# ─────────────────────────────────────────────────────────────────────────────


def unread_drive_refs(shortname: str) -> list[str]:
    """Drive refs for one course whose body is not stored yet.

    Reads ``course-ext-13`` metadata only; it never touches the network. The
    caller feeds the refs to :func:`ai.content_engine.acquire.drive_acquire`,
    which enforces the Index-job trigger and default-OFF enablement.
    """
    from ai import moodle_bank  # lazy

    path = moodle_bank._EXT / f"{shortname}.jsonl"
    if not path.is_file():
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        if str(row.get("course") or "") != shortname:
            continue
        source_kind = str(row.get("source_kind") or "")
        source_id = str(row.get("source_id") or "")
        if not source_id or source_kind.startswith("link:") or row.get("status") == "ok":
            continue
        if source_kind not in {"google-presentation", "google-document", "google-file"}:
            continue
        ref = f"{source_kind}:{source_id}"
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


__all__ = [
    "ROUTED_SUFFIXES",
    "default_index_root",
    "default_graph_root",
    "default_ocr_pending_root",
    "read_bytes",
    "read_path",
    "units_text",
    "ocr_bytes",
    "extract_text",
    "extra_payload_from_files",
    "build_course_index",
    "build_course_graph",
    "unread_drive_refs",
]
