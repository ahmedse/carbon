"""W-3 — pure graph driver helpers (eligibility + choice routing).

Callers compile a Plan → WorkflowGraph, then use ``ready_nodes`` /
``advance_and_ready_tasks`` to decide what runs next. Journaling of guard
decisions is done by the host via the ``on_choice`` callback.
"""

from __future__ import annotations

from typing import Callable, Iterable

from ai.engine.workflow.graph import WorkflowEdge, WorkflowGraph, WorkflowNode
from ai.engine.workflow.guards import GuardError, eval_guard

__all__ = [
    "ready_nodes",
    "choose_edge",
    "decide_choice",
    "outgoing",
    "incoming",
    "advance_and_ready_tasks",
    "step_id_for_node",
    "resolve_catch",
    "node_for_step",
]

# Gateways that auto-complete when their predecessors are done (no PlanStep).
# ``observe`` / ``loop`` / ``map`` / ``wait`` are host-driven (heal / iterate /
# fan-out / timer). Empty waits still complete via host evaluate_wait → immediate.
_AUTO_ADVANCE = frozenset({"parallel", "succeed", "choice"})


def outgoing(graph: WorkflowGraph, node_id: str) -> list[WorkflowEdge]:
    return [e for e in graph.edges if e.source == node_id]


def incoming(graph: WorkflowGraph, node_id: str) -> list[WorkflowEdge]:
    return [e for e in graph.edges if e.target == node_id]


def step_id_for_node(node: WorkflowNode) -> int | None:
    """Map a graph task node to a PlanStep.step_id, or None if synthetic."""
    if node.node_type != "task":
        return None
    meta = node.meta or {}
    if meta.get("synthetic"):
        return None
    if "step_id" in meta and meta["step_id"] is not None:
        try:
            return int(meta["step_id"])
        except (TypeError, ValueError):
            return None
    if node.id.startswith("t") and node.id[1:].isdigit():
        return int(node.id[1:])
    return None


def node_for_step(graph: WorkflowGraph, step_id: int) -> WorkflowNode | None:
    """Return the task node whose meta.step_id matches, if any."""
    for n in graph.nodes:
        if step_id_for_node(n) == step_id:
            return n
    # Fallback: conventional id ``t{step_id}``
    by_id = {n.id: n for n in graph.nodes}
    return by_id.get(f"t{step_id}")


def resolve_catch(
    node: WorkflowNode | None,
    error_class: str = "permanent",
) -> str | None:
    """Return the catch-target node id for ``error_class``, or None.

    ``catch`` entries look like::

        [{"on": ["permanent", "timeout"], "next": "observe_1"}]
    """
    if node is None:
        return None
    for rule in node.catch or []:
        if not isinstance(rule, dict):
            continue
        on = rule.get("on") or ["permanent", "timeout", "transient"]
        if not isinstance(on, (list, tuple, set)):
            on = [on]
        if error_class in on or "*" in on or "all" in on:
            nxt = rule.get("next")
            if nxt:
                return str(nxt)
    return None


def choose_edge(
    graph: WorkflowGraph,
    node_id: str,
    context: dict | None = None,
) -> WorkflowEdge | None:
    """XOR gateway: first edge whose guard is true, else the default edge."""
    outs = outgoing(graph, node_id)
    if not outs:
        return None
    ctx = context or {}
    default: WorkflowEdge | None = None
    for e in outs:
        if e.is_default or not e.guard:
            default = e
            continue
        try:
            if eval_guard(e.guard, ctx):
                return e
        except GuardError:
            continue
    return default


def decide_choice(
    graph: WorkflowGraph,
    node_id: str,
    context: dict | None = None,
) -> tuple[WorkflowEdge | None, list[dict]]:
    """Evaluate all outgoing guards; return (chosen_edge, evaluation_log).

    ``evaluation_log`` entries are journal-ready payloads for ``guard_eval``
    events (ADR-0034). The chosen edge is the same as ``choose_edge``.
    """
    outs = outgoing(graph, node_id)
    ctx = context or {}
    evaluations: list[dict] = []
    for e in outs:
        if e.is_default or not e.guard:
            evaluations.append({
                "source": e.source,
                "target": e.target,
                "guard": e.guard,
                "is_default": bool(e.is_default or not e.guard),
                "result": None,
            })
            continue
        try:
            result = eval_guard(e.guard, ctx)
            evaluations.append({
                "source": e.source,
                "target": e.target,
                "guard": e.guard,
                "is_default": False,
                "result": bool(result),
            })
        except GuardError as err:
            evaluations.append({
                "source": e.source,
                "target": e.target,
                "guard": e.guard,
                "is_default": False,
                "result": False,
                "error": str(err),
            })
    chosen = choose_edge(graph, node_id, ctx)
    return chosen, evaluations


