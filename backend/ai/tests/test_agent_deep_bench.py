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


def test_offline_plan_bank_failure_drops_mode_and_discuss():
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 11, "misses": [{"id": "ap-012"}], "gate_pass": False},
        soak={"soak_complete": True},
        retests=[],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T1"] == "fail"
    assert by_id["T3"] == "fail"
