"""Catalog parameter contract for host API steps.

Pure helper (RULE_20): the brand catalog owns ``parameters``. The engine
checks required fields and enums, and never imports a domain app.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


import json
from typing import Any

from ai.engine.cognition.plan.planner import _schema_violations

READ_GAP = T("plan/catalog_args.py::READ_GAP")
WRITE_HELD = T("plan/catalog_args.py::WRITE_HELD")

__all__ = [
    "READ_GAP",
    "WRITE_HELD",
    "catalog_arg_violations",
    "canonical_host_args",
    "apply_repaired_params",
    "parse_repair_payload",
    "rewrite_host_calls",
    "is_invalid_argument_error",
    "tool_output_is_invalid_args",
    "mutation_blocked_by_failed_read",
]


def _entry(api_catalog: Any, api_name: str) -> dict | None:
    name = str(api_name or "").strip()
    if not name:
        return None
    for item in api_catalog or []:
        if isinstance(item, dict) and str(item.get("name") or "") == name:
            return item
    return None


def _schema_for(api_catalog: Any, tool_args: dict | None) -> dict | None:
    if not isinstance(tool_args, dict):
        return None
    entry = _entry(api_catalog, str(tool_args.get("api_name") or ""))
    schema = (entry or {}).get("parameters") if isinstance(entry, dict) else None
    return schema if isinstance(schema, dict) and schema else None


def parameter_values(tool_args: dict, schema: dict) -> dict:
    """Values the schema applies to, from what the executor sends.

    Only ``path_params`` / ``query_params`` / ``body`` reach the host, so a
    top-level key is not a value. A blank string is omitted so a required
    field fails as missing.
    """
    props = schema.get("properties") or {}
    out: dict = {}
    for nest in ("path_params", "body", "query_params"):
        inner = tool_args.get(nest)
        if not isinstance(inner, dict):
            continue
        for key in props:
            if key not in inner:
                continue
            val = inner[key]
            if isinstance(val, str) and not val.strip():
                continue
            out[key] = val
    return out


def _surface(api_catalog: Any):
    from ai.engine.cognition.turn.capability import CapabilitySurface

    return CapabilitySurface(
        entries=tuple(e for e in (api_catalog or []) if isinstance(e, dict)),
    )


def canonical_host_args(api_catalog: Any, tool_args: dict | None) -> dict:
    """``tool_args`` in the one shape ``call_host_api`` sends (see ``host_args``)."""
    args = tool_args if isinstance(tool_args, dict) else {}
    name = str(args.get("api_name") or "").strip()
    if not name:
        return dict(args)
    return _surface(api_catalog).host_args(name, args)


def catalog_arg_violations(
    api_catalog: Any,
    tool_name: str | None,
    tool_args: dict | None,
) -> list[str]:
    """Schema misses for a catalog call. Empty when the entry has no schema."""
    if not isinstance(tool_args, dict):
        return []
    if (tool_name or "") != "call_host_api" and not tool_args.get("api_name"):
        return []
    schema = _schema_for(api_catalog, tool_args)
    if schema is None:
        return []
    return _schema_violations(schema, parameter_values(tool_args, schema))


def enum_fill_from_text(schema: dict | None, values: dict | None, text: str | None) -> dict | None:
    """Fill a missing required enum when the text names exactly one allowed value."""
    if not isinstance(schema, dict):
        return None
    props = schema.get("properties") or {}
    have = values if isinstance(values, dict) else {}
    hay = f" {(text or '').lower().replace('_', ' ')} "
    filled: dict = {}
    for key in schema.get("required") or []:
        if key in have and str(have.get(key) or "").strip():
            continue
        spec = props.get(key) if isinstance(props.get(key), dict) else {}
        enum = [str(item) for item in (spec.get("enum") or [])]
        hits = []
        for item in enum:
            token = item.lower().replace("_", " ")
            if token and f" {token} " in hay:
                hits.append(item)
        if len(hits) != 1:
            return None
        filled[key] = hits[0]
    return filled or None


def apply_repaired_params(
    tool_args: dict | None,
    repaired: dict | None,
    api_catalog: Any,
) -> dict:
    """Write repaired parameter values into the shape the executor sends."""
    args = dict(tool_args or {})
    schema = _schema_for(api_catalog, args) or {}
    props = schema.get("properties") or {}
    incoming = repaired if isinstance(repaired, dict) else {}
    if not str(args.get("api_name") or "").strip():
        return args
    from ai.engine.cognition.turn.capability import flat_args

    merged = {k: v for k, v in flat_args(args).items()}
    merged.update({k: v for k, v in incoming.items() if k in props})
    base = {k: args[k] for k in ("api_name", "explanation", "bind") if k in args}
    return canonical_host_args(api_catalog, {**base, **merged})


def parse_repair_payload(text: str | None) -> dict | None:
    """First JSON object in a repair draft. None when the draft is not JSON."""
    raw = (text or "").strip()
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def canonical_host_calls(calls: list | None, api_catalog: Any) -> list:
    """Every ``call_host_api`` call rewritten to the shape the executor sends."""
    out = []
    for tc in calls or []:
        fn = dict((tc or {}).get("function") or {}) if isinstance(tc, dict) else {}
        if (fn.get("name") or "") != "call_host_api":
            out.append(tc)
            continue
        raw = fn.get("arguments", "{}")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        except (json.JSONDecodeError, TypeError, ValueError):
            out.append(tc)
            continue
        args = canonical_host_args(api_catalog, parsed)
        args.pop("bind", None)
        fn["arguments"] = json.dumps(args, ensure_ascii=False, default=str)
        out.append({**tc, "function": fn})
    return out


def rewrite_host_calls(calls: list | None, tool_args: dict) -> list:
    """Point synthesized ``call_host_api`` calls at the repaired args."""
    sent = {k: v for k, v in (tool_args or {}).items() if k != "bind"}
    payload = json.dumps(sent, ensure_ascii=False, default=str)
    out = []
    for tc in calls or []:
        if not isinstance(tc, dict):
            out.append(tc)
            continue
        fn = dict(tc.get("function") or {})
        if (fn.get("name") or "") != "call_host_api":
            out.append(tc)
            continue
        fn["arguments"] = payload
        copied = dict(tc)
        copied["function"] = fn
        out.append(copied)
    return out


def is_invalid_argument_error(error: Any) -> bool:
    """True for a host 400. Timeouts and 5xx are not argument repairs."""
    if isinstance(error, dict):
        if error.get("status_code") == 400:
            return True
        error = error.get("error") or error.get("message") or ""
    text = str(error or "")
    lowered = text.lower()
    if lowered.startswith("[timeout]") or "timed out" in lowered or "timeout" in lowered:
        return False
    if any(token in text for token in ("429", "502", "503", "504")):
        return False
    if "unknown dimension" in lowered:
        return True
    return (
        "Host API returned 400" in text
        or '"status_code": 400' in text
        or "'status_code': 400" in text
    )


def tool_output_is_invalid_args(tool_output: Any) -> bool:
    """True when a tool result is a validation rejection, not a transport fault."""
    if not isinstance(tool_output, dict):
        return is_invalid_argument_error(tool_output)
    if tool_output.get("error") and is_invalid_argument_error(tool_output.get("error")):
        return True
    raw = tool_output.get("result", tool_output.get("data"))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = None
    if isinstance(raw, dict) and raw.get("status_code") == 400:
        return True
    return False


def mutation_blocked_by_failed_read(step: Any, failed_ids: Any) -> bool:
    """A write whose dependency failed must not open the consent gate."""
    if not bool(getattr(step, "is_mutation", False)):
        return False
    failed = set(failed_ids or [])
    deps = set(getattr(step, "depends_on", None) or [])
    return bool(deps & failed)
