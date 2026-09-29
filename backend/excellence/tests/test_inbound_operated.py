"""Rank-5 inbound collector. Missing evidence is unknown. A file read is not a pass."""
from __future__ import annotations

import json
from pathlib import Path

from excellence.catalogue import Check, Subject, load_catalogue
from excellence.inbound_operated import collect_inbound_operated

SUBJECT = Subject(id="platform.module.inbound", kind="module", title="inbound", tier="platform")


def _pair(check_id: str, **probe):
    real = load_catalogue().checks[check_id]
    merged = {**real.probe, **probe}
    check = Check(
        id=real.id, title=real.title, dimension=real.dimension, rank=real.rank,
        collector=real.collector, probe=merged, solution=real.solution, source=real.source,
    )
    return check


def _one(check_id: str, ctx: dict, **probe):
    check = _pair(check_id, **probe)
    drafts = collect_inbound_operated(None, [(check, SUBJECT)], ctx)
    return drafts[0]


def test_missing_nightly_workflow_is_unknown_and_does_not_run_playwright() -> None:
    called: list[str] = []
    draft = _one("INBOUND-COR-05", {"inbound_cmd": lambda script: called.append(script) or 0})
    assert draft.result == "unknown"
    assert called == []
    assert "inbound-nightly.yml" in draft.detail["why"]


def test_scheduled_success_for_this_commit_passes(tmp_path: Path) -> None:
    workflow = _write_nightly(tmp_path)
    draft = _one(
        "INBOUND-COR-05",
        {
            "head": "abc",
            "inbound_gh": lambda args: (0, json.dumps([
                {"conclusion": "success", "event": "schedule", "headSha": "abc", "databaseId": 1},
            ])),
        },
        workflow=str(workflow),
    )
    assert draft.result == "passed"
    assert draft.evidence_class == "enforcement-verified"


def test_yaml_only_ci_is_unknown() -> None:
    draft = _one("INBOUND-SEC-06", {"inbound_gh": lambda args: (1, "no auth")})
    assert draft.result == "unknown"
    assert draft.result != "passed"


def test_red_ci_run_fails_secure_and_governed() -> None:
    ctx = {
        "head": "abc",
        "inbound_gh": lambda args: (0, json.dumps([
            {"conclusion": "failure", "event": "push", "headSha": "abc", "databaseId": 9},
        ])),
    }
    secure = _one("INBOUND-SEC-06", ctx)
    governed = _one("INBOUND-GOV-05", ctx)
    assert secure.result == "failed"
    assert governed.result == "failed"
    assert secure.evidence_class == "enforcement-verified"


def test_green_ci_with_full_pytest_passes() -> None:
    ctx = {
        "head": "abc",
        "inbound_gh": lambda args: (0, json.dumps([
            {"conclusion": "success", "event": "push", "headSha": "abc", "databaseId": 3},
        ])),
    }
    draft = _one("INBOUND-SEC-06", ctx)
    assert draft.result == "passed"
    assert draft.evidence_class == "enforcement-verified"


def test_pytest_ignore_inbound_fails_even_when_ci_is_green(tmp_path: Path) -> None:
    workflow = _write_workflow(tmp_path, "python -m pytest --ignore=inbound")
    draft = _one(
        "INBOUND-SEC-06",
        {"head": "abc", "inbound_gh": lambda args: (0, json.dumps([
            {"conclusion": "success", "event": "push", "headSha": "abc", "databaseId": 4},
        ]))},
        workflow=str(workflow),
    )
    assert draft.result == "failed"
    assert "ignores" in draft.detail["why"]


def test_missing_series_is_unknown() -> None:
    draft = _one("INBOUND-OBS-05", {})
    assert draft.result == "unknown"
    assert draft.evidence_class == "unknown"


def test_series_mtime_without_a_matching_envelope_fails(tmp_path: Path) -> None:
    path = tmp_path / "series.json"
    path.write_text(json.dumps({
        "schema": 1,
        "rows": [{
            "date": "2026-09-29", "batch_id": 6, "status": "committed",
            "target_key": "people.leave_history",
            "insert": 1, "update": 0, "skip": 0, "reject": 0,
        }],
    }), encoding="utf-8")
    draft = _one(
        "INBOUND-OBS-05",
        {"inbound_batches": {6: {"smoke": {"insert": 0, "update": 0, "skip": 0, "reject": 1}}}},
        file=str(path),
    )
    assert draft.result == "failed"
    assert "insert" in draft.detail["why"]


