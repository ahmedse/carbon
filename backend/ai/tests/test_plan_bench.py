"""Pulse Plan benchmark surface (PULSE-PLAN-CONTRACT §5/§6).

Guards the offline path bank + ADR-0052 contract goldens, the new read-vs-goal
/ await-user / guard / affirmation checks, the live PL bank inventory, and the
coordinator report's honest "missing" status.
"""
from __future__ import annotations

import yaml
from pathlib import Path

from ai.eval import agent_plan_runner as runner
from ai.eval import plan_bench
from ai.eval.chat_plan_retest import BANKS, bank_doc

EVAL = Path(runner.__file__).resolve().parent


def test_offline_plan_bank_gate_passes():
    result = runner.score()
    assert result["gate_pass"], result["misses"]
    assert result["n"] >= 66
    assert result["plan_bank"]["gate_pass"]
    assert result["contract_bank"]["gate_pass"]


def test_inventory_covers_every_check_kind():
    kinds = {row["check"] for row in runner.inventory()}
    assert {
        "seed", "continuity", "commit", "ess_confirm", "chat_guard",
        "proposal", "await_user", "guard", "affirmation", "contract",
    } <= kinds


def test_proposal_read_is_not_a_task_but_a_goal_is():
    read = {
        "check": "proposal",
        "brief": "What is my leave balance?",
        "plan": {"steps": [{
            "step_id": 1, "intent": "read", "tool_name": "call_host_api",
            "tool_args": {"api_name": "get_my_leave_balance"},
        }]},
        "expect": {"is_task": False, "payload": False},
    }
    assert runner._check(read) == ""

    goal = {
        "check": "proposal",
        "brief": "lowest 20 salaries and their jobs",
        "plan": {"steps": [
            {"step_id": 1, "intent": "a", "tool_name": "call_host_api"},
            {"step_id": 2, "intent": "b", "tool_name": "call_host_api", "depends_on": [1]},
        ]},
        "expect": {"is_task": True, "payload": True, "blocked_count": 0},
    }
    assert runner._check(goal) == ""


def test_proposal_contract_blocks_create_on_undeclared_output():
    case = {
        "check": "proposal",
        "brief": "Board pack with average",
        "contract": True,
        "plan": {"steps": [
            {"step_id": 0, "intent": "headcount", "tool_name": "call_host_api",
             "tool_args": {"api_name": "analyze_employees", "dimension": "org_unit"}},
            {"step_id": 1, "intent": "export", "tool_name": "export_document",
             "tool_args": {"title": "Report", "columns": ["average"]},
             "depends_on": [0], "is_mutation": True},
        ]},
        "expect": {"is_task": True, "payload": True, "blocked_count": 1, "blocks_create": True},
    }
    assert runner._check(case) == ""


def test_await_user_pauses_then_resumes():
    pause = {
        "check": "await_user",
        "step": {"step_id": 0, "intent": "Own slips or the org?", "tool_name": "ask_clarification"},
        "expect": {"paused": True, "executed": False, "draft_text": "Own slips or the org?"},
    }
    assert runner._check(pause) == ""
    resume = {
        "check": "await_user",
        "step": {"step_id": 2, "intent": "Confirm", "tool_name": "ask_clarification"},
        "answered_token": "token-1",
        "expect": {"resumed": True, "executed": True},
    }
    assert runner._check(resume) == ""


def test_guard_outcome_choice_and_evidence():
    step = {"step_id": 6, "intent": "board", "tool_name": "export_document",
            "guard": {"step": 1, "field": "within_band", "value": True}}
    run = {"check": "guard", "step": step, "outputs": {"1": {"within_band": True}},
           "expect": {"outcome": "run"}}
    skip = {"check": "guard", "step": step, "outputs": {"1": {"within_band": False}},
            "expect": {"outcome": "skip"}}
    pause = {"check": "guard", "step": step, "outputs": {"1": {}}, "expect": {"outcome": "pause"}}
    choice = {"check": "guard", "step": step,
              "expect": {"choice_kind": "guard", "choice_step": 1, "choice_values": [True, False]}}
    ok = {"check": "guard", "depends_on": [3],
          "statuses": {"3": {"status": "completed", "failure_class": ""}},
          "expect": {"evidence_ok": [True]}}
    bad = {"check": "guard", "depends_on": [3],
           "statuses": {"3": {"status": "failed", "failure_class": "missing_binding"}},
           "expect": {"evidence_ok": [False]}}
    for case in (run, skip, pause, choice, ok, bad):
        assert runner._check(case) == "", case


