"""Typed data between plan steps.

A host step may need a path value (``{id}``) that an earlier step listed.
The step declares where it comes from in ``tool_args.bind``::

    {"id": {"step": 2, "field": "id", "select": "latest"}}

and the loop binds it from that step's rows before the call is built. When
the rows hold more than one candidate and the plan did not say which, the
step stops with a typed choice instead of calling the host without the id.

Pure helpers (RULE_20): no Django, no domain vocabulary. The catalog entry of
the listing read may declare ``latest_by`` (the row field that orders it).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Binding:
    """Outcome of binding one step's declared path values."""

    status: str = "none"  # none | bound | choice | missing
    tool_args: dict = field(default_factory=dict)
    key: str = ""
    from_step: int | None = None
    options: list[dict] = field(default_factory=list)


def _payload(tool_output: Any) -> Any:
    if not isinstance(tool_output, dict):
        return tool_output
    raw = tool_output.get("result", tool_output.get("data", tool_output))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(raw, dict) and "body" in raw and isinstance(raw["body"], (dict, list)):
        raw = raw["body"]
    return raw


def output_rows(tool_output: Any) -> list[dict]:
    """The row list a read returned (``[...]`` or the first list under a dict)."""
    raw = _payload(tool_output)
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list) and value and all(isinstance(r, dict) for r in value):
                return list(value)
    return []


def _label(row: dict, key_field: str) -> str:
    parts = [str(row.get(key_field))]
    for name, value in row.items():
        if name == key_field or isinstance(value, (dict, list)) or value in (None, ""):
            continue
        parts.append(f"{name}={value}")
        if len(parts) >= 4:
            break
    return " · ".join(parts)


def _select(rows: list[dict], key_field: str, select: str, order_by: str) -> dict | None:
    if len(rows) == 1:
        return rows[0]
    if select == "latest" and order_by:
        ordered = [r for r in rows if r.get(order_by) not in (None, "")]
        if ordered:
            return max(ordered, key=lambda r: str(r.get(order_by)))
    return None


def declare_bindings(step: Any, steps_by_id: dict, surface: Any) -> None:
    """Plan time: point each unfilled path key at the one listing read it depends on.

    A key the planner already bound keeps its declaration (and ``select``).
    """
    args = getattr(step, "tool_args", None)
    if getattr(step, "tool_name", None) != "call_host_api" or not isinstance(args, dict):
        return
    name = str(args.get("api_name") or "")
    missing = surface.missing_path_keys(name, args)
    if not missing:
        return
    declared = dict(args.get("bind") or {}) if isinstance(args.get("bind"), dict) else {}
    listings = []
    for dep_id in getattr(step, "depends_on", None) or []:
        dep = steps_by_id.get(dep_id)
        dep_args = getattr(dep, "tool_args", None) or {}
        dep_name = str(dep_args.get("api_name") or "") if isinstance(dep_args, dict) else ""
        if (
            getattr(dep, "tool_name", None) == "call_host_api"
            and dep_name
            and dep_name not in surface.writes
            and not surface.path_keys(dep_name)
        ):
            listings.append(dep_id)
    for key in missing:
        spec = declared.get(key) if isinstance(declared.get(key), dict) else {}
        if spec.get("step") is None and len(listings) == 1:
            spec = {**spec, "step": listings[0]}
        if spec.get("step") is not None:
            spec.setdefault("field", key)
            declared[key] = spec
    if declared:
        step.tool_args = {**args, "bind": declared}


def resolve_bindings(
    tool_args: dict | None,
    surface: Any,
    outputs_by_step: dict,
    names_by_step: dict | None = None,
) -> Binding:
    """Run time: fill declared path keys from the listing step's rows."""
    args = dict(tool_args or {})
    name = str(args.get("api_name") or "")
    missing = surface.missing_path_keys(name, args)
    if not name or not missing:
        return Binding(status="none", tool_args=args)
    declared = args.get("bind") if isinstance(args.get("bind"), dict) else {}
    path_params = dict(args.get("path_params") or {})
    for key in missing:
        spec = declared.get(key) if isinstance(declared.get(key), dict) else {}
        src = spec.get("step")
        if src is None:
            return Binding(status="missing", tool_args=args, key=key)
        key_field = str(spec.get("field") or key)
        rows = [r for r in output_rows(outputs_by_step.get(src)) if r.get(key_field) not in (None, "")]
        if not rows:
            return Binding(status="missing", tool_args=args, key=key, from_step=src)
        src_name = str((names_by_step or {}).get(src) or "")
        order_by = str((surface.entry(src_name) or {}).get("latest_by") or "")
        row = _select(rows, key_field, str(spec.get("select") or ""), order_by)
        if row is None:
            return Binding(
                status="choice",
                tool_args=args,
                key=key,
                from_step=src,
                options=[
                    {"value": r.get(key_field), "label": _label(r, key_field)}
                    for r in rows
                ],
            )
        path_params[key] = row.get(key_field)
    args["path_params"] = path_params
    return Binding(status="bound", tool_args=args)
