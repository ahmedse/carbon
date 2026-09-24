"""Unit tests for harness budget meter (no Django)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ai.eval.harness_budget import _COUNT_KEYS, gate_violations, measure

BACKEND = Path(__file__).resolve().parents[2]


def test_measure_returns_int_counters():
    result = measure()
    for key in _COUNT_KEYS:
        assert key in result
        assert isinstance(result[key], int), key
    assert isinstance(result["measured_at"], str)
    assert result["measured_at"]


def test_measure_minimums():
    result = measure()
    assert result["staged_exits"] >= 1
    assert result["re_compile"] >= 1
    assert result["runner_lines"] > 200


def test_gate_fails_when_staged_exits_ceiling_zero():
    measured = measure()
    violations = gate_violations(measured, {"staged_exits": 0})
    assert violations, "expected gate failure with staged_exits ceiling 0"


def test_gate_cli_exits_one_on_ceiling_breach(tmp_path):
    ceiling = tmp_path / "ceiling.json"
    ceiling.write_text(json.dumps({"staged_exits": 0}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "ai.eval.harness_budget", "--gate", str(ceiling)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
