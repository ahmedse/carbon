"""Deterministic (no-LLM) coverage for the AnswerEnvelope eval invariants.

These are the CI-runnable guards behind the golden harness: they encode the
exact regressions this platform hit — a data question rendering prose-only, and
a headline falsely claiming "no data" while the envelope carries tables.
"""
from __future__ import annotations

import pytest

from ai.eval.checks import assert_envelope_has_data, assert_envelope_not_no_data


def _envelope(**overrides) -> dict:
    base = {
        "headline": "AASTMT emissions totaled 10.3 million kg CO2e.",
        "prose": [],
        "tables": [{"title": "By scope", "columns": ["Scope", "kg"], "rows": [["1", "2258"]]}],
        "charts": [],
        "caveats": [],
        "sources": [{"tool": "call_host_api", "rows_returned": 3}],
    }
    base.update(overrides)
    return base


def test_has_data_passes_with_tables():
    assert_envelope_has_data(_envelope())  # no raise


def test_has_data_fails_when_prose_only():
    with pytest.raises(AssertionError):
        assert_envelope_has_data(_envelope(tables=[], charts=[]))


def test_not_no_data_flags_false_no_data_headline():
    bad = _envelope(headline="No carbon emissions data is available for AASTMT in 2026.")
    with pytest.raises(AssertionError):
        assert_envelope_not_no_data(bad)


def test_not_no_data_passes_for_real_answer():
    assert_envelope_not_no_data(_envelope())  # no raise


def test_not_no_data_ignores_empty_envelope():
    # An honest "no data" headline with no tables/charts is NOT a contradiction.
    empty = _envelope(
        headline="There are no records for this period.", tables=[], charts=[], sources=[],
    )
    assert_envelope_not_no_data(empty)  # no raise


def test_checks_accept_pydantic_envelope():
    from ai.envelope import AnswerEnvelope

    env = AnswerEnvelope(
        headline="Emissions totaled 10.3M kg CO2e.",
        prose=[],
        tables=[{"title": "By scope", "columns": ["Scope", "kg"], "rows": [["1", "2258"]]}],
        charts=[],
        caveats=[],
        sources=[{"tool": "call_host_api", "rows_returned": 3}],
    )
    assert_envelope_has_data(env)
    assert_envelope_not_no_data(env)
