"""Normalize ``tool_choice`` and apply strict JSON-schema flags to tool defs."""
from __future__ import annotations

import copy


def normalize_tool_choice(tool_choice: str | dict | None) -> str | dict | None:
    """Normalize an OpenAI ``tool_choice`` value for provider kwargs.

    None or '' → None (caller omits the kwarg).
    'auto' → 'auto'
    'required' → 'required'
    {'name': '<fn>'} or {'type':'function','function':{'name':...}}
        → {'type':'function','function':{'name': name}}

    Reject unknown shapes with ValueError.
    """
    if tool_choice is None or tool_choice == "":
        return None

    if isinstance(tool_choice, str):
        if tool_choice in ("auto", "required"):
            return tool_choice
        raise ValueError(f"Unknown tool_choice string: {tool_choice!r}")

    if isinstance(tool_choice, dict):
        if (
            tool_choice.get("type") == "function"
            and isinstance(tool_choice.get("function"), dict)
            and "name" in tool_choice["function"]
        ):
            name = tool_choice["function"]["name"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"Invalid function name in tool_choice: {name!r}")
            return {"type": "function", "function": {"name": name}}

        if "name" in tool_choice:
            name = tool_choice["name"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"Invalid function name in tool_choice: {name!r}")
            return {"type": "function", "function": {"name": name}}

        raise ValueError(f"Unknown tool_choice dict shape: {tool_choice!r}")

    raise ValueError(f"Unknown tool_choice type: {type(tool_choice).__name__}")


def apply_strict(tools: list[dict] | None, strict: bool) -> list[dict] | None:
    """Return tools with strict JSON-schema flags when *strict* is True.

    If not strict or tools is None, return tools unchanged (same object ok).
    If strict, return a deep copy where each function tool has
    ``function.strict = True`` and ``function.parameters.additionalProperties = False``
    when parameters is a dict. Does not mutate the input list.
    """
    if not strict or tools is None:
        return tools

    out = copy.deepcopy(tools)
    for tool in out:
        fn = tool.get("function")
        if not isinstance(fn, dict):
            continue
        fn["strict"] = True
        params = fn.get("parameters")
        if isinstance(params, dict):
            params["additionalProperties"] = False
    return out
