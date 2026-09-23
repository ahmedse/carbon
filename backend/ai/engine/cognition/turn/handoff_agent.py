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
    return bool(_SLOT_STATUS_RE.search(text or ""))


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
    if echo and api == "submit_my_leave":
        leave = str(body.get("leave_type") or "leave").strip()
        start = _pretty_date(body.get("start_date"))
        end = _pretty_date(body.get("end_date"))
        if locale == "ar":
            text = f"فهمت: إجازة {leave} من {start} إلى {end}. أأكد التواريخ؟"
        else:
            text = (
                f"I understand you want {leave} leave from {start} to {end}. "
                "Let me confirm those dates."
            )
    else:
        missing = missing_slots_for_chat(api, body)
        key = missing[0] if missing else "loan_type"
        pack = (_CLARIFY_TEXT.get(api) or {}).get(key) or {}
        text = pack.get(locale) or pack.get("en") or "What else do I need to know?"
        loan = str(body.get("loan_type") or "").strip()
        if api == "submit_my_loan" and loan and key == "principal":
            if locale == "ar":
                text = f"قرض {loan}. كم المبلغ الذي تحتاجه؟"
            else:
                text = f"{loan.title()} loan. How much do you need to borrow?"
    return ChatHandoffOutcome(
        text=text,
        actions=[],
        envelope=None,
        api_name=api,
        slots=body,
        tool_result={},
        decision="clarify",
    )


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


def _carryover_handoff_copy(
    spec: dict[str, str],
    *,
    draft: dict | None,
    locale: str,
) -> str:
    """Bilingual handoff that lists bound slots and Agent carry-over."""
    from ai.engine.agent.chat_surface import _FIELD_LABELS, _label

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
            bits.append(f"{lab}: {value}")

    if locale == "ar":
        if bits:
            have = "لدي: " + "؛ ".join(bits) + "."
        else:
            have = f"جهّزت تفاصيل {topic}."
        return (
            f"{have}\n\n"
            "لإرسال الطلب بدّل إلى وضع الوكيل (Agent) — سأنقل هذه التفاصيل "
            "معك. أو قدّم من تطبيقاتي. الدردشة لا تُرسل ولا تغيّر السجلات."
        )
    if bits:
        have = "I have: " + "; ".join(bits) + "."
    else:
        have = f"I have the details for your {topic}."
    return (
        f"{have}\n\n"
        "To submit it, switch to Agent — I'll carry these details over. "
        "Or open My and submit there. Chat does not submit or change records."
    )


def build_chat_write_handoff(
    *,
    api_name: str,
    slots: dict,
    user_message: str = "",
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
    text = _carryover_handoff_copy(spec, draft=body, locale=locale)
    actions = build_handoff_actions(spec, locale=locale)
    envelope = build_handoff_envelope(spec, draft=body, locale=locale)
    tool_result = build_chat_handoff_result(
        "call_host_api",
        {"api_name": api, "body": body},
        user_message=user_message,
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


_PAYROLL_OR_STATUS_ASK_RE = re.compile(
    r"("
    r"\b(?:what was|what were|what is my|how much was|when will)\b"
    r"|\b(?:net pay|take-home|payslip|deductions?|gosi|payroll)\b"
    r"|\bcan i download\b"
    r")",
    re.IGNORECASE,
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
    if _PAYROLL_OR_STATUS_ASK_RE.search(brief):
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
        return bool(_parse_amount(raw) or _first_alias(raw, _LOAN_TYPE_ALIASES))
    if api == "submit_my_leave":
        return bool(
            _first_alias(raw, _LEAVE_TYPE_ALIASES)
            or _parse_iso_date(raw)
            or _parse_named_dates(raw)
            or _parse_int(_DAYS_RE, raw)
        )
    if api == "submit_my_attendance_permission":
        return bool(
            _first_alias(raw, _PERMISSION_TYPE_ALIASES)
            or _parse_iso_date(raw)
            or _parse_hours(raw)
        )
    return False


# Lexical codes for Chat handoff only. Agent re-resolves via MDM on inherit.
# Must not import ``mdm`` / ``fill_write_body`` — Chat run() is async.
_LOAN_TYPE_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bemergency\b|طارئ|طارئة|طارئه", re.I), "emergency"),
    (re.compile(r"\bhousing\b|سكن|عقاري", re.I), "housing"),
    (re.compile(r"\bsalary\b|راتب", re.I), "salary"),
    (re.compile(r"\bcar\b|سيارة|سياره", re.I), "car"),
    (re.compile(r"\bpersonal\b|شخصي", re.I), "personal"),
)
_LEAVE_TYPE_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bannual\b|سنوي|سنوية|سنويه", re.I), "annual"),
    (re.compile(r"\bsick\b|مرض|مرضية|مرضيه", re.I), "sick"),
    (re.compile(r"\bemergency\b|طارئ|طارئة|عارضة|عارضه", re.I), "emergency"),
    (re.compile(r"\bunpaid\b|بدون\s*راتب", re.I), "unpaid"),
    (re.compile(r"\bmaternity\b|وضع|أمومة", re.I), "maternity"),
)
_PERMISSION_TYPE_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bofficial\b|رسمي", re.I), "official"),
    (re.compile(r"\bmedical\b|طبي", re.I), "medical"),
    (re.compile(r"\bemergency\b|طارئ", re.I), "emergency"),
    (re.compile(r"\bpersonal\b|شخصي", re.I), "personal"),
)


