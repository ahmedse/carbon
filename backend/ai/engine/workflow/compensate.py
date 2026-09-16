"""W-4 — saga compensation target resolution (pure, RULE_20).

A failed task node may declare ``compensation: \"<node_id>\"`` pointing at a
reversal task. The host queues that step with ``is_mutation=True`` so RULE_21
consent still applies — compensation never auto-writes.
"""

from __future__ import annotations

from ai.engine.workflow.driver import step_id_for_node
from ai.engine.workflow.graph import WorkflowGraph, WorkflowNode

__all__ = ["resolve_compensation_target", "compensation_step_id"]


def resolve_compensation_target(
    graph: WorkflowGraph,
    node: WorkflowNode | None,
) -> WorkflowNode | None:
    """Return the compensation node for ``node``, if declared and present."""
    if node is None:
        return None
    target_id = node.compensation
    if not target_id:
        return None
    by_id = {n.id: n for n in graph.nodes}
    return by_id.get(str(target_id))


def compensation_step_id(
    graph: WorkflowGraph,
    node: WorkflowNode | None,
) -> int | None:
    """PlanStep id of the compensation task, or None."""
    target = resolve_compensation_target(graph, node)
    if target is None:
        return None
    return step_id_for_node(target)
