"""Stub model reply for the v21 understand call.

A stubbed provider that ignores ``emit_decision`` makes understanding fail,
and ADR-0053 answers that with a typed error. ``answer_decision`` answers
the call the way a model does for a plain question. ``decision_for`` lets a
scripted model decide its own tool in the understand call (ADR-0056).
"""
from __future__ import annotations

import json
import types


def _offered(kw: dict) -> set:
    return {((t or {}).get("function") or {}).get("name") for t in kw.get("tools") or []}


def _emit(commands: list[dict]) -> list:
    args = {"commands": commands, "language": "en", "confidence": 0.9, "reason": "stub"}
    return [types.SimpleNamespace(
        id="call_emit_decision",
        type="function",
        function=types.SimpleNamespace(name="emit_decision", arguments=json.dumps(args)),
    )]


def answer_decision(kw: dict) -> list | None:
    """The ``emit_decision`` tool call for an ``answer`` turn, or None when not offered."""
    if "emit_decision" not in _offered(kw):
        return None
    return _emit([{"op": "answer"}])


def _catalog_names(kw: dict) -> list[str]:
    """Tool names the understand prompt lists under CATALOG (``- name: …`` lines)."""
    names: list[str] = []
    for msg in kw.get("messages") or []:
        if msg.get("role") != "system":
            continue
        for line in str(msg.get("content") or "").splitlines():
            if line.startswith("- "):
                head = line[2:].split(":", 1)[0].split(" ", 1)[0].strip()
                if head and head.replace("_", "").isalnum():
                    names.append(head)
    return names


def decision_for(kw: dict, decide) -> list | None:
    """Ask a scripted model the understand question the way a real model sees it.

    ``decide(kw)`` returns ``(content, tool_calls)`` for a drafting call. Given
    the catalog the understand prompt lists as its tools, a scripted tool
    call becomes ``call_tool``; anything else is ``answer`` (ADR-0056).
    """
    if "emit_decision" not in _offered(kw):
        return None
    names = [*_catalog_names(kw), "call_host_api"]
    probe = {**kw, "tools": [{"function": {"name": n}} for n in names]}
    _content, calls = decide(probe)
    for call in calls or []:
        fn = getattr(call, "function", None)
        name = str(getattr(fn, "name", "") or "")
        if name:
            try:
                args = json.loads(getattr(fn, "arguments", "") or "{}")
            except ValueError:
                args = {}
            if name == "call_host_api":
                name = str(args.pop("api_name", "") or "")
            return _emit([{"op": "call_tool", "name": name, "args": args}])
    return _emit([{"op": "answer"}])
