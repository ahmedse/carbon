"""Chat deep bench: stub green must not hide a live / week miss."""
from __future__ import annotations

from ai.eval.chat_deep_bench import OPERATOR_FILE, score_chat_bench
from ai.eval.intelligence_ladder import G5_FILE, _load


def test_operator_log_exists():
    row = _load(OPERATOR_FILE)
    assert row.get("tier") == "operator_observed"
    assert row.get("findings")
    assert all("Ahmed Mohamed" not in str(f.get("what")) for f in row["findings"])


def test_stub_does_not_upgrade_a_week_fail():
    g5 = _load(G5_FILE)
    assert (g5.get("per_objective_pass") or {}).get("C2") == 1.0
    report = score_chat_bench(retests=[])
    by_id = {row["id"]: row for row in report["objectives"]}
    assert by_id["C2"]["column"]["stub"] == "reached"
    assert by_id["C2"]["column"]["week"] == "fail"
    assert by_id["C2"]["column"]["honest"] == "fail"
    assert by_id["C6"]["column"]["honest"] == "fail"
    assert by_id["C5"]["column"]["honest"] == "reached"


def test_verdict_is_fragile_and_does_not_claim_l6():
    report = score_chat_bench(retests=[])
    assert report["verdict"] == "fragile"
    assert report["failed"] >= 3
    assert report["reached"] <= 5
    assert "not scored" in report["l6_l7"]
    assert "v21" in report["l6_l7"]


def test_expert_metrics_follow_chat_honesty():
    report = score_chat_bench(retests=[])
    by_id = {row["id"]: row for row in report["metrics"]}
    assert by_id["M01"]["column"]["honest"] == "fail"
    assert by_id["M02"]["column"]["honest"] == "fail"
    assert by_id["M06"]["column"]["honest"] == "reached"
    assert by_id["M03"]["column"]["honest"] == "missing"


def _run(stamp, findings, objectives=None, latency=None):
    return {
        "tier": "live_retest", "run_at": stamp, "_file": f"run-{stamp}",
        "findings": findings, "objectives": objectives or {},
        "latency": latency or {"turns": 10, "p50_ms": 3000, "over_4s": 1, "llm_calls_p50": 1},
    }


def test_a_finding_closes_only_after_three_passing_runs():
    from ai.eval.chat_deep_bench import finding_closure

    two = [_run("a", {"tes-ungrounded": True}), _run("b", {"tes-ungrounded": True})]
    assert finding_closure("tes-ungrounded", two)[0] is False
    three = two + [_run("c", {"tes-ungrounded": True})]
    assert finding_closure("tes-ungrounded", three)[0] is True
    reopened = three + [_run("d", {"tes-ungrounded": False})]
    assert finding_closure("tes-ungrounded", reopened)[0] is False


def test_a_closed_finding_stays_in_the_log_and_other_misses_still_fail():
    runs = [_run(x, {"tes-ungrounded": True, "hollow-export": True}) for x in "abc"]
    report = score_chat_bench(retests=runs)
    by_id = {row["id"]: row for row in report["objectives"]}
    assert by_id["C2"]["column"]["week"] == "reached"
    assert by_id["C6"]["column"]["honest"] == "fail"
    assert any(f["id"] == "tes-ungrounded" and "closed" in f["closure"] for f in report["findings"])


def test_retest_is_the_live_source_for_identity_and_plan_status():
    runs = [_run(x, {}, {"C6": True, "C9": True}) for x in "abc"]
    by_id = {row["id"]: row for row in score_chat_bench(retests=runs)["objectives"]}
    assert by_id["C9"]["column"]["live"] == "reached"
    assert by_id["C6"]["column"]["live"] == "reached"
    # The week invented-name miss is not closed by these runs.
    assert by_id["C6"]["column"]["honest"] == "fail"
    failing = runs[:2] + [_run("c", {}, {"C9": False})]
    by_id = {row["id"]: row for row in score_chat_bench(retests=failing)["objectives"]}
    assert by_id["C9"]["column"]["honest"] == "fail"


def test_a_partial_run_never_counts():
    from ai.eval.chat_deep_bench import load_retests
    import json, tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "PV2-chat-retest-x.json").write_text(json.dumps({**_run("x", {}), "partial": True}))
        assert load_retests(Path(tmp)) == []
