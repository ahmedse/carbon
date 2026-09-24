"""One understanding call (ADR-0049). The model emits emit_decision; code validates.

Default runtime stays on the legacy Intent→Draft path until PULSE_UNDERSTAND=v21.
"""
from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable

from ai.engine.cognition.turn.decision import (
    EMIT_DECISION_TOOL,
    Decision,
    parse_decision,
    validate_decision,
)

UNDERSTAND_FLAG = "PULSE_UNDERSTAND"

_UNDERSTAND_STATE_HINT = (
    "If CONVERSATION STATE shows a pending question and the user affirms, "
    "emit confirm. If the user asks about the previous answer (e.g. "
    "'is that for me?'), emit continue with the same tool or answer from "
    "state — do not ask again.\n"
    "A goal with several steps, a condition (if … then …), an approval "
    "gate, or an effect on other people (escalate, notify, send, assign) "
    "is an Agent plan, even when every step is a read: emit one "
    "handoff_agent with process_id=plan. Do not clarify its parameters in "
    "Chat and do not refuse it — Agent plans it and checks permissions.\n"
    "A single report, export, or explanation of data already on screen is "
    "answer. A follow-up that asks for charts / a full report / visuals on "
    "the same subject re-emits call_tool for the same read (do not answer "
    "without the tool).\n"
    "Two ESS topics in one utterance (leave+loan, leave+payslip, "
    "loan+salary) → clarify which one. Do not pick the first topic.\n"
    "Bare place nouns alone → navigate: attendance / حضور, payroll / "
    "رواتب, home. Bare leave / الإجازات → call_tool get_my_leave_balance. "
    "Bare payslip / قسيمة → call_tool list_my_payslips. Bare loan / قروض "
    "→ call_tool list_my_loans.\n"
    "Named coworker's leave (Wellie, Mohammad, emp_NNNN, Bilagot) → "
    "call_tool list_leave_entitlements with that person filter. Never "
    "refuse for permission and never call get_my_leave_balance for them — "
    "the host returns 403 when the caller cannot see that person.\n"
    "Request / submit / clock-me-in writes (أريد طلب إجازة, submit leave, "
    "clock me in) → handoff_agent with the write twin's process_id. Do not "
    "clarify slots in Chat and do not call a read twin.\n"
    "Questions about empty host data ('why is my balance zero', 'no "
    "payslip for this month') → answer (empty_render). Do not call_tool.\n"
    "First-person salary / compensation / راتبي / مرتبي → call_tool "
    "get_my_profile (not list_my_payslips). Explicit payslip / قسيمة / "
    "net pay → list_my_payslips. Own attendance / سجل حضوري / clock-in → "
    "list_my_attendance (not list_attendance).\n"
    "Clarify only when two catalog tools fit equally or a user preference "
    "is missing. Never clarify for a value a catalog read can fetch "
    "(ids, runs, periods, balances, records, advances / سلفة) — call that "
    "read instead."
)


def build_understand_system_prompt(
    *,
    catalog_lines: list[str],
    state: Any = None,
    user_info: dict[str, Any] | None = None,
    instance_config: dict[str, Any] | None = None,
) -> str:
    """ContextPack-backed system prompt for the v21 understand call (ADR-0047)."""
    from ai.engine.cognition.context_pack import build_context_pack

    catalog = "\n".join(catalog_lines)
    task_body = (
        "Emit emit_decision only. Reply language matches the user. "
        "Do not invent figures.\n"
        f"{catalog}\n\n{_UNDERSTAND_STATE_HINT}"
    )
    pack = build_context_pack(
        state,
        surface="chat",
        stage="understand",
        user_info=user_info,
        instance_config=instance_config,
        include_history=False,
        include_knowledge=False,
        include_memory=False,
        include_state=True,
        task_body=task_body,
    )
    return pack.system_prompt()


