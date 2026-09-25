"""Pulse 2.1 Decision — the only thing the understanding call may emit.

Commands are a closed set. Validation is policy (ADR-0046 / RBAC), not a
second router. ``Arbiter.decide`` stays the v2 path; this module is the v21
path behind ``PULSE_UNDERSTAND``.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

from dataclasses import dataclass, field
from typing import Any, Callable

COMMAND_OPS = T("turn/decision.py::COMMAND_OPS")

# How a call_tool / continue answer is shown. A chart or table renders the
# decided tool's payload only — never whatever other payload is chartable.
RENDER_MODES = T("turn/decision.py::RENDER_MODES")

# handoff_agent target for a multi-step / conditional goal (Agent plans it).
PLAN_PROCESS_ID = "plan"

# Chat may call reads and the handoff command. Writes are Agent + RULE_21.
_CHAT_WRITE_PREFIXES = T("turn/decision.py::_CHAT_WRITE_PREFIXES")


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
    # The chart shape the user named (pie / bar / line), or "" when none was named.
    chart: str = ""

    def reads_host(self) -> bool:
        """A read the executor runs: a named call, a confirm, or a continue."""
        return self.op in {"call_tool", "confirm", "continue"}


@dataclass(frozen=True)
class Rejection:
    """Why validation dropped a command. Feedback for repair, never user text."""

    index: int
    name: str
    code: str  # not_on_surface | invalid_args | missing_name
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "name": self.name, "code": self.code, "detail": self.detail}


@dataclass
class Decision:
    commands: list[Command]
    language: str = "en"
    confidence: float = 0.0
    reason: str = ""
    rejections: list[Rejection] = field(default_factory=list)
    raw_ops: list[str] = field(default_factory=list)
    repaired: bool = False
    # The emit_decision exchange that produced this Decision, kept so a
    # repair round can answer the model's own call. Not part of equality.
    exchange: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

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
    chart = str(raw.get("chart") or "").strip().lower()
    if chart not in {"pie", "bar", "line"}:
        chart = ""
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
        chart=chart,
    )


def parse_decision(payload: Any) -> Decision | None:
    """Parse a strict Decision object. None when the shape is unusable."""
    return decision_or_cause(payload)[0]


def decision_or_cause(payload: Any) -> tuple[Decision | None, str]:
    """The Decision, or None and why the shape is unusable.

    Causes: ``not_json``, ``not_object``, ``commands_not_list``,
    ``no_commands``, ``bad_command``, ``unknown_op``.
    """
    import json

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None, "not_json"
    if not isinstance(payload, dict):
        return None, "not_object"
    raw_cmds = payload.get("commands")
    if isinstance(raw_cmds, str):
        return None, "commands_not_list"
    if not isinstance(raw_cmds, list) or not raw_cmds:
        return None, "no_commands"
    commands: list[Command] = []
    for item in raw_cmds[:3]:
        cmd = _cmd_from_obj(item)
        if cmd is None:
            if isinstance(item, dict) and str(item.get("op") or "").strip() not in COMMAND_OPS:
                return None, "unknown_op"
            return None, "bad_command"
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
    ), ""


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
    arg_violations: Callable[[str, dict], list[str]] | None = None,
) -> Decision:
    """Enforce policy. Never drop to a free answer that writes.

    Chat (ADR-0046): call_tool on a write name becomes handoff_agent.
    A name off the surface or args that break its schema is dropped and
    recorded as a ``Rejection`` — repair feedback, never user text. A
    Decision whose every command was dropped has no commands; the caller
    repairs or falls through.
    ``confirm`` without a pending open question becomes clarify.
    """
    from ai.engine.agent.surface import Surface

    # Ask the enum, never the spelling: ``chat.plan`` is Chat too, and a raw
    # ``== "chat"`` would have let its write tools through.
    on_chat = Surface.resolve(surface).is_chat
    pending = _pending_open_question(state)
    out: list[Command] = []
    rejections: list[Rejection] = []
    for index, cmd in enumerate(decision.commands):
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
                rejections.append(Rejection(index, "", "missing_name"))
                continue
            if allowed_tools is not None and name not in allowed_tools:
                rejections.append(Rejection(index, name, "not_on_surface"))
                continue
            write = _is_write_tool(name, write_tools)
            if not write and arg_violations is not None:
                problems = arg_violations(name, dict(cmd.args or {}))
                if problems:
                    rejections.append(
                        Rejection(index, name, "invalid_args", "; ".join(problems)[:400])
                    )
                    continue
            if on_chat and write:
                out.append(
                    Command(
                        op="handoff_agent",
                        process_id=cmd.process_id or name,
                        args=dict(cmd.args or {}),
                        reason="Chat does not mutate the host (ADR-0046).",
                    )
                )
                continue
        out.append(cmd)
    return Decision(
        commands=out[:3],
        language=decision.language,
        confidence=decision.confidence,
        reason=decision.reason,
        rejections=rejections,
        raw_ops=decision.raw_ops or decision.ops(),
        repaired=decision.repaired,
    )


EMIT_DECISION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "emit_decision",
        "description": (
            "Emit the turn decision. Use call_tool only for a tool in the "
            "provided catalog. Use confirm when the user affirms a pending "
            "question in CONVERSATION STATE. Use continue when they ask about "
            "the previous answer; it re-uses the last view with no new read, "
            "so a new filter or period is call_tool with those args. Use "
            "reject when they decline. To change host data, use call_tool "
            "with the write's catalog name and the args the user gave; on "
            "Chat it is handed to Agent with those args, never run. Use "
            "handoff_agent with process_id=plan for a "
            "multi-step or conditional goal. Use answer, with no tool, when "
            "the reply needs no live read (greetings, identity, dates, "
            "knowledge, advice, or a question the rows already in "
            "CONVERSATION STATE fully answer). A follow-up about a different "
            "record than those rows hold is call_tool for that record's "
            "tool. The reply is written after this decision. Use navigate with "
            "target_id set to one NAV name when the user wants to open a "
            "place in the app. When one catalog example is this message, call "
            "that tool. Use clarify when the message asks for two different "
            "records at once, so only the first is not run, and when two "
            "tools both fit and neither excludes the message. "
            "When the user must pick, put each choice in options as a short "
            "label. The question is one sentence and does not list the "
            "choices. Send options empty only when you need their own words "
            "and have no menu. "
            "Set render=chart "
            "or render=table when the user wants a chart, visual, or report of "
            "that data; the chart is drawn from THAT tool's result only. A "
            "request for charts of the previous answer is continue (same tool) "
            "with render=chart, never a different domain. Set chart to the "
            "shape the user named in any language (pie, bar, line); keep the "
            "shape they named earlier when they follow up on the same chart; "
            "use an empty string when they named none. Never invent figures."
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
                            "chart": {
                                "type": "string",
                                "enum": ["", "bar", "line", "pie"],
                            },
                        },
                        "required": ["op"],
                    },
                },
                "language": {"type": "string", "enum": ["ar", "en"]},
                "confidence": {"type": "number"},
                "reason": {
                    "type": "string",
                    "description": (
                        "One or two sentences in the user's language: what you "
                        "understood the user wants. Do not list steps or promise "
                        "work; the commands are the work. No tool names, no code."
                    ),
                },
            },
            "required": ["commands", "language", "confidence"],
        },
    },
}
