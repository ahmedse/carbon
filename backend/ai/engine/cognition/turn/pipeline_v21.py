"""v21 act-on-Decision. Used only when PULSE_UNDERSTAND=v21.

``answer`` and ``navigate`` return None so the legacy spine still speaks.
A forced ``call_tool`` is executed by the caller-supplied coroutine.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from ai.engine.cognition.turn.decision import PLAN_PROCESS_ID, Decision
from ai.engine.cognition.turn.ess_read import answer_bound_ess_tools
from ai.engine.cognition.turn.grounding import ungrounded_numbers

ExecuteTool = Callable[[str, dict], Awaitable[Any]]


def _reply_for(cmd_op: str, decision: Decision) -> str | None:
    cmd = decision.commands[0]
    lang = decision.language
    if cmd_op == "clarify":
        if cmd.question:
            return cmd.question
        return "أي واحد تقصد؟" if lang == "ar" else "Which one do you mean?"
    if cmd_op in {"refuse", "reject"}:
        if cmd.reason:
            return cmd.reason
        if cmd_op == "reject":
            return "حسناً." if lang == "ar" else "Okay."
        return "ما أقدر أساعد في هذا." if lang == "ar" else "I can't help with that."
    if cmd_op == "handoff_agent":
        if cmd.process_id == PLAN_PROCESS_ID:
            if lang == "ar":
                return (
                    "هذه مهمة متعددة الخطوات. حوّل إلى وضع الوكيل لأضع لك "
                    "خطة تراجعها وتوافق عليها قبل التنفيذ."
                )
            return (
                "This is a multi-step run. Switch to Agent and I'll draft a "
                "plan for you to review and approve before anything runs."
            )
        if lang == "ar":
            return "هذا يغيّر بيانات في النظام. حوّل إلى وضع الوكيل لإتمامه."
        return "This changes data in the system. Switch to Agent to submit it."
    return None


def _confirm_api(state: Any) -> str:
    question = getattr(state, "open_question", None) if state is not None else None
    if not isinstance(question, dict):
        return ""
    confirm = question.get("confirm")
    if not isinstance(confirm, dict) or confirm.get("op") != "call_tool":
        return ""
    return str(confirm.get("api") or confirm.get("name") or "").strip()


def _continue_api(state: Any) -> str:
    rows = getattr(state, "last_results", None) if state is not None else None
    if not rows:
        return ""
    last = rows[-1]
    if not isinstance(last, dict):
        return ""
    return str(last.get("api") or "").strip()


async def _execute_bound_read(
    api_name: str,
    *,
    execute_tool: ExecuteTool,
    user_message: str,
    args: dict | None = None,
    executed: list[dict] | None = None,
) -> str | None:
    payload = await execute_tool(api_name, dict(args or {}))
    tool_row = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": api_name},
        "result": payload,
    }
    if executed is not None:
        executed.append(tool_row)
    text = answer_bound_ess_tools(
        [tool_row],
        api_name=api_name,
        user_message=user_message,
    )
    bad = ungrounded_numbers(text, [payload])
    if bad:
        for token in bad:
            text = text.replace(token, "")
        text = " ".join(text.split())
    return text or None


async def act_on_decision(
    decision: Decision | None,
    *,
    execute_tool: ExecuteTool | None,
    user_message: str,
    state: Any = None,
    executed: list[dict] | None = None,
) -> str | None:
    """Reply text, or None to fall through to the legacy turn.

    ``executed`` (when given) receives the tool rows this Decision ran —
    the only payloads ``render_envelope`` may draw from.
    """
    if decision is None or not decision.commands:
        return None
    cmd = decision.commands[0]
    fixed = _reply_for(cmd.op, decision)
    if fixed is not None:
        return fixed
    if cmd.op == "confirm":
        api = _confirm_api(state)
    elif cmd.op == "continue":
        api = _continue_api(state) or cmd.name.strip()
    elif cmd.op == "call_tool":
        api = cmd.name.strip()
    else:
        return None
    if not api or execute_tool is None:
        return None
    return await _execute_bound_read(
        api,
        execute_tool=execute_tool,
        user_message=user_message,
        args=dict(cmd.args or {}) if cmd.op == "call_tool" else None,
        executed=executed,
    )


def render_envelope(
    decision: Decision | None,
    executed: list[dict] | None,
    *,
    headline: str = "",
    user_message: str = "",
) -> dict | None:
    """Chart/table envelope for ``render`` != text, built from ``executed`` only.

    No other payload (prior turns, other domains) can reach the chart, so a
    leave thread cannot produce a payroll figure.
    """
    if decision is None or not decision.commands:
        return None
    return rows_envelope(
        executed,
        render=decision.commands[0].render,
        headline=headline,
        user_message=user_message,
    )


def rows_envelope(
    executed: list[dict] | None,
    *,
    render: str,
    headline: str = "",
    user_message: str = "",
) -> dict | None:
    """Envelope from exactly these tool rows. Shared by v21 and the bound read."""
    if not executed or render not in {"chart", "table"}:
        return None
    from ai.envelope_service import _deterministic_fallback_envelope

    envelope = _deterministic_fallback_envelope(list(executed), user_message)
    if envelope is None:
        return None
    if render == "table":
        envelope = envelope.model_copy(update={"charts": []})
        if not envelope.tables:
            return None
    first_line = next((ln.strip() for ln in (headline or "").splitlines() if ln.strip()), "")
    if first_line:
        envelope = envelope.model_copy(update={"headline": first_line[:200]})
    return envelope.model_dump()
