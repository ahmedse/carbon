"""Chat ``handoff_agent`` decision (PV2-3B · ADR-0046 · F-LIVE-2/4).

When Chat would run a plan that includes a mutating ``call_host_api``, do not
execute ReAct / stage consent. Emit a deterministic bilingual handoff and
persist bound slots into ConversationState so Agent can inherit them.
"""
from __future__ import annotations

from ai.engine.host_ids import (
    ID_ENUM_ANNUAL,
    ID_ENUM_CAR,
    ID_ENUM_EMERGENCY,
    ID_ENUM_HOUSING,
    ID_ENUM_MATERNITY,
    ID_ENUM_MEDICAL,
    ID_ENUM_OFFICIAL,
    ID_ENUM_PERSONAL,
    ID_ENUM_SICK,
    ID_ENUM_UNPAID,
    ID_LEAVE_TYPE,
    ID_LOAN_TYPE,
    ID_PERMISSION_TYPE,
    ID_PRINCIPAL,
    ID_SUBMIT_MY_ATTENDANCE_PERMISSION,
    ID_SUBMIT_MY_LEAVE,
    ID_SUBMIT_MY_LOAN,
    ID_SUBMIT_MY_PREFIX,
)
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import LV, V, live_alt, live_pattern, row_for, same_id


import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_word
from ai.engine.cognition.turn.handoff_agent_i18n import (
    AFFIRM_AR,
    AMOUNT_CURRENCY_AR,
    AMOUNT_PREFIX_AR,
    clarify_pack,
    DAYS_AR,
    HOURS_AR,
    JAILBREAK_AR,
    LEAVE_ANNUAL_AR,
    LEAVE_EMERGENCY_AR,
    LEAVE_MATERNITY_AR,
    LEAVE_SICK_AR,
    LEAVE_UNPAID_AR,
    LOAN_CAR_AR,
    LOAN_EMERGENCY_AR,
    LOAN_HOUSING_AR,
    LOAN_PERSONAL_AR,
    LOAN_SALARY_AR,
    MONTHS_AR,
    PERM_EMERGENCY_AR,
    PERM_MEDICAL_AR,
    PERM_OFFICIAL_AR,
    PERM_PERSONAL_AR,
    QUESTION_AR,
    READY_TO_SUBMIT_AR,
    RELATIVE_DAY_AR,
    SLOT_STATUS_AR,
    any_needle,
)

logger = logging.getLogger("pulse.cognition.turn.handoff_agent")

# Minimum slots before Chat stops clarifying and hands off (Agent fills the rest).
_MIN_SLOT_ROWS = (
    (ID_SUBMIT_MY_LOAN, (ID_LOAN_TYPE, ID_PRINCIPAL)),
    (ID_SUBMIT_MY_LEAVE, (ID_LEAVE_TYPE,)),
    (ID_SUBMIT_MY_ATTENDANCE_PERMISSION, (ID_PERMISSION_TYPE,)),
)


def _required_slots(api: str) -> tuple[str, ...] | None:
    row = row_for(_MIN_SLOT_ROWS, api)
    if row is None:
        return None
    return tuple(s for item in row if (s := str(item)))

#  also needs a date or day count (either is enough to stop Chat looping).
_LEAVE_DATE_SLOTS = T("turn/handoff_agent.py::_LEAVE_DATE_SLOTS")


@dataclass
class ChatHandoffOutcome:
    """Deterministic Chat write handoff — never stages host mutations."""

    text: str
    actions: list[dict] = field(default_factory=list)
    envelope: dict | None = None
    api_name: str = ""
    slots: dict = field(default_factory=dict)
    tool_result: dict = field(default_factory=dict)
    decision: str = "handoff_agent"
    #: Closed-set answers for a clarify ( /  / permission type).
    #: Rendered as clickable chips in Chat; each string re-parses as a slot.
    follow_ups: list[str] = field(default_factory=list)


def plan_has_mutating_host_api(
    plan: Any,
    *,
    api_catalog: list[dict] | None = None,
) -> bool:
    """True when any plan step is a host write Chat must not execute.

    Mutating = ``is_mutation``, catalog ``requires_confirmation``, or non-GET
    ``call_host_api`` (fail-closed when catalog entry missing).
    """
    catalog = {
        str(e.get("name") or "").strip(): e
        for e in (api_catalog or [])
        if isinstance(e, dict) and e.get("name")
    }
    for step in getattr(plan, "steps", None) or []:
        tool = (getattr(step, "tool_name", None) or "").strip()
        args = getattr(step, "tool_args", None) or {}
        if not isinstance(args, dict):
            args = {}
        if tool != "call_host_api":
            # Other known writers (DQ create, etc.) — Chat must not run them
            # via multi-step either.
            if tool in {
                "create_dq_rule",
                "propose_dq_rule",
                "save_dq_rule",
                "approve_plan",
            }:
                return True
            continue
        if getattr(step, "is_mutation", False):
            return True
        api = str(args.get("api_name") or args.get("api") or "").strip()
        method = str(args.get("_method") or args.get("method") or "").upper()
        if method and method != "GET":
            return True
        entry = catalog.get(api) if api else None
        if entry is not None:
            if entry.get("requires_confirmation"):
                return True
            em = str(entry.get("method") or "GET").upper()
            if em and em != "GET":
                return True
        elif api.startswith(("submit_", "create_", "update_", "delete_", "post_", "put_", "patch_")):
            return True
        elif args.get("body"):
            return True
    return False


def extract_plan_write(plan: Any) -> tuple[str, dict]:
    """Return ``(api_name, body)`` from the first mutating ``call_host_api`` step."""
    for step in getattr(plan, "steps", None) or []:
        tool = (getattr(step, "tool_name", None) or "").strip()
        if tool != "call_host_api":
            continue
        args = getattr(step, "tool_args", None) or {}
        if not isinstance(args, dict):
            continue
        api = str(args.get("api_name") or args.get("api") or "").strip()
        body = args.get("body") if isinstance(args.get("body"), dict) else {}
        if getattr(step, "is_mutation", False) or (
            api.startswith(("submit_", "create_", "update_", "delete_"))
        ):
            return api, dict(body)
    return "", {}


