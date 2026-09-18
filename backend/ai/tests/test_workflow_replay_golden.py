"""W-3 — workflow replay-golden fixtures (choice / wait / retry / catch).

Pure deterministic gates: each JSON fixture under
``tests/fixtures/workflow_replay/`` asserts driver / wait / retry / catch
outcomes so control-flow regressions fail closed (DESIGN §8).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.engine.workflow.driver import (
    advance_and_ready_tasks,
    decide_choice,
    resolve_catch,
)
from ai.engine.workflow.graph import WorkflowGraph, WorkflowNode
from ai.engine.workflow.retry import should_retry
from ai.engine.workflow.wait import evaluate_wait

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflow_replay"


def _load(name: str) -> dict:
    path = FIXTURE_DIR / name
    assert path.is_file(), f"missing golden {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_choice_ok_routes_and_skips():
    raw = _load("choice_ok.json")
    g = WorkflowGraph.from_dict(raw["graph"])
    chosen, evaluations = decide_choice(g, "c", raw["context"])
    assert chosen is not None
    assert chosen.target == raw["expected_chosen_target"]
    assert evaluations  # at least one guard_eval style record

    ready, skipped, gateways, skipped_nodes = advance_and_ready_tasks(
        g,
        completed_step_ids=raw["completed_step_ids"],
        context=raw["context"],
    )
    assert ready == raw["expected_ready_tasks"]
    assert set(skipped) == set(raw["expected_skipped_steps"])
    assert "c" in gateways
    assert "t2" in skipped_nodes


def test_golden_wait_duration():
    raw = _load("wait_duration.json")
    node = WorkflowNode(
        id=raw["node"]["id"],
        node_type="wait",
        meta=dict(raw["node"].get("meta") or {}),
    )
    pending = evaluate_wait(node, raw["context"], elapsed_ms=raw["elapsed_ms"])
    assert pending.satisfied is raw["expected_satisfied"]
    assert pending.reason == raw["expected_reason"]

    done = evaluate_wait(
        node, raw["context"], elapsed_ms=raw["elapsed_ms_done"],
    )
    assert done.satisfied is raw["expected_satisfied_done"]
    assert done.reason == raw["expected_reason_done"]


def test_golden_retry_transient_policy():
    raw = _load("retry_transient.json")
    assert should_retry(
        raw["policy"], raw["error"], raw["attempt"],
    ) is raw["expected_should_retry"]
    assert should_retry(
        raw["policy"], raw["error"], raw["attempt_exhausted"],
    ) is raw["expected_should_retry_exhausted"]


def test_golden_catch_timeout_routes():
    raw = _load("catch_timeout.json")
    node = WorkflowNode(
        id=raw["node"]["id"],
        node_type=raw["node"]["node_type"],
        catch=raw["node"]["catch"],
    )
    assert resolve_catch(node, raw["error_class"]) == raw["expected_catch_target"]
    assert resolve_catch(node, raw["error_class_miss"]) == raw["expected_catch_miss"]


def test_all_workflow_replay_goldens_present():
    """Fail closed: expected fixture set must exist (no silent drift)."""
    expected = {
        "choice_ok.json",
        "wait_duration.json",
        "retry_transient.json",
        "catch_timeout.json",
    }
    found = {p.name for p in FIXTURE_DIR.glob("*.json")}
    assert expected <= found, f"missing goldens: {expected - found}"