def test_series_matching_the_envelope_passes(tmp_path: Path) -> None:
    path = tmp_path / "series.json"
    path.write_text(json.dumps({
        "schema": 1,
        "rows": [{
            "date": "2026-09-29", "batch_id": 6, "status": "committed",
            "target_key": "people.leave_history",
            "insert": 1, "update": 0, "skip": 0, "reject": 1,
        }],
    }), encoding="utf-8")
    draft = _one(
        "INBOUND-OBS-05",
        {"inbound_batches": {6: {"smoke": {"insert": 1, "update": 0, "skip": 0, "reject": 1}}}},
        file=str(path),
    )
    assert draft.result == "passed"
    assert draft.evidence_class == "enforcement-verified"


def test_no_db_cannot_pass_the_series(tmp_path: Path) -> None:
    path = _series_file(tmp_path)
    draft = _one(
        "INBOUND-OBS-05",
        {"no_db": True},
        file=str(path),
    )
    assert draft.result == "unknown"
    assert "no-db" in draft.detail["why"]


def test_tracked_series_file_fails(tmp_path: Path) -> None:
    path = _series_file(tmp_path)
    draft = _one(
        "INBOUND-OBS-05",
        {
            "inbound_tracked": True,
            "inbound_batches": {6: {"smoke": {"insert": 1, "update": 0, "skip": 0, "reject": 1}}},
        },
        file=str(path),
    )
    assert draft.result == "failed"
    assert "tracked" in draft.detail["why"]


def test_unset_password_does_not_call_http() -> None:
    called: list[str] = []

    def http(method, url, token, payload):
        called.append(url)
        return 200, {}

    draft = _one("INBOUND-PRF-06", {"inbound_http": http, "inbound_environ": {}})
    assert draft.result == "unknown"
    assert called == []


def test_health_path_is_rejected() -> None:
    draft = _one(
        "INBOUND-PRF-06",
        {"inbound_environ": {"NIBRAS_HR_PASSWORD": "secret"}, "inbound_http": lambda *a: (200, {"sample": []})},
        path="/carbon-api/health/",
    )
    assert draft.result == "failed"
    assert "health" in draft.detail["why"]


def test_sample_longer_than_20_fails() -> None:
    draft = _one("INBOUND-PRF-06", _http_ctx(sample=list(range(21)), row_count=21))
    assert draft.result == "failed"
    assert draft.detail["sample_len"] == 21


def test_sample_of_one_passes() -> None:
    draft = _one("INBOUND-PRF-06", _http_ctx(sample=[{"row": 1}], row_count=1))
    assert draft.result == "passed"
    assert draft.evidence_class == "enforcement-verified"
    assert draft.detail["batch_id"] == 6


def test_i18n_exit_zero_without_rtl_is_unknown() -> None:
    draft = _one("INBOUND-USE-06", {"inbound_cmd": lambda script: 0})
    assert draft.result == "unknown"
    assert "alone" in draft.detail["why"]


def test_named_spec_run_passes_without_the_seam() -> None:
    draft = _one("INBOUND-USE-06", {
        "run_playwright": {"carbon-frontend/e2e/journeys/journey-dms-people-door-ar.spec.ts"},
        "inbound_cmd": lambda script: 0,
        "inbound_spec_exit": 0,
    })
    assert draft.result == "passed"
    assert draft.source.endswith("journey-dms-people-door-ar.spec.ts")


def test_named_spec_run_fails_when_playwright_fails() -> None:
    draft = _one("INBOUND-USE-06", {
        "run_playwright": {"carbon-frontend/e2e/journeys/journey-dms-people-door-ar.spec.ts"},
        "inbound_cmd": lambda script: 0,
        "inbound_spec_exit": 1,
    })
    assert draft.result == "failed"


def test_i18n_and_arabic_rtl_passes() -> None:
    draft = _one("INBOUND-USE-06", {
        "inbound_cmd": lambda script: 0,
        "inbound_rtl": {
            "dir": "rtl",
            "eye_name": "فتح الدفعة",
            "primary_name": "استيراد جديد",
            "search_placeholder": "بحث الدفعات",
        },
    })
    assert draft.result == "passed"
    assert draft.evidence_class == "enforcement-verified"


def test_code_diff_without_the_studio_doc_fails() -> None:
    draft = _one("INBOUND-SPC-11", {"inbound_git": _git(["backend/inbound/views.py"])})
    assert draft.result == "failed"


def test_no_inbound_code_diff_passes() -> None:
    draft = _one("INBOUND-SPC-11", {"inbound_git": _git(["docs/other.md"])})
    assert draft.result == "passed"
    assert draft.detail["no_code_diff"] is True


