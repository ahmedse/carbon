"""Pulse 2.1 Decision — the only thing the understanding call may emit.

Commands are a closed set. Validation is policy (ADR-0046 / RBAC), not a
second router. ``Arbiter.decide`` stays the v2 path; this module is the v21
path behind ``PULSE_UNDERSTAND``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

COMMAND_OPS = frozenset(
    {
        "call_tool",
        "navigate",
        "clarify",
        "set_slot",
        "answer",
        "handoff_agent",
        "refuse",
        "confirm",
        "reject",
        "continue",
    }
)

# How a call_tool / continue answer is shown. A chart or table renders the
# decided tool's payload only — never whatever other payload is chartable.
RENDER_MODES = frozenset({"text", "chart", "table"})

# handoff_agent target for a multi-step / conditional goal (Agent plans it).
PLAN_PROCESS_ID = "plan"

# Chat may call reads and the handoff command. Writes are Agent + RULE_21.
_CHAT_WRITE_PREFIXES = (
    "create_",
    "submit_",
    "approve_",
    "reject_",
    "update_",
    "delete_",
    "cancel_",
    "post_",
)


@dataclass
class Command:
    op: str
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    target_id: str = ""
    question: str = ""
    options: list[str] = field(default_factory=list)
    key: str = ""
    value: str = ""
    process_id: str = ""
    reason: str = ""
    text: str = ""
    render: str = "text"


@dataclass
class Decision:
    commands: list[Command]
    language: str = "en"
    confidence: float = 0.0
    reason: str = ""

    def ops(self) -> list[str]:
        return [c.op for c in self.commands]


def _cmd_from_obj(raw: Any) -> Command | None:
    if not isinstance(raw, dict):
        return None
    op = str(raw.get("op") or "").strip()
    if op not in COMMAND_OPS:
        return None
    args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    render = str(raw.get("render") or "text").strip().lower()
    if render not in RENDER_MODES:
        render = "text"
    return Command(
        op=op,
        name=str(raw.get("name") or ""),
        args=dict(args),
        target_id=str(raw.get("target_id") or ""),
        question=str(raw.get("question") or ""),
        options=[str(o) for o in options][:8],
        key=str(raw.get("key") or ""),
        value=str(raw.get("value") or ""),
        process_id=str(raw.get("process_id") or ""),
        reason=str(raw.get("reason") or ""),
        text=str(raw.get("text") or ""),
        render=render,
    )


def parse_decision(payload: Any) -> Decision | None:
    """Parse a strict Decision object. None when the shape is unusable."""
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, dict):
        return None
    raw_cmds = payload.get("commands")
    if not isinstance(raw_cmds, list) or not raw_cmds:
        return None
    commands: list[Command] = []
    for item in raw_cmds[:3]:
        cmd = _cmd_from_obj(item)
        if cmd is None:
            return None
        commands.append(cmd)
    lang = str(payload.get("language") or "en").strip().lower()
    if lang not in {"ar", "en"}:
        lang = "en"
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    return Decision(
        commands=commands,
        language=lang,
        confidence=confidence,
        reason=str(payload.get("reason") or "")[:500],
    )


def tool_choice_for(decision: Decision | None) -> dict | str | None:
    """Named tool_choice when the Decision is exactly one call_tool."""
    if decision is None or len(decision.commands) != 1:
        return None
    cmd = decision.commands[0]
    if cmd.op != "call_tool" or not cmd.name:
        return None
    return {"name": cmd.name}


def _is_write_tool(name: str, write_tools: set[str] | None) -> bool:
    if name in (write_tools or set()):
        return True
    return any(name.startswith(p) for p in _CHAT_WRITE_PREFIXES)


def _pending_open_question(state: Any) -> dict:
    if state is None:
        return {}
    question = getattr(state, "open_question", None)
    return question if isinstance(question, dict) else {}


def _confirm_call_api(confirm: Any) -> str:
    if not isinstance(confirm, dict) or confirm.get("op") != "call_tool":
        return ""
    return str(confirm.get("api") or confirm.get("name") or "").strip()


def validate_decision(
    decision: Decision,
    *,
    surface: str | None = None,
    allowed_tools: set[str] | None = None,
    write_tools: set[str] | None = None,
    state: Any = None,
) -> Decision:
    """Downgrade policy violations to clarify or handoff. Never drop to a free answer that writes.

    Chat (ADR-0046): call_tool on a write name becomes handoff_agent.
    Unknown tool names become clarify.
    ``confirm`` without a pending open question becomes clarify.
    """
    from ai.engine.agent.surface import Surface

    # Ask the enum, never the spelling: ``chat.plan`` is Chat too, and a raw
    # ``== "chat"`` would have let its write tools through.
    on_chat = Surface.resolve(surface).is_chat
    pending = _pending_open_question(state)
    out: list[Command] = []
    for cmd in decision.commands:
        if cmd.op == "confirm":
            if not pending.get("text"):
                out.append(
                    Command(
                        op="clarify",
                        question="I'm not sure what you're confirming.",
                    )
                )
                continue
            api = _confirm_call_api(pending.get("confirm"))
            if on_chat and api and _is_write_tool(api, write_tools):
                out.append(
                    Command(
                        op="handoff_agent",
                        process_id=api,
                        reason="Chat does not mutate the host (ADR-0046).",
                    )
                )
                continue
        if cmd.op == "call_tool":
            name = cmd.name.strip()
            if not name:
                out.append(Command(op="clarify", question="Which action should I take?"))
                continue
            if allowed_tools is not None and name not in allowed_tools:
                out.append(
                    Command(
                        op="clarify",
                        question=f"I can't use {name} from here.",
                    )
                )
                continue
            if on_chat and _is_write_tool(name, write_tools):
                out.append(
                    Command(
                        op="handoff_agent",
                        process_id=cmd.process_id or name,
                        reason="Chat does not mutate the host (ADR-0046).",
                    )
                )
                continue
        out.append(cmd)
    if not out:
        out = [Command(op="clarify", question="Can you say which one you mean?")]
    return Decision(
        commands=out[:3],
        language=decision.language,
        confidence=decision.confidence,
        reason=decision.reason,
    )


EMIT_DECISION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_decision",
        "description": (
            "Emit the turn decision. Use call_tool only for a tool in the "
            "provided catalog. Use confirm when the user affirms a pending "
            "question in CONVERSATION STATE. Use continue when they ask about "
            "the previous answer. Use reject when they decline. Use "
            "handoff_agent for anything that would change host data while the "
            "surface is Chat, and handoff_agent with process_id=plan for a "
            "multi-step or conditional goal. Use clarify when two tools fit. "
            "Set render=chart "
            "or render=table when the user wants a chart, visual, or report of "
            "that data; the chart is drawn from THAT tool's result only. A "
            "request for charts of the previous answer is continue (same tool) "
            "with render=chart, never a different domain. Never invent figures."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "commands": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": sorted(COMMAND_OPS),
                            },
                            "name": {"type": "string"},
                            "args": {"type": "object"},
                            "target_id": {"type": "string"},
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "process_id": {"type": "string"},
                            "reason": {"type": "string"},
                            "text": {"type": "string"},
                            "render": {
                                "type": "string",
                                "enum": sorted(RENDER_MODES),
                            },
                        },
                        "required": ["op"],
                    },
                },
                "language": {"type": "string", "enum": ["ar", "en"]},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
            },
            "required": ["commands", "language", "confidence"],
        },
    },
}
