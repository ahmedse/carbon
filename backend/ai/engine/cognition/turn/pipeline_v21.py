"""v21 act-on-Decision.

Reads run through the caller-supplied coroutine. ``answer``, ``set_slot``,
``navigate`` and a plan handoff return None here; the runner finishes them
from the Decision (``finish.py``, ADR-0056).
"""
from __future__ import annotations
from ai.engine.pack_vocab import V


from typing import Any, Awaitable, Callable

from ai.engine.cognition.turn.decision import PLAN_PROCESS_ID, Command, Decision
from ai.engine.cognition.turn.degradation import Degradation
from ai.engine.cognition.turn.degradation import caveat as degradation_caveat
from ai.engine.cognition.turn.degradation import sentence as degradation_sentence
from ai.engine.cognition.turn.ess_read import answer_bound_ess_tools
from ai.engine.cognition.turn.grounding import ungrounded_numbers
from ai.engine.text.word_match import has_arabic_script

ExecuteTool = Callable[[str, dict], Awaitable[Any]]

_WRITE_RETRY_INSTRUCTIONS = {
    "invalid_output": (
        "(The last summary was not valid JSON. Reply again with the same "
        "schema, using only numbers from the tool results.)"
    ),
    "empty_output": (
        "(Write a short headline and at least one sentence from the tool "
        "results. Use only numbers that appear in them.)"
    ),
    "model_error": (
        "(The last write call failed. Try once more from the tool results.)"
    ),
}


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


def _last_read(state: Any) -> dict:
    rows = getattr(state, "last_results", None) if state is not None else None
    if not rows:
        return {}
    last = rows[-1]
    return last if isinstance(last, dict) else {}


def _continue_api(state: Any) -> str:
    return str(_last_read(state).get("api") or "").strip()


def _continue_args(state: Any) -> dict:
    """The args the last read ran with; a ``continue`` re-runs it for fresh data."""
    last = _last_read(state)
    args = last.get("args")
    return dict(args) if isinstance(args, dict) and str(last.get("api") or "").strip() else {}


async def _execute_bound_read(
    api_name: str,
    *,
    execute_tool: ExecuteTool,
    user_message: str,
    args: dict | None = None,
    executed: list[dict] | None = None,
    catalog: list | None = None,
    fields: list[str] | None = None,
) -> str | None:
    from ai.engine.cognition.turn.catalog_render import catalog_entry_named

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
        catalog_entry=catalog_entry_named(catalog, api_name),
        fields=fields,
    )
    if not text and not has_arabic_script(user_message or ""):
        from ai.engine.cognition.turn.zero_llm import render_resolve_grounded

        text = render_resolve_grounded(user_message, payload)
    # A restatement with a number the payload lacks is not edited: it is
    # withheld, and the writer speaks from the payload instead (ADR-0056).
    if ungrounded_numbers(text, [payload]):
        return None
    return text or None


