"""Offline extraction-gap report for the aast-med passage bank. Read-only.

The Index coverage metric counts a Pulse-active ingestible activity as loaded
only when a real passage exists (``ai.moodle_bank.course_roster``). This module
answers the *backlog* question behind the "105 unread" note: for the activities
that are NOT loaded, which extraction technique would be needed to recover a
body, and how many does each technique reach?

It is a measurement, not a feature. It writes nothing, calls no host, changes
no answer, and is not imported by any turn path (locked by
``test_moodle_extraction_gap.py``). Counts are the offline join-level view of
the committed bank; the canvas ``864/969`` figure is the live-Moodle
``mdl_course_modules`` row view and is deliberately not reproduced here.

Technique names are mechanical (a file extension or a remote family), never a
phrase table and never a routing regex. Nothing here is host-domain vocabulary
for ``engine/**``; this module lives with the other medicine seams.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

from ai.moodle_bank import course_roster, listed_shortnames, roster_family

#: Roster families that the coverage metric counts (the same set as
#: ``test_moodle_join_coverage._INGESTIBLE_FAMILIES``).
INGESTIBLE_FAMILIES = frozenset({"file", "url", "page", "label", "book"})

#: A roster row with either status has a real passage behind it.
LOADED_STATUSES = frozenset({"ok", "loaded"})

#: Higher wins when several bank rows collapse to one Moodle module key.
_STATUS_RANK = {"ok": 3, "loaded": 3, "empty": 2, "unavailable": 1, "not_in_pack": 0}

#: The closed set of technique buckets. A row that lands in ``other`` is a bug
#: in the classifier, not a hidden item.
TECHNIQUES = (
    "legacy_ppt",     # .ppt — needs LibreOffice headless → .pptx before any reader.
    "scanned_pdf",    # .pdf with no extractable layer — needs OCR.
    "office_no_text", # .pptx/.pptm/.docx read but empty — notes/vision may deepen it.
    "media",          # .mp4/.mov/.avi — no local text extractor.
    "remote_google",  # Drive/Docs/Slides — a remote body, not an extraction gap.
    "remote_youtube", # YouTube — a remote caption, not an extraction gap.
    "external_web",   # an arbitrary website link — no document extractor at all.
    "c3_gap",         # page/label/book with no stored text (should be empty).
    "file_other",     # a file family the classifier does not recognise.
    "other",          # anything else (must stay 0; asserted by the test).
)

_DOC_RECOVERABLE = ("legacy_ppt", "scanned_pdf")
_REMOTE = ("remote_google", "remote_youtube", "external_web")


@dataclass(frozen=True)
class CourseGap:
    """One listed course's coverage and the technique split of its unread rows."""

    shortname: str
    active: int
    loaded: int
    by_technique: dict[str, int]

    @property
    def unread(self) -> int:
        return self.active - self.loaded

    @property
    def document_recoverable(self) -> int:
        """Unread rows a document reader (conversion or OCR) could reach."""
        return sum(self.by_technique.get(name, 0) for name in _DOC_RECOVERABLE)

    @property
    def remote(self) -> int:
        """Unread rows that are remote bodies or links, not extraction work."""
        return sum(self.by_technique.get(name, 0) for name in _REMOTE)


def technique_for(row: dict) -> str:
    """The extraction technique that would be needed for one roster row."""
    family = roster_family(str(row.get("kind") or ""))
    kind = str(row.get("kind") or "").strip().lower()
    filename = str(row.get("source") or row.get("name") or "")
    if family == "file":
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix == ".ppt":
            return "legacy_ppt"
        if suffix == ".pdf":
            return "scanned_pdf"
        if suffix in {".pptx", ".pptm", ".docx"}:
            return "office_no_text"
        if suffix in {".mp4", ".mov", ".avi"}:
            return "media"
        return "file_other"
    if family == "url":
        if kind == "youtube":
            return "remote_youtube"
        if kind.startswith("google"):
            return "remote_google"
        return "external_web"
    if family in {"page", "label", "book"}:
        return "c3_gap"
    return "other"


def _unread_rows(shortname: str) -> list[dict]:
    """One representative roster row per unread ingestible join key.

    A module can carry several bank rows that collapse to one key; the coverage
    metric dedupes by key, so this does too. The representative is the best
    status for the key, matching ``test_moodle_join_coverage._coverage``.
    """
    best: dict[str, dict] = {}
    for row in course_roster(shortname)["activities"]:
        key = str(row.get("key") or "")
        if not key or roster_family(str(row.get("kind") or "")) not in INGESTIBLE_FAMILIES:
            continue
        status = str(row.get("status") or "empty")
        current = best.get(key)
        if current is None or _STATUS_RANK.get(status, -1) > _STATUS_RANK.get(
            str(current.get("status") or "empty"), -1
        ):
            best[key] = row
    return [row for row in best.values() if str(row.get("status") or "") not in LOADED_STATUSES]


def course_gap(shortname: str) -> CourseGap:
    """Coverage and technique split for one listed course."""
    name = str(shortname or "").strip()
    if name not in listed_shortnames():
        return CourseGap(shortname=name, active=0, loaded=0, by_technique={})
    best: dict[str, dict] = {}
    for row in course_roster(name)["activities"]:
        key = str(row.get("key") or "")
        if not key or roster_family(str(row.get("kind") or "")) not in INGESTIBLE_FAMILIES:
            continue
        status = str(row.get("status") or "empty")
        current = best.get(key)
        if current is None or _STATUS_RANK.get(status, -1) > _STATUS_RANK.get(
            str(current.get("status") or "empty"), -1
        ):
            best[key] = row
    loaded = sum(
        1 for row in best.values() if str(row.get("status") or "") in LOADED_STATUSES
    )
    counts: dict[str, int] = {}
    for row in _unread_rows(name):
        name_of = technique_for(row)
        counts[name_of] = counts.get(name_of, 0) + 1
    return CourseGap(shortname=name, active=len(best), loaded=loaded, by_technique=counts)


def report() -> tuple[CourseGap, ...]:
    """One ``CourseGap`` per listed course, sorted by shortname."""
    return tuple(course_gap(shortname) for shortname in sorted(listed_shortnames()))


def totals(gaps: Iterable[CourseGap]) -> dict[str, int]:
    """Technique counts summed across courses. Only named techniques appear."""
    out: dict[str, int] = {}
    for gap in gaps:
        for name, value in gap.by_technique.items():
            out[name] = out.get(name, 0) + value
    return out
