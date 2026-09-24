"""W-1 — typed workflow graph schema + old-plan compile shim.

Backward compatible: today's ``Plan`` (steps + phases + depends_on) compiles
into a ``WorkflowGraph`` of ``task`` nodes. New node types (choice, parallel,
map, loop, wait, human, observe, succeed, fail, subflow) validate here; the
driver (W-3) consumes the graph later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

__all__ = [
    "NODE_TYPES",
    "WorkflowEdge",
    "WorkflowGraph",
    "WorkflowNode",
    "compile_plan_to_graph",
    "validate_graph",
    "GraphValidationError",
]

NODE_TYPES = frozenset({
    "task",
    "choice",
    "parallel",
    "map",
    "loop",
    "wait",
    "human",
    "subflow",
    "observe",
    "succeed",
    "fail",
})

_TERMINAL = frozenset({"succeed", "fail"})


class GraphValidationError(ValueError):
    """Raised when a workflow graph fails structural validation."""


@dataclass
class WorkflowEdge:
    """Directed edge; optional guard is a W-2 expression string."""
    source: str
    target: str
    guard: str | None = None
    label: str | None = None
    is_default: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v is not False}


@dataclass
class WorkflowNode:
    """One node in the workflow graph."""
    id: str
    node_type: str = "task"
    intent: str = ""
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    is_mutation: bool = False
    # Resilience (W-4); stored now, enforced by the driver later.
    retry: dict | None = None
    catch: list | None = None
    timeout_ms: int | None = None
    compensation: str | None = None
    # Loop / map extras
    max_iterations: int | None = None
    collection_path: str | None = None
    # Parallel join policy: all | any | quorum
    join: str | None = None
    # Opaque extras for UI / planner
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != {} and v != []}


@dataclass
class WorkflowGraph:
    """Declarative workflow graph (ASL-inspired)."""
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    entry: str | None = None
    version: str = "1"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "entry": self.entry,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "WorkflowGraph":
        nodes = [
            WorkflowNode(
                id=str(n["id"]),
                node_type=n.get("node_type", "task"),
                intent=n.get("intent") or "",
                tool_name=n.get("tool_name"),
                tool_args=dict(n.get("tool_args") or {}),
                is_mutation=bool(n.get("is_mutation")),
                retry=n.get("retry"),
                catch=n.get("catch"),
                timeout_ms=n.get("timeout_ms"),
                compensation=n.get("compensation"),
                max_iterations=n.get("max_iterations"),
                collection_path=n.get("collection_path"),
                join=n.get("join"),
                meta=dict(n.get("meta") or {}),
            )
            for n in (raw.get("nodes") or [])
        ]
        edges = [
            WorkflowEdge(
                source=str(e["source"]),
                target=str(e["target"]),
                guard=e.get("guard"),
                label=e.get("label"),
                is_default=bool(e.get("is_default")),
            )
            for e in (raw.get("edges") or [])
        ]
        return cls(
            nodes=nodes,
            edges=edges,
            entry=raw.get("entry"),
            version=str(raw.get("version") or "1"),
        )


def validate_graph(graph: WorkflowGraph) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []
    ids = [n.id for n in graph.nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    id_set = set(ids)
    for n in graph.nodes:
        if n.node_type not in NODE_TYPES:
            errors.append(f"node {n.id}: unknown node_type {n.node_type!r}")
        if n.node_type == "loop" and (n.max_iterations is None or n.max_iterations < 1):
            errors.append(f"node {n.id}: loop requires max_iterations >= 1")
        if n.node_type == "map" and not n.collection_path:
            errors.append(f"node {n.id}: map requires collection_path")
        if n.node_type == "parallel" and n.join not in (None, "all", "any", "quorum"):
            errors.append(f"node {n.id}: parallel join must be all|any|quorum")
    for e in graph.edges:
        if e.source not in id_set:
            errors.append(f"edge source unknown: {e.source}")
        if e.target not in id_set:
            errors.append(f"edge target unknown: {e.target}")
    if graph.nodes and not graph.entry:
        errors.append("entry node is required when nodes are present")
    elif graph.entry and graph.entry not in id_set:
        errors.append(f"entry {graph.entry!r} not in nodes")
    # choice nodes need a default edge or at least one outgoing edge
    out_by_src: dict[str, list[WorkflowEdge]] = {}
    for e in graph.edges:
        out_by_src.setdefault(e.source, []).append(e)
    for n in graph.nodes:
        if n.node_type == "choice":
            outs = out_by_src.get(n.id, [])
            if not outs:
                errors.append(f"choice node {n.id} has no outgoing edges")
            elif not any(e.is_default or not e.guard for e in outs):
                errors.append(f"choice node {n.id} needs a default (unguarded) edge")
        if n.node_type in _TERMINAL and out_by_src.get(n.id):
            errors.append(f"terminal node {n.id} must not have outgoing edges")
    if graph.entry in id_set:
        reachable: set[str] = set()
        pending = [graph.entry]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(edge.target for edge in out_by_src.get(current, []))
        disconnected = sorted(id_set - reachable)
        if disconnected:
            errors.append(
                "nodes unreachable from entry: " + ", ".join(disconnected)
            )
    return errors


def compile_plan_to_graph(plan: Any) -> WorkflowGraph:
    """Compile a legacy ``Plan`` (or plan-like object) into a WorkflowGraph.

    Mapping:
      * sequential phase / depends_on chain → edges between ``task`` nodes
      * parallel phase → a ``parallel`` gateway + fan-out/fan-in task edges
      * bare steps with depends_on → edges from deps to step
    """
    steps = list(getattr(plan, "steps", None) or [])
    phases = list(getattr(plan, "phases", None) or [])

    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []
    step_node_id = {s.step_id: f"t{s.step_id}" for s in steps}

    for s in steps:
        nodes.append(
            WorkflowNode(
                id=step_node_id[s.step_id],
                node_type="task",
                intent=getattr(s, "intent", "") or "",
                tool_name=getattr(s, "tool_name", None),
                tool_args=dict(getattr(s, "tool_args", None) or {}),
                is_mutation=bool(getattr(s, "is_mutation", False)),
                meta={
                    "step_id": s.step_id,
                    "agent_role": getattr(s, "agent_role", None),
                },
            )
        )

    # Explicit dependencies are contractual and must survive phase compilation.
    for s in steps:
        for dep in getattr(s, "depends_on", None) or []:
            if dep in step_node_id:
                edges.append(WorkflowEdge(
                    source=step_node_id[dep],
                    target=step_node_id[s.step_id],
                ))

    # Phase-aware edges. Phase boundaries are connected in declared order so
    # a later parallel gateway can never become a second, disconnected entry.
    if phases:
        previous_exit: str | None = None
        for phase in phases:
            strategy = getattr(phase, "strategy", None) or "sequential"
            step_ids = [
                sid for sid in (getattr(phase, "step_ids", None) or [])
                if sid in step_node_id
            ]
            if not step_ids:
                continue
            if strategy == "parallel" and len(step_ids) > 1:
                gid = f"p{getattr(phase, 'phase_id', phase)}"
                join_id = f"{gid}_join"
                nodes.append(
                    WorkflowNode(
                        id=gid,
                        node_type="parallel",
                        intent=getattr(phase, "name", "") or "parallel",
                        join="all",
                        meta={"phase_id": getattr(phase, "phase_id", None)},
                    )
                )
                nodes.append(
                    WorkflowNode(
                        id=join_id,
                        node_type="task",
                        intent="join",
                        meta={"synthetic": True, "join_for": gid},
                    )
                )
                # Wire prior deps into the parallel gateway when present.
                for sid in step_ids:
                    nid = step_node_id[sid]
                    edges.append(WorkflowEdge(source=gid, target=nid))
                    edges.append(WorkflowEdge(source=nid, target=join_id))
                phase_entry = gid
                phase_exit = join_id
            else:
                # sequential within phase
                for a, b in zip(step_ids, step_ids[1:]):
                    edges.append(
                        WorkflowEdge(source=step_node_id[a], target=step_node_id[b])
                    )
                phase_entry = step_node_id[step_ids[0]]
                phase_exit = step_node_id[step_ids[-1]]
            if previous_exit is not None:
                edges.append(WorkflowEdge(
                    source=previous_exit,
                    target=phase_entry,
                ))
            previous_exit = phase_exit
    else:
        # If no depends_on at all, chain in step_id order.
        if steps and not edges:
            ordered = sorted(steps, key=lambda x: x.step_id)
            for a, b in zip(ordered, ordered[1:]):
                edges.append(
                    WorkflowEdge(
                        source=step_node_id[a.step_id],
                        target=step_node_id[b.step_id],
                    )
                )

    entry = None
    if steps:
        # Prefer a node with no incoming edges.
        targets = {e.target for e in edges}
        roots = [step_node_id[s.step_id] for s in steps if step_node_id[s.step_id] not in targets]
        # Parallel gateways may be roots too
        for n in nodes:
            if n.node_type == "parallel" and n.id not in targets:
                roots.insert(0, n.id)
        entry = roots[0] if roots else step_node_id[min(step_node_id, key=lambda k: k)]

    graph = WorkflowGraph(nodes=nodes, edges=_dedupe_edges(edges), entry=entry)
    errs = validate_graph(graph)
    if errs:
        raise GraphValidationError("; ".join(errs))
    return graph


def _dedupe_edges(edges: Iterable[WorkflowEdge]) -> list[WorkflowEdge]:
    seen: set[tuple] = set()
    out: list[WorkflowEdge] = []
    for e in edges:
        key = (e.source, e.target, e.guard, e.is_default)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
