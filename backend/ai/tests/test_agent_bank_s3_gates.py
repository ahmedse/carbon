"""Agent bank S3 CI gates — pass^k + fabrication=0 (G1 merge gate).

Sprint S3 from docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md:
  * fabrication_rate must be exactly 0
  * pass^k=3 identical green harness runs
  * ECF headcount / kuwaiti metrics stable across k calls
  * invented figures trip the fabrication check (negative control)

Run::

    cd backend && ../.venv/bin/python -m pytest ai/tests/test_agent_bank_s3_gates.py -q
    EVAL_PASS_K=3 ../.venv/bin/python -m ai.eval.run_harness
"""

from __future__ import annotations

import pytest

from ai.eval.checks import assert_no_pay_figures_beyond_db
from ai.eval.run_harness import (
    DEFAULT_PASS_K,
    deliberate_fabrication_would_fail,
    metrics_fail_ci,
    run_harness,
    run_harness_pass_k,
)
from ai.tests.test_ecf_golden import (
    METRIC_CASES,
    assert_golden_invariants,
    call_nibras_metric,
)

pytestmark = [pytest.mark.eval_golden]


def test_s3_g1_fabrication_rate_zero():
    """G1 / S3: harness fabrication_rate == 0 on a full suite pass."""
    metrics = run_harness()["metrics"]
    assert metrics["fabrication_rate"] == 0.0
    assert metrics["grounding_pass"] == 1.0
    assert metrics["failed"] == 0


def test_s3_pass_k_merge_gate():
    """S3: pass^k=3 — identical fingerprints, all green, CI gate open."""
    assert DEFAULT_PASS_K == 3
    report = run_harness_pass_k(k=DEFAULT_PASS_K)
    m = report["metrics"]
    assert m["pass_k"] == 3
    assert m["pass_k_ok"] is True
    assert m["pass_k_identical"] is True
    assert m["fabrication_rate"] == 0.0
    assert not metrics_fail_ci(m)


def test_s3_invented_figure_fails_fabrication_check():
    """S3 negative: invented money must fail (fabrication ≠ silent pass)."""
    with pytest.raises(AssertionError, match="9999"):
        assert_no_pay_figures_beyond_db(
            "Active headcount is fine but net=9999.999",
            [{"amount": "1315.000"}, {"amount": "1500.000"}],
        )
    assert deliberate_fabrication_would_fail() is True


@pytest.mark.parametrize("case", METRIC_CASES, ids=[c.id for c in METRIC_CASES])
def test_s3_pc_metric_pass_k(case):
    """PC headcount/kuwaiti: metric value stable across k=3 offline calls."""
    values = []
    for _ in range(3):
        result = call_nibras_metric(case.query)
        assert_golden_invariants(case, result)
        values.append(result["value"])
    assert len(set(values)) == 1, f"{case.id} flaked across pass^k: {values}"
