"""Structural and baseline smoke tests for G6 understanding bank."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai.eval.g6_runner import (
    G6_CATEGORIES,
    G6_TIERS,
    _matches_expect,
    baseline_decision,
    case_tier,
    load_bank,
    score_bank,
)

BANK_PATH = Path(__file__).resolve().parent / "g6_bank.yaml"

BASELINE_N = 61
V21_N = 13


def test_bank_has_unique_ids_per_tier():
    bank = load_bank()
    ids = [case["id"] for case in bank]
    assert len(set(ids)) == len(ids) == BASELINE_N + V21_N
    tiers = {case_tier(c) for c in bank}
    assert tiers <= G6_TIERS
    assert sum(1 for c in bank if case_tier(c) == "baseline") == BASELINE_N
    assert sum(1 for c in bank if case_tier(c) == "v21") == V21_N


def test_v21_tier_cases_are_shaped_and_stay_out_of_offline_gate():
    """ADR-0049 §8: v21 goldens are scored by the understand call, not by
    adding regexes to the ladder. They must not be in the baseline gate set,
    and history (when given) must be role/content messages."""
    bank = load_bank()
    v21 = [c for c in bank if case_tier(c) == "v21"]
    assert {c["id"] for c in v21} == {
        "g6-062", "g6-063", "g6-064", "g6-065", "g6-066", "g6-067",
        "g6-068", "g6-069", "g6-070", "g6-071", "g6-072", "g6-073", "g6-074",
    }
    for case in v21:
        assert case["expect_op"] in {"call_tool", "handoff_agent", "answer", "clarify"}
        for msg in case.get("history") or []:
            assert msg["role"] in {"user", "assistant"} and msg["content"]
    # Read/write twin contrast: same payslip context, opposite ops.
    read = next(c for c in v21 if c["id"] == "g6-062")
    write = next(c for c in v21 if c["id"] == "g6-067")
    assert read["expect_api"] == "list_my_loans"
    assert write["expect_op"] == "handoff_agent"
    report = score_bank()  # default tier=baseline
    assert report["n"] == BASELINE_N
    pending = {row["id"]: row for row in report["v21_pending"]}
    assert set(pending) == {c["id"] for c in v21}
    # The legacy ladder does not solve the loan-read class; that is the point.
    assert pending["g6-062"]["baseline_passes"] is False
    assert pending["g6-064"]["baseline_passes"] is False
    # The ladder has no render mode, so no chart follow-up can pass it.
    for cid in ("g6-068", "g6-069", "g6-070"):
        assert pending[cid]["baseline_passes"] is False


def test_chart_followups_pin_subject_from_state():
    """A chart is a render of the state's read, not a new domain."""
    from ai.eval.g6_runner import _case_state, _decision_to_dict
    from ai.engine.cognition.turn.decision import Command, Decision

    case = next(c for c in load_bank() if c["id"] == "g6-068")
    assert case["expect_render"] == "chart"
    state = _case_state(case)
    got = _decision_to_dict(
        Decision(commands=[Command(op="continue", render="chart")]), state,
    )
    assert (got["op"], got["api"], got["render"]) == ("call_tool", "get_my_leave_balance", "chart")
    assert _matches_expect(got, case)
    assert not _matches_expect({**got, "render": "text"}, case)


def test_every_category_at_least_three():
    bank = load_bank()
    counts: dict[str, int] = {}
    for case in bank:
        cat = case["category"]
        assert cat in G6_CATEGORIES, f"unknown category {cat!r} on {case['id']}"
        counts[cat] = counts.get(cat, 0) + 1
    for cat in G6_CATEGORIES:
        assert counts.get(cat, 0) >= 3, f"{cat} has {counts.get(cat, 0)} cases"


def test_score_bank_runs_and_accuracy_in_unit_interval():
    report = score_bank()
    assert report["n"] == BASELINE_N
    acc = report["decision_accuracy"]
    assert isinstance(acc, float)
    assert 0.0 <= acc <= 1.0
    assert isinstance(report["parity"], float)
    assert 0.0 <= report["parity"] <= 1.0
    assert isinstance(report["misses"], list)


def test_leave_balance_baseline_on_canonical_en():
    bank = load_bank()
    hit = next(
        (c for c in bank if c["en"] == "What is my leave balance?"),
        None,
    )
    assert hit is not None, "bank must include canonical leave balance EN utterance"
    dec = baseline_decision(hit["en"])
    assert dec["op"] == "call_tool"
    assert dec["api"] == "get_my_leave_balance"


def test_g6_001_shape():
    bank = load_bank()
    case = next(c for c in bank if c["id"] == "g6-001")
    assert case["category"] == "leave_balance"
    assert case["expect_op"] == "call_tool"
    assert case["expect_api"] == "get_my_leave_balance"


def test_g6_offline_baseline_meets_exit_gate():
    """Q0/Q6 exit: offline decision accuracy ≥ 0.95 and AR/EN parity ≥ 0.98
    on the baseline tier. v21-tier goldens are gated by --mode understand."""
    report = score_bank(tier="baseline")
    assert report["decision_accuracy"] >= 0.95
    assert report["parity"] >= 0.98
    assert report["misses"] == []


def test_plan_goldens_pin_process_and_persona():
    from ai.eval.g6_runner import _decision_to_dict, _user_info_for
    from ai.engine.cognition.turn.decision import Command, Decision

    case = next(c for c in load_bank() if c["id"] == "g6-071")
    assert _user_info_for(case)["audience"] == ["ess", "hr"]
    plan = _decision_to_dict(Decision(commands=[Command(op="handoff_agent", process_id="plan")]))
    other = _decision_to_dict(Decision(commands=[Command(op="handoff_agent", process_id="submit_my_loan")]))
    assert _matches_expect(plan, case)
    assert not _matches_expect(other, case)
    assert _decision_to_dict(None)["op"] == "malformed"


def test_catalog_example_owns_the_three_l6_splits_only():
    """A catalog example owns Wellie, Mohammad, and the payslip chart.

    It must not steal an ordinary balance ask.
    """
    import yaml
    from pathlib import Path
    from ai.engine.cognition.catalog_retrieval import catalog_choice

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "engine/instances/nibras/instance.yaml").read_text())
    catalog = cfg["api_catalog"] if "api_catalog" in cfg else None
    if catalog is None:
        for value in cfg.values():
            if isinstance(value, dict) and "api_catalog" in value:
                catalog = value["api_catalog"]
                break
    bank = {c["id"]: c for c in load_bank()}
    assert catalog_choice(bank["g6-045"]["en"], catalog)["name"] == "list_leave_entitlements"
    assert catalog_choice(bank["g6-047"]["en"], catalog)["name"] == "list_leave_entitlements"
    assert catalog_choice(bank["g6-070"]["en"], catalog)["name"] == "list_my_payslips"
    assert catalog_choice(bank["g6-001"]["en"], catalog) is None
    assert catalog_choice(bank["g6-038"]["ar"], catalog) is None
