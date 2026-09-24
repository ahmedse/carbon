"""Chat ``handoff_agent`` decision (PV2-3B · ADR-0046 · F-LIVE-2/4).

When Chat would run a plan that includes a mutating ``call_host_api``, do not
execute ReAct / stage consent. Emit a deterministic bilingual handoff and
persist bound slots into ConversationState so Agent can inherit them.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_word
from ai.engine.cognition.turn.handoff_agent_i18n import (
    AFFIRM_AR,
    AMOUNT_CURRENCY_AR,
    AMOUNT_PREFIX_AR,
    CLARIFY_TEXT,
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
_MIN_SLOTS: dict[str, tuple[str, ...]] = {
    "submit_my_loan": ("loan_type", "principal"),
    "submit_my_leave": ("leave_type",),
    "submit_my_attendance_permission": ("permission_type",),
}

# Leave also needs a date or day count (either is enough to stop Chat looping).
_LEAVE_DATE_SLOTS = ("start_date", "end_date", "days")


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
    #: Closed-set answers for a clarify (loan / leave / permission type).
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
    if api == "submit_my_loan" and "principal" not in body and "amount" in body:
        body = {**body, "principal": body["amount"]}
    required = _MIN_SLOTS.get(api)
    if required is None:
        # Unknown write API — hand off as soon as any slot is bound.
        return True
    if not all(body.get(k) not in (None, "", [], {}) for k in required):
        return False
    if api == "submit_my_leave":
        return any(body.get(k) not in (None, "", [], {}) for k in _LEAVE_DATE_SLOTS)
    return True


def missing_slots_for_chat(api_name: str, slots: dict | None) -> list[str]:
    """Required slot keys still empty — used for 0-LLM clarify."""
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    api = (api_name or "").strip().lower()
    if api == "submit_my_loan" and "principal" not in body and "amount" in body:
        body = {**body, "principal": body["amount"]}
    required = list(_MIN_SLOTS.get(api) or ())
    missing = [k for k in required if body.get(k) in (None, "", [], {})]
    if api == "submit_my_leave" and not any(
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
    leave = str(body.get("leave_type") or "").strip()
    if leave and re.search(r"\btype\b|\bleave\b", text or "", re.I):
        return f"You requested {leave} leave."
    loan = str(body.get("loan_type") or "").strip()
    amount = body.get("principal", body.get("amount"))
    if loan or amount not in (None, ""):
        bits = []
        if loan:
            bits.append(f"{loan} loan")
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
    if echo and api == "submit_my_leave":
        leave = str(body.get("leave_type") or "leave").strip()
        start = _pretty_date(body.get("start_date"))
        end = _pretty_date(body.get("end_date"))
        if locale == "ar":
            text = f"فهمت: إجازة {leave} من {start} إلى {end}. أأكد التواريخ؟"
        else:
            text = (
                f"I understand you want {leave} leave from {start} to {end}. "
                "Let me confirm those dates?"
            )
    else:
        missing = missing_slots_for_chat(api, body)
        key = missing[0] if missing else "loan_type"
        pack = (CLARIFY_TEXT.get(api) or {}).get(key) or {}
        text = pack.get(locale) or pack.get("en") or "What else do I need to know?"
        loan = str(body.get("loan_type") or "").strip()
        if api == "submit_my_loan" and loan and key == "principal":
            if locale == "ar":
                text = f"قرض {loan}. كم المبلغ الذي تحتاجه؟"
            else:
                text = f"{loan.title()} loan. How much do you need to borrow?"
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
        en_lab, ar_lab = _FIELD_LABELS.get(
            key, (key.replace("_", " "), key.replace("_", " "))
        )
        lab = ar_lab if locale == "ar" else en_lab
        bits.append(f"{lab}: {_display_slot_value(value, user_message)}")
    if not bits:
        return ""
    if locale == "ar":
        return "فهمت: " + "؛ ".join(bits) + ". "
    return "Got it: " + "; ".join(bits) + ". "


# Closed-set slot choices. Every label must re-parse through the alias tables
# below (``_first_alias``) so a chip click is a valid slot fill, and must stay
# a host vocabulary (Nibras loan/leave/permission types) — never invented.
_SLOT_CHOICES: dict[str, dict[str, tuple[tuple[str, str, str], ...]]] = {
    "submit_my_loan": {
        "loan_type": (
            ("emergency", "Emergency loan", "قرض طارئ"),
            ("housing", "Housing loan", "قرض سكن"),
            ("salary", "Salary advance", "سلفة راتب"),
            ("car", "Car loan", "قرض سيارة"),
            ("personal", "Personal loan", "قرض شخصي"),
        ),
    },
    "submit_my_leave": {
        "leave_type": (
            ("annual", "Annual leave", "إجازة سنوية"),
            ("sick", "Sick leave", "إجازة مرضية"),
            ("emergency", "Emergency leave", "إجازة طارئة"),
            ("unpaid", "Unpaid leave", "إجازة بدون راتب"),
            ("maternity", "Maternity leave", "إجازة أمومة"),
        ),
    },
    "submit_my_attendance_permission": {
        "permission_type": (
            ("official", "Official permission", "استئذان رسمي"),
            ("medical", "Medical permission", "استئذان طبي"),
            ("emergency", "Emergency permission", "استئذان طارئ"),
            ("personal", "Personal permission", "استئذان شخصي"),
        ),
    },
}


def clarify_choices(api_name: str, slot_key: str, locale: str = "en") -> list[str]:
    """Chip labels for a governed slot; ``[]`` for free-form slots (amount, dates)."""
    table = (_SLOT_CHOICES.get((api_name or "").strip()) or {}).get(slot_key) or ()
    idx = 2 if locale == "ar" else 1
    return [row[idx] for row in table]


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


_READY_TO_SUBMIT_PHRASES = (
    "anything else you need", "anything else you needed", "anything else i need",
    "anything else i needed", "is that all", "is that everything",
    "do you need anything", "do you need everything", "do you need all",
    "do you have anything", "do you have everything", "do you have all",
)


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
    if api == "submit_my_leave":
        leave = str(body.get("leave_type") or "leave").strip()
        start = _pretty_date(body.get("start_date"))
        end = _pretty_date(body.get("end_date")) or start
        if locale == "ar":
            text = f"طلبك: إجازة {leave} من {start} إلى {end}."
        else:
            text = f"Your leave request: {leave} leave, {start} to {end}."
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
_QUESTION_START_WORDS = ("when", "how", "why", "what", "will", "can", "does")
_AFFIRM_WORDS = ("yes", "yep", "exactly", "correct")
_AFFIRM_PHRASES = ("that's all", "thats all")


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
            en_lab, ar_lab = _FIELD_LABELS.get(
                key, (key.replace("_", " "), key.replace("_", " "))
            )
            lab = ar_lab if locale == "ar" else en_lab
            bits.append(f"{lab}: {_display_slot_value(value, user_message)}")

    if locale == "ar":
        if bits:
            have = "لدي: " + "؛ ".join(bits) + "."
        else:
            have = f"جهّزت تفاصيل {topic}."
        return (
            f"{have}\n\n"
            "لإرسال الطلب بدّل إلى وضع الوكيل (Agent) — سأنقل هذه التفاصيل "
            f"معك. أو قدّم من تطبيقاتي. وضع «{dial}» لا يُرسل ولا يغيّر السجلات."
        )
    if bits:
        have = "I have: " + "; ".join(bits) + "."
    else:
        have = f"I have the details for your {topic}."
    return (
        f"{have}\n\n"
        "To submit it, switch to Agent — I'll carry these details over. "
        f"Or open My and submit there. {dial} does not submit or change records."
    )


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


_PAYROLL_STATUS_PHRASES = (
    "what was", "what were", "what is my", "how much was", "when will",
    "net pay", "take-home", "take home", "can i download",
)
_PAYROLL_STATUS_WORDS = (
    "payslip", "payslips", "deduction", "deductions", "gosi", "payroll",
)


def is_ess_write_utterance(text: str) -> bool:
    """True when the utterance is a personal loan / leave / attendance write.

    Used by the Chat handoff path and the ``_should_force_action`` fallback so
    ESS writes are not gated only on ``_is_mutation_request`` (which is leave-
    and DQ-shaped and misses "apply for a loan"). Payroll recall
    ("what was the loan amount?") is not a write.
    """
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
    if not api.startswith("submit_my_") or not raw:
        return False
    if api == "submit_my_loan":
        return bool(
            _parse_amount(raw)
            or _first_alias(raw, _LOAN_TYPE_WORDS, _LOAN_TYPE_NEEDLES)
        )
    if api == "submit_my_leave":
        return bool(
            _first_alias(raw, _LEAVE_TYPE_WORDS, _LEAVE_TYPE_NEEDLES)
            or _parse_iso_date(raw)
            or _parse_named_dates(raw)
            or _parse_count_with_units(raw, _DAYS_RE, DAYS_AR)
        )
    if api == "submit_my_attendance_permission":
        return bool(
            _first_alias(raw, _PERMISSION_TYPE_WORDS, _PERMISSION_TYPE_NEEDLES)
            or _parse_iso_date(raw)
            or _parse_hours(raw)
        )
    return False


# Lexical codes for Chat handoff only. Agent re-resolves via MDM on inherit.
# Must not import ``mdm`` / ``fill_write_body`` — Chat run() is async.
_NeedleRow = tuple[tuple[str, ...], str]
_LOAN_TYPE_WORDS = ("emergency", "housing", "salary", "car", "personal")
_LOAN_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (LOAN_EMERGENCY_AR, "emergency"),
    (LOAN_HOUSING_AR, "housing"),
    (LOAN_SALARY_AR, "salary"),
    (LOAN_CAR_AR, "car"),
    (LOAN_PERSONAL_AR, "personal"),
)
_LEAVE_TYPE_WORDS = ("annual", "sick", "emergency", "unpaid", "maternity")
_LEAVE_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (LEAVE_ANNUAL_AR, "annual"),
    (LEAVE_SICK_AR, "sick"),
    (LEAVE_EMERGENCY_AR, "emergency"),
    (LEAVE_UNPAID_AR, "unpaid"),
    (LEAVE_MATERNITY_AR, "maternity"),
)
_PERMISSION_TYPE_WORDS = ("official", "medical", "emergency", "personal")
_PERMISSION_TYPE_NEEDLES: tuple[_NeedleRow, ...] = (
    (PERM_OFFICIAL_AR, "official"),
    (PERM_MEDICAL_AR, "medical"),
    (PERM_EMERGENCY_AR, "emergency"),
    (PERM_PERSONAL_AR, "personal"),
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
                return code
        return None
    for en_words, needles, code in table_or_en:
        if has_any_word(raw, en_words) or any_needle(raw, needles):
            return code
    return None


_AR_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "0123456789",
)
_AMOUNT_RE = re.compile(
    r"([0-9]{2,}(?:[.,][0-9]+)?)\s*(?:sar|kwd|riyal|dinar|dinars)?"
    r"|(?:sar|kwd|loan)\s*([0-9]{2,}(?:[.,][0-9]+)?)",
    re.I,
)
# No trailing word-boundary after unit stems that carry suffixes.
_MONTHS_RE = re.compile(r"\b(\d{1,2})\s*(?:months?\b)", re.I)
_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(?:days?\b)", re.I)
_HOURS_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*(?:hour|hours)\b", re.I)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
_MONTH_INDEX = {name: i for i, name in enumerate(_MONTH_NAMES, 1)}
_NAMED_DATE_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES) + r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*(\d{4}))?\b"
    r"|\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTH_NAMES) + r")"
    r"(?:,\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_SLOT_STATUS_PHRASES = (
    "what type", "what date", "what dates", "what amount", "what information",
    "how much", "what did i", "what was", "which date", "which dates",
    "is it marked", "marked as",
)


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


def _parse_relative_day(text: str) -> str | None:
    raw = (text or "").strip()
    if not re.search(r"\btoday\b", raw, re.I) and not any_needle(
        raw, RELATIVE_DAY_AR
    ):
        return None
    try:
        from django.utils import timezone

        return timezone.localdate().isoformat()
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
    """Bind ESS write slots from a combined brief (loan/leave/attendance).

    Lexical only — no MDM / ``write_slots``. Chat is async; governed lookup
    is Agent's job after handoff. Returns ``(api_name, body)`` or None.

    ``prefer_api`` forces the write kind when the current turn is a slot
    continuation (e.g. \"I need 3000 SAR\") that is not itself a loan brief.
    """
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
    as_loan = prefer == "submit_my_loan" or is_personal_loan_brief(text)
    as_leave = prefer == "submit_my_leave" or (
        not as_loan and is_personal_leave_brief(text)
    )
    as_attendance = prefer == "submit_my_attendance_permission" or (
        not as_loan and not as_leave and is_personal_attendance_brief(text)
    )

    if as_loan:
        body: dict = {}
        code = _first_alias(text, _LOAN_TYPE_WORDS, _LOAN_TYPE_NEEDLES)
        if code:
            body["loan_type"] = code
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
        return "submit_my_loan", body

    if as_leave:
        body = {}
        code = _first_alias(text, _LEAVE_TYPE_WORDS, _LEAVE_TYPE_NEEDLES)
        if code:
            body["leave_type"] = code
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
        days = _parse_count_with_units(text, _DAYS_RE, DAYS_AR)
        if days:
            body["days"] = days
        return "submit_my_leave", body

    if as_attendance:
        body = {}
        code = _first_alias(text, _PERMISSION_TYPE_WORDS, _PERMISSION_TYPE_NEEDLES)
        if code:
            body["permission_type"] = code
        parsed = _parse_iso_date(text)
        if parsed:
            body["date"] = parsed
        hours = _parse_hours(text)
        if hours is not None:
            body["hours"] = hours
        return "submit_my_attendance_permission", body

    return None


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


def chat_grounding_rules_block() -> str:
    """Chat-surface grounding — never instructs mutation tool calls for host writes."""
    return (
        "GROUNDING RULES — follow them exactly:\n"
        "- You have tools available. For READS (balances, lists, profile, "
        "distributions, analytics), call the matching read tool and answer — "
        "never call plan_task for a question.\n"
        "- ASK MODE: answers only. Never call plan_task / approve_plan / "
        "edit_plan. Never invent a Tasks-panel plan. If the user needs a "
        "multi-step or reviewable plan, tell them to switch the dial to Plan "
        "(same conversation) — do not invent Open-in-Agent or Open-My for "
        "read questions.\n"
        "- DISTRIBUTION / ANALYTICS: for salary or headcount distributions, "
        "return aggregates, buckets, and a chart or summary table — NEVER paste "
        "raw employee-by-employee salary rows into the chat.\n"
        "- BROAD REPORT BRIEFS: if the user asks for a 'full' / 'complete' "
        "salary or payroll report without saying the angle or audience, ask "
        "ONE short clarifying question with options (distribution, run health, "
        "GOSI, board summary) before calling tools.\n"
        "- HOST WRITES (leave, loan, attendance, payroll, DQ create): Chat never "
        "stages or submits them. Do NOT call submit_my_* / mutation "
        "call_host_api / create_dq_rule. When the user wants to submit and you "
        "have the details, tell them to switch to Agent (you will carry the "
        "details over) or open My — one clear next step.\n"
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
