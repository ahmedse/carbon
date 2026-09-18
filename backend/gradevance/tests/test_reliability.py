"""Reliability gate unit tests."""
from gradevance.services.reliability import cohen_kappa, passes_reliability_gate


def test_cohen_kappa_perfect_agreement():
    assert cohen_kappa(["A", "B", "A"], ["A", "B", "A"]) == 1.0


def test_cohen_kappa_chance_level_not_one():
    k = cohen_kappa(["A", "A", "B", "B"], ["A", "B", "A", "B"])
    assert k < 1.0


def test_reliability_gate_threshold():
    result = passes_reliability_gate(
        ["SG+", "SG-", "SG++"],
        ["SG+", "SG-", "SG++"],
        minimum=0.6,
    )
    assert result["passed"] is True
    assert result["value"] == 1.0
