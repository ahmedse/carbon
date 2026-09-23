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
    required = _MIN_SLOTS.get(api)
    if required is None:
        # Unknown write API — hand off as soon as any slot is bound.
        return True
    if not all(body.get(k) not in (None, "", [], {}) for k in required):
        return False
    if api == "submit_my_leave":
        return any(body.get(k) not in (None, "", [], {}) for k in _LEAVE_DATE_SLOTS)
    return True


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


def is_ess_write_utterance(text: str) -> bool:
    """True when the utterance is a personal loan / leave / attendance write.

    Used by the Chat handoff path and the ``_should_force_action`` fallback so
    ESS writes are not gated only on ``_is_mutation_request`` (which is leave-
    and DQ-shaped and misses "apply for a loan").
    """
    brief = (text or "").strip()
    if not brief:
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


def _parse_iso_date(text: str) -> str | None:
    match = _ISO_DATE_RE.search(_latin_digits(text))
    return match.group(1) if match else None


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
        if parsed:
            body["start_date"] = parsed
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
