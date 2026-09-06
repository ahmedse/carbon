"""Live answer-quality judge harness (opt-in, excluded from CI).

This module is the *skeleton* of the full-pipeline judge that will run every
``GOLDEN_QUERIES`` entry through the complete Pulse pipeline and apply the
deterministic ``ai.eval.checks`` to the synthesized output.  It requires a real
LLM, so it is marked ``live`` and skipped unless ``PULSE_EVAL_LIVE=1``.

CI default:  ``pytest -m "not live"``  (see ``backend/pytest.ini``).
Run manually: ``PULSE_EVAL_LIVE=1 python -m pytest ai/tests/test_answer_quality_live.py -q``
"""

from __future__ import annotations

import os

import pytest

from ai.eval.golden import GOLDEN_QUERIES

pytestmark = pytest.mark.live

_REQUIRED_KEYS = {"question", "expected_tool", "expected_dimension", "invariants"}


def _live_enabled() -> bool:
    return os.environ.get("PULSE_EVAL_LIVE") == "1"


@pytest.mark.django_db(transaction=True)
def test_live_golden_queries_are_well_formed():
    """The golden set is loadable and covers the required answer surfaces."""
    assert len(GOLDEN_QUERIES) >= 5, "golden set must cover all answer surfaces"
    for entry in GOLDEN_QUERIES:
        missing = _REQUIRED_KEYS - set(entry)
        assert not missing, f"entry missing keys {missing}: {entry!r}"
        assert isinstance(entry["question"], str) and entry["question"].strip()
        assert isinstance(entry["invariants"], list) and entry["invariants"]
        assert entry["expected_tool"] is None or isinstance(entry["expected_tool"], str)
        assert entry["expected_dimension"] is None or isinstance(
            entry["expected_dimension"], str
        )


@pytest.mark.django_db(transaction=True)
def test_live_full_pipeline_over_golden_queries():
    """Run the FULL pipeline over ``GOLDEN_QUERIES`` (real LLM, opt-in).

    The full runner is wired in a later phase (PAQ-2A/2B) once the Answer
    Envelope + deterministic renderer exist.  Until then this is a documented
    stub that guarantees the golden set is non-trivial and correctly marked.
    """
    if not _live_enabled():
        pytest.skip("live harness requires a configured model — set PULSE_EVAL_LIVE=1")

    # Full pipeline execution goes here once the envelope/renderer land.
    assert len(GOLDEN_QUERIES) >= 5
    for entry in GOLDEN_QUERIES:
        assert entry["invariants"], f"no invariants to assert for {entry['question']!r}"
