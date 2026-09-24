"""Catalog parameter contract for host API steps.

Pure helper (RULE_20): the brand catalog owns ``parameters``. The engine
checks required fields and enums, and never imports a domain app.
"""

from __future__ import annotations

import json
from typing import Any

from ai.engine.cognition.plan.planner import _schema_violations

READ_GAP = (
    "This read could not be completed. "
    "A required field was missing or not allowed."
)
WRITE_HELD = (
    "This step is waiting on a read that did not complete. "
    "Edit the plan, or run again after that read succeeds."
)

__all__ = [
    "READ_GAP",
    "WRITE_HELD",
    "catalog_arg_violations",
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
    """Values the schema applies to, from args, query_params, or body.

    A blank string is omitted so a required field fails as missing.
    """
    props = schema.get("properties") or {}
    query = tool_args.get("query_params")
    query = query if isinstance(query, dict) else {}
    body = tool_args.get("body")
    body = body if isinstance(body, dict) else {}
    skip = {"api_name", "query_params", "body", "method", "path"}
    out: dict = {}
    for key in props:
        if key in query:
            val = query[key]
        elif key in tool_args and key not in skip:
            val = tool_args[key]
        elif key in body:
            val = body[key]
        else:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[key] = val
    return out


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


def apply_repaired_params(
    tool_args: dict | None,
    repaired: dict | None,
    api_catalog: Any,
) -> dict:
    """Write repaired parameter values back onto the call args."""
    args = dict(tool_args or {})
    schema = _schema_for(api_catalog, args) or {}
    props = schema.get("properties") or {}
    incoming = repaired if isinstance(repaired, dict) else {}
    if isinstance(args.get("query_params"), dict):
        query = dict(args["query_params"])
        for key, val in incoming.items():
            if key in props:
                query[key] = val
        args["query_params"] = query
        return args
    for key, val in incoming.items():
        if key in props:
            args[key] = val
    return args


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


def rewrite_host_calls(calls: list | None, tool_args: dict) -> list:
    """Point synthesized ``call_host_api`` calls at the repaired args."""
    payload = json.dumps(tool_args or {}, ensure_ascii=False, default=str)
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
    return "Host API returned 400" in text or '"status_code": 400' in text


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
