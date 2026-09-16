"""Deterministic answer-quality eval harness for the AI layer.

This package holds the golden dataset + pure check functions used by the
CI-safe ``test_answer_quality_eval.py`` gate (and, later, the opt-in live
judge harness).

PEC-4A Nibras baseline:
  * ``scenarios_nibras`` — ≥20 golden HRMS scenarios
  * ``run_harness`` — CI entry (``python -m ai.eval.run_harness``); metrics JSON
    with ``fabrication_rate`` hard-gated to 0
  * ``test_harness_golden`` — pytest marker ``eval_golden``
"""