def enough_slots_for_chat_handoff(api_name: str, slots: dict | None) -> bool:
    """True when Chat has enough bound values to stop clarifying and hand off."""
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    if not body:
        return False
    api = (api_name or "").strip().lower()
    # Accept amount as a synonym for principal (StateBlock / C8 alias).
    principal = str(ID_PRINCIPAL)
    if same_id(api, ID_SUBMIT_MY_LOAN) and principal and principal not in body and "amount" in body:
        body = {**body, principal: body["amount"]}
    required = _required_slots(api)
    if required is None:
        # Unknown write API — hand off as soon as any slot is bound.
        return True
    if not all(body.get(k) not in (None, "", [], {}) for k in required):
        return False
    if api == ID_SUBMIT_MY_LEAVE:
        return any(body.get(k) not in (None, "", [], {}) for k in _LEAVE_DATE_SLOTS)
    return True


def missing_slots_for_chat(api_name: str, slots: dict | None) -> list[str]:
    """Required slot keys still empty — used for 0-LLM clarify."""
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    api = (api_name or "").strip().lower()
    principal = str(ID_PRINCIPAL)
    if same_id(api, ID_SUBMIT_MY_LOAN) and principal and principal not in body and "amount" in body:
        body = {**body, principal: body["amount"]}
    required = list(_required_slots(api) or ())
    missing = [k for k in required if body.get(k) in (None, "", [], {})]
    if api == ID_SUBMIT_MY_LEAVE and not any(
        body.get(k) not in (None, "", [], {}) for k in _LEAVE_DATE_SLOTS
    ):
        missing.append("start_date")
    return missing


def is_slot_status_ask(text: str) -> bool:
    """True for 'what type / dates / amount did I request?' — not a new write."""
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _SLOT_STATUS_PHRASES)
        or any_needle(raw, SLOT_STATUS_AR)
    )


def render_slot_status(text: str, slots: dict | None) -> str:
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    kind_value = str(body.get(ID_LEAVE_TYPE) or "").strip()
    if kind_value and live_alt(r"\btype\b", LV("t_rx_leave_word"), flags=re.I).search(text or ""):
        return f"You requested {kind_value} {V("t_leave")}."
    advance_value = str(body.get(ID_LOAN_TYPE) or "").strip()
    amount = body.get("principal", body.get("amount"))
    if advance_value or amount not in (None, ""):
        bits = []
        if advance_value:
            bits.append(f"{advance_value} {V("t_loan_2")}")
        if amount not in (None, ""):
            bits.append(str(amount))
        return "The agent has " + " and ".join(bits) + "."
    if not body:
        return "I do not have those details on record yet."
    return "I have: " + "; ".join(f"{k} {v}" for k, v in list(body.items())[:6]) + "."


def build_chat_write_clarify(
    *,
    api_name: str,
    slots: dict,
    user_message: str = "",
    echo: bool = False,
) -> ChatHandoffOutcome:
    """0-LLM clarify — seed slots, never stage a host write."""
    from ai.engine.agent.chat_surface import detect_locale

    locale = detect_locale(user_message)
    api = (api_name or "").strip()
    body = dict(slots or {})
    choices: list[str] = []
    if echo and api == ID_SUBMIT_MY_LEAVE:
        kind_value = str(body.get(ID_LEAVE_TYPE) or V("t_leave")).strip()
        start = _pretty_date(body.get("start_date"))
        end = _pretty_date(body.get("end_date"))
        if locale == "ar":
            text = f"فهمت: {V("t_إجازة")} {kind_value} من {start} إلى {end}. أأكد التواريخ؟"
        else:
            text = (
                f"I understand you want {kind_value} {V("t_leave")} from {start} to {end}. "
                "Let me confirm those dates?"
            )
    else:
        missing = missing_slots_for_chat(api, body)
        key = missing[0] if missing else ID_LOAN_TYPE
        pack = clarify_pack(api, str(key))
        text = str(pack.get(locale) or pack.get("en") or "")
        if not text:
            text = "What else do I need to know?"
        advance_value = str(body.get(ID_LOAN_TYPE) or "").strip()
        if api == ID_SUBMIT_MY_LOAN and advance_value and key == "principal":
            if locale == "ar":
                text = f"{V("t_قرض")} {advance_value}. كم المبلغ الذي تحتاجه؟"
            else:
                text = f"{advance_value.title()} {V("t_loan_2")}. How much do you need to borrow?"
        else:
            # Echo what is already bound so the question reads as a
            # continuation, not a cold restart ("Got it: 500 over 12 months.").
            text = _understood_prefix(
                body, locale=locale, user_message=user_message, skip_key=key,
            ) + text
        choices = clarify_choices(api, key, locale)
    return ChatHandoffOutcome(
        text=text,
        actions=[],
        envelope=None,
        api_name=api,
        slots=body,
        tool_result={},
        decision="clarify",
        follow_ups=choices,
    )


def _understood_prefix(
    body: dict,
    *,
    locale: str,
    user_message: str,
    skip_key: str,
) -> str:
    """"Got it: Principal: ٥٠٠; Term (months): ١٢. " or "" when nothing is bound."""
    from ai.engine.agent.chat_surface import _FIELD_LABELS

    bits: list[str] = []
    for key, value in list((body or {}).items())[:8]:
        if key == skip_key or value in (None, "", [], {}):
            continue
        if key == "interest_rate" and value in (0, 0.0, "0"):
            continue
        en_lab, ar_lab = _FIELD_LABELS(key)
        lab = ar_lab if locale == "ar" else en_lab
        bits.append(f"{lab}: {_display_slot_value(value, user_message)}")
    if not bits:
        return ""
    if locale == "ar":
        return "فهمت: " + "؛ ".join(bits) + ". "
    return "Got it: " + "; ".join(bits) + ". "


