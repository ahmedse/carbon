"""W-3 — bounded ``loop`` / ``map`` helpers (pure, RULE_20).

``loop``: while ``meta.guard`` (default ``true``) and under ``max_iterations``,
re-run ``meta.body_step_ids`` (or step ids of non-default outgoing targets).

``map``: expand ``collection_path`` from context and fan out the body once
per item (bounded), exposing ``map_item`` / ``map_index`` to the host context.
"""

from __future__ import annotations

from typing import Any, Callable

from ai.engine.workflow.driver import outgoing, step_id_for_node
from ai.engine.workflow.graph import WorkflowGraph, WorkflowNode
from ai.engine.workflow.guards import GuardError, eval_guard

__all__ = [
    "body_step_ids",
    "evaluate_loop",
    "evaluate_map",
    "expand_map",
    "DEFAULT_MAP_LIMIT",
]

DEFAULT_MAP_LIMIT = 20


def body_step_ids(graph: WorkflowGraph, node: WorkflowNode) -> list[int]:
    """Step ids that form the loop/map body."""
    meta = node.meta or {}
    raw = meta.get("body_step_ids")
    if isinstance(raw, (list, tuple)) and raw:
        out: list[int] = []
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        if out:
            return out
    by_id = {n.id: n for n in graph.nodes}
    ids: list[int] = []
    for e in outgoing(graph, node.id):
        if e.is_default:
            continue
        target = by_id.get(e.target)
        if target is None:
            continue
        sid = step_id_for_node(target)
        if sid is not None:
            ids.append(sid)
    return ids


def evaluate_loop(
    graph: WorkflowGraph,
    node: WorkflowNode,
    context: dict | None,
    loop_iters: dict[str, int],
    *,
    on_loop_iter: Callable[[str, int, int], None] | None = None,
) -> tuple[str, list[int], dict[str, int]]:
    """Decide whether to run the loop body again or exit.

    Returns
    -------
    action
        ``\"body\"`` — re-queue body step ids; ``\"exit\"`` — mark loop done.
    step_ids
        Body step ids when action is ``body``, else empty.
    loop_iters
        Updated iteration counters (copy).
    """
    iters = dict(loop_iters or {})
    current = int(iters.get(node.id, 0))
    max_it = int(node.max_iterations or 1)
    meta = node.meta or {}
    guard_expr = meta.get("guard")
    ctx = context or {}

    should = current < max_it
    if should and guard_expr:
        try:
            should = bool(eval_guard(str(guard_expr), ctx))
        except GuardError:
            should = False
    elif should and guard_expr is None:
        # Count-only loop: continue until max_iterations.
        should = True

    if not should:
        return "exit", [], iters

    nxt = current + 1
    iters[node.id] = nxt
    if on_loop_iter is not None:
        on_loop_iter(node.id, nxt, max_it)
    return "body", body_step_ids(graph, node), iters


def expand_map(
    node: WorkflowNode,
    context: dict | None,
    *,
    limit: int = DEFAULT_MAP_LIMIT,
) -> list[Any]:
    """Resolve ``collection_path`` against context; return up to ``limit`` items."""
    path = node.collection_path or (node.meta or {}).get("collection_path")
    if not path:
        return []
    ctx = context or {}
    cur: Any = ctx
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return []
    if not isinstance(cur, (list, tuple)):
        return []
    max_it = node.max_iterations or limit
    return list(cur)[: min(int(max_it), limit)]


def evaluate_map(
    graph: WorkflowGraph,
    node: WorkflowNode,
    context: dict | None,
    map_iters: dict[str, int],
) -> tuple[str, list[int], dict[str, int], Any | None]:
    """Advance one map item; return body step ids + current item.

    Returns ``(\"body\", body_ids, iters, item)`` or ``(\"exit\", [], iters, None)``.
    """
    iters = dict(map_iters or {})
    items = expand_map(node, context)
    idx = int(iters.get(node.id, 0))
    if idx >= len(items):
        return "exit", [], iters, None
    item = items[idx]
    iters[node.id] = idx + 1
    return "body", body_step_ids(graph, node), iters, item
