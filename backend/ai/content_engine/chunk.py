"""Structure-aware, overlapping chunker for Pulse content.

This module is intentionally standalone and dependency-free. It owns ONLY the
chunking concern; it never imports readers, the engine, or any turn path.

Frozen interface (plain dicts, no shared types module)
------------------------------------------------------
TextUnit input::

    {
        "text": str,
        "kind": str,              # e.g. "heading" | "paragraph" | "slide" | "question"
        "source_ref": str,
        "locator": str,           # structural locator inside the source
        "citable": bool,
        "course": str | None,
        "activity_ref": str | None,
        "status": str,
    }

Chunk output::

    {
        "chunk_id": str,          # STABLE, content-addressed (see _chunk_id)
        "course": str,
        "section": str,
        "activity_ref": str,
        "source_ref": str,
        "locator": str,
        "ordinal": int,
        "text": str,
        "char_start": int,        # offset inside the unit's text (overlap-aware)
        "char_end": int,
        "prev_id": str | None,
        "next_id": str | None,
    }

The chunk_id is content-addressed and reproducible::

    f"{course}:{activity_ref}:{kind}:{locator}:{ordinal}"

No uuid and no run-varying hash — the same input always yields the same ids.
"""

from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# Chunking parameters (explicit, deterministic, no tokenizer / no network)
# ─────────────────────────────────────────────────────────────────────────────

# Soft ceiling for a single window, measured in CHARACTERS (not tokens) so the
# chunker never needs a tokenizer or any external service.
TARGET_CHARS = 1200

# Fraction of a window shared with the next window inside the same structural
# unit. 0.15 -> ~180 chars of overlap at the default TARGET_CHARS. Overlap is
# always measured in whole sentences, never mid-sentence or mid-word.
OVERLAP_RATIO = 0.15

# A single "sentence" longer than TARGET_CHARS is further split at word
# boundaries so one giant run-on cannot produce an unbounded chunk.
MAX_SENTENCE_CHARS = TARGET_CHARS

# Structural kinds that start a new section. Purely structural labels — these
# are not routing words and are never used to route a turn.
_SECTION_KINDS = frozenset({"heading", "section", "title"})

# Sentence terminators (English + Arabic question mark) and newlines. A run of
# terminators plus trailing whitespace ends a sentence; the whitespace stays
# with the sentence so char offsets remain contiguous over the unit.
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?؟\n]+[ \t]*")

# Word run used only to split an over-long sentence without slicing a word.
_WORD_RE = re.compile(r"\S+")


def _chunk_id(course: str, activity_ref: str, kind: str, locator: str, ordinal: int) -> str:
    """Stable content-addressed id. Pure function of the unit identity/order."""
    return f"{course}:{activity_ref}:{kind}:{locator}:{ordinal}"


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return contiguous [start, end) sentence spans covering ``text``.

    Boundaries fall on terminator runs + trailing whitespace (or newlines), so
    every span is a whole number of sentences and offsets tile the text.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_BOUNDARY_RE.finditer(text):
        spans.append((start, m.end()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return [(s, e) for (s, e) in spans if e > s]


def _split_long_span(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split one over-long span at whitespace so no piece exceeds the target.

    Word boundaries are respected: a piece always ends on whitespace or at the
    span end, never in the middle of a word.
    """
    pieces: list[tuple[int, int]] = []
    piece_start = start
    last_boundary = start
    for m in _WORD_RE.finditer(text, start, end):
        # If adding this word would blow the cap, cut at the previous boundary.
        if m.end() - piece_start > TARGET_CHARS and last_boundary > piece_start:
            pieces.append((piece_start, last_boundary))
            piece_start = last_boundary
        last_boundary = m.end()
    if piece_start < end:
        pieces.append((piece_start, end))
    return pieces


def _windows(text: str) -> list[tuple[int, int]]:
    """Sentence-aligned, overlapping windows over one unit's text.

    Never slices mid-sentence or mid-word. Consecutive windows overlap by about
    ``OVERLAP_RATIO`` of the target, measured in whole trailing sentences.
    """
    if not text:
        return []

    sentences: list[tuple[int, int]] = []
    for s, e in _sentence_spans(text):
        if e - s <= MAX_SENTENCE_CHARS:
            sentences.append((s, e))
        else:
            sentences.extend(_split_long_span(text, s, e))
    if not sentences:  # pragma: no cover - defensive
        sentences = [(0, len(text))]

    overlap_target = int(TARGET_CHARS * OVERLAP_RATIO)
    windows: list[tuple[int, int]] = []
    i = 0
    n = len(sentences)
    while i < n:
        start = sentences[i][0]
        end = sentences[i][1]
        j = i
        while j + 1 < n and (sentences[j + 1][1] - start) <= TARGET_CHARS:
            j += 1
            end = sentences[j][1]
        windows.append((start, end))
        if j + 1 >= n:
            break
        # Pick the latest sentence boundary whose tail still meets the overlap
        # target, so the next window shares ~overlap_target chars with this one.
        next_i = i + 1
        for k in range(i + 1, j + 1):
            if end - sentences[k][0] >= overlap_target:
                next_i = k
            else:
                break
        i = next_i
    return windows


def chunk_units(units: list[dict]) -> list[dict]:
    """Chunk ``units`` in reading order into stable, linked chunk dicts.

    Structure is applied first: a heading/section/title unit updates the
    running ``section`` label; every unit is then windowed within its own text.
    ``prev_id`` / ``next_id`` link chunks across the whole emitted run.
    """
    chunks: list[dict] = []
    current_section = ""

    for unit in units:
        text = unit.get("text") or ""
        kind = unit.get("kind") or ""
        locator = unit.get("locator") or ""
        course = unit.get("course") or ""
        activity_ref = unit.get("activity_ref") or ""
        source_ref = unit.get("source_ref") or ""

        if kind in _SECTION_KINDS:
            current_section = text.strip().splitlines()[0] if text.strip() else ""

        for ordinal, (char_start, char_end) in enumerate(_windows(text)):
            chunk_text = text[char_start:char_end]
            if not chunk_text:
                continue
            chunks.append(
                {
                    "chunk_id": _chunk_id(course, activity_ref, kind, locator, ordinal),
                    "course": course,
                    "section": current_section,
                    "activity_ref": activity_ref,
                    "source_ref": source_ref,
                    "locator": locator,
                    "ordinal": ordinal,
                    "text": chunk_text,
                    "char_start": char_start,
                    "char_end": char_end,
                    "prev_id": None,
                    "next_id": None,
                }
            )

    for idx, chunk in enumerate(chunks):
        chunk["prev_id"] = chunks[idx - 1]["chunk_id"] if idx > 0 else None
        chunk["next_id"] = chunks[idx + 1]["chunk_id"] if idx + 1 < len(chunks) else None

    return chunks


__all__ = ["TARGET_CHARS", "OVERLAP_RATIO", "MAX_SENTENCE_CHARS", "chunk_units", "_chunk_id"]