def ready_nodes(
    graph: WorkflowGraph,
    completed: Iterable[str],
    *,
    context: dict | None = None,
    failed: Iterable[str] | None = None,
    skipped: Iterable[str] | None = None,
) -> list[WorkflowNode]:
    """Return nodes eligible to run given completed (and failed) node ids.

    Rules (subset of ASL / BPMN):
      * ``task`` / ``human`` / ``observe`` / ``wait`` / ``subflow`` / ``succeed`` /
        ``fail``: ready when every predecessor is completed (or failed-but-caught —
        catch routing is W-4; for now only completed predecessors unlock).
      * ``choice``: same as task; after it runs, ``choose_edge`` picks the next.
      * ``parallel``: ready when predecessors completed; its children are ready
        once the parallel node itself is marked completed (fan-out start).
      * ``map`` / ``loop``: treated like task until the full driver lands.
    """
    done = set(completed)
    failed_set = set(failed or ())
    skipped_set = set(skipped or ())
    by_id = {n.id: n for n in graph.nodes}
    ready: list[WorkflowNode] = []

    for node in graph.nodes:
        if node.id in done or node.id in failed_set or node.id in skipped_set:
            continue
        preds = incoming(graph, node.id)
        if not preds:
            # entry / roots
            if graph.entry and node.id != graph.entry and any(
                n.id == graph.entry for n in graph.nodes
            ):
                # non-entry roots only if entry already done (parallel join etc.)
                if graph.entry not in done:
                    continue
            ready.append(node)
            continue

        # Skipped predecessors do not unlock — and do not block — a node.
        # Active preds must all be completed (XOR merge after a choice).
        active_preds = [e for e in preds if e.source not in skipped_set]
        if not active_preds:
            continue
        if not all(e.source in done for e in active_preds):
            continue

        # If any predecessor is a choice node, only the chosen edge's target
        # is ready (re-evaluate with context for determinism under replay).
        choice_preds = [
            e for e in active_preds
            if by_id.get(e.source) and by_id[e.source].node_type == "choice"
        ]
        if choice_preds:
            unlocked = False
            for e in choice_preds:
                chosen = choose_edge(graph, e.source, context)
                if chosen and chosen.target == node.id:
                    unlocked = True
                    break
            if not unlocked:
                continue

        ready.append(node)

    return ready


def _descendants(graph: WorkflowGraph, start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for e in outgoing(graph, cur):
            if e.target not in seen:
                stack.append(e.target)
    return seen


def advance_and_ready_tasks(
    graph: WorkflowGraph,
    completed_step_ids: Iterable[int],
    context: dict | None = None,
    *,
    completed_gateways: set[str] | None = None,
    skipped_graph_ids: set[str] | None = None,
    on_choice: Callable[[str, WorkflowEdge | None, list[dict]], None] | None = None,
) -> tuple[list[int], set[int], set[str], set[str]]:
    """Advance auto gateways / choices; return ready + skipped PlanStep ids.

    Returns
    -------
    ready_step_ids
        Task step_ids eligible to execute now.
    newly_skipped_step_ids
        Task step_ids on unchosen branches (caller should drop from remaining).
    completed_gateways
        Updated set of auto-advanced gateway node ids (carry across loop turns).
    skipped_graph_ids
        Updated set of skipped graph node ids.
    """
    by_id = {n.id: n for n in graph.nodes}
    step_to_node: dict[int, str] = {}
    for n in graph.nodes:
        sid = step_id_for_node(n)
        if sid is not None:
            step_to_node[sid] = n.id

    done_steps = set(completed_step_ids)
    gateways = set(completed_gateways or ())
    skipped = set(skipped_graph_ids or ())
    newly_skipped_steps: set[int] = set()
    ctx = context or {}

    # Seed completed graph nodes from finished tasks.
    completed_graph = set(gateways)
    for sid in done_steps:
        nid = step_to_node.get(sid)
        if nid:
            completed_graph.add(nid)

    # Iteratively auto-advance gateways + synthetic joins until stable.
    progressed = True
    while progressed:
        progressed = False
        ready = ready_nodes(
            graph, completed_graph, context=ctx, skipped=skipped,
        )
        for node in ready:
            sid = step_id_for_node(node)
            if sid is not None:
                continue  # real PlanStep — caller executes
            if node.id in completed_graph or node.id in skipped:
                continue

            if node.node_type == "choice":
                chosen, evaluations = decide_choice(graph, node.id, ctx)
                if on_choice is not None:
                    on_choice(node.id, chosen, evaluations)
                # Skip unchosen branches, but keep nodes still reachable from
                # the chosen path (diamond join after XOR).
                chosen_target = chosen.target if chosen else None
                chosen_reach = (
                    _descendants(graph, chosen_target) if chosen_target else set()
                )
                for e in outgoing(graph, node.id):
                    if chosen_target is not None and e.target == chosen_target:
                        continue
                    for desc in _descendants(graph, e.target):
                        if desc in chosen_reach or desc in skipped:
                            continue
                        skipped.add(desc)
                        dn = by_id.get(desc)
                        if dn is None:
                            continue
                        dsid = step_id_for_node(dn)
                        if dsid is not None and dsid not in done_steps:
                            newly_skipped_steps.add(dsid)
                completed_graph.add(node.id)
                gateways.add(node.id)
                progressed = True
                continue

            if node.node_type == "wait":
                # Host must evaluate timer / until and add to completed_gateways.
                continue

            if node.node_type in _AUTO_ADVANCE or sid is None:
                # parallel fan-out, synthetic join, observe (host may pre-complete) …
                completed_graph.add(node.id)
                gateways.add(node.id)
                progressed = True

    ready_tasks = []
    for node in ready_nodes(
        graph, completed_graph, context=ctx, skipped=skipped,
    ):
        sid = step_id_for_node(node)
        if sid is None:
            continue
        if sid in done_steps or sid in newly_skipped_steps:
            continue
        if node.id in skipped:
            continue
        ready_tasks.append(sid)

    return ready_tasks, newly_skipped_steps, gateways, skipped
