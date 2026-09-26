"""Structural Tasks workbench.

Core cases are domain-free. Pack cases are loaded from
``domain_packs/<id>/banks/tasks_workbench.yaml`` and are never inlined here.

The bench compiles each case onto the workflow graph, walks guards, applies
edits, and checks consent, citations, and agent tool sets. It does not call
a model and it does not write the host. A pass here is not a live Tasks score.

CLI::

    python -m ai.eval.tasks_workbench
    python -m ai.eval.tasks_workbench --gate
    python -m ai.eval.tasks_workbench --write
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from ai.engine.workflow.graph import WorkflowGraph, validate_graph
from ai.engine.workflow.guards import GuardError, eval_guard

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_BANK = Path(__file__).resolve().parent / "tasks_workbench_core.yaml"
PACKS_ROOT = REPO_ROOT / "domain_packs"
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"
OUT_FILE = EVIDENCE / "PV2-tasks-workbench-2026-09-26.json"


def _load_yaml(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = doc.get("cases") if isinstance(doc, dict) else doc
    return [row for row in rows or [] if isinstance(row, dict) and row.get("id")]


def pack_banks(root: Path = PACKS_ROOT) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob("*/banks/tasks_workbench.yaml"))


def load_cases() -> list[dict]:
    cases = _load_yaml(CORE_BANK)
    for path in pack_banks():
        for row in _load_yaml(path):
            row = dict(row)
            row.setdefault("pack", path.parent.parent.name)
            cases.append(row)
    return cases


def _graph_dict(case: dict) -> dict:
    raw = copy.deepcopy(case.get("graph") or {})
    ctx = dict(case.get("context") or {})
    for edit in case.get("edits") or []:
        if not isinstance(edit, dict):
            continue
        op = edit.get("op")
        if op == "set_context":
            ctx.update(edit.get("context") or {})
        elif op == "set_args":
            for node in raw.get("nodes") or []:
                if node.get("id") == edit.get("node"):
                    args = dict(node.get("tool_args") or {})
                    args.update(edit.get("args") or {})
                    node["tool_args"] = args
        elif op == "drop_edge":
            raw["edges"] = [
                edge for edge in raw.get("edges") or []
                if not (edge.get("source") == edit.get("source") and edge.get("target") == edit.get("target"))
            ]
    raw["_context"] = ctx
    return raw


def _as_graph(raw: dict) -> WorkflowGraph:
    body = {k: v for k, v in raw.items() if k != "_context"}
    return WorkflowGraph.from_dict(body)


def _outgoing(graph: WorkflowGraph) -> dict[str, list]:
    out: dict[str, list] = {}
    for edge in graph.edges:
        out.setdefault(edge.source, []).append(edge)
    return out


def _take(edges: list, ctx: dict):
    for edge in edges:
        if not edge.guard:
            continue
        try:
            if eval_guard(edge.guard, ctx):
                return edge
        except GuardError:
            continue
    for edge in edges:
        if edge.is_default or not edge.guard:
            return edge
    return None


def walk(graph: WorkflowGraph, ctx: dict) -> list[str]:
    """The path the guards take. A parallel node records each direct target."""
    if not graph.entry:
        return []
    out = _outgoing(graph)
    by_id = {node.id: node for node in graph.nodes}
    path: list[str] = []
    seen: set[str] = set()
    current = graph.entry
    while current and current not in seen and len(path) < 40:
        seen.add(current)
        path.append(current)
        node = by_id.get(current)
        edges = out.get(current) or []
        if node is None or node.node_type in {"succeed", "fail"}:
            break
        if node.node_type == "parallel":
            path.extend(edge.target for edge in edges if edge.target not in path)
            break
        taken = _take(edges, ctx) if node.node_type == "choice" else (edges[0] if edges else None)
        current = taken.target if taken is not None else ""
    return path


def _gated(graph: WorkflowGraph, path: list[str]) -> bool:
    by_id = {node.id: node for node in graph.nodes}
    consented = False
    for node_id in path:
        node = by_id.get(node_id)
        if node is None:
            continue
        if node.node_type == "human" or (node.meta or {}).get("consent"):
            consented = True
        if node.is_mutation and node.node_type != "human" and not consented:
            return False
    return True


def _cite(passages: list, tokens: list) -> list[str]:
    hits = []
    for passage in passages:
        text = str(passage.get("text") or "").lower()
        if tokens and all(str(token).lower() in text for token in tokens):
            hits.append(str(passage.get("id")))
    return hits


def _check(case: dict) -> str:
    lane = case.get("lane") or "graph"
    expect = case.get("expect") or {}
    if lane == "retrieval":
        passages = list(case.get("passages") or [])
        tokens = list(case.get("tokens") or [])
        hits = _cite(passages, tokens)
        if "cited" in expect and hits != list(expect["cited"]):
            return f"cited={hits}"
        if expect.get("refuses_when_empty") and _cite([], tokens):
            return "empty passages still cited"
        return ""
    if lane == "agents":
        agents = [row for row in case.get("agents") or [] if isinstance(row, dict)]
        roles = [row.get("role") for row in agents]
        if "roles" in expect and roles != list(expect["roles"]):
            return f"roles={roles}"
        by_role = {row.get("role"): row for row in agents}
        for role in expect.get("readonly_roles") or []:
            if (by_role.get(role) or {}).get("mutation_tools"):
                return f"{role} has mutation tools"
        if "critic_tools" in expect and (by_role.get("critic") or {}).get("tools") != list(expect["critic_tools"]):
            return "critic tools"
        return ""

    raw = _graph_dict(case)
    ctx = raw.pop("_context", {})
    try:
        graph = _as_graph(raw)
    except (KeyError, TypeError, ValueError) as exc:
        return f"graph:{exc}"
    errors = validate_graph(graph)
    if "valid" in expect and bool(errors) == bool(expect["valid"]):
        return "invalid" if errors else "expected invalid"
    if expect.get("valid") is False:
        return ""
    path = walk(graph, ctx)
    if "path" in expect and path != list(expect["path"]):
        return f"path={path}"
    missing = [node for node in expect.get("path_has") or [] if node not in path]
    if missing:
        return f"missing={missing}"
    extra = [node for node in expect.get("path_excludes") or [] if node in path]
    if extra:
        return f"present={extra}"
    if expect.get("mutations_gated") and not _gated(graph, path):
        return "ungated mutation"
    if expect.get("detects") == "ungated_mutation" and _gated(graph, path):
        return "trap not detected"
    by_id = {node.id: node for node in graph.nodes}
    for node_id, limit in (expect.get("max_iterations") or {}).items():
        if (by_id.get(node_id).max_iterations if by_id.get(node_id) else None) != limit:
            return f"max_iterations {node_id}"
    for node_id, collection in (expect.get("collection_path") or {}).items():
        if (by_id.get(node_id).collection_path if by_id.get(node_id) else None) != collection:
            return f"collection {node_id}"
    for node_id, target in (expect.get("compensation") or {}).items():
        if (by_id.get(node_id).compensation if by_id.get(node_id) else None) != target:
            return f"compensation {node_id}"
    for node_id, args in (expect.get("args") or {}).items():
        actual = dict((by_id.get(node_id).tool_args if by_id.get(node_id) else {}) or {})
        for key, value in dict(args).items():
            if actual.get(key) != value:
                return f"args {node_id}.{key}={actual.get(key)}"
    for node_id, hidden in (expect.get("hidden_on") or {}).items():
        blob = json.dumps((by_id.get(node_id).tool_args if by_id.get(node_id) else {}) or {})
        for name in hidden:
            if str(name) in blob:
                return f"hidden {name}"
    differ = expect.get("roles_differ") or []
    if len(differ) == 2:
        left = (by_id.get(differ[0]).meta or {}).get("role") if by_id.get(differ[0]) else None
        right = (by_id.get(differ[1]).meta or {}).get("role") if by_id.get(differ[1]) else None
        if not left or not right or left == right:
            return "roles do not differ"
    return ""


def score(cases: list[dict] | None = None) -> dict[str, Any]:
    rows = cases if cases is not None else load_cases()
    misses = []
    for case in rows:
        why = _check(case)
        if why:
            misses.append({"id": case.get("id"), "why": why, "pack": case.get("pack") or "core"})
    n = len(rows)
    return {
        "tier": "structural",
        "n": n,
        "passed": n - len(misses),
        "misses": misses,
        "gate_pass": n > 0 and not misses,
        "live": "not a Tasks retest — T9 stays missing",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Structural Tasks workbench")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    result = score()
    print(
        f"tasks workbench  {result['passed']}/{result['n']}  "
        f"gate={'pass' if result['gate_pass'] else 'FAIL'}  tier=structural"
    )
    for miss in result["misses"]:
        print(f"  {miss['id']}: {miss['why']}")
    if args.write:
        OUT_FILE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT_FILE}")
    if args.gate and not result["gate_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
