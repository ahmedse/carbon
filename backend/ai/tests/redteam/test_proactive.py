"""PATH 5 — PROACTIVE trigger-condition SQL injection attempts.

A proactive trigger condition tries to smuggle SQL through the structured
predicate renderer, the read-only SQL validator, or a legacy raw-string
``where`` clause.  Each is fail-closed.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from ai.tests.redteam import mutations


@pytest.mark.parametrize("case", mutations.PROACTIVE, ids=[c["id"] for c in mutations.PROACTIVE])
def test_proactive_injection_is_blocked(case, monkeypatch):
    target = case["target"]

    if target == "render_where":
        from ai.engine.proactive.trigger_evaluator import _render_where

        with pytest.raises(ValueError):
            _render_where(case["payload"])

    elif target == "validate_sql":
        from ai.engine.core.exceptions import ToolExecutionError
        from ai.engine.core.sql_validator import validate_sql

        with pytest.raises(ToolExecutionError):
            validate_sql(case["payload"])

    elif target == "legacy_where":
        from ai.engine.proactive import trigger_evaluator

        called = []

        async def _fake_query(*args, **kwargs):
            called.append((args, kwargs))
            return 1.0

        monkeypatch.setattr(trigger_evaluator, "_query_aggregation", _fake_query)

        trigger = types.SimpleNamespace(id="trig", severity="warning", name="Legacy")
        condition = {
            "table": "readings",
            "column": "temp",
            "operator": ">",
            "value": 100.0,
            "where": case["payload"],
            "aggregation": "latest",
        }

        result = asyncio.run(
            trigger_evaluator._evaluate_threshold(trigger, condition, [], "postgresql://x")
        )

        assert result.fired is False, f"{case['id']}: legacy raw where fired"
        assert "legacy" in result.detail.lower(), (
            f"{case['id']}: expected 'legacy' in detail {result.detail!r}"
        )
        assert called == [], f"{case['id']}: raw where reached the query helper"

    else:  # pragma: no cover - catalogue typo guard
        raise AssertionError(f"unknown proactive target {target!r}")
