"""Stub model reply for the v21 understand call.

A stubbed provider that ignores ``emit_decision`` makes understanding fail,
and ADR-0053 answers that with a typed error. Tests that exercise the
drafting spine answer the call the way a model does for a plain question:
one ``answer`` command, which the spine then drafts.
"""
from __future__ import annotations

import json
import types


def answer_decision(kw: dict) -> list | None:
    """The ``emit_decision`` tool call for an ``answer`` turn, or None when not offered."""
    names = {((t or {}).get("function") or {}).get("name") for t in kw.get("tools") or []}
    if "emit_decision" not in names:
        return None
    args = {"commands": [{"op": "answer"}], "language": "en", "confidence": 0.9, "reason": "stub"}
    return [types.SimpleNamespace(
        id="call_emit_decision",
        type="function",
        function=types.SimpleNamespace(name="emit_decision", arguments=json.dumps(args)),
    )]