def catalog_prompt_lines(
    user_message: str,
    catalog: list[dict] | None,
    *,
    k: int = 12,
    max_examples: int = 3,
    context: str = "",
) -> tuple[list[str], set[str], set[str]]:
    """Catalog-as-router lines for the understand prompt (ADR-0049 §2).

    Returns ``(lines, allowed_names, write_names)``. Write twins are
    *described* — marked Agent-only — so the model can use their ``not_for``
    to separate "I have a loan" (read) from "I want a loan" (write). Chat
    never executes them: ``validate_decision`` turns a write ``call_tool``
    into ``handoff_agent`` (ADR-0046). One helper feeds both the runtime and
    the G6 understand scorer so they see the same catalog.

    ``catalog`` must already be RBAC-scoped. Every entry is described and
    allowed: lexical ranking only orders the list and picks which ``k``
    entries carry examples. A ranker miss (short Arabic) must never hide the
    right tool from the model or make ``validate_decision`` reject it.
    """
    from ai.engine.cognition.catalog_retrieval import rank_tools

    entries = [t for t in (catalog or []) if isinstance(t, dict)]
    ranked = rank_tools(user_message or "", entries, k=len(entries), context=context)
    seen = {str(t.get("name") or "") for t in ranked}
    ranked += [t for t in entries if str(t.get("name") or "") not in seen]

    lines: list[str] = []
    allowed: set[str] = set()
    writes: set[str] = set()
    for rank, tool in enumerate(ranked):
        name = str(tool.get("name") or "").strip()
        if not name:
            continue
        allowed.add(name)
        desc = " ".join(str(tool.get("description") or "").split())
        not_for = " ".join(str(tool.get("not_for") or "").split())
        kind = str(tool.get("kind") or "")
        method = str(tool.get("method") or "GET").strip().upper()
        # Same rule as the Chat execute guard: any non-GET is a host write.
        if kind == "write" or method != "GET":
            writes.add(name)
            head = (
                f"- {name} (write — Agent only: emit handoff_agent "
                f"with process_id={name}, never call_tool)"
            )
        else:
            head = f"- {name}"
        line = f"{head}: {desc}"
        if not_for:
            line += f" Not for: {not_for}"
        lines.append(line)
        shown = 0
        for ex in tool.get("examples") or [] if rank < k else []:
            if shown >= max_examples:
                break
            if isinstance(ex, dict):
                en = str(ex.get("en") or "").strip()
                ar = str(ex.get("ar") or "").strip()
                sample = " / ".join(s for s in (en, ar) if s)
            else:
                sample = str(ex).strip()
            if sample:
                lines.append(f"  e.g. {sample}")
                shown += 1
    return lines, allowed, writes


def catalog_context(history: list | None) -> str:
    """Recent transcript used when the utterance itself matches no tool."""
    parts: list[str] = []
    for msg in list(history or [])[-4:]:
        if not isinstance(msg, dict):
            continue
        text = msg.get("content")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def understand_mode() -> str:
    """``legacy`` (default), ``shadow`` (log only), or ``v21`` (act)."""
    raw = (os.environ.get(UNDERSTAND_FLAG) or "legacy").strip().lower()
    if raw == "v21":
        return "v21"
    if raw in {"shadow", "shadow_only", "log"}:
        return "shadow"
    return "legacy"


Completer = Callable[..., Awaitable[dict]]


def decision_from_tool_result(result: dict | None) -> Decision | None:
    """Pull the emit_decision arguments out of a route_chat-shaped result."""
    calls = (result or {}).get("tool_calls") or []
    for call in calls:
        fn = (call or {}).get("function") or {}
        if str(fn.get("name") or "") != "emit_decision":
            continue
        raw = fn.get("arguments")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                return None
        return parse_decision(raw)
    content = (result or {}).get("content")
    if isinstance(content, str) and content.strip().startswith("{"):
        return parse_decision(content)
    return None


async def understand_turn(
    *,
    complete: Completer,
    messages: list[dict],
    catalog_tools: list[dict] | None = None,
    surface: str = "chat",
    allowed_tools: set[str] | None = None,
    write_tools: set[str] | None = None,
    state: Any = None,
) -> Decision | None:
    """Call ``complete`` once with forced emit_decision, then validate.

    ``complete`` has the same shape as ``route_chat`` (messages, tools,
    tool_choice, strict_tools) and returns a dict with tool_calls.
    Unparseable output returns None: the model did not decide, so the
    caller falls through to the legacy turn. It never becomes user text.
    """
    tools = [EMIT_DECISION_TOOL]
    # Catalog tools are described in the prompt by the caller. Forcing
    # emit_decision means the model cannot skip the decision by chatting.
    del catalog_tools  # described in the prompt by the caller, not a second tool list
    result = await complete(
        messages=messages,
        tools=tools,
        tool_choice={"name": "emit_decision"},
        strict_tools=True,
    )
    parsed = decision_from_tool_result(result if isinstance(result, dict) else None)
    if parsed is None:
        return None
    return validate_decision(
        parsed,
        surface=surface,
        allowed_tools=allowed_tools,
        write_tools=write_tools,
        state=state,
    )
