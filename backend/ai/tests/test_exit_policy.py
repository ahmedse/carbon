"""Q4 exit_policy — soft exits off under v21 only."""
from __future__ import annotations

import pytest

from ai.engine.cognition.turn.exit_policy import may_stage, stage_exit


def test_legacy_allows_all_soft_gates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PULSE_UNDERSTAND", raising=False)
    assert may_stage("zero_llm") is True
    assert may_stage("restyle") is True
    assert may_stage("off_limits") is True


def test_v21_keeps_refuse_handoff_ess(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    assert may_stage("off_limits") is True
    assert may_stage("chat_handoff") is True
    assert may_stage("ess_bound_self_read") is True
    assert may_stage("zero_llm") is False
    assert may_stage("process_brief") is False
    assert may_stage("nav_fast_path") is False


def test_stage_exit_respects_policy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    staged: list = []
    from ai.engine.cognition.turn.exit_policy import stage_soft_exit

    assert stage_soft_exit(staged, "answer", "zero_llm", object()) is False
    assert staged == []
    assert stage_exit(staged, "refuse", "off_limits", object()) is True
    assert len(staged) == 1


def test_runner_spine_exits_at_most_four():
    """Q4 lean meter: spine stage_exit( call sites ≤ 4."""
    from ai.eval.harness_budget import SPINE_RUNNER_PATHS

    n = 0
    for path in SPINE_RUNNER_PATHS:
        if path.is_file():
            n += path.read_text(encoding="utf-8").count("stage_exit(")
    assert 1 <= n <= 4, n