def _first_alias(text: str, table: tuple[tuple[re.Pattern[str], str], ...]) -> str | None:
    for pattern, code in table:
        if pattern.search(text):
            return code
    return None


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_AMOUNT_RE = re.compile(
    r"([0-9]{2,}(?:[.,][0-9]+)?)\s*(?:sar|kwd|riyal|dinar|dinars|ريال|دينار|دنانير)?"
    r"|(?:sar|kwd|مبلغ|قرض|loan)\s*([0-9]{2,}(?:[.,][0-9]+)?)",
    re.I,
)
_MONTHS_RE = re.compile(r"\b(\d{1,2})\s*(?:month|months|شهر|أشهر|اشهر)\b", re.I)
_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(?:day|days|يوم|أيام|ايام)\b", re.I)
_HOURS_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*(?:hour|hours|ساعة|ساعات)\b", re.I)
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
_SLOT_STATUS_RE = re.compile(
    r"("
    r"\bwhat (?:type|dates?|amount|information)\b"
    r"|\bhow much\b"
    r"|\bwhat (?:did i|was)\b"
    r"|\bwhich dates?\b"
    r")",
    re.IGNORECASE,
)
_CLARIFY_TEXT = {
    "submit_my_loan": {
        "loan_type": {
            "en": "What type of loan are you interested in?",
            "ar": "أي نوع قرض تريد؟",
        },
        "principal": {
            "en": "How much do you need?",
            "ar": "كم المبلغ الذي تحتاجه؟",
        },
    },
    "submit_my_leave": {
        "leave_type": {
            "en": "What type of leave do you want to take?",
            "ar": "أي نوع إجازة تريد؟",
        },
        "start_date": {
            "en": "Which dates do you want to take leave?",
            "ar": "ما تواريخ الإجازة؟",
        },
    },
    "submit_my_attendance_permission": {
        "permission_type": {
            "en": "What type of permission do you need?",
            "ar": "أي نوع استئذان تحتاج؟",
        },
    },
}


def _latin_digits(text: str) -> str:
    return (text or "").translate(_AR_DIGITS)


def _parse_amount(text: str) -> float | None:
    match = _AMOUNT_RE.search(_latin_digits(text))
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _parse_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(_latin_digits(text))
    if not match:
        return None
    try:
        return int(float(match.group(1)))
    except ValueError:
        return None


def _parse_hours(text: str) -> float | None:
    match = _HOURS_RE.search(_latin_digits(text))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


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
        code = _first_alias(text, _LOAN_TYPE_ALIASES)
        if code:
            body["loan_type"] = code
        amount = _parse_amount(text)
        if amount is not None:
            body["principal"] = amount
            body["amount"] = amount  # C8 / StateBlock alias
        months = _parse_int(_MONTHS_RE, text)
        if months:
            body["term_months"] = months
        parsed = _parse_iso_date(text)
        if parsed:
            body["start_date"] = parsed
        return "submit_my_loan", body

    if as_leave:
        body = {}
        code = _first_alias(text, _LEAVE_TYPE_ALIASES)
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
        days = _parse_int(_DAYS_RE, text)
        if days:
            body["days"] = days
        return "submit_my_leave", body

    if as_attendance:
        body = {}
        code = _first_alias(text, _PERMISSION_TYPE_ALIASES)
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
        "- You have tools available. For READS (balances, lists, profile), call "
        "the matching tool instead of guessing.\n"
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
        "prose; only call plan_task when the user explicitly confirms converting "
        "to a task.\n"
        "- If a tool errors, report the error plainly.\n"
        "- CLARIFICATION POLICY: if the object is ambiguous, ask one clarifying "
        "question instead of guessing.\n"
        "- TENANT-ORG EXCEPTION: the platform's own organisation name is NEVER "
        "an ambiguous object — answer with live read tools immediately."
    )
