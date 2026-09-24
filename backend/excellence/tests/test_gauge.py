"""Gauge dry-run (``--no-db``) against the committed manifests and the repo collector."""
from __future__ import annotations

import json

from excellence import gauge
from excellence.catalogue import load_catalogue
from excellence.collectors import run_collectors


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
    # repo probes alone: rank 1 (owner, paths) passes; rank 2 ADR passes; rank 3 tests present;
    # rank 4 pytest is unmeasured → L3
    assert excellence_row["level"] == 3
    assert excellence_row["next"] == ["PLAT-COR-02"]


def test_gauge_text_renders(capsys) -> None:
    rc = gauge.main(["--tier", "pulse", "--no-db"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "[pulse]" in text and "pulse.agent.planner" in text
