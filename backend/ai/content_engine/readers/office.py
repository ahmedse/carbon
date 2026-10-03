"""Office readers: pptx / ppt (legacy OLE2) / docx.

* ``pptx`` — slide text and speaker notes are both first-class citable units.
* ``ppt``  — the binary OLE2/CFB reader from ``scripts/ingest_aast_med_external``
  is reimplemented here identically (that script is not an importable package),
  so there is exactly one legacy-PowerPoint algorithm, not a fork of the idea.
* ``docx`` — paragraphs and table cells, kept in document order.

Every unit here is verbatim file text and therefore citable.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

_OFFICE_KIND = {
    ".pptx": "pptx",
    ".pptm": "pptx",
    ".ppsx": "pptx",
    ".ppt": "ppt",
    ".docx": "docx",
}


def _result(units: list[dict], status: str, error: str | None) -> dict:
    return {"units": units, "status": status, "reader": "office", "error": error}


def _unit(text: str, kind: str, locator: str = "n/a") -> dict:
    return {
        "text": text,
        "kind": kind,
        "source_ref": "",
        "locator": locator,
        "citable": True,
        "course": None,
        "activity_ref": None,
        "status": "ok",
    }


def read(path: str, mime: str | None = None) -> dict:
    suffix = Path(path).suffix.lower()
    kind = _OFFICE_KIND.get(suffix)
    if kind is None:
        return _result([], "unreadable", f"unsupported_office:{suffix or 'no_ext'}")
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")
    if not data.strip():
        return _result([], "empty", "no_text")

    try:
        if kind == "pptx":
            units = _pptx_units(data)
        elif kind == "docx":
            units = _docx_units(data)
        else:
            units = _ppt_units(data)
    except _BadArchive as exc:
        return _result([], "unreadable", str(exc))
    except Exception as exc:  # noqa: BLE001 - a bad file is a status, not a crash.
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")

    if not units:
        return _result([], "empty", "no_text")
    return _result(units, "ok", None)


class _BadArchive(Exception):
    """The container could not be opened at all."""


def _tidy(text: str) -> str:
    lines = [" ".join(line.split()) for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line)


# --- pptx -----------------------------------------------------------------


def _pptx_units(data: bytes) -> list[dict]:
    import io

    from pptx import Presentation  # python-pptx

    try:
        presentation = Presentation(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise _BadArchive(f"{type(exc).__name__}: {exc}") from exc

    units: list[dict] = []
    for index, slide in enumerate(presentation.slides, start=1):
        pieces = [
            shape.text_frame.text
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and _tidy(getattr(shape.text_frame, "text", ""))
        ]
        body = _tidy("\n".join(pieces))
        if body:
            units.append(_unit(body, "pptx", str(index)))
        notes = _slide_notes(slide)
        if notes:
            units.append(_unit(notes, "pptx", f"notes {index}"))
    return units


def _slide_notes(slide) -> str:
    try:
        if not slide.has_notes_slide:
            return ""
        frame = slide.notes_slide.notes_text_frame
    except Exception:  # noqa: BLE001
        return ""
    return _tidy(getattr(frame, "text", ""))


# --- docx -----------------------------------------------------------------


def _docx_units(data: bytes) -> list[dict]:
    import io

    from docx import Document  # python-docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise _BadArchive(f"{type(exc).__name__}: {exc}") from exc

    lines: list[str] = []
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = _tidy(Paragraph(child, document).text)
            if text:
                lines.append(text)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells = [_tidy(cell.text) for cell in row.cells]
                row_text = " | ".join(cell for cell in cells if cell)
                if row_text:
                    lines.append(row_text)

    text = "\n".join(lines)
    return [_unit(text, "docx")] if text else []


# --- legacy .ppt (OLE2 compound file) -------------------------------------
# A PowerPoint 97-2003 deck is an OLE2/CFB container. Its slide text lives as
# verbatim TextCharsAtom/TextBytesAtom records inside the "PowerPoint Document"
# stream. This host has no LibreOffice, so the deck is read directly: slide text
# is copied verbatim, and a Notes record is kept only when it is real speaker
# text (an empty notes page repeats the slide-master placeholder prompt, which
# is dropped). A deck that yields no text yields ""; nothing is invented.
#
# Reimplemented identically from scripts/ingest_aast_med_external.py.

_PPT_SIG = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PPT_FREE = 0xFFFFFFFF
_PPT_END = 0xFFFFFFFE
_PPT_CHARS = 0x0FA0
_PPT_BYTES = 0x0FA8
_PPT_SLIDE = 1006
_PPT_NOTES = 1008
_PPT_MASTER = 1016
_PPT_IMAGE = re.compile(r".+\.(?:jpe?g|png|gif|bmp|emf|wmf|tiff?)$", re.IGNORECASE)


def _le16(raw: bytes, off: int) -> int:
    return int.from_bytes(raw[off : off + 2], "little")


def _le32(raw: bytes, off: int) -> int:
    return int.from_bytes(raw[off : off + 4], "little")


def _le64(raw: bytes, off: int) -> int:
    return int.from_bytes(raw[off : off + 8], "little")


class _PptCfb:
    """Minimal read-only OLE2/CFB reader for the PowerPoint Document stream."""

    def __init__(self, data: bytes):
        if data[:8] != _PPT_SIG:
            raise ValueError("not a legacy .ppt (OLE2) file")
        self.data = data
        self.sector = 1 << _le16(data, 0x1E)
        self.num_fat = _le32(data, 0x2C)
        self.dir_start = _le32(data, 0x30)
        self.mini_cutoff = _le32(data, 0x38)
        self.difat_start = _le32(data, 0x44)
        self.num_difat = _le32(data, 0x48)
        self._read_difat()
        self._read_fat()
        self._read_dir()

    def _sector_bytes(self, n: int) -> bytes:
        start = 512 + n * self.sector
        return self.data[start : start + self.sector]

    def _read_difat(self) -> None:
        self.difat = [_le32(self.data, 0x4C + 4 * i) for i in range(109)]
        sect = self.difat_start
        for _ in range(self.num_difat):
            raw = self._sector_bytes(sect)
            self.difat.extend(_le32(raw, 4 * i) for i in range(self.sector // 4 - 1))
            sect = _le32(raw, self.sector - 4)

    def _read_fat(self) -> None:
        self.fat: list[int] = []
        for i in range(self.num_fat):
            raw = self._sector_bytes(self.difat[i])
            self.fat.extend(_le32(raw, 4 * j) for j in range(self.sector // 4))

    def _chain(self, start: int) -> list[int]:
        out, sect, seen = [], start, set()
        while sect not in (_PPT_END, _PPT_FREE) and sect not in seen:
            seen.add(sect)
            out.append(sect)
            sect = self.fat[sect] if sect < len(self.fat) else _PPT_END
        return out

    def _read_dir(self) -> None:
        raw = b"".join(self._sector_bytes(s) for s in self._chain(self.dir_start))
        self.entries: list[dict | None] = []
        for off in range(0, len(raw), 128):
            name_len = _le16(raw, off + 0x40)
            if name_len < 2:
                self.entries.append(None)
                continue
            self.entries.append(
                {
                    "name": raw[off : off + name_len - 2].decode("utf-16-le", "replace"),
                    "type": raw[off + 0x42],
                    "start": _le32(raw, off + 0x74),
                    "size": _le64(raw, off + 0x78),
                }
            )

    def stream(self, name: str) -> bytes:
        for entry in self.entries:
            if entry and entry["type"] == 2 and entry["name"] == name:
                if entry["size"] < self.mini_cutoff:
                    return b""  # the deck's text stream is never a mini stream
                return b"".join(
                    self._sector_bytes(s) for s in self._chain(entry["start"])
                )[: entry["size"]]
        return b""


def _ppt_walk(blob: bytes, start: int, end: int, buckets: dict, stack: tuple = ()) -> None:
    off = start
    while off + 8 <= end:
        ver_inst = _le16(blob, off)
        rec_type = _le16(blob, off + 2)
        rec_len = _le32(blob, off + 4)
        body = off + 8
        if (ver_inst & 0x000F) == 0x000F:  # a container; recurse into its children
            child_end = body + rec_len if rec_len else end
            _ppt_walk(blob, body, min(child_end, end), buckets, stack + (rec_type,))
            off = body + rec_len if rec_len else end
        else:
            top = stack[0] if stack else None
            if top in (_PPT_SLIDE, _PPT_NOTES, _PPT_MASTER) and rec_type in (
                _PPT_CHARS,
                _PPT_BYTES,
            ):
                codec = "utf-16-le" if rec_type == _PPT_CHARS else "cp1252"
                buckets[top].append(blob[body : body + rec_len].decode(codec, "replace"))
            off = body + rec_len


def _legacy_ppt_text(data: bytes) -> str:
    """Slide text plus real speaker notes from a binary PowerPoint deck.

    Slide text is copied verbatim. A Notes record is kept only when it is real
    speaker text: an empty notes page repeats the slide-master placeholder
    prompt, so a note whose text also appears in the slides or the master is
    dropped, as are a bare bullet and an image filename. Never invents text; an
    unreadable deck returns "".
    """
    blob = _PptCfb(data).stream("PowerPoint Document")
    buckets: dict[int, list[str]] = {_PPT_SLIDE: [], _PPT_NOTES: [], _PPT_MASTER: []}
    _ppt_walk(blob, 0, len(blob), buckets)
    slides = buckets[_PPT_SLIDE]
    context = _tidy(" ".join(slides + buckets[_PPT_MASTER])).lower()
    kept = list(slides)
    for raw in buckets[_PPT_NOTES]:
        text = _tidy(raw)
        bare = text.lstrip("*\u2022-\u2013 \t")
        if not bare or _PPT_IMAGE.match(text) or bare.lower() in context:
            continue
        kept.append(raw)
    return _tidy(" ".join(kept))


def _ppt_units(data: bytes) -> list[dict]:
    try:
        text = _legacy_ppt_text(data)
    except ValueError as exc:
        raise _BadArchive(f"legacy_ppt:{exc}") from exc
    return [_unit(text, "ppt")] if text else []