async def act_on_decision(
    decision: Decision | None,
    *,
    execute_tool: ExecuteTool | None,
    user_message: str,
    state: Any = None,
    executed: list[dict] | None = None,
    surface: str | None = None,
    catalog: list | None = None,
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
        if cmd.op == "continue" and last_view(state):
            continue  # the reply re-renders the last view; no host read
        api = _read_api(cmd, state)
        if cmd.op == "call_tool":
            args = dict(cmd.args or {})
        elif cmd.op == "continue" and api == _continue_api(state):
            args = _continue_args(state)
        else:
            args = {}
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
            catalog=catalog,
            fields=list(cmd.fields or []),
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
        # A continue that re-renders the last view speaks from tool rows too.
        return "tools_executed" if executed or lead.op == "continue" else ""
    return {
        "clarify": "chat_clarify",
        "navigate": "nav_ground",
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


def decision_chart(decision: Decision | None) -> str:
    """The chart shape the user named on a decided read, or ""."""
    for cmd in (decision.commands if decision else []):
        if cmd.reads_host() and cmd.chart:
            return cmd.chart
    return ""


def _apply_chart_shape(envelope: dict, chart: str) -> dict:
    """Draw every chart as the named shape. Say so once when the split is uneven."""
    if not chart:
        return envelope
    charts = []
    uneven = False
    for item in envelope.get("charts") or []:
        points = [
            p for s in (item.get("series") or []) if isinstance(s, dict)
            for p in (s.get("data") or []) if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        shape = chart
        if chart == "pie" and len(points) > 8:
            shape = item.get("chart_type") or "bar"
        values = [float(p[1]) for p in points if isinstance(p[1], (int, float))]
        if shape == "pie" and values and max(values) / (sum(values) or 1) >= 0.7:
            uneven = True
        charts.append({**item, "chart_type": shape})
    out = {**envelope, "charts": charts}
    if uneven:
        out["caveats"] = [*(envelope.get("caveats") or []), {
            "level": "info",
            "text": "One category holds most of the total, so small slices are hard to see.",
        }]
    return out


async def narrate_envelope(
    envelope: dict,
    evidence: list[dict] | None,
    *,
    user_message: str,
    understood: str = "",
    language: str = "en",
    instance_id: str,
    conversation_id: str,
) -> tuple[str, dict, Degradation | None] | None:
    """Headline and prose written for this turn's message, from ``evidence`` only.

    Data blocks stay deterministic. The model's words are shown as written:
    a number not in the evidence, bad JSON, an empty body, or a model flake
    each get one retry, then the turn fails visibly (ADR-0056). When the
    writer fails the reply says so and carries a typed ``Degradation``
    (ADR-0053); it never returns the template.
    None only when the writer is switched off by configuration.
    """
    from ai.engine.core.config import get_settings

    if not get_settings().PULSE_ENVELOPE_ENABLED:
        return None
    ok_rows = [r for r in evidence or [] if not _is_error(r)]
    if not ok_rows:
        return None
    from ai.envelope_service import EnvelopeWriteError, synthesize_envelope
    from ai.engine.llm.call_meter import stage

    question = user_message
    if understood:
        question = f"{user_message}\n(Understood as: {understood})"
    payloads = [r.get("result") for r in ok_rows]
    cause = ""
    typed = None
    headline = ""
    prose: list[str] = []
    note = ""
    # One retry on flake (bad JSON / empty / model / ungrounded). A second
    # failure stays typed — never a template that looks like an answer.
    for attempt in range(2):
        cause = ""
        try:
            with stage("draft"):
                typed = await synthesize_envelope(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=f"{question}\n{note}" if note else question,
                    usable_tools=ok_rows,
                    strict=True,
                )
        except EnvelopeWriteError as exc:
            cause = exc.cause
        except Exception:  # noqa: BLE001 — reported below as a typed degradation
            cause = "model_error"
        if not cause:
            headline = (typed.headline or "").strip() if typed is not None else ""
            prose = [p.strip() for p in (typed.prose if typed is not None else []) or [] if p and p.strip()]
            bad = ungrounded_numbers("\n".join([headline, *prose]), payloads)
            if not prose:
                cause = "empty_output"
            elif bad:
                cause = "ungrounded"
                note = (
                    "(These numbers are not in the tool results: "
                    f"{', '.join(bad[:8])}. Use only numbers that appear in them.)"
                )
            else:
                break
        if cause == "no_rows" or attempt:
            break
        if cause != "ungrounded":
            note = _WRITE_RETRY_INSTRUCTIONS.get(cause, _WRITE_RETRY_INSTRUCTIONS["invalid_output"])
        continue
    if cause:
        failed = Degradation(stage="write", cause=cause)
        line = degradation_sentence(failed, language)
        degraded = {
            **envelope,
            "headline": "",
            "prose": [line],
            "caveats": [*(envelope.get("caveats") or []), degradation_caveat(failed)],
        }
        return line, degraded, failed
    merged = {**envelope, "headline": headline, "prose": prose}
    return "\n\n".join(ln for ln in [headline, *prose] if ln), merged, None


def last_view(state: Any) -> dict:
    view = getattr(state, "last_view", None) if state is not None else None
    return view if isinstance(view, dict) and (view.get("tables") or view.get("charts")) else {}


def _view_envelope(view: dict, chart: str) -> dict:
    envelope = {
        "headline": "",
        "prose": [],
        "tables": list(view.get("tables") or []),
        "charts": list(view.get("charts") or []),
        "caveats": list(view.get("caveats") or []),
        "sources": [{"tool": "last_view", "rows_returned": len(view.get("tables") or []),
                     "truncated": False, "resolved_at": None}],
    }
    return _apply_chart_shape(envelope, chart)


def _remember_view(state: Any, envelope: dict, executed: list[dict] | None) -> None:
    if state is None or not hasattr(state, "last_view"):
        return
    from ai.engine.cognition.state_store import bound_view

    apis = [
        str((r.get("tool_args") or {}).get("api_name") or r.get("tool_name") or "")
        for r in executed or [] if isinstance(r, dict) and not _is_error(r)
    ]
    state.last_view = bound_view({
        "turn": state.next_turn(),
        "apis": apis,
        "tables": envelope.get("tables") or [],
        "charts": envelope.get("charts") or [],
        "caveats": envelope.get("caveats") or [],
    })


async def speak_turn(
    decision: Decision | None,
    executed: list[dict] | None,
    *,
    text: str | None,
    user_message: str,
    instance_id: str,
    conversation_id: str,
    state: Any = None,
) -> tuple[str, dict | None, Degradation | None]:
    """The reply for the decided reads.

    A restated read speaks for itself. A ``continue`` on the last view
    re-renders it with no host read. Otherwise the reply is written for this
    message from these rows. A writer failure is returned typed, not hidden.
    """
    lead = lead_command(decision)
    language = decision.language if decision else "en"
    understood = decision.reason if decision else ""
    view = last_view(state)
    if (
        not executed
        and lead is not None
        and lead.op in {"continue", "answer"}
        and view
    ):
        from ai.engine.cognition.turn.catalog_render import restate_last_view

        envelope = _view_envelope(view, decision_chart(decision))
        restated_view = restate_last_view(view, language)
        if restated_view:
            spoken = {**envelope, "headline": "", "prose": [restated_view]}
            _remember_view(state, spoken, [])
            return restated_view, spoken, None
        if lead.op == "continue":
            evidence = [{"tool_name": "last_view", "result": {
                "tables": envelope["tables"], "charts": envelope["charts"],
            }}]
            narrated = await narrate_envelope(
                envelope, evidence, user_message=user_message, understood=understood,
                language=language, instance_id=instance_id, conversation_id=conversation_id,
            )
            if narrated is None:
                return "", envelope, None
            _remember_view(state, narrated[1], [])
            return narrated

    restated = bool((text or "").strip())
    spoken, envelope = speak_rows(decision, executed, text=text, user_message=user_message)
    if envelope and executed:
        _remember_view(state, envelope, executed)
    if not envelope and not restated and any(not _is_error(r) for r in executed or []):
        # A payload with no table (a receipt, a passage, a card) is still
        # evidence: the grounded writer speaks from it (ADR-0056).
        envelope = {"headline": "", "prose": [], "tables": [], "charts": [], "caveats": [], "sources": []}
    if not envelope or restated:
        return spoken, envelope, None
    narrated = await narrate_envelope(
        envelope, executed, user_message=user_message, understood=understood,
        language=language, instance_id=instance_id, conversation_id=conversation_id,
    )
    if narrated is None:
        return spoken, envelope, None
    from ai.engine.cognition.turn.reasoning import revision

    replaced = revision(spoken, narrated[0], "The summary was rewritten for this message.")
    if replaced is not None:
        narrated[1]["revision"] = replaced
    return narrated


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


def _parsed(payload: Any) -> Any:
    import json

    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            return payload
    return payload


def mismatched_reads(
    executed: list[dict] | None,
    *,
    user_message: str,
    path_keys: Callable[[str], set[str]],
) -> list[dict]:
    """Path-keyed reads that did not return the record the user identified.

    The user's own numerals are the identifiers they gave. A read addressed
    by a path key must return a record that carries at least one of them;
    a not-found or a different record means the path value was not the
    record id for what the user named.
    """
    asked = list(dict.fromkeys(ungrounded_numbers(user_message, [])))
    if not asked:
        return []
    out: list[dict] = []
    for row in executed or []:
        if not isinstance(row, dict):
            continue
        args = row.get("tool_args") or {}
        name = str(args.get("api_name") or "")
        keys = path_keys(name) if name else set()
        if not keys:
            continue
        given = args.get("path_params") if isinstance(args.get("path_params"), dict) else {}
        used = {k: given.get(k) for k in keys if given.get(k) is not None}
        data = _parsed(row.get("result"))
        status = data.get("status_code") if isinstance(data, dict) else None
        body = data.get("data") if isinstance(data, dict) and "data" in data else data
        not_found = status == 404
        missing = ungrounded_numbers(" ".join(asked), [body])
        if not not_found and len(missing) < len(asked):
            continue
        slots = ", ".join(f"{k}={v}" for k, v in used.items()) or ", ".join(sorted(keys))
        what = "no record has that path value" if not_found else "the record returned does not carry it"
        out.append({
            "name": name,
            "detail": (
                f"The user identified the record by {', '.join(asked)}; {what} ({slots}). "
                "A path key takes the record id from an earlier lookup result, not a "
                "number the user typed. Look the record up by the value the user gave."
            ),
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
        chart=decision_chart(decision),
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
    chart = decision_chart(decision)
    spoken = (text or "").strip()
    ok_rows = [r for r in executed or [] if not _is_error(r)]
    if spoken or not ok_rows:
        return spoken, rows_envelope(
            executed, render=render, headline=spoken, user_message=user_message, chart=chart,
        )
    envelope = rows_envelope(
        ok_rows,
        render=render if render != "text" else "table",
        user_message=user_message,
        chart=chart,
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
    chart: str = "",
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
    return _apply_chart_shape(envelope.model_dump(), chart)
