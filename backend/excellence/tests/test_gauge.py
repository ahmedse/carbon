"""Gauge dry-run (``--no-db``) against the committed manifests and the repo collector."""
from __future__ import annotations

import json

from excellence import gauge
from excellence.catalogue import load_catalogue
from excellence.collectors import run_collectors


def test_file_contains_fails_when_the_marker_is_absent() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_repo

    check = Check(
        id="T-CONTAINS", title="marker", dimension="correct", rank=2, collector="repo",
        probe={
            "type": "file_contains",
            "file": "docs/migration/DATA-MIGRATION-STUDIO.md",
            "text": "NOT-A-REAL-MARKER",
        },
    )
    subject = Subject(id="platform.module.inbound", kind="module", title="inbound", tier="platform")
    drafts = collect_repo(None, [(check, subject)], {})
    assert drafts[0].result == "failed"
    assert drafts[0].detail["missing"] == "NOT-A-REAL-MARKER"


def test_def_contains_does_not_see_another_function() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_repo

    check = Check(
        id="T-DEF", title="body", dimension="reliable", rank=3, collector="repo",
        probe={
            "type": "def_contains",
            "file": "backend/inbound/tests/test_pipe.py",
            "def": "test_unknown_target_400",
            "text": "STATUS_SMOKED",
        },
    )
    subject = Subject(id="platform.module.inbound", kind="module", title="inbound", tier="platform")
    drafts = collect_repo(None, [(check, subject)], {})
    assert drafts[0].result == "failed"
    assert drafts[0].detail["missing"] == "STATUS_SMOKED"


def test_pytest_nodes_reject_a_parent_path() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_pytest

    check = Check(
        id="T-NODE", title="nodes", dimension="specified", rank=4, collector="pytest",
        probe={"type": "pytest_app", "app": "inbound-criteria", "nodes": ["../outside.py"]},
    )
    subject = Subject(id="platform.module.inbound", kind="module", title="inbound", tier="platform")
    drafts = collect_pytest(None, [(check, subject)], {"run_apps": {"inbound-criteria"}})
    assert drafts[0].result == "failed"
    assert "relative" in drafts[0].detail["why"]


def test_forbidden_import_fails_when_the_name_is_imported() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_repo

    check = Check(
        id="T-BAN", title="ban", dimension="maintainable", rank=3, collector="repo",
        probe={
            "type": "forbidden_import",
            "root": "backend/inbound/tests",
            "names": ["pytest"],
            "skip_tests": False,
        },
    )
    subject = Subject(id="platform.module.inbound", kind="module", title="inbound", tier="platform")
    drafts = collect_repo(None, [(check, subject)], {})
    assert drafts[0].result == "failed"
    assert drafts[0].detail["offenders"]


def test_repo_collector_declares_platform_modules(capsys) -> None:
    cat = load_catalogue()
    drafts = run_collectors(cat, cat.subjects_in("platform"), only={"repo"})
    by_check = {(d.subject_id, d.check_id): d.result for d in drafts}
    assert by_check[("platform.module.accounts", "PLAT-GOV-01")] == "passed"
    assert by_check[("platform.module.accounts", "PLAT-GOV-02")] == "passed"
    assert by_check[("platform.module.accounts", "PLAT-COR-01")] == "passed"
    # regulations now has an owner; still no tests package → COR fail, not unknown
    assert by_check[("platform.module.regulations", "PLAT-GOV-01")] == "passed"
    assert by_check[("platform.module.regulations", "PLAT-COR-01")] == "failed"
    assert all(d.result in {"passed", "failed"} for d in drafts), "repo probes never answer unknown"