# Closed-set slot choices. Every label must re-parse through the alias tables
# below (``_first_alias``) so a chip click is a valid slot fill, and must stay
# a host vocabulary (//permission types) — never invented.
_SLOT_CHOICE_ROWS = (
    (ID_SUBMIT_MY_LOAN, (
        (ID_LOAN_TYPE, (
            (ID_ENUM_EMERGENCY, LV("t_emergency_loan"), LV("t_قرض_طارئ")),
            (ID_ENUM_HOUSING, LV("t_housing_loan"), LV("t_قرض_سكن")),
            (LV("t_salary"), LV("t_salary_advance"), LV("t_سلفة_راتب")),
            (ID_ENUM_CAR, LV("t_car_loan"), LV("t_قرض_سيارة")),
            (ID_ENUM_PERSONAL, LV("t_personal_loan"), LV("t_قرض_شخصي")),
        )),
    )),
    (ID_SUBMIT_MY_LEAVE, (
        (ID_LEAVE_TYPE, (
            (ID_ENUM_ANNUAL, LV("t_annual_leave_2"), LV("t_إجازة_سنوية")),
            (ID_ENUM_SICK, LV("t_sick_leave"), LV("t_إجازة_مرضية")),
            (ID_ENUM_EMERGENCY, LV("t_emergency_leave"), LV("t_إجازة_طارئة")),
            (ID_ENUM_UNPAID, LV("t_unpaid_leave"), LV("t_إجازة_بدون_راتب")),
            (ID_ENUM_MATERNITY, LV("t_maternity_leave"), LV("t_إجازة_أمومة")),
        )),
    )),
    (ID_SUBMIT_MY_ATTENDANCE_PERMISSION, (
        (ID_PERMISSION_TYPE, (
            (ID_ENUM_OFFICIAL, LV("t_rx_copy_perm_official"), LV("t_rx_copy_perm_official_ar")),
            (ID_ENUM_MEDICAL, LV("t_rx_copy_perm_medical"), LV("t_rx_copy_perm_medical_ar")),
            (ID_ENUM_EMERGENCY, LV("t_rx_copy_perm_emergency"), LV("t_rx_copy_perm_emergency_ar")),
            (ID_ENUM_PERSONAL, LV("t_rx_copy_perm_personal"), LV("t_rx_copy_perm_personal_ar")),
        )),
    )),
)


def _slot_choice_table(api_name: str, slot_key: str):
    slots = row_for(_SLOT_CHOICE_ROWS, (api_name or "").strip())
    if not slots:
        return ()
    for key, rows in slots:
        if same_id(slot_key, key):
            return rows
    return ()


def clarify_choices(api_name: str, slot_key: str, locale: str = "en") -> list[str]:
    """Chip labels for a governed slot; ``[]`` for free-form slots (amount, dates)."""
    table = _slot_choice_table(api_name, slot_key)
    idx = 2 if locale == "ar" else 1
    return [label for row in table if (label := str(row[idx]))]


def build_slot_status_answer(
    *,
    api_name: str,
    slots: dict,
    user_message: str = "",
) -> ChatHandoffOutcome:
    return ChatHandoffOutcome(
        text=render_slot_status(user_message, slots),
        actions=[],
        envelope=None,
        api_name=api_name,
        slots=dict(slots or {}),
        tool_result={},
        decision="answer",
    )


_READY_TO_SUBMIT_PHRASES = T("turn/handoff_agent.py::_READY_TO_SUBMIT_PHRASES")


def is_ready_to_submit_ask(text: str) -> bool:
    """True for 'is there anything else you need?' after slots are bound."""
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _READY_TO_SUBMIT_PHRASES)
        or any_needle(raw, READY_TO_SUBMIT_AR)
    )


def build_bound_write_confirmation_answer(
    *,
    api_name: str,
    slots: dict,
    user_message: str = "",
) -> ChatHandoffOutcome:
    """0-LLM restatement while Chat is still clarifying — not a second handoff."""
    from ai.engine.agent.chat_surface import detect_locale

    locale = detect_locale(user_message)
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    api = (api_name or "").strip()
    if api == ID_SUBMIT_MY_LEAVE:
        kind_value = str(body.get(ID_LEAVE_TYPE) or V("t_leave")).strip()
        start = _pretty_date(body.get("start_date"))
        end = _pretty_date(body.get("end_date")) or start
        if locale == "ar":
            text = f"طلبك: {V("t_إجازة")} {kind_value} من {start} إلى {end}."
        else:
            text = f"Your {V("t_leave")} request: {kind_value} {V("t_leave")}, {start} to {end}."
    elif locale == "ar":
        text = render_slot_status(user_message, body)
    else:
        text = render_slot_status(user_message, body)
    return ChatHandoffOutcome(
        text=text,
        actions=[],
        envelope=None,
        api_name=api,
        slots=body,
        tool_result={},
        decision="answer",
    )


def combine_user_brief(
    user_message: str,
    conversation_history: list[dict] | None = None,
    prior_slots: dict | None = None,
) -> str:
    """Concatenate recent user turns + prior slot hints for slot fill."""
    parts: list[str] = []
    for msg in (conversation_history or [])[-12:]:
        if not isinstance(msg, dict):
            continue
        if (msg.get("role") or "") != "user":
            continue
        text = (msg.get("content") or "").strip()
        if text:
            parts.append(text)
    current = (user_message or "").strip()
    if current:
        parts.append(current)
    if prior_slots:
        hints = []
        for key, value in prior_slots.items():
            if value in (None, "", [], {}):
                continue
            hints.append(f"{key}={value}")
        if hints:
            parts.append("Known details: " + ", ".join(hints))
    return "\n".join(parts)


_EASTERN_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "0123456789",
)
_TO_EASTERN_DIGITS = str.maketrans(
    "0123456789",
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
)
_QUESTION_START_WORDS = T("turn/handoff_agent.py::_QUESTION_START_WORDS")
_AFFIRM_WORDS = T("turn/handoff_agent.py::_AFFIRM_WORDS")
_AFFIRM_PHRASES = T("turn/handoff_agent.py::_AFFIRM_PHRASES")


