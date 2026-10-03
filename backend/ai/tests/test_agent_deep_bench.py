"""Tasks / Agent deep bench: a missing live bank never scores reached.

A full run closes T9 only when it covers every case id of the current bank.
A run made before the bank grew is stale: it may still lift T4/T5/T7/T8, but
T9 stays partial until fresh full runs land (PULSE-TASKS-CONTRACT TL-7).
"""
from ai.eval.agent_deep_bench import (
    CLOSE_RUNS,
    bank_case_ids,
    covers_bank,
    retest_is_full,
    score_agent_bench,
)

FULL_BANK = sorted(bank_case_ids())


def test_bank_is_present_and_nonempty():
    assert FULL_BANK, "tasks_retest_bank.yaml must exist with cases"


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


def _pass_run(stamp: str, cases: list[str] | None = None, **objectives: bool) -> dict:
    base = {"T4": True, "T5": True, "T7": True, "T8": True, "T9": True}
    base.update(objectives)
    walked = FULL_BANK if cases is None else cases
    return {
        "tier": "live_retest",
        "run_at": stamp,
        "partial": False,
        "pass": True,
        "bank": "tasks_retest_bank.yaml",
        "cases": [{"id": cid, "pass": True} for cid in walked],
        "objectives": base,
        "latency": {"p50_ms": 40_000, "cases": len(walked)},
        "_file": f"PV2-tasks-retest-{stamp}.json",
    }


def test_retest_is_full_requires_tier_and_not_partial():
    assert retest_is_full(_pass_run("2026-09-27-1000"))
    assert not retest_is_full({**_pass_run("2026-09-27-1000"), "partial": True})
    assert not retest_is_full({**_pass_run("2026-09-27-1000"), "tier": "structural"})
    assert not retest_is_full({**_pass_run("2026-09-27-1000"), "bank": "other_bank.yaml"})
    assert not retest_is_full({**_pass_run("2026-09-27-1000"), "cases": []})


def test_covers_bank_flags_a_stale_subset():
    assert covers_bank(_pass_run("2026-09-27-1000"), set(FULL_BANK))
    assert not covers_bank(_pass_run("2026-09-27-1000", cases=FULL_BANK[:1]), set(FULL_BANK))


def test_three_full_covering_passes_reach_t9_and_lift_dated_partials():
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


def test_three_full_runs_that_predate_the_bank_keep_t9_partial():
    """A run that never walked the current bank cannot close T9."""
    stale = [_pass_run(f"2026-09-27-1{i}", cases=FULL_BANK[: max(1, len(FULL_BANK) - 1)]) for i in range(3)]
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 12, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=stale,
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] == "partial"
    assert report["verdict"] != "reliable"
    notes = {row["tid"]: row["note"] for row in report["objectives"]}
    assert "Stale" in notes["T9"]


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


def test_partial_run_never_closes_t9():
    runs = [_pass_run(f"2026-09-27-1{i}") for i in range(CLOSE_RUNS - 1)]
    partial = {**_pass_run("2026-09-27-1999"), "partial": True}
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 12, "misses": [], "gate_pass": True},
        soak={"soak_complete": True},
        retests=[*runs, partial],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T9"] != "reached"


def test_offline_plan_bank_failure_drops_mode_and_discuss():
    report = score_agent_bench(
        plan_bank={"n": 12, "passed": 11, "misses": [{"id": "ap-012"}], "gate_pass": False},
        soak={"soak_complete": True},
        retests=[],
    )
    by_id = {row["tid"]: row["honest"] for row in report["objectives"]}
    assert by_id["T1"] == "fail"
    assert by_id["T3"] == "fail"