def test_affirmation_commit_only_word_is_not_a_bare_yes():
    commit_only = {
        "check": "affirmation",
        "message": "اعتمدها",
        "expect": {"is_affirmation": False, "is_commit": True, "starts_with": False},
    }
    assert runner._check(commit_only) == ""
    yes = {"check": "affirmation", "message": "yes",
           "expect": {"is_affirmation": True, "is_commit": True, "starts_with": True}}
    assert runner._check(yes) == ""


def test_contract_bank_scoring_matches_the_goldens():
    result = runner.score_contract()
    assert result["gate_pass"], result["misses"]
    cases = runner.load_contract_bank()
    assert cases and all("blocking" in c for c in cases)


def test_contract_bank_new_cases_are_gated():
    ids = {c["id"] for c in runner.load_contract_bank()}
    assert {
        "sibling-exports-are-one-effect",
        "two-writes-without-a-guard-branch",
        "exclusive-guards-allow-two-writes",
        "guarded-within-band-keeps-the-export",
        "review-cannot-call-a-tool",
        "review-needs-something-to-review",
        "tool-less-hop-feeding-an-export-is-a-gap",
    } <= ids


def test_live_plan_banks_discovered_and_read_only():
    assert {"PL-01", "PL-02", "PL-03"} <= set(BANKS)
    for bank_id in BANKS:
        doc = bank_doc(bank_id)
        assert doc.get("tier") == "live_plan"
        assert doc.get("threads")
        assert not doc.get("write"), f"{bank_id} must stay read-only (Plan proposes; Agent applies)"


def test_live_bank_evidence_filename_convention():
    from datetime import datetime, timezone

    from ai.eval.chat_plan_retest import _bank_filename

    stamp = datetime(2026, 10, 3, 11, 31, tzinfo=timezone.utc)
    assert _bank_filename("PL-01", stamp) == "PV2-plan-PL01-2026-10-03-1131.json"


def test_plan_report_is_missing_without_live_evidence():
    report = plan_bench.build_report()
    assert report["offline"]["gate_pass"]
    assert report["live_reached"] == 0
    assert report["live_total"] == 3
    assert all(b["honest"]["status"] == "missing" for b in report["live_banks"])
    assert report["surface"] == "plan"
    assert "Never merged" in report["rule"]


def test_live_status_closes_only_on_three_full_runs(tmp_path):
    import json

    rows = [
        {"tier": "live_plan", "bank": "PL-01", "run_at": f"2026-10-0{i}", "pass": True}
        for i in (1, 2, 3)
    ]
    for i, row in enumerate(rows, start=1):
        (tmp_path / f"PV2-plan-PL01-2026-10-0{i}-1200.json").write_text(
            json.dumps(row), encoding="utf-8"
        )
    status = plan_bench.live_status("PL-01", root=tmp_path)
    assert status["status"] == "reached"
    assert len(status["evidence"]) == 3

    rows[2]["pass"] = False
    (tmp_path / "PV2-plan-PL01-2026-10-03-1200.json").write_text(
        json.dumps(rows[2]), encoding="utf-8"
    )
    assert plan_bench.live_status("PL-01", root=tmp_path)["status"] == "fail"


def test_plan_bank_yaml_is_a_list_of_cases():
    doc = yaml.safe_load((EVAL / "agent_plan_bank.yaml").read_text(encoding="utf-8"))
    assert isinstance(doc, list)
    assert all(isinstance(c, dict) and c.get("id") and c.get("check") for c in doc)