def test_ubuntu_latest_nightly_fails_before_github(tmp_path: Path) -> None:
    called: list[str] = []
    workflow = _write_nightly(tmp_path)
    workflow.write_text(workflow.read_text(encoding="utf-8") + "runs-on: ubuntu-latest\n", encoding="utf-8")
    draft = _one(
        "INBOUND-COR-05",
        {"head": "abc", "inbound_gh": lambda args: called.append("gh") or (0, "[]")},
        workflow=str(workflow),
    )
    assert draft.result == "failed"
    assert "ubuntu-latest" in draft.detail["why"]
    assert called == []


def test_nightly_with_the_wrong_cron_fails_and_does_not_run_playwright(tmp_path: Path) -> None:
    called: list[str] = []
    workflow = tmp_path / "workflow.yml"
    workflow.write_text("on:\n  schedule:\n    - cron: '0 2 * * *'\n", encoding="utf-8")
    draft = _one(
        "INBOUND-COR-05",
        {"inbound_cmd": lambda script: called.append(script) or 0, "head": "abc"},
        workflow=str(workflow),
    )
    assert draft.result == "failed"
    assert draft.detail["why"] == "cron mismatch"
    assert called == []


def test_ratchet_against_real_ci_without_a_run_is_unknown() -> None:
    draft = _one("INBOUND-MNT-05", {"inbound_gh": lambda args: (1, "")})
    assert draft.result == "unknown"
    assert "gh" in draft.detail["why"]


def test_ratchet_shorthand_without_the_real_lines_fails(tmp_path: Path) -> None:
    workflow = _write_workflow(tmp_path, "python -m excellence.gauge --gate --changed")
    draft = _one(
        "INBOUND-MNT-05",
        {"head": "abc", "inbound_gh": lambda args: (0, json.dumps([
            {"conclusion": "success", "event": "push", "headSha": "abc", "databaseId": 1},
        ]))},
        workflow=str(workflow),
        step="Run tests",
    )
    assert draft.result == "failed"
    assert "substrings" in draft.detail["why"]


def test_missing_scheduled_run_is_unknown(tmp_path: Path) -> None:
    workflow = _write_workflow(tmp_path, "nightly")
    draft = _one(
        "INBOUND-REL-06",
        {"inbound_gh": lambda args: (0, "[]")},
        workflow=str(workflow),
    )
    assert draft.result == "unknown"


def _series_file(directory: Path) -> Path:
    path = directory / "series.json"
    path.write_text(json.dumps({
        "schema": 1,
        "rows": [{
            "date": "2026-09-29", "batch_id": 6, "status": "committed",
            "target_key": "people.leave_history",
            "insert": 1, "update": 0, "skip": 0, "reject": 1,
        }],
    }), encoding="utf-8")
    return path


def _git(names: list[str]):
    def run(args: list[str]) -> tuple[int, str]:
        if args[:2] == ["rev-parse", "HEAD"]:
            return 0, "abc\n"
        if args[:2] == ["diff", "--name-only"]:
            return 0, "\n".join(names) + "\n"
        return 1, ""

    return run


def _http_ctx(*, sample: list, row_count: int) -> dict:
    def http(method, url, token, payload):
        if method == "POST":
            return 200, {"access": "token"}
        if "batches/?" in url or url.endswith("typed_object"):
            return 200, {"results": [{"id": 6, "status": "committed"}, {"id": 1, "status": "smoked"}]}
        return 200, {"sample": sample, "row_count": row_count, "target_key": "people.leave_history"}

    return {
        "inbound_http": http,
        "inbound_environ": {"NIBRAS_HR_PASSWORD": "secret"},
    }


def _write_nightly(directory: Path) -> Path:
    path = directory / "inbound-nightly.yml"
    path.write_text(
        "on:\n  schedule:\n    - cron: '30 3 * * *'\n"
        "jobs:\n  journey:\n    steps:\n      - name: People door\n        run: |\n"
        "          CI=1 npx playwright test e2e/journeys/journey-dms-people-door.spec.ts "
        "--config e2e/playwright.config.ts\n",
        encoding="utf-8",
    )
    return path


def _write_workflow(directory: Path, run: str) -> Path:
    path = directory / "workflow.yml"
    path.write_text(
        "jobs:\n  test:\n    steps:\n      - name: Run tests\n        run: |\n          "
        + run
        + "\n",
        encoding="utf-8",
    )
    return path
