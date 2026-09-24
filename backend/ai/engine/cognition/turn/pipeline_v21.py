"""v21 act-on-Decision. Used only when PULSE_UNDERSTAND=v21.

``answer`` and ``navigate`` return None so the legacy spine still speaks.
A forced ``call_tool`` is executed by the caller-supplied coroutine.
"""
from __future__ import annotations
from ai.engine.pack_vocab import V


from typing import Any, Awaitable, Callable

from ai.engine.cognition.turn.decision import PLAN_PROCESS_ID, Command, Decision
from ai.engine.cognition.turn.ess_read import answer_bound_ess_tools
from ai.engine.cognition.turn.grounding import ungrounded_numbers

ExecuteTool = Callable[[str, dict], Awaitable[Any]]


def _reply_for(
    cmd: Command, decision: Decision, *, surface: str | None = None,
) -> str | None:
    from ai.engine.agent.surface import Surface

    cmd_op = cmd.op
    lang = decision.language
    # Unset surface is Ask. A caller that already resolved the dial passes it
    # so this copy cannot tell someone to switch to the seat they are in.
    current = Surface.resolve(surface)
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
            # Plan drafts the plan. Agent runs an approved one. Either seat
            # already owns the next step, so a "switch" sentence would loop.
            # None lets the turn fall through to the planner.
            if current is Surface.CHAT_PLAN or current.may_host_mutate:
                return None
            if lang == "ar":
                return (
                    "هذه مهمة متعددة الخطوات. بدّل المفتاح إلى «خطّة» لأضع لك "
                    "خطة تراجعها وتوافق عليها قبل التنفيذ."
                )
            return (
                "This is a multi-step run. Switch the dial to Plan and I'll "
                "draft a plan for you to review and approve before anything runs."
            )
        # A host write. Agent stages it with consent; saying "switch to Agent"
        # there is the same loop. Chat names the dial the user can see.
        if current.may_host_mutate:
            return None
        if lang == "ar":
            return (
                f"هذا يغيّر بيانات في النظام. وضع «{current.dial_label('ar')}» "
                "لا يُرسله — حوّل إلى الوكيل لإتمامه."
            )
        return (
            f"This changes data in the system. {current.dial_label('en')} "
            "does not submit it — switch to Agent to submit it."
        )
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
    tool_args: dict[str, Any] = {"api_name": api_name}
    if args:
        tool_args["query_params"] = dict(args)
    tool_row = {
        "tool_name": "call_host_api",
        "tool_args": tool_args,
        "result": payload,
    }
    if executed is not None:
        executed.append(tool_row)
    text = answer_bound_ess_tools(
        [tool_row],
        api_name=api_name,
        user_message=user_message,
        unread_text=False,
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
    surface: str | None = None,
) -> str | None:
    """Reply text, or None to fall through to the legacy turn.

    ``executed`` (when given) receives the tool rows this Decision ran —
    the only payloads ``render_envelope`` may draw from.

    A handoff or refuse anywhere in the Decision wins (policy first).
    Otherwise a Decision led by a read runs every read it holds, in order;
    one led by anything else speaks that command.
    """
    lead = lead_command(decision)
    if lead is None:
        return None
    if not lead.reads_host():
        return _reply_for(lead, decision, surface=surface)
    if execute_tool is None:
        return None
    texts: list[str] = []
    seen: set[str] = set()
    for cmd in decision.commands:
        if not cmd.reads_host():
            continue
        api = _read_api(cmd, state)
        args = dict(cmd.args or {}) if cmd.op == "call_tool" else {}
        key = f"{api}|{sorted(args.items(), key=lambda kv: kv[0])!r}"
        if not api or key in seen:
            continue
        seen.add(key)
        text = await _execute_bound_read(
            api,
            execute_tool=execute_tool,
            user_message=user_message,
            args=args or None,
            executed=executed,
        )
        if text:
            texts.append(text)
    return "\n\n".join(texts) or None


def lead_command(decision: Decision | None) -> Command | None:
    """The command that decides the turn: a handoff / refuse wins, else the first."""
    if decision is None or not decision.commands:
        return None
    policy = next(
        (c for c in decision.commands if c.op in {"handoff_agent", "refuse"}), None,
    )
    return policy or decision.commands[0]


def arbiter_gate(decision: Decision | None, *, executed: bool) -> str:
    """The existing Arbiter gate this v21 act fired, so the Arbiter records it."""
    lead = lead_command(decision)
    if lead is None:
        return ""
    if lead.reads_host():
        return "tools_executed" if executed else ""
    return {
        "clarify": "chat_clarify",
        "handoff_agent": "chat_handoff",
        "refuse": "off_limits",
    }.get(lead.op, "")


def _read_api(cmd: Command, state: Any) -> str:
    if cmd.op == "confirm":
        return _confirm_api(state)
    if cmd.op == "continue":
        return _continue_api(state) or cmd.name.strip()
    return cmd.name.strip()


def decision_render(decision: Decision | None) -> str:
    """How the decided reads are shown: chart beats table beats text."""
    modes = {c.render for c in (decision.commands if decision else []) if c.reads_host()}
    for mode in ("chart", "table"):
        if mode in modes:
            return mode
    return "text"


def failed_reads(executed: list[dict] | None) -> list[dict]:
    """Executed rows the host refused, with the api name and its detail."""
    from ai.engine.cognition.plan.catalog_args import tool_output_is_invalid_args
    from ai.engine.cognition.turn.repair import host_error_detail

    out: list[dict] = []
    for row in executed or []:
        payload = row.get("result") if isinstance(row, dict) else None
        if tool_output_is_invalid_args(payload):
            out.append({
                "name": str((row.get("tool_args") or {}).get("api_name") or ""),
                "detail": host_error_detail(payload),
            })
    return out


def render_envelope(
    decision: Decision | None,
    executed: list[dict] | None,
    *,
    headline: str = "",
    user_message: str = "",
) -> dict | None:
    V("t_chart_table_envelope_for_render_text")
    if decision is None or not decision.commands:
        return None
    return rows_envelope(
        executed,
        render=decision_render(decision),
        headline=headline,
        user_message=user_message,
    )


def speak_rows(
    decision: Decision | None,
    executed: list[dict] | None,
    *,
    text: str | None,
    user_message: str = "",
) -> tuple[str, dict | None]:
    """Reply text and envelope for the decided reads.

    A restated read speaks for itself. Rows no restater covers are shown
    as a table (or the chart the user asked for), and the envelope's own
    headline and prose are the text — drawn from these rows only.
    """
    render = decision_render(decision)
    spoken = (text or "").strip()
    ok_rows = [r for r in executed or [] if not _is_error(r)]
    if spoken or not ok_rows:
        return spoken, rows_envelope(executed, render=render, headline=spoken, user_message=user_message)
    envelope = rows_envelope(
        ok_rows,
        render=render if render != "text" else "table",
        user_message=user_message,
    )
    if envelope is None:
        return "", None
    lines = [str(envelope.get("headline") or "").strip()]
    lines += [str(p).strip() for p in envelope.get("prose") or [] if str(p).strip()]
    return "\n\n".join(ln for ln in lines if ln), envelope


def _is_error(row: dict) -> bool:
    payload = row.get("result") if isinstance(row, dict) else None
    if isinstance(payload, dict):
        if payload.get("error"):
            return True
        status = payload.get("status_code")
        if isinstance(status, int) and status >= 400:
            return True
    return payload is None


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
