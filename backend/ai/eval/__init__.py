"""Deterministic answer-quality eval harness for the AI layer.

This package holds the golden dataset + pure check functions used by the
CI-safe ``test_answer_quality_eval.py`` gate (and, later, the opt-in live
judge harness).  Nothing in this package performs network or LLM calls.
"""
