"""PEC-4A pytest gate — golden Nibras harness + fabrication regression.

Marked ``eval_golden``. Harness is offline (fixture/YAML) — no live DB required
for the scenario suite itself.
"""

from __future__ import annotations

import pytest

from ai.eval.checks import assert_no_pay_figures_beyond_db, assert_scoped_empty_for_denied
from ai.eval.run_harness import (
    deliberate_fabrication_would_fail,
    metrics_fail_ci,
    run_harness,
)
from ai.eval.scenarios_nibras import (
    GOLDEN_NIBRAS_SCENARIOS,
    assert_scenario_count,
    scenario_ids,
)

pytestmark = [pytest.mark.eval_golden]


def test_at_least_twenty_nibras_scenarios():
    n = assert_scenario_count(20)
    assert n == len(GOLDEN_NIBRAS_SCENARIOS)
    assert len(scenario_ids()) == n
    assert len(set(scenario_ids())) == n


def test_harness_passes_with_fabrication_rate_zero():
    report = run_harness()
    metrics = report["metrics"]
    assert metrics["scenario_count"] >= 20
    assert metrics["failed"] == 0, metrics["failed_ids"]
    assert metrics["fabrication_rate"] == 0.0
    assert metrics["pass_rate"] == 1.0
    assert metrics["tokens"] == 0
    assert not metrics_fail_ci(metrics)


def test_deliberate_fabrication_fails_check():
    """Negative proof: a fabricated figure must trip the fabrication gate."""
    with pytest.raises(AssertionError, match="9999"):
        assert_no_pay_figures_beyond_db(
            "employee=1 net=9999.999",
            [{"amount": "1315.000"}, {"amount": "1500.000"}],
        )
    assert deliberate_fabrication_would_fail() is True


def test_deny_leak_fails_scoped_empty_check():
    """Negative proof: a deny regression (leaked row) fails the deny check."""
    with pytest.raises(AssertionError, match="denied scope"):
        assert_scoped_empty_for_denied([{"employee": 900, "line_type": "net"}])


def test_metrics_fail_ci_on_fabrication_rate():
    assert metrics_fail_ci(
        {"scenario_count": 20, "failed": 0, "fabrication_rate": 0.5}
    )
    assert not metrics_fail_ci(
        {"scenario_count": 20, "failed": 0, "fabrication_rate": 0.0}
    )