def _western_digits(text: str) -> str:
    return (text or "").translate(_EASTERN_DIGITS)


def _numbers_in(text: str) -> list[str]:
    return re.findall(r"\d+", _western_digits(text))


def is_bound_write_affirmation(text: str, slots: dict | None) -> bool:
    """True when the user confirms a write whose slots are already bound.

    «نعم، أريد ٥٠٠٠ بالضبط» after a handoff is not a new draft. A question
    is not an affirmation. A different amount is a slot change, not a confirm.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    stripped = raw.lstrip()
    if (
        "?" in raw
        or any(stripped.casefold().startswith(f"{w} ") or stripped.casefold() == w
               for w in _QUESTION_START_WORDS)
        or any_needle(raw, QUESTION_AR)
    ):
        return False
    if not (
        has_any_word(raw, _AFFIRM_WORDS)
        or contains_any_phrase(raw, _AFFIRM_PHRASES)
        or any_needle(raw, AFFIRM_AR)
    ):
        return False
    known = set()
    for value in (slots or {}).values():
        known.update(_numbers_in(str(value)))
    stated = _numbers_in(raw)
    return all(num in known for num in stated)


def _display_slot_value(value, user_message: str) -> str:
    text = str(value)
    if text.endswith(".0"):
        text = text[:-2]
    if text and text in _western_digits(user_message):
        eastern = text.translate(_TO_EASTERN_DIGITS)
        if eastern in (user_message or ""):
            return eastern
    return text


def _carryover_handoff_copy(
    spec: dict[str, str],
    *,
    draft: dict | None,
    locale: str,
    user_message: str = "",
    surface=None,
) -> str:
    """Bilingual handoff that lists bound slots and Agent carry-over."""
    from ai.engine.agent.chat_surface import _FIELD_LABELS, _label
    from ai.engine.agent.surface import Surface

    # Name the dial the user can see. "Chat does not submit" reads as a bug to
    # someone whose dial says Plan, even though the refusal is right.
    dial = Surface.resolve(surface).dial_label(locale)

    topic = _label(spec, "topic", locale)
    bits: list[str] = []
    if isinstance(draft, dict):
        for key, value in list(draft.items())[:8]:
            if value in (None, "", [], {}):
                continue
            # Default zero interest is noise in the carry-over summary.
            if key == "interest_rate" and value in (0, 0.0, "0"):
                continue
            en_lab, ar_lab = _FIELD_LABELS(key)
            lab = ar_lab if locale == "ar" else en_lab
            bits.append(f"{lab}: {_display_slot_value(value, user_message)}")

    on_ask = Surface.resolve(surface) is Surface.CHAT_ASK
    if locale == "ar":
        if bits:
            have = "لدي: " + "؛ ".join(bits) + "."
        else:
            have = f"جهّزت تفاصيل {topic}."
        if on_ask:
            step = (
                "لإرسال الطلب بدّل المفتاح إلى «خطّة» — سأنقل هذه التفاصيل "
                f"معك. أو قدّم من تطبيقاتي. وضع «{dial}» لا يُرسل ولا يغيّر السجلات. "
                "وضع السؤال لا يُنشئ مهاماً."
            )
        else:
            step = (
                "لإرسال الطلب بدّل إلى وضع الوكيل (Agent) — سأنقل هذه التفاصيل "
                f"معك. أو قدّم من تطبيقاتي. وضع «{dial}» لا يُرسل ولا يغيّر السجلات."
            )
        return f"{have}\n\n{step}"
    if bits:
        have = "I have: " + "; ".join(bits) + "."
    else:
        have = f"I have the details for your {topic}."
    if on_ask:
        step = (
            "To submit it, switch to Plan — I'll carry these details over. "
            f"Or open My and submit there. {dial} does not submit or change records. "
            "Ask does not create tasks."
        )
    else:
        step = (
            "To submit it, switch to Agent — I'll carry these details over. "
            f"Or open My and submit there. {dial} does not submit or change records."
        )
    return f"{have}\n\n{step}"


def build_chat_write_handoff(
    *,
    api_name: str,
    slots: dict,
    user_message: str = "",
    surface=None,
) -> ChatHandoffOutcome:
    """Build text + actions + synthetic ``chat_handoff`` tool result."""
    from ai.engine.agent.chat_surface import (
        build_chat_handoff_result,
        build_handoff_actions,
        build_handoff_envelope,
        detect_locale,
        handoff_spec_for_api,
    )

    locale = detect_locale(user_message)
    api = (api_name or "").strip()
    body = dict(slots or {})
    spec = handoff_spec_for_api(api)
    text = _carryover_handoff_copy(
        spec, draft=body, locale=locale, user_message=user_message,
        surface=surface,
    )
    actions = build_handoff_actions(spec, locale=locale, surface=surface)
    carry = brief_from_write_slots(api, body)
    for action in actions:
        if str(action.get("panel") or "") == "plan":
            action["draft"] = dict(body)
            if carry:
                action["brief"] = carry
    envelope = build_handoff_envelope(
        spec, draft=body, locale=locale, surface=surface,
    )
    tool_result = build_chat_handoff_result(
        "call_host_api",
        {"api_name": api, "body": body},
        user_message=user_message,
        surface=surface,
    )
    # Prefer carry-over copy over the generic handoff_copy inside tool_result.
    tool_result["message"] = text
    tool_result["envelope"] = envelope
    tool_result["actions"] = actions
    return ChatHandoffOutcome(
        text=text,
        actions=actions,
        envelope=envelope,
        api_name=api,
        slots=body,
        tool_result=tool_result,
    )


_PAYROLL_STATUS_PHRASES = T("turn/handoff_agent.py::_PAYROLL_STATUS_PHRASES")
_PAYROLL_STATUS_WORDS = T("turn/handoff_agent.py::_PAYROLL_STATUS_WORDS")


def is_ess_write_utterance(text: str) -> bool:
    V("t_true_when_the_utterance_is_a")
    brief = (text or "").strip()
    if not brief:
        return False
    if is_slot_status_ask(brief):
        return False
    if (
        contains_any_phrase(brief, _PAYROLL_STATUS_PHRASES)
        or has_any_word(brief, _PAYROLL_STATUS_WORDS)
    ):
        return False
    if (
        has_any_word(brief, ("ignore", "disregard", "bypass", "override", "jailbreak"))
        or any_needle(brief, JAILBREAK_AR)
    ):
        return False
    try:
        from ai.engine.cognition.plan.process_dial import (
            is_personal_attendance_brief,
            is_personal_leave_brief,
            is_personal_loan_brief,
        )
    except Exception:  # noqa: BLE001
        logger.debug("process_dial import failed", exc_info=True)
        return False
    return bool(
        is_personal_loan_brief(brief)
        or is_personal_leave_brief(brief)
        or is_personal_attendance_brief(brief)
    )


def is_ess_slot_continuation(text: str, api_name: str | None) -> bool:
    """True when the turn only fills a slot for an already-open ESS write."""
    api = (api_name or "").strip().lower()
    raw = (text or "").strip()
    prefix = str(ID_SUBMIT_MY_PREFIX)
    if not prefix or not api.startswith(prefix) or not raw:
        return False
    if api == ID_SUBMIT_MY_LOAN:
        return bool(
            _parse_amount(raw)
            or _first_alias(raw, _LOAN_TYPE_WORDS, _LOAN_TYPE_NEEDLES)
        )
    if api == ID_SUBMIT_MY_LEAVE:
        return bool(
            _first_alias(raw, _LEAVE_TYPE_WORDS, _LEAVE_TYPE_NEEDLES)
            or _parse_iso_date(raw)
            or _parse_named_dates(raw)
            or _parse_count_with_units(raw, _DAYS_RE, DAYS_AR)
        )
    if api == ID_SUBMIT_MY_ATTENDANCE_PERMISSION:
        return bool(
            _first_alias(raw, _PERMISSION_TYPE_WORDS, _PERMISSION_TYPE_NEEDLES)
            or _parse_iso_date(raw)
            or _parse_hours(raw)
        )
    return False


# Lexical codes for Chat handoff only. Agent re-resolves via MDM on inherit.
# Must not import ``mdm`` / ``fill_write_body`` — Chat run() is async.
_NeedleRow = tuple[tuple[str, ...], str]
_LOAN_TYPE_WORDS = T("turn/handoff_agent.py::_LOAN_TYPE_WORDS")
_LOAN_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (LOAN_EMERGENCY_AR, ID_ENUM_EMERGENCY),
    (LOAN_HOUSING_AR, ID_ENUM_HOUSING),
    (LOAN_SALARY_AR, LV("t_salary")),
    (LOAN_CAR_AR, ID_ENUM_CAR),
    (LOAN_PERSONAL_AR, ID_ENUM_PERSONAL),
)
_LEAVE_TYPE_WORDS = T("turn/handoff_agent.py::_LEAVE_TYPE_WORDS")
_LEAVE_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (LEAVE_ANNUAL_AR, ID_ENUM_ANNUAL),
    (LEAVE_SICK_AR, ID_ENUM_SICK),
    (LEAVE_EMERGENCY_AR, ID_ENUM_EMERGENCY),
    (LEAVE_UNPAID_AR, ID_ENUM_UNPAID),
    (LEAVE_MATERNITY_AR, ID_ENUM_MATERNITY),
)
_PERMISSION_TYPE_WORDS = T("turn/handoff_agent.py::_PERMISSION_TYPE_WORDS")
_PERMISSION_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (PERM_OFFICIAL_AR, ID_ENUM_OFFICIAL),
    (PERM_MEDICAL_AR, ID_ENUM_MEDICAL),
    (PERM_EMERGENCY_AR, ID_ENUM_EMERGENCY),
    (PERM_PERSONAL_AR, ID_ENUM_PERSONAL),
)
_AliasRow = tuple[tuple[str, ...], tuple[str, ...], str]
_LOAN_TYPE_ALIASES: tuple[_AliasRow, ...] = tuple(
    ((code,), needles, code) for needles, code in _LOAN_TYPE_NEEDLES
)
_LEAVE_TYPE_ALIASES: tuple[_AliasRow, ...] = tuple(
    ((code,), needles, code) for needles, code in _LEAVE_TYPE_NEEDLES
)
_PERMISSION_TYPE_ALIASES: tuple[_AliasRow, ...] = tuple(
    ((code,), needles, code) for needles, code in _PERMISSION_TYPE_NEEDLES
)


def _first_alias(
    text: str,
    table_or_en: tuple[str, ...] | tuple[_AliasRow, ...],
    needles_table: tuple[_NeedleRow, ...] | None = None,
) -> str | None:
    raw = text or ""
    if needles_table is not None:
        for word in table_or_en:
            if has_word(raw, word):
                return word
        for needles, code in needles_table:
            if any_needle(raw, needles):
                return str(code) or None
        return None
    for en_words, needles, code in table_or_en:
        if has_any_word(raw, en_words) or any_needle(raw, needles):
            return str(code) or None
    return None


_AR_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "0123456789",
)
_AMOUNT_RE = live_pattern(
    r"([0-9]{2,}(?:[.,][0-9]+)?)\s*(?:sar|kwd|riyal|dinar|dinars)?",
    LV("t_sar_kwd_loan_s_0_9"),
    flags=re.I,
)
# No trailing word-boundary after unit stems that carry suffixes.
_MONTHS_RE = re.compile(r"\b(\d{1,2})\s*(?:months?\b)", re.I)
_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(?:days?\b)", re.I)
_HOURS_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*(?:hour|hours)\b", re.I)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_NAMES = T("turn/handoff_agent.py::_MONTH_NAMES")
_MONTH_INDEX = {name: i for i, name in enumerate(_MONTH_NAMES, 1)}
_NAMED_DATE_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES) + r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*(\d{4}))?\b"
    r"|\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTH_NAMES) + r")"
    r"(?:,\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_SLOT_STATUS_PHRASES = T("turn/handoff_agent.py::_SLOT_STATUS_PHRASES")


def _latin_digits(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


def _parse_amount(text: str) -> float | None:
    raw_text = text or ""
    latin = _latin_digits(raw_text)
    match = _AMOUNT_RE.search(latin)
    if match:
        raw = match.group(1) or match.group(2)
        if raw:
            try:
                return float(raw.replace(",", ""))
            except ValueError:
                pass
    if any_needle(raw_text, AMOUNT_PREFIX_AR + AMOUNT_CURRENCY_AR):
        nums = re.findall(r"\d+", latin)
        if nums:
            try:
                return float(nums[0])
            except ValueError:
                return None
    return None


def _parse_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(_latin_digits(text))
    if not match:
        return None
    try:
        return int(float(match.group(1)))
    except ValueError:
        return None


def _parse_count_with_units(
    text: str,
    pattern: re.Pattern[str],
    unit_needles: tuple[str, ...],
) -> int | None:
    latin = _latin_digits(text or "")
    val = _parse_int(pattern, latin)
    if val is not None:
        return val
    raw = text or ""
    for unit in unit_needles:
        if unit not in raw:
            continue
        direct = re.findall(rf"(\d+)\s*{re.escape(unit)}", latin)
        if direct:
            try:
                return int(float(direct[-1]))
            except ValueError:
                continue
        idx = raw.find(unit)
        prefix = latin[: max(idx, 0)]
        trailing = re.findall(r"\d+", prefix)
        if trailing:
            try:
                return int(float(trailing[-1]))
            except ValueError:
                continue
    return None


def _parse_hours(text: str) -> float | None:
    latin = _latin_digits(text or "")
    match = _HOURS_RE.search(latin)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    count = _parse_count_with_units(text or "", _HOURS_RE, HOURS_AR)
    return float(count) if count is not None else None


def _pretty_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        from datetime import date as _date
        day = _date.fromisoformat(raw[:10])
        return f"{day.strftime('%B')} {day.day}, {day.year}"
    except ValueError:
        return raw


def _parse_iso_date(text: str) -> str | None:
    match = _ISO_DATE_RE.search(_latin_digits(text))
    return match.group(1) if match else None


def _parse_named_weekday(text: str) -> str | None:
    """The coming weekday when the user said next or this plus its name.

    Names live in the function so they are not a routing phrase set.
    """
    raw = (text or "").lower()
    if "next" not in raw and "this" not in raw:
        return None
    names = (
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    )
    index = next((i for i, name in enumerate(names) if name in raw), None)
    if index is None:
        return None
    try:
        from ai.engine.host_services import localdate

        today = localdate()
    except Exception:  # noqa: BLE001
        from datetime import date as _date

        today = _date.today()
    ahead = (index - today.weekday()) % 7
    if "next" in raw and ahead == 0:
        ahead = 7
    from datetime import timedelta

    return (today + timedelta(days=ahead)).isoformat()


def _inclusive_end(start: str, days: Any) -> str | None:
    try:
        from datetime import date as _date
        from datetime import timedelta

        span = int(days)
        if span < 1:
            return None
        day = _date.fromisoformat(str(start)[:10])
    except (TypeError, ValueError):
        return None
    return (day + timedelta(days=span - 1)).isoformat()


def _parse_relative_day(text: str) -> str | None:
    raw = (text or "").strip()
    if not re.search(r"\btoday\b", raw, re.I) and not any_needle(
        raw, RELATIVE_DAY_AR
    ):
        return None
    try:
        from ai.engine.host_services import localdate

        return localdate().isoformat()
    except Exception:  # noqa: BLE001
        from datetime import date as _date

        return _date.today().isoformat()


def _parse_named_dates(text: str) -> list[str]:
    """English month-name dates → ISO strings (year inferred from later hits)."""
    raw = _latin_digits(text or "")
    parsed: list[tuple[int, int, int | None]] = []
    for match in _NAMED_DATE_RE.finditer(raw):
        if match.group(1):
            month = _MONTH_INDEX.get(match.group(1).lower(), 0)
            day = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else None
        else:
            day = int(match.group(4))
            month = _MONTH_INDEX.get((match.group(5) or "").lower(), 0)
            year = int(match.group(6)) if match.group(6) else None
        if month and 1 <= day <= 31:
            parsed.append((month, day, year))
    if not parsed:
        return []
    fallback_year = next((y for _m, _d, y in parsed if y), None)
    from datetime import date as _date
    if fallback_year is None:
        fallback_year = _date.today().year
    out: list[str] = []
    for month, day, year in parsed:
        try:
            out.append(_date(year or fallback_year, month, day).isoformat())
        except ValueError:
            continue
    return out


def resolve_ess_write_from_brief(
    brief: str,
    *,
    prefer_api: str | None = None,
) -> tuple[str, dict] | None:
    V("t_bind_ess_write_slots_from_a")
    text = (brief or "").strip()
    if not text:
        return None
    try:
        from ai.engine.cognition.plan.process_dial import (
            is_personal_attendance_brief,
            is_personal_leave_brief,
            is_personal_loan_brief,
        )
    except Exception:  # noqa: BLE001
        logger.debug("lexical ESS resolve import failed", exc_info=True)
        return None

    prefer = (prefer_api or "").strip().lower()
    as_loan = prefer == ID_SUBMIT_MY_LOAN or is_personal_loan_brief(text)
    as_leave = prefer == ID_SUBMIT_MY_LEAVE or (
        not as_loan and is_personal_leave_brief(text)
    )
    as_attendance = prefer == ID_SUBMIT_MY_ATTENDANCE_PERMISSION or (
        not as_loan and not as_leave and is_personal_attendance_brief(text)
    )

    if as_loan:
        body: dict = {}
        code = _first_alias(text, _LOAN_TYPE_WORDS, _LOAN_TYPE_NEEDLES)
        if code:
            body[ID_LOAN_TYPE] = code
        amount = _parse_amount(text)
        if amount is not None:
            body["principal"] = amount
            body["amount"] = amount  # C8 / StateBlock alias
        months = _parse_count_with_units(text, _MONTHS_RE, MONTHS_AR)
        if months:
            body["term_months"] = months
        parsed = _parse_iso_date(text)
        if parsed:
            body["start_date"] = parsed
        return ID_SUBMIT_MY_LOAN, body

    if as_leave:
        body = {}
        code = _first_alias(text, _LEAVE_TYPE_WORDS, _LEAVE_TYPE_NEEDLES)
        if code:
            body[ID_LEAVE_TYPE] = code
        parsed = _parse_iso_date(text)
        named = _parse_named_dates(text)
        if parsed:
            body["start_date"] = parsed
        if named:
            body["start_date"] = named[0]
            if len(named) > 1:
                body["end_date"] = named[-1]
        relative = _parse_relative_day(text)
        if relative and "start_date" not in body:
            body["start_date"] = relative
        weekday = _parse_named_weekday(text)
        if weekday and "start_date" not in body:
            body["start_date"] = weekday
        days = _parse_count_with_units(text, _DAYS_RE, DAYS_AR)
        if days:
            body["days"] = days
        if body.get("start_date") and body.get("days") and "end_date" not in body:
            end = _inclusive_end(body["start_date"], body["days"])
            if end:
                body["end_date"] = end
        return ID_SUBMIT_MY_LEAVE, body

    if as_attendance:
        body = {}
        code = _first_alias(text, _PERMISSION_TYPE_WORDS, _PERMISSION_TYPE_NEEDLES)
        if code:
            body[ID_PERMISSION_TYPE] = code
        parsed = _parse_iso_date(text)
        if parsed:
            body["date"] = parsed
        hours = _parse_hours(text)
        if hours is not None:
            body["hours"] = hours
        return ID_SUBMIT_MY_ATTENDANCE_PERMISSION, body

    return None


def carry_handoff_slots(
    api_name: str,
    command_args: dict | None,
    *,
    prior_slots: dict | None = None,
    user_message: str = "",
    conversation_history: list[dict] | None = None,
) -> dict:
    """Slots for a Chat handoff card.

    Stored slots come first, then this command. Values the user's own words
    already bind win, including a date the command invented.
    """
    from ai.engine.cognition.turn.capability import flat_args

    prior = dict(prior_slots or {})
    brief = combine_user_brief(user_message, conversation_history, prior)
    bound: dict = {}
    try:
        resolved = resolve_ess_write_from_brief(brief, prefer_api=api_name or None)
    except Exception:  # noqa: BLE001 — an empty bind still shows stored slots
        resolved = None
    if resolved:
        bound = dict(resolved[1] or {})
    return merge_slots(prior, flat_args(command_args), bound)


def brief_from_write_slots(api_name: str, slots: dict | None) -> str:
    """A Plan brief from slots the conversation already bound.

    The last chip is not the brief. This sentence is what Plan materializes.
    """
    body = {
        key: value
        for key, value in (slots or {}).items()
        if value not in (None, "", [], {})
    }
    if not body:
        return ""
    kind = str(
        body.get(ID_LEAVE_TYPE)
        or body.get(ID_LOAN_TYPE)
        or body.get(ID_PERMISSION_TYPE)
        or ""
    ).strip()
    parts = ["I want"]
    if kind:
        parts.append(kind)
    if body.get(ID_LEAVE_TYPE):
        parts.append(V("t_leave"))
    elif body.get(ID_LOAN_TYPE):
        parts.append(V("t_loan_2"))
    else:
        parts.append("this request")
    days = body.get("days")
    if days not in (None, ""):
        parts.append(f"for {days} days")
    hours = body.get("hours")
    if hours not in (None, ""):
        parts.append(f"for {hours} hours")
    amount = body.get("principal", body.get("amount"))
    if amount not in (None, ""):
        parts.append(str(amount))
    start = body.get("start_date") or body.get("date")
    if start:
        parts.append(f"starting {start}")
    end = body.get("end_date")
    if end:
        parts.append(f"ending {end}")
    return " ".join(parts) + "."


def bound_write_args(
    messages: list[dict] | None,
    state: Any = None,
) -> tuple[str, dict] | None:
    """A write the user's words already bind, or None.

    Used when a confirm has nothing to confirm, so the turn does not spend
    another model call inventing the missing values.
    """
    users: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict) or (msg.get("role") or "") != "user":
            continue
        text = str(msg.get("content") or "").strip()
        if text:
            users.append(text)
    if not users:
        return None
    prior: dict = {}
    prefer = ""
    if state is not None:
        prior = dict(getattr(state, "slots", None) or {})
        prefer = str((getattr(state, "intent", None) or {}).get("api") or "")
    history = [{"role": "user", "content": text} for text in users[:-1]]
    brief = combine_user_brief(users[-1], history, prior)
    try:
        resolved = resolve_ess_write_from_brief(brief, prefer_api=prefer or None)
    except Exception:  # noqa: BLE001
        return None
    if resolved is None:
        return None
    api_name, _body = resolved
    slots = carry_handoff_slots(
        api_name,
        {},
        prior_slots=prior,
        user_message=users[-1],
        conversation_history=history,
    )
    if not enough_slots_for_chat_handoff(api_name, slots):
        return None
    return api_name, slots


def merge_slots(*parts: dict | None) -> dict:
    """Left-to-right merge; later non-empty values win."""
    out: dict = {}
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key, value in part.items():
            if value in (None, "", [], {}):
                continue
            out[str(key)] = value
    return out


def seed_slots_into_state(state_ctx: Any, api_name: str, slots: dict) -> None:
    """Persist intent/slots early so Agent (and later Chat turns) inherit them."""
    if state_ctx is None:
        return
    state = getattr(state_ctx, "state", None)
    if state is None:
        return
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    if not body and not api_name:
        return
    prior_api = (state.intent or {}).get("api")
    if api_name and prior_api and api_name != prior_api:
        state.slots = {}
    merged = dict(state.slots or {})
    merged.update(body)
    state.slots = merged
    if api_name:
        prior = state.intent or {}
        state.intent = {
            "zone": prior.get("zone") or "platform",
            "action": api_name,
            "confidence": prior.get("confidence", 0.0),
            "since_turn": prior.get("since_turn", state.next_turn()),
            "api": api_name,
        }
    try:
        from ai.engine.cognition.state_store import upsert_active_plan
        from ai.engine.cognition.turn.plan_status import _title_from_slots

        upsert_active_plan(
            state,
            plan_id="",
            status="handoff_ready",
            title=_title_from_slots(merged),
            slots=merged,
        )
    except Exception:  # noqa: BLE001
        logger.debug("handoff active_plans seed skipped", exc_info=True)


def chat_grounding_rules_block(
    surface: str | None = None,
    *,
    process_mode: str | None = None,
) -> str:
    """Grounding for this surface. Ask answers reads. Plan drafts a task.

    The default (no surface, no dial) stays Ask so older callers keep the
    read-and-answer contract. Plan must not inherit that contract.
    """
    from ai.engine.agent.surface import Surface

    current = Surface.resolve(surface, process_mode=process_mode)
    if current is Surface.CHAT_PLAN:
        return _plan_grounding_rules_block()
    if current.may_host_mutate:
        return _agent_grounding_rules_block()
    return _ask_grounding_rules_block()


def _plan_grounding_rules_block() -> str:
    """Plan dial: the planner drafts the task. This reply never invents steps."""
    return (
        "GROUNDING RULES — follow them exactly:\n"
        "- PLAN MODE. The user is already on Plan. Do not answer the brief "
        "by fetching live data.\n"
        "- The planner drafts the task and shows its steps. You are here "
        "because it could not. Never write a plan of your own, and never "
        "list steps you did not get from a tool result.\n"
        "- Say plainly that you could not turn this into a task, then ask "
        "one short question about the one thing that would let you. One "
        "question, no menu in the sentence.\n"
        "- A short reply (\"both\", \"1,2,3\", \"the first one\") answers your "
        "own last question about the earlier brief. Apply it to that brief. "
        "Never treat it as a new subject and never ask what it refers to.\n"
        "- Do not call read tools (call_host_api, resolve_entity, "
        "aggregate_entity) to produce the answer in this bubble.\n"
        "- Do not submit host writes. Plan drafts only.\n"
        "- Never tell the user to switch to Plan.\n"
        "- NEVER claim a task was created unless plan_task returned it.\n"
        "- If a tool errors, report the error plainly."
    )


def _agent_grounding_rules_block() -> str:
    """Agent dial: an approved plan may stage effects with step consent."""
    return (
        "GROUNDING RULES — follow them exactly:\n"
        "- AGENT MODE. The user is already in Agent. An approved plan may "
        "stage host effects with step consent.\n"
        "- Never tell the user to switch to Agent.\n"
        "- NEVER claim an action succeeded unless a tool result confirms it.\n"
        "- If a tool errors, report the error plainly."
    )


def _ask_grounding_rules_block() -> str:
    """Ask dial: answer reads. A reviewable plan belongs on the Plan dial.

    Host sentences are included only when the bound pack has both halves.
    A pack that does not supply them gets no substitute paragraph.
    """
    writes = V("t_host_writes_leave_loan_attendance_payroll")
    submit = V("t_rx_copy_ask_no_submit")
    if not (writes and submit):
        return ""
    head = (
        "GROUNDING RULES — follow them exactly:\n"
        "- You have tools available. For READS (balances, lists, profile, "
        "distributions, analytics), call the matching read tool and answer — "
        "never call plan_task for a question.\n"
        "- ASK MODE: answers only. Never call plan_task / approve_plan / "
        "edit_plan. Never invent a Tasks-panel plan. If the user needs a "
        "multi-step or reviewable plan, tell them to switch the dial to Plan "
        "(same conversation) — do not invent Open-in-Agent or Open-My for "
        "read questions.\n"
    )
    distribution = V("t_distribution_analytics_for_salary_or_headcount")
    raw_rows = V("t_raw_employee_by_employee_salary_rows")
    if distribution and raw_rows:
        analytics = (
            distribution
            + "return aggregates, buckets, and a chart or summary table — NEVER paste "
            + raw_rows
        )
    else:
        analytics = ""
    report = V("t_salary_or_payroll_report_without_saying")
    board = V("t_gosi_board_summary_before_calling_tools")
    if report and board:
        broad = (
            "- BROAD REPORT BRIEFS: if the user asks for a 'full' / 'complete' "
            + report
            + "ONE short clarifying question with options (distribution, run health, "
            + board
        )
    else:
        broad = ""
    host = (
        writes
        + "stages or submits them. Do NOT call "
        + submit
        + " / mutation "
        "call_host_api / create_dq_rule. When the user wants to submit and you "
        "have the details, tell them to switch to Agent (you will carry the "
        "details over) or open My — one clear next step.\n"
    )
    tail = (
        "- If required details are missing, ask ONE short clarifying question "
        "for the missing piece only; never re-ask slots already known.\n"
        "- NEVER claim an action succeeded unless a tool result confirms it.\n"
        "- Memory (learn_fact / forget_fact) may stage a confirm card — that is "
        "the only Chat write exception.\n"
        "- PLAN FIRST for multi-step analytical work: propose numbered steps in "
        "prose when helpful; only when the user is in Plan mode (or explicitly "
        "asks to convert to a task) may plan_task run.\n"
        "- If a tool errors, report the error plainly.\n"
        "- CLARIFICATION POLICY: if the object is ambiguous, ask one clarifying "
        "question instead of guessing.\n"
        "- TENANT-ORG EXCEPTION: the platform's own organisation name is NEVER "
        "an ambiguous object — answer with live read tools immediately."
    )
    return head + analytics + broad + host + tail
