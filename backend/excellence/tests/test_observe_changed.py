"""Changed-subject mapping and observe collector (ADR-0051 P3–P4)."""
from __future__ import annotations

from excellence.catalogue import Catalogue, Subject, load_catalogue
from excellence.changed import subjects_touched
from excellence.collectors import collect_observe, run_collectors


def test_subjects_touched_by_path_prefix() -> None:
    cat = load_catalogue()
    hit = subjects_touched(cat, {"backend/accounts/models.py", "README.md"})
    ids = {s.id for s in hit}
    assert "platform.module.accounts" in ids
    assert "platform.module.core" not in ids


def test_observe_evaluator_self_check_passes() -> None:
    cat = load_catalogue()
    subject = cat.subjects["platform.repo"]
    checks = [c for c in cat.checks_for(subject) if c.id == "PLAT-OBS-01"]
    assert checks
    drafts = collect_observe(cat, [(checks[0], subject)], {})
    assert drafts[0].result == "passed"
    assert drafts[0].evidence_class == "fault-demonstrated"


def test_observe_ci_and_runbook_on_platform_repo() -> None:
    cat = load_catalogue()
    drafts = run_collectors(cat, [cat.subjects["platform.repo"]], only={"observe"})
    by_id = {d.check_id: d for d in drafts}
    assert by_id["PLAT-REL-01"].result == "passed"
    assert by_id["PLAT-REL-02"].result == "passed"
    assert by_id["PLAT-OBS-01"].result == "passed"


def test_gauge_changed_empty_is_clean(capsys) -> None:
    from excellence import gauge

    # A bogus base that yields no paths → empty subjects → exit 0 under --gate
    rc = gauge.main(["--changed", "HEAD", "--gate", "--no-db", "--json"])
    # HEAD...HEAD is empty → clean
    assert rc == 0
