"""Expand compact specs into a large structural Tasks bank.

Eval-only. No engine phrase tables. Core cases stay pack-free.
Pack specs live in domain_packs/<id>/banks/tasks_workbench_expand.yaml.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ai.engine.workflow.guards import GuardError, eval_guard

PACKS_ROOT = Path(__file__).resolve().parents[3] / "domain_packs"


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return doc if isinstance(doc, dict) else {}


def _guard_holds(expr: str, ctx: dict) -> bool:
    try:
        return bool(eval_guard(expr, ctx))
    except GuardError:
        return False


def expand_core() -> list[dict]:
    cases: list[dict] = []
    cases.extend(_core_guards())
    cases.extend(_core_parallels())
    cases.extend(_core_retrieval())
    cases.extend(_core_agents())
    cases.extend(_core_invalid())
    cases.extend(_core_loops_maps())
    cases.extend(_core_nested())
    cases.extend(_core_hidden())
    cases.extend(_core_binds())
    cases.extend(_core_consent_order())
    cases.extend(_core_citation_strict())
    cases.extend(_core_toolsets())
    cases.extend(_core_compensate_core())
    cases.extend(_core_edit_consent())
    cases.extend(_core_hidden_broad())
    return cases


def expand_packs(root: Path = PACKS_ROOT) -> list[dict]:
    cases: list[dict] = []
    if not root.is_dir():
        return cases
    for path in sorted(root.glob("*/banks/tasks_workbench_expand.yaml")):
        pack = path.parent.parent.name
        spec = _load(path)
        for row in _expand_pack(pack, spec):
            row = dict(row)
            row.setdefault("pack", pack)
            cases.append(row)
    return cases


def _core_guards() -> list[dict]:
    cases = []
    ops = ("<=", ">=", "==", "!=", "<", ">")
    values = (0, 1, 5, 9, 10, 11, 15, 30)
    threshold = 10
    for op in ops:
        for value in values:
            ctx = {"band": value}
            guard = f"band {op} {threshold}"
            take = _guard_holds(guard, ctx)
            cid = f"core.gen.guard.{_op_slug(op)}.{value}-vs-{threshold}"
            expect: dict[str, Any] = {"valid": True, "mutations_gated": True}
            if take:
                expect["path"] = ["read", "gate", "ask", "write", "done"]
            else:
                expect["path"] = ["read", "gate", "stop"]
                expect["path_excludes"] = ["write"]
            cases.append({
                "id": cid,
                "lane": "graph",
                "brief": f"Numeric {guard} with band={value}.",
                "context": ctx,
                "graph": _choice_graph(guard),
                "expect": expect,
            })
    return cases


def _op_slug(op: str) -> str:
    return {"<=": "le", ">=": "ge", "==": "eq", "!=": "ne", "<": "lt", ">": "gt"}[op]


def _choice_graph(guard: str) -> dict:
    return {
        "entry": "read",
        "nodes": [
            {"id": "read", "node_type": "task", "tool_name": "read_record"},
            {"id": "gate", "node_type": "choice"},
            {"id": "ask", "node_type": "human"},
            {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
            {"id": "stop", "node_type": "fail"},
            {"id": "done", "node_type": "succeed"},
        ],
        "edges": [
            {"source": "read", "target": "gate"},
            {"source": "gate", "target": "ask", "guard": guard},
            {"source": "gate", "target": "stop", "is_default": True},
            {"source": "ask", "target": "write"},
            {"source": "write", "target": "done"},
        ],
    }


def _core_parallels() -> list[dict]:
    cases = []
    for width in (2, 3, 4):
        for join in ("all", "any", "quorum"):
            for after in ("succeed", "gated", "ungated"):
                branches = [f"b{i}" for i in range(width)]
                nodes = [
                    {"id": "fan", "node_type": "parallel", "join": join},
                    *[
                        {"id": bid, "node_type": "task", "tool_name": "read_record"}
                        for bid in branches
                    ],
                    {"id": "join", "node_type": "task", "tool_name": "merge_records"},
                ]
                edges = (
                    [{"source": "fan", "target": bid} for bid in branches]
                    + [{"source": bid, "target": "join"} for bid in branches]
                )
                expect: dict[str, Any] = {
                    "valid": True,
                    "join": {"fan": join},
                    "path_has": ["fan", *branches, "join"],
                }
                if after == "succeed":
                    nodes += [{"id": "done", "node_type": "succeed"}]
                    edges += [{"source": "join", "target": "done"}]
                    expect["path_has"] = [*expect["path_has"], "done"]
                    expect["mutations_gated"] = True
                elif after == "gated":
                    nodes += [
                        {"id": "ask", "node_type": "human"},
                        {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                        {"id": "done", "node_type": "succeed"},
                    ]
                    edges += [
                        {"source": "join", "target": "ask"},
                        {"source": "ask", "target": "write"},
                        {"source": "write", "target": "done"},
                    ]
                    expect["path_has"] = [*expect["path_has"], "ask", "write"]
                    expect["mutations_gated"] = True
                else:
                    nodes += [
                        {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                        {"id": "done", "node_type": "succeed"},
                    ]
                    edges += [
                        {"source": "join", "target": "write"},
                        {"source": "write", "target": "done"},
                    ]
                    expect["detects"] = "ungated_mutation"
                cases.append({
                    "id": f"core.gen.parallel.w{width}.{join}.{after}",
                    "lane": "graph",
                    "brief": f"Parallel width {width}, join {join}, then {after}.",
                    "graph": {"entry": "fan", "nodes": nodes, "edges": edges},
                    "expect": expect,
                })
    return cases


def _core_retrieval() -> list[dict]:
    cases = []
    hits = [
        ("alpha-15", "Code ALPHA ceiling is 15.", ["ALPHA", "15"]),
        ("beta-9", "Code BETA ceiling is 9 units.", ["BETA", "9", "units"]),
        ("gamma-ok", "Flag GAMMA is ready.", ["GAMMA", "ready"]),
        ("delta-cap", "Cap DELTA holds 40.", ["DELTA", "40"]),
    ]
    for hid, text, tokens in hits:
        cases.append({
            "id": f"core.gen.retrieval.hit.{hid}",
            "lane": "retrieval",
            "brief": "Cite the passage that holds every token.",
            "passages": [
                {"id": "hit", "text": text},
                {"id": "decoy", "text": "Unrelated note with no matching code."},
            ],
            "tokens": tokens,
            "expect": {"cited": ["hit"], "refuses_when_empty": True},
        })
        cases.append({
            "id": f"core.gen.retrieval.miss.{hid}",
            "lane": "retrieval",
            "brief": "Tokens the passages do not hold are a refuse.",
            "passages": [{"id": "other", "text": "Unrelated note with no matching code."}],
            "tokens": tokens,
            "expect": {"cited": [], "refuses_when_empty": True},
        })
        if len(tokens) >= 2:
            cases.append({
                "id": f"core.gen.retrieval.split.{hid}",
                "lane": "retrieval",
                "brief": "Tokens split across passages do not cite.",
                "passages": [
                    {"id": "p1", "text": f"Token {tokens[0]} only."},
                    {"id": "p2", "text": f"Token {tokens[1]} only."},
                ],
                "tokens": tokens[:2],
                "expect": {"cited": [], "refuses_when_empty": True},
            })
    cases.append({
        "id": "core.gen.retrieval.empty",
        "lane": "retrieval",
        "brief": "Empty corpus refuses.",
        "passages": [],
        "tokens": ["ALPHA"],
        "expect": {"cited": [], "refuses_when_empty": True},
    })
    return cases


def _core_agents() -> list[dict]:
    cases = []
    readonly = ("researcher", "planner", "critic")
    for role in readonly:
        cases.append({
            "id": f"core.gen.agents.{role}-write-trap",
            "lane": "agents",
            "brief": f"A {role} that carries a write tool is a trap.",
            "agents": [
                {"role": role, "tools": ["write_record"], "mutation_tools": ["write_record"]},
                {"role": "critic" if role != "critic" else "researcher", "tools": [], "mutation_tools": []},
            ],
            "expect": {"detects": "mutation_on_readonly", "readonly_roles": [role]},
        })
        cases.append({
            "id": f"core.gen.agents.{role}-readonly",
            "lane": "agents",
            "brief": f"{role} stays readonly.",
            "agents": [
                {"role": "orchestrator", "tools": ["search_knowledge"], "mutation_tools": []},
                {"role": role, "tools": ["search_knowledge", "read_record"], "mutation_tools": []},
                {"role": "critic", "tools": [], "mutation_tools": []},
            ],
            "expect": {
                "readonly_roles": [role, "critic"],
                "critic_tools": [],
            },
        })
    return cases


def _core_invalid() -> list[dict]:
    return [
        {
            "id": "core.gen.trap.join-bogus",
            "lane": "graph",
            "brief": "An unknown join policy is invalid.",
            "graph": {
                "entry": "fan",
                "nodes": [
                    {"id": "fan", "node_type": "parallel", "join": "magic"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "fan", "target": "done"}],
            },
            "expect": {"valid": False, "invalid_has": "join"},
        },
        {
            "id": "core.gen.trap.loop-zero",
            "lane": "graph",
            "brief": "A loop with max 0 is invalid.",
            "graph": {
                "entry": "retry",
                "nodes": [
                    {"id": "retry", "node_type": "loop", "max_iterations": 0, "tool_name": "read_record"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "retry", "target": "done"}],
            },
            "expect": {"valid": False, "invalid_has": "max_iterations"},
        },
        {
            "id": "core.gen.trap.duplicate-id",
            "lane": "graph",
            "brief": "Duplicate node ids are invalid.",
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "read", "node_type": "succeed"},
                ],
                "edges": [{"source": "read", "target": "read"}],
            },
            "expect": {"valid": False, "invalid_has": "duplicate"},
        },
        {
            "id": "core.gen.trap.entry-missing",
            "lane": "graph",
            "brief": "An entry that is not a node is invalid.",
            "graph": {
                "entry": "ghost",
                "nodes": [{"id": "done", "node_type": "succeed"}],
                "edges": [],
            },
            "expect": {"valid": False, "invalid_has": "entry"},
        },
    ]


def _core_loops_maps() -> list[dict]:
    cases = []
    for n in (1, 2, 3, 5, 8):
        cases.append({
            "id": f"core.gen.loop.max-{n}",
            "lane": "graph",
            "brief": f"Bounded loop max {n}.",
            "graph": {
                "entry": "retry",
                "nodes": [
                    {"id": "retry", "node_type": "loop", "max_iterations": n, "tool_name": "read_record"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "retry", "target": "done"}],
            },
            "expect": {"valid": True, "max_iterations": {"retry": n}},
        })
    for name in ("rows", "items", "units", "batch"):
        cases.append({
            "id": f"core.gen.map.{name}",
            "lane": "graph",
            "brief": f"Map walks {name}.",
            "graph": {
                "entry": "each",
                "nodes": [
                    {"id": "each", "node_type": "map", "collection_path": name, "tool_name": "read_record"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "each", "target": "done"}],
            },
            "expect": {"valid": True, "collection_path": {"each": name}},
        })
        cases.append({
            "id": f"core.gen.map.{name}.then-human",
            "lane": "graph",
            "brief": f"After map {name}, a write waits for a human.",
            "graph": {
                "entry": "each",
                "nodes": [
                    {"id": "each", "node_type": "map", "collection_path": name, "tool_name": "read_record"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "each", "target": "ask"},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "collection_path": {"each": name},
                "path_has": ["ask", "write"],
                "mutations_gated": True,
            },
        })
    for kind in ("wait", "observe", "subflow"):
        cases.append({
            "id": f"core.gen.{kind}.then-succeed",
            "lane": "graph",
            "brief": f"{kind} then stop. No write.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "step", "target": "done"}],
            },
            "expect": {"valid": True, "path": ["step", "done"], "mutations_gated": True},
        })
        cases.append({
            "id": f"core.gen.{kind}.then-human-write",
            "lane": "graph",
            "brief": f"After {kind}, a write waits for a human.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "step", "target": "ask"},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {"valid": True, "path": ["step", "ask", "write", "done"], "mutations_gated": True},
        })
    return cases


def _core_nested() -> list[dict]:
    cases = []
    for a, b, expect_path, excludes in (
        (True, True, ["read", "g1", "g2", "ask", "write", "done"], []),
        (True, False, ["read", "g1", "g2", "stop"], ["write"]),
        (False, True, ["read", "g1", "halt"], ["write"]),
        (False, False, ["read", "g1", "halt"], ["write"]),
    ):
        cases.append({
            "id": f"core.gen.nested.a{int(a)}-b{int(b)}",
            "lane": "graph",
            "brief": "Two gates. The second is only reached when the first holds.",
            "context": {"a": a, "b": b},
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "g1", "node_type": "choice"},
                    {"id": "g2", "node_type": "choice"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "halt", "node_type": "fail"},
                    {"id": "stop", "node_type": "fail"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "g1"},
                    {"source": "g1", "target": "g2", "guard": "a == true"},
                    {"source": "g1", "target": "halt", "is_default": True},
                    {"source": "g2", "target": "ask", "guard": "b == true"},
                    {"source": "g2", "target": "stop", "is_default": True},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "path": expect_path,
                **({"path_excludes": excludes} if excludes else {}),
                "mutations_gated": True,
            },
        })
    return cases


def _core_binds() -> list[dict]:
    """A detail read waits for a bound key. Halt follows the detail, never skips it."""
    cases = []
    for key, present in (("ref", 0), ("ref", 7), ("item", 0), ("item", 3)):
        take = present >= 1
        cases.append({
            "id": f"core.gen.bind.{key}.{present}",
            "lane": "graph",
            "brief": f"Detail read needs {key}. Missing key stops.",
            "context": {key: present},
            "graph": {
                "entry": "listing",
                "nodes": [
                    {"id": "listing", "node_type": "task", "tool_name": "list_records"},
                    {"id": "gate", "node_type": "choice"},
                    {"id": "detail", "node_type": "task", "tool_name": "read_record", "tool_args": {key: present}},
                    {"id": "halt", "node_type": "observe"},
                    {"id": "stop", "node_type": "fail"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "listing", "target": "gate"},
                    {"source": "gate", "target": "detail", "guard": f"{key} >= 1"},
                    {"source": "gate", "target": "stop", "is_default": True},
                    {"source": "detail", "target": "halt"},
                    {"source": "halt", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "path": ["listing", "gate", "detail", "halt", "done"] if take else ["listing", "gate", "stop"],
                **({} if take else {"path_excludes": ["detail"]}),
                "mutations_gated": True,
            },
        })
    return cases


def _core_hidden() -> list[dict]:
    cases = []
    for hidden in ("secret", "pay", "token", "hash"):
        cases.append({
            "id": f"core.gen.hidden.{hidden}",
            "lane": "graph",
            "brief": f"{hidden} stays off the read args.",
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record", "tool_args": {"ref": "a1"}},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "read", "target": "done"}],
            },
            "expect": {
                "valid": True,
                "args": {"read": {"ref": "a1"}},
                "hidden_on": {"read": [hidden]},
            },
        })
    return cases


def _core_consent_order() -> list[dict]:
    """Consent must precede every mutation. Order and separation are structural."""
    cases: list[dict] = []
    kinds = ("wait", "observe", "subflow")
    for kind in kinds:
        cases.append({
            "id": f"core.gen.consent.{kind}.before",
            "lane": "graph",
            "brief": f"{kind} then a human, then a write.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "step", "target": "ask"},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {"valid": True, "path": ["step", "ask", "write", "done"], "mutations_gated": True},
        })
        cases.append({
            "id": f"core.gen.consent.{kind}.write-before-human",
            "lane": "graph",
            "brief": f"{kind} writes before the human. That is a trap.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "ask", "node_type": "human"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "step", "target": "write"},
                    {"source": "write", "target": "ask"},
                    {"source": "ask", "target": "done"},
                ],
            },
            "expect": {"valid": True, "path": ["step", "write", "ask", "done"], "detects": "ungated_mutation"},
        })
        cases.append({
            "id": f"core.gen.consent.{kind}.two-humans-differ",
            "lane": "graph",
            "brief": "Two humans with different roles precede the write.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "ask", "node_type": "human", "meta": {"role": "requester"}},
                    {"id": "review", "node_type": "human", "meta": {"role": "approver"}},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "step", "target": "ask"},
                    {"source": "ask", "target": "review"},
                    {"source": "review", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "path": ["step", "ask", "review", "write", "done"],
                "roles_differ": ["ask", "review"],
                "mutations_gated": True,
            },
        })
        cases.append({
            "id": f"core.gen.consent.{kind}.two-humans-same",
            "lane": "graph",
            "brief": "Two humans who share a role do not separate duties.",
            "graph": {
                "entry": "step",
                "nodes": [
                    {"id": "step", "node_type": kind},
                    {"id": "ask", "node_type": "human", "meta": {"role": "reviewer"}},
                    {"id": "review", "node_type": "human", "meta": {"role": "reviewer"}},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "step", "target": "ask"},
                    {"source": "ask", "target": "review"},
                    {"source": "review", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "path": ["step", "ask", "review", "write", "done"],
                "detects": "same_role",
                "humans": ["ask", "review"],
                "mutations_gated": True,
            },
        })
    return cases


def _core_citation_strict() -> list[dict]:
    """Citation refuses when any token is missing. Match is case-insensitive."""
    cases: list[dict] = []
    cases.append({
        "id": "core.gen.cite.empty-tokens",
        "lane": "retrieval",
        "brief": "No tokens means no citation, even with passages present.",
        "passages": [{"id": "p1", "text": "Code ALPHA ceiling is 15."}],
        "tokens": [],
        "expect": {"cited": [], "refuses_when_empty": True},
    })
    cases.append({
        "id": "core.gen.cite.duplicate-hits",
        "lane": "retrieval",
        "brief": "Two passages that both hold every token are both cited, in order.",
        "passages": [
            {"id": "p1", "text": "Code ALPHA ceiling is 15."},
            {"id": "p2", "text": "Note: ALPHA ceiling 15 applies."},
        ],
        "tokens": ["ALPHA", "15"],
        "expect": {"cited": ["p1", "p2"], "refuses_when_empty": True},
    })
    cases.append({
        "id": "core.gen.cite.single-token",
        "lane": "retrieval",
        "brief": "One token cites only the passage that carries it.",
        "passages": [
            {"id": "p1", "text": "Code ALPHA ceiling is 15."},
            {"id": "p2", "text": "Code BETA ceiling is 9."},
        ],
        "tokens": ["BETA"],
        "expect": {"cited": ["p2"], "refuses_when_empty": True},
    })
    cases.append({
        "id": "core.gen.cite.missing-one-of-three",
        "lane": "retrieval",
        "brief": "A passage missing one token of three is not cited.",
        "passages": [
            {"id": "hit", "text": "Code ALPHA ceiling is 15 units."},
            {"id": "miss", "text": "Code ALPHA ceiling is 15."},
        ],
        "tokens": ["ALPHA", "15", "units"],
        "expect": {"cited": ["hit"], "refuses_when_empty": True},
    })
    cases.append({
        "id": "core.gen.cite.arabic-token",
        "lane": "retrieval",
        "brief": "Non-Latin tokens cite by substring, case-insensitively.",
        "passages": [
            {"id": "hit", "text": "رمز الفا والسقف 15."},
            {"id": "decoy", "text": "رمز بيتا والسقف 9."},
        ],
        "tokens": ["الفا", "15"],
        "expect": {"cited": ["hit"], "refuses_when_empty": True},
    })
    return cases


def _core_toolsets() -> list[dict]:
    """Roles and tool sets. A mutation tool on a readonly role is a trap."""
    cases: list[dict] = []
    for role in ("domain_specialist", "researcher", "planner", "critic"):
        cases.append({
            "id": f"core.gen.toolset.{role}.write-trap",
            "lane": "agents",
            "brief": f"A {role} that carries a write tool is a trap.",
            "agents": [
                {"role": "orchestrator", "tools": ["search_knowledge"], "mutation_tools": []},
                {"role": role, "tools": ["search_knowledge", "write_record"], "mutation_tools": ["write_record"]},
                {"role": "critic" if role != "critic" else "researcher", "tools": [], "mutation_tools": []},
            ],
            "expect": {"detects": "mutation_on_readonly", "readonly_roles": [role]},
        })
        cases.append({
            "id": f"core.gen.toolset.{role}.readonly",
            "lane": "agents",
            "brief": f"{role} stays readonly with read tools only.",
            "agents": [
                {"role": "orchestrator", "tools": ["search_knowledge"], "mutation_tools": []},
                {"role": role, "tools": ["read_record", "search_knowledge"], "mutation_tools": []},
                {"role": "critic", "tools": [], "mutation_tools": []},
            ],
            "expect": {"readonly_roles": [role], "critic_tools": []},
        })
    cases.append({
        "id": "core.gen.toolset.full-fanout-readonly",
        "lane": "agents",
        "brief": "The whole fan-out stays readonly. The critic holds no tools.",
        "agents": [
            {"role": "orchestrator", "tools": ["search_knowledge", "read_record"], "mutation_tools": []},
            {"role": "researcher", "tools": ["search_knowledge"], "mutation_tools": []},
            {"role": "planner", "tools": ["search_knowledge"], "mutation_tools": []},
            {"role": "domain_specialist", "tools": ["read_record"], "mutation_tools": []},
            {"role": "critic", "tools": [], "mutation_tools": []},
        ],
        "expect": {
            "roles": ["orchestrator", "researcher", "planner", "domain_specialist", "critic"],
            "readonly_roles": ["researcher", "critic"],
            "critic_tools": [],
        },
    })
    return cases


def _core_compensate_core() -> list[dict]:
    """A reversal is itself a mutation and still sits behind a human."""
    return [
        {
            "id": "core.gen.compensate.gated",
            "lane": "graph",
            "brief": "Read, human, write, then a named reversal.",
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True, "compensation": "undo"},
                    {"id": "undo", "node_type": "task", "tool_name": "undo_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "ask"},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                    {"source": "write", "target": "undo", "guard": "undo == true"},
                ],
            },
            "expect": {"valid": True, "path_has": ["ask", "write"], "compensation": {"write": "undo"}, "mutations_gated": True},
        },
        {
            "id": "core.gen.compensate.ungated-trap",
            "lane": "graph",
            "brief": "A reversal with no human is a trap.",
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True, "compensation": "undo"},
                    {"id": "undo", "node_type": "task", "tool_name": "undo_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "write"},
                    {"source": "write", "target": "done"},
                    {"source": "write", "target": "undo", "guard": "undo == true"},
                ],
            },
            "expect": {"valid": True, "compensation": {"write": "undo"}, "detects": "ungated_mutation"},
        },
        {
            "id": "core.gen.compensate.undo-taken-gated",
            "lane": "graph",
            "brief": "The reversal branch is walked and still sits behind the human.",
            "context": {"undo": True},
            "graph": {
                "entry": "ask",
                "nodes": [
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True, "compensation": "undo"},
                    {"id": "undo", "node_type": "task", "tool_name": "undo_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "undo", "guard": "undo == true"},
                    {"source": "write", "target": "done", "is_default": True},
                    {"source": "undo", "target": "done"},
                ],
            },
            "expect": {
                "valid": True,
                "path": ["ask", "write", "undo", "done"],
                "compensation": {"write": "undo"},
                "mutations_gated": True,
            },
        },
    ]


def _core_edit_consent() -> list[dict]:
    """An edit may re-route the graph. Consent must follow the write."""
    return [
        {
            "id": "core.gen.edit.reroute-past-consent",
            "lane": "graph",
            "brief": "An edit flips the guard so the write is reached without the human.",
            "context": {"flag": True},
            "edits": [{"op": "set_context", "context": {"flag": False}}],
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "gate", "node_type": "choice"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "gate"},
                    {"source": "gate", "target": "ask", "guard": "flag == true"},
                    {"source": "gate", "target": "write", "is_default": True},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {"valid": True, "path": ["read", "gate", "write", "done"], "detects": "ungated_mutation"},
        },
        {
            "id": "core.gen.edit.drop-consent-edge",
            "lane": "graph",
            "brief": "Dropping the consent edge leaves the write unreachable, so the edit is invalid.",
            "context": {"flag": True},
            "edits": [{"op": "drop_edge", "source": "ask", "target": "write"}],
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "ask"},
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                ],
            },
            "expect": {"valid": False, "invalid_has": "unreachable"},
        },
    ]


def _core_hidden_broad() -> list[dict]:
    """Sensitive fields never ride on read args."""
    cases: list[dict] = []
    for hidden in ("secret", "pay", "token", "hash", "ssn", "iban", "address", "salary"):
        cases.append({
            "id": f"core.gen.hidden2.{hidden}",
            "lane": "graph",
            "brief": f"{hidden} is not among the read fields.",
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": "read_record", "tool_args": {"fields": ["id", "status"]}},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [{"source": "read", "target": "done"}],
            },
            "expect": {
                "valid": True,
                "args": {"read": {"fields": ["id", "status"]}},
                "hidden_on": {"read": [hidden]},
            },
        })
    return cases


def _expand_pack(pack: str, spec: dict) -> list[dict]:
    cases: list[dict] = []
    prefix = spec.get("prefix") or pack
    for mut in spec.get("mutations") or []:
        if not isinstance(mut, dict) or not mut.get("id") or not mut.get("tool"):
            continue
        mid = str(mut["id"])
        tool = str(mut["tool"])
        undo = mut.get("undo")
        cases.append(_pack_gated(prefix, mid, tool))
        cases.append(_pack_trap(prefix, mid, tool))
        cases.append(_pack_wait_gated(prefix, mid, tool))
        cases.append(_pack_loop_gated(prefix, mid, tool))
        if undo:
            cases.append(_pack_compensate(prefix, mid, tool, str(undo), gated=True))
            cases.append(_pack_compensate(prefix, mid, tool, str(undo), gated=False))
            cases.append(_pack_undo_taken(prefix, mid, tool, str(undo)))
        sod = [str(r) for r in (mut.get("sod") or []) if r]
        if len(sod) >= 2:
            cases.append(_pack_sod(prefix, mid, tool, sod, same=False))
            cases.append(_pack_sod(prefix, mid, tool, sod, same=True))
        after = [str(r) for r in (mut.get("after") or []) if r]
        if len(after) >= 2:
            cases.append(_pack_parallel_then_write(prefix, mid, tool, after))
        cases.append(_pack_agent_trap(prefix, mid, tool))
    for stack in spec.get("stacks") or []:
        if isinstance(stack, dict) and stack.get("id"):
            cases.extend(_pack_stack(prefix, stack))
    reads = [r for r in (spec.get("reads") or []) if isinstance(r, dict) and r.get("id") and r.get("tool")]
    for row in reads:
        hid = list(row.get("hidden") or [])
        if hid:
            cases.append(_pack_hidden(prefix, str(row["id"]), str(row["tool"]), hid, row.get("args") or {}))
    for i, left in enumerate(reads):
        for right in reads[i + 1 :]:
            cases.append(_pack_parallel(prefix, left, right))
    for cite in spec.get("citations") or []:
        if not isinstance(cite, dict) or not cite.get("id"):
            continue
        tokens = list(cite.get("tokens") or [])
        hit = cite.get("hit")
        miss = cite.get("miss")
        if hit:
            cases.append({
                "id": f"{prefix}.gen.cite.{cite['id']}",
                "lane": "retrieval",
                "brief": cite.get("brief") or "Cite the passage that holds every token.",
                "passages": [
                    {"id": "hit", "text": str(hit)},
                    {"id": "decoy", "text": str(miss or "Unrelated.")},
                ],
                "tokens": tokens,
                "expect": {"cited": ["hit"], "refuses_when_empty": True},
            })
        if miss:
            cases.append({
                "id": f"{prefix}.gen.cite-miss.{cite['id']}",
                "lane": "retrieval",
                "brief": "A miss refuses.",
                "passages": [{"id": "other", "text": str(miss)}],
                "tokens": tokens,
                "expect": {"cited": [], "refuses_when_empty": True},
            })
    for bind in spec.get("binds") or []:
        if not isinstance(bind, dict) or not bind.get("id"):
            continue
        listing = str(bind.get("list") or "")
        detail = str(bind.get("detail") or "")
        key = str(bind.get("key") or "id")
        if listing and detail:
            cases.append(_pack_bind(prefix, str(bind["id"]), listing, detail, key, bound=False))
            cases.append(_pack_bind(prefix, str(bind["id"]), listing, detail, key, bound=True))
            cases.append(_pack_bind_halt(prefix, str(bind["id"]), listing, detail))
    for row in spec.get("observes") or []:
        if isinstance(row, dict) and row.get("id") and row.get("tool"):
            cases.append(_pack_observe(prefix, str(row["id"]), str(row["tool"])))
    return cases


def _pack_bind(prefix: str, bid: str, listing: str, detail: str, key: str, *, bound: bool) -> dict:
    value = 56 if bound else 0
    take = bound
    return {
        "id": f"{prefix}.gen.bind.{bid}.{'hit' if bound else 'miss'}",
        "lane": "graph",
        "brief": f"{detail} waits for {key} from {listing}.",
        "context": {key: value},
        "graph": {
            "entry": "listing",
            "nodes": [
                {"id": "listing", "node_type": "task", "tool_name": listing},
                {"id": "gate", "node_type": "choice"},
                {"id": "detail", "node_type": "task", "tool_name": detail, "tool_args": {key: value}},
                {"id": "halt", "node_type": "observe"},
                {"id": "stop", "node_type": "fail"},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "listing", "target": "gate"},
                {"source": "gate", "target": "detail", "guard": f"{key} >= 1"},
                {"source": "gate", "target": "stop", "is_default": True},
                {"source": "detail", "target": "halt"},
                {"source": "halt", "target": "done"},
            ],
        },
        "expect": {
            "valid": True,
            "path": ["listing", "gate", "detail", "halt", "done"] if take else ["listing", "gate", "stop"],
            **({} if take else {"path_excludes": ["detail"]}),
            "mutations_gated": True,
        },
    }


def _pack_bind_halt(prefix: str, bid: str, listing: str, detail: str) -> dict:
    return {
        "id": f"{prefix}.gen.bind.{bid}.halt-after",
        "lane": "graph",
        "brief": f"Halt follows {detail}. It does not skip the bind.",
        "graph": {
            "entry": "listing",
            "nodes": [
                {"id": "listing", "node_type": "task", "tool_name": listing},
                {"id": "detail", "node_type": "task", "tool_name": detail},
                {"id": "halt", "node_type": "observe"},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "listing", "target": "detail"},
                {"source": "detail", "target": "halt"},
                {"source": "halt", "target": "done"},
            ],
        },
        "expect": {"valid": True, "path": ["listing", "detail", "halt", "done"], "path_has": ["detail", "halt"]},
    }


def _pack_observe(prefix: str, rid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.observe.{rid}",
        "lane": "graph",
        "brief": f"{tool} then observe. No write.",
        "graph": {
            "entry": "read",
            "nodes": [
                {"id": "read", "node_type": "task", "tool_name": tool},
                {"id": "look", "node_type": "observe"},
                {"id": "write", "node_type": "task", "tool_name": "write_record", "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "read", "target": "look"},
                {"source": "look", "target": "done"},
                {"source": "look", "target": "write", "guard": "write == true"},
                {"source": "write", "target": "done"},
            ],
        },
        "expect": {
            "valid": True,
            "path": ["read", "look", "done"],
            "path_excludes": ["write"],
            "mutations_gated": True,
        },
    }


def _pack_gated(prefix: str, mid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.gated",
        "lane": "graph",
        "brief": f"{tool} waits for a human.",
        "graph": {
            "entry": "ask",
            "nodes": [
                {"id": "ask", "node_type": "human"},
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "ask", "target": "write"},
                {"source": "write", "target": "done"},
            ],
        },
        "expect": {"valid": True, "path": ["ask", "write", "done"], "mutations_gated": True},
    }


def _pack_trap(prefix: str, mid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.trap",
        "lane": "graph",
        "brief": f"{tool} with no human is a trap.",
        "graph": {
            "entry": "write",
            "nodes": [
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [{"source": "write", "target": "done"}],
        },
        "expect": {"valid": True, "detects": "ungated_mutation"},
    }


def _pack_wait_gated(prefix: str, mid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.wait-gated",
        "lane": "graph",
        "brief": f"After a wait, {tool} still waits for a human.",
        "graph": {
            "entry": "hold",
            "nodes": [
                {"id": "hold", "node_type": "wait"},
                {"id": "ask", "node_type": "human"},
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "hold", "target": "ask"},
                {"source": "ask", "target": "write"},
                {"source": "write", "target": "done"},
            ],
        },
        "expect": {"valid": True, "path": ["hold", "ask", "write", "done"], "mutations_gated": True},
    }


def _pack_loop_gated(prefix: str, mid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.loop-gated",
        "lane": "graph",
        "brief": f"After a bounded loop, {tool} still waits for a human.",
        "graph": {
            "entry": "retry",
            "nodes": [
                {"id": "retry", "node_type": "loop", "max_iterations": 2, "tool_name": "read_record"},
                {"id": "ask", "node_type": "human"},
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "retry", "target": "ask"},
                {"source": "ask", "target": "write"},
                {"source": "write", "target": "done"},
            ],
        },
        "expect": {
            "valid": True,
            "max_iterations": {"retry": 2},
            "path_has": ["ask", "write"],
            "mutations_gated": True,
        },
    }


def _pack_compensate(prefix: str, mid: str, tool: str, undo: str, *, gated: bool) -> dict:
    if gated:
        return {
            "id": f"{prefix}.gen.{mid}.compensate-gated",
            "lane": "graph",
            "brief": f"{tool} is consented. {undo} is named as compensation.",
            "graph": {
                "entry": "ask",
                "nodes": [
                    {"id": "ask", "node_type": "human"},
                    {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True, "compensation": "undo"},
                    {"id": "undo", "node_type": "task", "tool_name": undo, "is_mutation": True},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "ask", "target": "write"},
                    {"source": "write", "target": "done"},
                    {"source": "write", "target": "undo", "guard": "undo == true"},
                ],
            },
            "expect": {"valid": True, "compensation": {"write": "undo"}, "mutations_gated": True},
        }
    return {
        "id": f"{prefix}.gen.{mid}.compensate-trap",
        "lane": "graph",
        "brief": f"{tool} with compensation but no human is a trap.",
        "graph": {
            "entry": "write",
            "nodes": [
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True, "compensation": "undo"},
                {"id": "undo", "node_type": "task", "tool_name": undo, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "write", "target": "done"},
                {"source": "write", "target": "undo", "guard": "undo == true"},
            ],
        },
        "expect": {"valid": True, "compensation": {"write": "undo"}, "detects": "ungated_mutation"},
    }


def _pack_agent_trap(prefix: str, mid: str, tool: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.researcher-trap",
        "lane": "agents",
        "brief": f"A researcher that can {tool} is a trap.",
        "agents": [
            {"role": "researcher", "tools": [tool], "mutation_tools": [tool]},
            {"role": "critic", "tools": [], "mutation_tools": []},
        ],
        "expect": {"detects": "mutation_on_readonly", "readonly_roles": ["researcher"]},
    }


def _pack_hidden(prefix: str, rid: str, tool: str, hidden: list, args: dict) -> dict:
    tool_args = dict(args) if args else {"fields": ["id", "status"]}
    return {
        "id": f"{prefix}.gen.{rid}.hidden",
        "lane": "graph",
        "brief": f"{tool} does not carry hidden fields.",
        "graph": {
            "entry": "read",
            "nodes": [
                {"id": "read", "node_type": "task", "tool_name": tool, "tool_args": tool_args},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [{"source": "read", "target": "done"}],
        },
        "expect": {"valid": True, "hidden_on": {"read": hidden}},
    }


def _pack_parallel(prefix: str, left: dict, right: dict) -> dict:
    lid, rid = str(left["id"]), str(right["id"])
    return {
        "id": f"{prefix}.gen.parallel.{lid}-and-{rid}",
        "lane": "graph",
        "brief": f"{left['tool']} and {right['tool']} in parallel. No write.",
        "graph": {
            "entry": "fan",
            "nodes": [
                {"id": "fan", "node_type": "parallel", "join": "all"},
                {"id": "left", "node_type": "task", "tool_name": str(left["tool"])},
                {"id": "right", "node_type": "task", "tool_name": str(right["tool"])},
                {"id": "join", "node_type": "task", "tool_name": "merge_records"},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "fan", "target": "left"},
                {"source": "fan", "target": "right"},
                {"source": "left", "target": "join"},
                {"source": "right", "target": "join"},
                {"source": "join", "target": "done"},
            ],
        },
        "expect": {"valid": True, "path_has": ["left", "right", "join"], "mutations_gated": True},
    }


def _pack_undo_taken(prefix: str, mid: str, tool: str, undo: str) -> dict:
    return {
        "id": f"{prefix}.gen.{mid}.undo-taken",
        "lane": "graph",
        "brief": f"{tool} is consented. Undo is taken and still behind the human.",
        "context": {"undo": True},
        "graph": {
            "entry": "ask",
            "nodes": [
                {"id": "ask", "node_type": "human"},
                {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True, "compensation": "undo"},
                {"id": "undo", "node_type": "task", "tool_name": undo, "is_mutation": True},
                {"id": "done", "node_type": "succeed"},
            ],
            "edges": [
                {"source": "ask", "target": "write"},
                {"source": "write", "target": "undo", "guard": "undo == true"},
                {"source": "write", "target": "done", "is_default": True},
                {"source": "undo", "target": "done"},
            ],
        },
        "expect": {
            "valid": True,
            "path": ["ask", "write", "undo", "done"],
            "compensation": {"write": "undo"},
            "mutations_gated": True,
        },
    }


def _pack_sod(prefix: str, mid: str, tool: str, roles: list[str], *, same: bool) -> dict:
    humans = [{"id": f"h{i}", "node_type": "human", "meta": {"role": (roles[0] if same else role)}} for i, role in enumerate(roles)]
    nodes = humans + [
        {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
        {"id": "done", "node_type": "succeed"},
    ]
    ids = [h["id"] for h in humans]
    edges = [{"source": ids[i], "target": ids[i + 1]} for i in range(len(ids) - 1)]
    edges += [{"source": ids[-1], "target": "write"}, {"source": "write", "target": "done"}]
    expect: dict[str, Any] = {"valid": True, "path": [*ids, "write", "done"], "mutations_gated": True}
    if same:
        expect["detects"] = "same_role"
        expect["humans"] = ids
    else:
        expect["roles_differ"] = ids
    return {
        "id": f"{prefix}.gen.{mid}.sod-{'same' if same else 'differ'}",
        "lane": "graph",
        "brief": f"{tool} with {len(roles)} humans. Roles {'collide' if same else 'differ'}.",
        "graph": {"entry": ids[0], "nodes": nodes, "edges": edges},
        "expect": expect,
    }


def _pack_parallel_then_write(prefix: str, mid: str, tool: str, reads: list[str]) -> dict:
    branches = [f"r{i}" for i in range(len(reads))]
    nodes = (
        [{"id": "fan", "node_type": "parallel", "join": "all"}]
        + [{"id": bid, "node_type": "task", "tool_name": name} for bid, name in zip(branches, reads)]
        + [
            {"id": "join", "node_type": "task", "tool_name": "merge_records"},
            {"id": "ask", "node_type": "human"},
            {"id": "write", "node_type": "task", "tool_name": tool, "is_mutation": True},
            {"id": "done", "node_type": "succeed"},
        ]
    )
    edges = (
        [{"source": "fan", "target": bid} for bid in branches]
        + [{"source": bid, "target": "join"} for bid in branches]
        + [
            {"source": "join", "target": "ask"},
            {"source": "ask", "target": "write"},
            {"source": "write", "target": "done"},
        ]
    )
    return {
        "id": f"{prefix}.gen.{mid}.parallel-then-write",
        "lane": "graph",
        "brief": f"{' and '.join(reads)} join, then {tool} waits for a human.",
        "graph": {"entry": "fan", "nodes": nodes, "edges": edges},
        "expect": {
            "valid": True,
            "path_has": [*branches, "ask", "write"],
            "mutations_gated": True,
        },
    }


def _pack_stack(prefix: str, stack: dict) -> list[dict]:
    sid = str(stack["id"])
    read = str(stack.get("read") or "read_record")
    write = str(stack.get("write") or "write_record")
    mutating = bool(stack.get("mutation", True))
    cases = []
    for variant in stack.get("variants") or []:
        if not isinstance(variant, dict) or not variant.get("id"):
            continue
        ctx = {k: v for k, v in variant.items() if k not in {"id", "expect"}}
        dest = str(variant.get("expect") or "write")
        if dest == "write":
            path = ["read", "g1", "g2", "ask", "act", "done"]
            excludes = ["short", "mismatch"]
        elif dest == "short":
            path = ["read", "g1", "short"]
            excludes = ["act"]
        else:
            path = ["read", "g1", "g2", "mismatch"]
            excludes = ["act"]
        expect: dict[str, Any] = {
            "valid": True,
            "path": path,
            "path_excludes": excludes,
        }
        if mutating:
            expect["mutations_gated"] = True
        cases.append({
            "id": f"{prefix}.gen.stack.{sid}.{variant['id']}",
            "lane": "graph",
            "brief": f"{read} then two gates then {write}. Variant {variant['id']}.",
            "context": ctx,
            "graph": {
                "entry": "read",
                "nodes": [
                    {"id": "read", "node_type": "task", "tool_name": read},
                    {"id": "g1", "node_type": "choice"},
                    {"id": "g2", "node_type": "choice"},
                    {"id": "ask", "node_type": "human"},
                    {"id": "act", "node_type": "task", "tool_name": write, "is_mutation": mutating},
                    {"id": "short", "node_type": "fail"},
                    {"id": "mismatch", "node_type": "fail"},
                    {"id": "done", "node_type": "succeed"},
                ],
                "edges": [
                    {"source": "read", "target": "g1"},
                    {"source": "g1", "target": "g2", "guard": str(stack.get("gate1") or "ok == true")},
                    {"source": "g1", "target": "short", "is_default": True},
                    {"source": "g2", "target": "ask", "guard": str(stack.get("gate2") or "fit == true")},
                    {"source": "g2", "target": "mismatch", "is_default": True},
                    {"source": "ask", "target": "act"},
                    {"source": "act", "target": "done"},
                ],
            },
            "expect": expect,
        })
    return cases
