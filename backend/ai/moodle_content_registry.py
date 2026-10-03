"""Read-only content-format registry + capability reporter for the aast-med bank.

This is a measurement, not a feature. It enumerates every raw row in the
committed passage bank, decides which reader (if any) the row's format needs,
and counts rows in each state. It writes nothing, calls no host, fetches no
network body, runs no OCR, opens no vector store, and builds no graph. It is
Django-free and is not imported by any turn path (locked by
``test_moodle_content_registry``).

It is the Deliverable 1 companion to ``ai/moodle_extraction_gap``: that module
classifies the *join view* (unread roster rows by technique); this module
classifies the *raw bank rows* by format and names the exact reader function.
Neither is a claim about a rung.

Reader identity is mechanical (a module::function string, an extension, or a
remote family), never a phrase table and never a routing regex. Nothing here is
host-domain vocabulary for ``engine/**``; this module lives with the other
medicine seams.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

#: Raw bank roots. Absent roots simply contribute no rows.
_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med" / "bank"
_MEAT = _PACK / "course-meat-13"
_KEYS = _PACK / "course-keys-13"
_EXT = _PACK / "course-ext-13"
_EXTRA = _PACK / "course-extra-13"

#: How a format is read. ``yields`` is ``text`` (a real citable body),
#: ``label`` (non-citable metadata such as a Moodle intro), or ``none``.
YIELDS = ("text", "label", "none")

_EXTERNAL = "scripts/ingest_aast_med_external.py"
_LOCAL = "scripts/ingest_aast_med_local_files.py"
_BANK = "ai/moodle_bank.py"


@dataclass(frozen=True)
class FormatReader:
    """One format in the dispatcher: how it is read and whether it is citable."""

    format_id: str
    extensions: tuple[str, ...]
    reader: str
    yields: str
    citable: bool
    #: True when today's ingest dispatcher actually routes this extension.
    routed: bool = True
    #: True when a bank row of this format is expected. Zero-row formats are
    #: kept so the matrix states the absence explicitly.
    bank_backed: bool = True


#: The dispatcher. One entry per format; the order is the display order.
READERS: tuple[FormatReader, ...] = (
    FormatReader("pdf", (".pdf",), f"{_EXTERNAL}::_pdf_text", "text", True),
    FormatReader("pptx", (".pptx",), f"{_EXTERNAL}::_office_text", "text", True),
    FormatReader("pptm", (".pptm",), f"{_EXTERNAL}::_office_text", "text", True),
    # The shared content-engine registry routes ``.ppsx`` to the office reader
    # (the same algorithm as ``_office_text``), so a re-ingest now accepts it.
    FormatReader("ppsx", (".ppsx",), f"{_EXTERNAL}::_office_text", "text", True),
    FormatReader("ppt", (".ppt",), f"{_EXTERNAL}::_legacy_ppt_text", "text", True),
    FormatReader("docx", (".docx",), f"{_EXTERNAL}::_office_text", "text", True),
    FormatReader("media", (".mp4", ".mov", ".avi"), f"{_LOCAL}::_extract", "none", False),
    FormatReader("page", (), f"{_BANK}::load_c3", "text", True),
    FormatReader("label", (), f"{_BANK}::load_c3", "text", True),
    FormatReader("book", (), f"{_BANK}::load_c3", "text", True),
    # Section titles are citable through the signed-snapshot L1 door, not as a
    # load_c3 passage.
    FormatReader("section", (), "snapshot::section_door", "text", True),
    # Meat ``kind:url`` text is the Moodle intro: no loader reads it as a body.
    FormatReader("moodle_intro", (), "none", "label", False, routed=False),
    FormatReader("google_slides", (), f"{_EXTERNAL}::google_presentation", "text", True),
    FormatReader("google_docs", (), f"{_EXTERNAL}::google_document", "text", True),
    FormatReader("google_drive", (), f"{_EXTERNAL}::google_file", "text", True),
    FormatReader("docs_link", (), "none", "none", False, routed=False),
    FormatReader("youtube", (), f"{_EXTERNAL}::youtube_caption", "text", True),
    # Extra .txt/.md/.json is supplied as already-split passages by the plugin;
    # Carbon has no file reader for it.
    FormatReader("extra", (".txt", ".md", ".json"), f"{_BANK}::write_extra_index", "text", True),
    FormatReader("html", (".html", ".htm"), "none", "none", False, routed=False, bank_backed=False),
    FormatReader("image", (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"), "none", "none", False, routed=False, bank_backed=False),
    FormatReader("web", (), "none", "none", False, routed=False, bank_backed=False),
    FormatReader("folder", (), "none", "none", False, routed=False, bank_backed=False),
)

BY_ID: dict[str, FormatReader] = {fmt.format_id: fmt for fmt in READERS}

_EXT_TO_FORMAT: dict[str, str] = {
    ext: fmt.format_id for fmt in READERS for ext in fmt.extensions
}


def format_for_extension(extension: str) -> str:
    """Format id for a filename extension (with or without the dot).

    Unknown extensions return ``"unclassified"`` so a caller never silently
    drops a row.
    """
    ext = str(extension or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    if not ext:
        return "unclassified"
    return _EXT_TO_FORMAT.get(ext, "unclassified")


@dataclass(frozen=True)
class FormatRow:
    """Counted rows for one format in the raw bank."""

    format_id: str
    reader: str
    yields: str
    citable: bool
    routed: bool
    total: int
    with_text: int

    @property
    def citable_rows(self) -> int:
        """Rows that can be a verbatim cite today."""
        return self.with_text if self.citable else 0


def _rows(root: Path) -> list[dict]:
    out: list[dict] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("{"):
                out.append(json.loads(line))
    return out


def _meat_format(row: dict) -> str:
    kind = str(row.get("kind") or "").strip().lower()
    if kind == "file":
        ref = str(row.get("ref") or row.get("name") or "")
        suffix = Path(ref).suffix
        return format_for_extension(suffix)
    if kind == "url":
        return "moodle_intro"
    if kind in {"page", "label", "book", "section"}:
        return kind
    return "unclassified"


def _ext_format(row: dict) -> str:
    source_kind = str(row.get("source_kind") or "").strip().lower()
    if source_kind.startswith("link:"):
        return "docs_link"
    if source_kind == "youtube":
        return "youtube"
    if source_kind == "google-presentation":
        return "google_slides"
    if source_kind == "google-document":
        return "google_docs"
    if source_kind == "google-file":
        return "google_drive"
    return "unclassified"


def _raw_rows() -> list[tuple[str, dict]]:
    """``(format_id, row)`` for every raw content bank row.

    Covers meat, ext, and extra. The ``course-keys-13`` root is the join
    manifest (section + family + name), not content, so it is not counted here.
    """
    out: list[tuple[str, dict]] = []
    for row in _rows(_MEAT):
        out.append((_meat_format(row), row))
    for row in _rows(_EXT):
        out.append((_ext_format(row), row))
    for row in _rows(_EXTRA):
        if str(row.get("kind") or "") == "extra":
            out.append(("extra", row))
    return out


def matrix() -> tuple[FormatRow, ...]:
    """One ``FormatRow`` per registered format, in dispatcher order.

    Formats with no bank rows are present with ``total == 0`` so the absence of
    a reader is stated, never hidden.
    """
    counts: dict[str, list[int]] = {fmt.format_id: [0, 0] for fmt in READERS}
    for format_id, row in _raw_rows():
        if format_id not in counts:
            counts[format_id] = [0, 0]
        counts[format_id][0] += 1
        if str(row.get("text") or "").strip():
            counts[format_id][1] += 1
    rows: list[FormatRow] = []
    for fmt in READERS:
        total, with_text = counts.get(fmt.format_id, [0, 0])
        rows.append(
            FormatRow(
                format_id=fmt.format_id,
                reader=fmt.reader,
                yields=fmt.yields,
                citable=fmt.citable,
                routed=fmt.routed,
                total=total,
                with_text=with_text,
            )
        )
    return tuple(rows)


def unclassified_rows() -> list[dict]:
    """Raw rows the registry could not place. Must stay empty (a bug, not data)."""
    return [row for format_id, row in _raw_rows() if format_id == "unclassified"]


def totals() -> dict[str, int]:
    """``{format_id: total}`` for every format with at least one raw row."""
    return {row.format_id: row.total for row in matrix() if row.total}


def summary() -> dict[str, int]:
    """Headline counters for the matrix, all derived from the raw bank."""
    rows = matrix()
    backed = [row for row in rows if BY_ID[row.format_id].bank_backed]
    return {
        "formats": len(rows),
        "formats_with_rows": sum(1 for row in rows if row.total),
        "formats_with_reader": sum(1 for row in rows if row.reader != "none"),
        "raw_rows": sum(row.total for row in rows),
        "rows_with_text": sum(row.with_text for row in rows),
        "citable_rows": sum(row.citable_rows for row in rows),
        # Narrow reader functions named in the registry itself, excluding the
        # snapshot loader, the section door, the plugin-supplied extra path, and
        # the ingest dispatcher ``_extract``.
        "reader_functions": len(
            {
                row.reader
                for row in backed
                if row.reader
                not in {
                    "none",
                    "snapshot::section_door",
                    f"{_BANK}::load_c3",
                    f"{_BANK}::write_extra_index",
                    f"{_LOCAL}::_extract",
                }
            }
        ),
    }


def join_techniques() -> dict[str, int]:
    """Unread roster rows by technique (the join view), from the gap reporter."""
    from ai.moodle_extraction_gap import report, totals as gap_totals

    return gap_totals(report())


def rows_by(format_id: str) -> list[tuple[str, dict]]:
    """Raw rows for one format id (read-only convenience)."""
    return [(fid, row) for fid, row in _raw_rows() if fid == format_id]


def _iter_formats() -> Iterable[FormatReader]:
    return iter(READERS)
