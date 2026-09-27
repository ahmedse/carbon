"""Tasks / Agent deep bench: a missing live bank never scores reached."""
from ai.eval.agent_deep_bench import score_agent_bench


def test_no_tasks_retest_file_keeps_t9_missing_and_blocks_ten():
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 12, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=[],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] == "missing"
    assert by_id["T10"] == "missing"
    assert report["reached"] < 10
    assert report["verdict"] != "reliable"
    assert report["l6_l7"] == "not scored"
    assert report["night_2026_09_23"] == "FAIL stays"


def _pass_run(stamp: str, **objectives: bool) -> dict:
    base = {"T4": True, "T5": True, "T7": True, "T8": True, "T9": True}
    base.update(objectives)
    return {
        "tier": "live_retest",
        "run_at": stamp,
        "partial": False,
        "pass": True,
        "objectives": base,
        "latency": {"p50_ms": 40_000, "cases": 6},
        "_file": f"PV2-tasks-retest-{stamp}.json",
    }


def test_three_full_passes_reach_t9_and_lift_dated_partials():
    runs = [_pass_run(f"2026-09-27-1{i}") for i in range(3)]
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 12, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=runs,
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] == "reached"
    assert by_id["T4"] == "reached"
    assert by_id["T5"] == "reached"
    assert by_id["T7"] == "reached"
    assert by_id["T8"] == "reached"
    assert by_id["T10"] == "reached"
    assert report["reached"] == 10


def test_one_tasks_retest_is_partial_not_nine():
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 12, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=[_pass_run("2026-09-27-1000")],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] == "partial"
    assert by_id["T4"] == "partial"
    assert by_id["T10"] == "missing"
    assert report["reached"] == 4


def test_offline_plan_bank_failure_drops_mode_and_discuss():
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 11, "misses": [{"id": "ap-012"}], "gate_pass": False},
        soak={"soak_complete": True},
        retests=[],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T1"] == "fail"
    assert by_id["T3"] == "fail"
