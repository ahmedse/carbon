"""Lock the extraction-gap measurement with no behavior change.

The report is a read-only count of the medicine bank's unread Pulse-active
ingestible activities, split by the extraction technique each would need. These
tests pin the classification rule and the honesty of the total, and prove the
module is inert (not imported by a turn path, Django-free, writes nothing).

No count here is a claim about a rung. The 105 unread note on the canvas is the
live-Moodle row view; this is the offline join-level view of the committed bank.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ai.moodle_bank import course_roster, listed_shortnames, roster_family
from ai.moodle_extraction_gap import (
    INGESTIBLE_FAMILIES,
    LOADED_STATUSES,
    TECHNIQUES,
    course_gap,
    report,
    technique_for,
    totals,
)

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent

_STATUS_RANK = {"ok": 3, "loaded": 3, "empty": 2, "unavailable": 1, "not_in_pack": 0}


def _independent_counts(shortname: str) -> tuple[int, int]:
    """Recompute active / loaded exactly as the coverage test does."""
    best: dict[str, bool] = {}
    for row in course_roster(shortname)["activities"]:
        key = str(row.get("key") or "")
        if not key or roster_family(str(row.get("kind") or "")) not in INGESTIBLE_FAMILIES:
            continue
        is_loaded = str(row.get("status") or "") in LOADED_STATUSES
        best[key] = bool(best.get(key)) or is_loaded
    return len(best), sum(1 for value in best.values() if value)


def _independent_statuses(shortname: str) -> dict[str, str]:
    best: dict[str, str] = {}
    for row in course_roster(shortname)["activities"]:
        key = str(row.get("key") or "")
        if not key or roster_family(str(row.get("kind") or "")) not in INGESTIBLE_FAMILIES:
            continue
        status = str(row.get("status") or "empty")
        if _STATUS_RANK.get(status, -1) > _STATUS_RANK.get(best.get(key, ""), -1):
            best[key] = status
    return best


def test_report_covers_every_listed_course_once():
    gaps = report()
    assert [gap.shortname for gap in gaps] == sorted(listed_shortnames())
    assert len(gaps) == len(listed_shortnames())


def test_active_loaded_unread_match_the_coverage_join():
    for gap in report():
        active, loaded = _independent_counts(gap.shortname)
        assert (gap.active, gap.loaded) == (active, loaded), gap.shortname
        assert gap.unread == active - loaded, gap.shortname


def test_every_unread_row_lands_in_exactly_one_named_technique():
    for gap in report():
        assert sum(gap.by_technique.values()) == gap.unread, gap.shortname
        assert set(gap.by_technique) <= set(TECHNIQUES), gap.shortname
        assert "other" not in gap.by_technique, gap.shortname


def test_technique_classifier_is_a_total_function_of_one_roster_row():
    for shortname in sorted(listed_shortnames()):
        statuses = _independent_statuses(shortname)
        unread_keys = {key for key, status in statuses.items() if status not in LOADED_STATUSES}
        seen: dict[str, str] = {}
        for row in course_roster(shortname)["activities"]:
            key = str(row.get("key") or "")
            if key not in unread_keys:
                continue
            seen.setdefault(key, technique_for(row))
        assert set(seen) == unread_keys, shortname
        for technique in seen.values():
            assert technique in TECHNIQUES


def test_document_recovery_is_legacy_ppt_plus_scanned_pdf():
    for gap in report():
        expected = gap.by_technique.get("legacy_ppt", 0) + gap.by_technique.get("scanned_pdf", 0)
        assert gap.document_recoverable == expected, gap.shortname
        # Remote rows are never counted as document recovery.
        assert gap.document_recoverable + gap.remote <= gap.unread, gap.shortname


def test_the_gap_is_not_vacuous():
    all_totals = totals(report())
    assert sum(all_totals.values()) == sum(gap.unread for gap in report())
    # The 9 legacy .ppt decks were read on 2026-10-03 (see the B1 line), so the
    # remaining document-recoverable row is the scanned Arabic PDF, which still
    # needs OCR. The backlog is honest about what document extraction cannot
    # reach: most unread rows are remote / media, not a document-reader gap.
    assert all_totals.get("scanned_pdf", 0) >= 1
    assert all_totals.get("remote_google", 0) + all_totals.get("remote_youtube", 0) > 0


def test_report_is_deterministic():
    assert report() == report()
    assert totals(report()) == totals(report())


def test_report_leaves_the_bank_and_gold_untouched():
    watched = [
        REPO / "domain_packs" / "aast-med" / "bank" / "course-meat-13" / "NMD1103.jsonl",
        REPO / "domain_packs" / "aast-med" / "bank" / "course-keys-13" / "MED520.jsonl",
        REPO / "domain_packs" / "aast-med" / "gold" / "l5.yaml",
    ]
    before = {path: path.read_bytes() for path in watched}
    report()
    for path, blob in before.items():
        assert path.read_bytes() == blob, path


def test_module_is_not_imported_by_a_turn_path():
    seams = [
        BACKEND / "ai" / "moodle_host.py",
        BACKEND / "ai" / "moodle_page.py",
        BACKEND / "ai" / "moodle_host_api.py",
        BACKEND / "ai" / "moodle_bank.py",
        BACKEND / "ai" / "moodle_integrity.py",
        BACKEND / "ai" / "moodle_refusals.py",
        BACKEND / "ai" / "moodle_onboarding.py",
    ]
    for path in seams:
        assert "moodle_extraction_gap" not in path.read_text(encoding="utf-8"), path
    for path in (BACKEND / "ai" / "engine").rglob("*.py"):
        assert "moodle_extraction_gap" not in path.read_text(encoding="utf-8"), path


def test_report_is_django_free():
    code = (
        "import sys, ai.moodle_extraction_gap; "
        "assert 'django' not in sys.modules, 'extraction gap pulled Django in'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