def test_gauge_no_db_json_reports_every_subject(capsys) -> None:
    rc = gauge.main(["--tier", "platform", "--collect", "--only", "repo", "--no-db", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["problems"] == []
    ids = {row["subject_id"] for row in out["subjects"]}
    assert "platform.module.excellence" in ids
    excellence_row = next(r for r in out["subjects"] if r["subject_id"] == "platform.module.excellence")
    # Rank-1 governed passes on repo. Secure has a rank-1 check, so it is bound, not open.
    assert excellence_row["level"] == 0
    assert "secure:1" not in excellence_row["open"]
    assert "specified:1" in excellence_row["open"]


def test_domain_rank1_covers_specified_correct_reliable(capsys) -> None:
    rc = gauge.main(["--tier", "nibras", "--collect", "--only", "repo", "--no-db", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    people = next(r for r in out["subjects"] if r["subject_id"] == "nibras.module.people")
    assert people["dimensions"]["specified"] >= 1
    assert people["dimensions"]["correct"] >= 1
    assert people["dimensions"]["reliable"] >= 1
    assert people["dimensions"]["observed"] >= 1
    assert people["dimensions"]["maintainable"] >= 1


def test_platform_rank1_collectors_bind_secure_performant_usable(capsys) -> None:
    rc = gauge.main([
        "--tier", "platform", "--collect", "--only", "rbac,budget,design_lint", "--no-db", "--json",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    row = next(r for r in out["subjects"] if r["subject_id"] == "platform.module.accounts")
    assert row["dimensions"]["secure"] >= 1
    assert row["dimensions"]["performant"] >= 1
    assert row["dimensions"]["usable"] >= 1


def test_pulse_rank1_binds_secure_performant_usable(capsys) -> None:
    rc = gauge.main([
        "--tier", "pulse", "--collect", "--only", "repo,rbac,budget,design_lint", "--no-db", "--json",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    core = next(r for r in out["subjects"] if r["subject_id"] == "pulse.engine.core")
    assert core["dimensions"]["secure"] >= 1
    assert core["dimensions"]["performant"] >= 1
    assert core["dimensions"]["usable"] >= 1
    assert core["level"] == 0  # specified, correct, reliable, observed still open at rank 1


def test_runtime_window_is_unknown_until_a_loopback_sample(capsys) -> None:
    cat = load_catalogue()
    subject = cat.subjects["platform.module.accounts"]
    quiet = run_collectors(cat, [subject], only={"runtime"})
    assert {d.check_id for d in quiet} >= {"PLAT-PRF-05", "PLAT-REL-05", "PLAT-SEC-05"}
    assert all(d.result == "unknown" and d.evidence_class == "configured" for d in quiet)

    def fetch(_url: str) -> tuple[int, str]:
        return 200, "ok"

    live = run_collectors(cat, [subject], only={"runtime"}, ctx={
        "run_runtime": "http://127.0.0.1:8009",
        "runtime_fetch": fetch,
    })
    by_id = {d.check_id: d for d in live}
    assert by_id["PLAT-PRF-05"].result == "passed"
    assert by_id["PLAT-PRF-05"].evidence_class == "enforcement-verified"
    assert by_id["PLAT-REL-05"].result == "passed"
    assert by_id["PLAT-SEC-05"].result == "passed"

    def failing(_url: str) -> tuple[int, str]:
        return 500, ""

    bad = run_collectors(cat, [subject], only={"runtime"}, ctx={
        "run_runtime": "http://127.0.0.1:8009",
        "runtime_fetch": failing,
    })
    assert next(d for d in bad if d.check_id == "PLAT-REL-05").result == "failed"
    try:
        run_collectors(cat, [subject], only={"runtime"}, ctx={"run_runtime": "http://example.com"})
    except Exception:
        raise AssertionError("a non-loopback origin must fail the check, not raise")
    remote = run_collectors(cat, [subject], only={"runtime"}, ctx={"run_runtime": "http://example.com"})
    assert all(d.result == "failed" for d in remote)


def test_gauge_text_renders(capsys) -> None:
    rc = gauge.main(["--tier", "pulse", "--no-db"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "[pulse]" in text and "pulse.agent.planner" in text


def test_spec_window_fails_when_code_moves_without_the_spec() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_repo

    check = Check(
        id="T-SPEC", title="window", dimension="specified", rank=5, collector="repo",
        probe={
            "type": "spec_window",
            "code": ["backend/emissions/onboarding_o1.py"],
            "paths": ["docs/spec.md"],
        },
    )
    subject = Subject(id="s", kind="journey", title="s", tier="carbon")
    missed = collect_repo(None, [(check, subject)], {"spec_names": ["backend/emissions/onboarding_o1.py"]})
    assert missed[0].result == "failed"
    assert missed[0].evidence_class == "enforcement-verified"
    both = collect_repo(None, [(check, subject)], {"spec_names": [
        "backend/emissions/onboarding_o1.py", "docs/spec.md",
    ]})
    assert both[0].result == "passed"
    quiet = collect_repo(None, [(check, subject)], {"spec_names": ["docs/other.md"]})
    assert quiet[0].result == "passed"
    assert quiet[0].detail["no_code_diff"] is True


def test_rtl_a11y_needs_both_the_i18n_command_and_the_spec() -> None:
    from excellence.catalogue import Check, Subject
    from excellence.collectors import collect_playwright

    check = Check(
        id="T-RTL", title="rtl", dimension="usable", rank=5, collector="playwright",
        probe={
            "type": "rtl_a11y",
            "file": "carbon-frontend/e2e/journeys/journey-o1-onboarding-ar.spec.ts",
            "script": "npm run i18n:check",
        },
    )
    subject = Subject(id="s", kind="journey", title="s", tier="carbon")
    quiet = collect_playwright(None, [(check, subject)], {})
    assert quiet[0].result == "unknown"
    missed = collect_playwright(None, [(check, subject)], {
        "run_playwright": {check.probe["file"]},
        "playwright_i18n_exit": 1,
    })
    assert missed[0].result == "failed"
    assert missed[0].evidence_class == "enforcement-verified"
    both = collect_playwright(None, [(check, subject)], {
        "run_playwright": {check.probe["file"]},
        "playwright_i18n_exit": 0,
        "playwright_spec_exit": 0,
    })
    assert both[0].result == "passed"
    assert both[0].evidence_class == "enforcement-verified"
