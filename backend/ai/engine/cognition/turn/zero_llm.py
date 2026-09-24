"""Deterministic 0-LLM Chat surfaces (C8) — thanks, clock, notification FAQ.

Navigation and how/where UI grounding stay in ``navigation.py``.
Write handoff stays in ``handoff_agent.py``. Plan status stays in
``plan_status.py``. This module is only the leftover clock/ack/FAQ
short-circuits that must not spend intent+draft.
"""
from __future__ import annotations

import calendar
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from ai.engine.cognition.turn.navigation import detect_lang, normalize_text
from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_word
from ai.engine.cognition.turn.zero_llm_i18n import (
    CLOCK_AR,
    DAY_SPAN_AR,
    WHEN_START_AR,
    COWORKER_FOLLOWUP_AR,
    EMPTY_PAYSLIP_REPLY_AR,
    MONTH_ASK_AR,
    NOTIFICATION_AR,
    NOTIFICATION_TEXT,
    PAYROLL_FOLLOWUP_AR,
    PAYROLL_POLICY_AR,
    PAYROLL_SCHEDULE_AR,
    PAYROLL_SCHEDULE_TEXT,
    PAYSLIP_DOWNLOAD_AR,
    PAYSLIP_DOWNLOAD_TEXT,
    PROFILE_ASK_AR,
    SHOW_OPEN_AR,
    THANKS_AR,
    THANKS_TEXT,
    THANKS_WRITE_AR,
    any_needle,
)

# EN-only patterns — Arabic literals live in ``zero_llm_i18n`` (ADR-0049 L7).
_THANKS_STARTS = ("thanks", "thank you", "thx", "ty")
_THANKS_WRITE_WORDS = ("submit", "apply", "request", "approve", "send")
_CLOCK_RE = re.compile(
    r"("
    r"\b(?:what(?:'s| is)|tell\s+me)\b.{0,24}"
    r"\b(?:today'?s\s+date|the\s+date|date\s+today|day\s+is\s+it|month)\b"
    r"|\bwhat\s+month\b"
    r"|\bwhat\s+year\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_SHOW_OPEN_WORDS = ("show", "open", "where")
_SHOW_OPEN_PHRASES = ("go to",)
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_DATE_IN_TEXT_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_DEIXIS_RE = re.compile(
    r"\bis that\s+(before|after|earlier than|later than)\b",
    re.IGNORECASE,
)
_PAYROLL_SCHEDULE_PHRASES = (
    "when will payroll be processed",
    "when will next month's payroll be processed",
    "when will next months payroll be processed",
    "when is payroll run",
    "when is the payroll run",
    "when does payroll run",
    "when does the payroll run",
    "when does payroll get processed",
    "when is payroll get processed",
)
_PAYSLIP_DOWNLOAD_PHRASES = (
    "can i download my payslip", "can i download my payslips",
    "can i download payslip", "can i download payslips",
    "download my payslip", "download my payslips", "download payslip",
    "download payslips",
)
_PAYROLL_FOLLOWUP_WORDS = ("deduction", "deductions", "gosi")
_PAYROLL_FOLLOWUP_PHRASES = (
    "take-home", "take home", "take_home", "net pay", "loan amount",
    "total deductions", "after gosi",
)
_COWORKER_FOLLOWUP_WORDS = (
    "her", "his", "she", "he", "their", "position", "department", "role",
    "title", "manager", "report", "reports",
)
_COWORKER_FOLLOWUP_PHRASES = ("is she a manager",)
_EASTERN_DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "0123456789",
)
_PROFILE_ASK_PHRASES = (
    "employee number", "employee no", "what number",
)
_PROFILE_ASK_WORDS = ("department", "manager")
_OTHER_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,})\b")
_OTHER_NAME_STOP = frozenset({
    "what", "how", "who", "which", "her", "his", "she", "the", "now",
    "tell", "about", "back", "department", "position", "role", "title",
})


def last_directory_deny(last_results: list[dict] | None) -> dict | None:
    """Latest resolve_entity 403 (people:view). Invents no coworker record."""
    for row in reversed(last_results or []):
        if not isinstance(row, dict):
            continue
        if row.get("unauthorized"):
            return row
        digest = str(row.get("digest") or "").lower()
        if "unauthorized=true" in digest or "people:view" in digest:
            return row
        if str(row.get("tool") or "") == "resolve_entity" and "not authorized" in digest:
            return row
    return None


def _mentions_other_person(text: str, query: str) -> bool:
    q = (query or "").strip().casefold()
    if not q:
        return False
    for name in _OTHER_NAME_RE.findall(text or ""):
        if name.casefold() in _OTHER_NAME_STOP:
            continue
        if name.casefold() not in q and q not in name.casefold():
            return True
    return False


def should_replay_directory_deny(text: str, deny: dict | None) -> bool:
    """Replay the 403 on same-person follow-ups. New names look up again."""
    if not deny:
        return False
    from ai.engine.agent.tools import (
        extract_named_coworker_query,
        first_person_profile_ask,
    )

    if first_person_profile_ask(text):
        return False
    query = str(deny.get("query") or "").strip()
    if _mentions_other_person(text, query):
        return False
    named = extract_named_coworker_query(text)
    if named:
        if not query:
            return True
        return named.casefold() == query.casefold() or named.casefold() in query.casefold()
    raw = text or ""
    return bool(
        has_any_word(raw, _COWORKER_FOLLOWUP_WORDS)
        or contains_any_phrase(raw, _COWORKER_FOLLOWUP_PHRASES)
        or any_needle(raw, COWORKER_FOLLOWUP_AR)
    )


def render_directory_deny(deny: dict, text: str = "") -> str:
    msg = str(deny.get("message") or "").strip()
    if msg:
        return msg
    grounded = render_resolve_grounded(text, {
        "unauthorized": True,
        "message": deny.get("message"),
    })
    return grounded or "Not authorized to look up other employees (people:view required)."


_PAYROLL_POLICY_WORDS = ("appeal", "objection", "object", "certificate")
_USER_AMOUNT_RE = re.compile(
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+",
)


def _western_digits(text: str) -> str:
    return (text or "").translate(_EASTERN_DIGITS)


def _is_payroll_followup(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, _PAYROLL_FOLLOWUP_WORDS)
        or contains_any_phrase(raw, _PAYROLL_FOLLOWUP_PHRASES)
        or any_needle(raw, PAYROLL_FOLLOWUP_AR)
    )


def _is_payroll_policy(text: str) -> bool:
    raw = text or ""
    return bool(
        has_any_word(raw, _PAYROLL_POLICY_WORDS)
        or any_needle(raw, PAYROLL_POLICY_AR)
    )


def _is_profile_ask(text: str) -> bool:
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _PROFILE_ASK_PHRASES)
        or has_any_word(raw, _PROFILE_ASK_WORDS)
        or any_needle(raw, PROFILE_ASK_AR)
    )


def is_thanks(text: str) -> bool:
    """True for a bare thank-you — not 'thanks for submitting'."""
    raw = (text or "").strip()
    if not raw:
        return False
    cf = raw.casefold().lstrip()
    if not (
        any(cf.startswith(prefix) for prefix in _THANKS_STARTS)
        or any_needle(raw, THANKS_AR)
    ):
        return False
    return not (
        has_any_word(raw, _THANKS_WRITE_WORDS)
        or any_needle(raw, THANKS_WRITE_AR)
    )


def is_day_span_ask(text: str) -> bool:
    """Days between today and a date already in the transcript.

    Not a balance read, and not 'how many days until end of month'.
    """
    raw = text or ""
    if contains_any_phrase(raw, ("end of month", "end of the month")):
        return False
    if any_needle(raw, DAY_SPAN_AR):
        return True
    return bool(
        has_any_word(raw, ("day", "days"))
        and contains_any_phrase(raw, ("from now", "from today", "until"))
    )


def is_when_start_ask(text: str) -> bool:
    """'When does my leave start' is a date, not a balance GET."""
    raw = text or ""
    if any_needle(raw, WHEN_START_AR):
        return True
    return bool(
        has_word(raw, "when")
        and has_any_word(raw, ("start", "starts", "begin", "begins"))
    )


def is_calendar_not_balance(text: str) -> bool:
    return is_day_span_ask(text) or is_when_start_ask(text)


def is_clock_ask(text: str) -> bool:
    """True for today's date / current month — not leave-start or payroll when."""
    raw = (text or "").strip()
    return bool(raw and (_CLOCK_RE.search(raw) or any_needle(raw, CLOCK_AR)))


def is_payroll_schedule_ask(text: str) -> bool:
    """When is payroll processed — not leave start, not net pay."""
    raw = (text or "").strip()
    return bool(
        raw and (
            contains_any_phrase(raw, _PAYROLL_SCHEDULE_PHRASES)
            or any_needle(raw, PAYROLL_SCHEDULE_AR)
        )
    )


_EMPTY_PAYSLIP_REPLY_PHRASES = (
    "no payslips", "no committed payslips", "found no payslips",
    "no payslips are on file", "no payslips were on file",
    "no payslips are found", "no payslips were found",
)


def _empty_payslip_digest(text: str) -> bool:
    blob = (text or "").lower()
    return (
        "count=0" in blob
        or 'count":0' in blob
        or "count = 0" in blob
        or "results=[]" in blob
        or 'results":[]' in blob
        or "results = []" in blob
        or "no payslips" in blob
        or "0 rows" in blob
        or "0 row" in blob
    )


def _empty_payslip_reply(text: str) -> bool:
    return contains_any_phrase(text or "", _EMPTY_PAYSLIP_REPLY_PHRASES)


def _history_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            else:
                parts.append(str(part))
        text = " ".join(parts)
    else:
        text = ""
    extra = msg.get("text")
    if extra:
        return f"{text} {extra}"
    return text


def _unwrap_tool_json(raw: Any) -> Any:
    data = raw
    for _ in range(3):
        if isinstance(data, str):
            text = data.strip()
            if not text:
                return data
            try:
                import json
                data = json.loads(text)
            except (TypeError, ValueError):
                return data
            continue
        if isinstance(data, dict) and "data" in data and (
            "status_code" in data or "results" in (data.get("data") or {})
        ):
            data = data.get("data")
            continue
        break
    return data


def last_payslip_was_empty(
    last_results: list[dict] | None,
    history: list[dict] | None = None,
) -> bool:
    """True when a prior turn already established empty ESS payslips."""
    for row in reversed(last_results or []):
        if not isinstance(row, dict):
            continue
        api = str(row.get("api") or "")
        digest = str(row.get("digest") or "")
        if "list_my_payslips" not in api and "list_my_payslips" not in digest:
            continue
        if _empty_payslip_digest(digest):
            return True
        if re.search(r"count=[1-9]", digest) or payslip_lines_from_state([row]):
            return False
        # A payslip digest that is not clearly empty is not evidence of rows
        # either — keep scanning older rows and history. Do not return False.
    for msg in reversed(history or []):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").lower()
        if role not in ("assistant", "ai", "model"):
            continue
        hist = _history_text(msg)
        if _empty_payslip_reply(hist) or any_needle(
            hist, EMPTY_PAYSLIP_REPLY_AR
        ):
            return True
    return False


def is_empty_payslip_tool_result(completed_tools: list | None) -> bool:
    """True when this turn's payslip tool returned no committed rows."""
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        args = item.get("tool_args") if isinstance(item.get("tool_args"), dict) else {}
        api = str(
            args.get("api_name") or args.get("name") or args.get("api") or ""
        )
        blob = f"{args} {api} {item.get('tool_name') or ''} {item.get('result') or ''}"
        looks_payslip = (
            "payslip" in blob.lower()
            or "قسيمة" in blob
            or "list_my_payslips" in api
        )
        if not looks_payslip:
            continue
        data = _unwrap_tool_json(item.get("result"))
        if isinstance(data, dict):
            results = data.get("results")
            try:
                count = int(data.get("count")) if data.get("count") is not None else None
            except (TypeError, ValueError):
                count = None
            if count == 0 or results == []:
                return True
        if isinstance(data, list) and len(data) == 0:
            return True
    return False


_PAYSLIP_LINE_CODES = ("gross", "gosi", "loan_installment", "net")
_DIGEST_AMOUNT_RE = re.compile(
    r"\b(gross|gosi|loan_installment|net)\s*=\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)


def _fmt_amount(value: Any) -> str | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if number == number.to_integral_value():
        return str(int(number))
    return format(number, "f").rstrip("0").rstrip(".")


def _line_type_code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code") or value.get("name") or "").strip().lower()
    return str(value or "").strip().lower()


def payslip_lines_from_payload(data: Any) -> dict[str, str]:
    """Map line_type → amount from a host payslip payload."""
    records: list[dict] = []
    if isinstance(data, list):
        records = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        raw = data.get("results")
        if isinstance(raw, list):
            records = [row for row in raw if isinstance(row, dict)]
    out: dict[str, str] = {}
    for row in records:
        code = _line_type_code(row.get("line_type"))
        if code not in _PAYSLIP_LINE_CODES:
            continue
        amount = _fmt_amount(row.get("amount"))
        if amount is not None:
            out[code] = amount
    return out


def payslip_lines_from_tools(completed_tools: list | None) -> dict[str, str]:
    """Read committed payslip amounts from this turn's tool results."""
    out: dict[str, str] = {}
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        args = item.get("tool_args") if isinstance(item.get("tool_args"), dict) else {}
        api = str(args.get("api_name") or args.get("name") or args.get("api") or "")
        blob = f"{args} {api} {item.get('tool_name') or ''} {item.get('result') or ''}"
        if (
            "payslip" not in blob.lower()
            and "قسيمة" not in blob
            and "list_my_payslips" not in api
        ):
            continue
        out.update(payslip_lines_from_payload(_unwrap_tool_json(item.get("result"))))
    return out


def payslip_lines_from_state(
    last_results: list[dict] | None,
    completed_tools: list | None = None,
) -> dict[str, str]:
    """Prefer this turn's tools; else parse last_results digests."""
    from_tools = payslip_lines_from_tools(completed_tools)
    if from_tools:
        return from_tools
    out: dict[str, str] = {}
    for row in reversed(last_results or []):
        if not isinstance(row, dict):
            continue
        blob = f"{row.get('api') or ''} {row.get('digest') or ''}"
        looks_payslip = (
            "list_my_payslips" in blob
            or "payslip" in blob.lower()
            or bool(_DIGEST_AMOUNT_RE.search(str(row.get("digest") or "")))
        )
        if not looks_payslip:
            continue
        for match in _DIGEST_AMOUNT_RE.finditer(str(row.get("digest") or "")):
            out[match.group(1).lower()] = _fmt_amount(match.group(2)) or match.group(2)
        if out:
            break
    return {key: value for key, value in out.items() if value}


def render_payslip_grounded(text: str, lines: dict[str, str]) -> str | None:
    """Answer a payroll follow-up from committed line amounts. Invents none."""
    if not lines:
        return None
    raw = (text or "").strip()
    if _is_payroll_policy(raw):
        return None
    net = lines.get("net")
    gosi = lines.get("gosi")
    loan = lines.get("loan_installment")
    gross = lines.get("gross")
    after_gosi = None
    total = None
    try:
        if gross and gosi:
            after_gosi = _fmt_amount(Decimal(gross) - Decimal(gosi))
        if gosi and loan:
            total = _fmt_amount(Decimal(gosi) + Decimal(loan))
    except (InvalidOperation, TypeError, ValueError):
        after_gosi = after_gosi
        total = total
    lower = raw.lower()
    lang = "ar" if detect_lang(raw) == "ar" else "en"
    if re.search(r"deductions? were|what deductions|applied|خصم|استقطاع", lower):
        parts = []
        if gosi:
            parts.append(f"GOSI {gosi}")
        if loan:
            parts.append(
                f"قسط القرض {loan}" if lang == "ar" else f"loan installment {loan}"
            )
        if parts:
            if lang == "ar":
                return "الاستقطاعات المعتمدة: " + " و".join(parts) + "."
            return "Committed deductions: " + " and ".join(parts) + "."
        return None
    if re.search(r"after gosi|take[\s_-]*home|بعد.{0,12}gosi|صافي.{0,8}بعد", lower):
        if after_gosi:
            if lang == "ar":
                return (
                    f"بعد خصم GOSI البالغ {gosi}، المتبقي قبل قسط القرض هو {after_gosi}."
                )
            return (
                f"After the GOSI deduction of {gosi}, take-home before the "
                f"loan installment is {after_gosi}."
            )
        if net:
            return (
                f"صافي الراتب المعتمد هو {net}."
                if lang == "ar"
                else f"Committed take-home (net) is {net}."
            )
        return None
    if re.search(r"net\s*pay|last month|صافي|راتبي|الراتب", lower) and net:
        if lang == "ar":
            if gross and re.search(r"شهري|إجمالي|اجمالي", raw):
                return f"الراتب الإجمالي المعتمد هو {gross}. الصافي {net}."
            return f"صافي الراتب المعتمد هو {net}."
        return f"Last month's committed net pay is {net}."
    if re.search(r"loan amount|قسط.{0,8}قرض", lower) and loan:
        return (
            f"قسط القرض المعتمد هو {loan}."
            if lang == "ar"
            else f"The committed loan installment is {loan}."
        )
    if re.search(r"total deductions|إجمالي.{0,8}خصم|اجمالي.{0,8}خصم", lower) and total:
        stated = [
            m.group(0)
            for m in _USER_AMOUNT_RE.finditer(_western_digits(raw))
        ]
        base = (
            f"إجمالي الاستقطاعات المعتمدة {total} (GOSI {gosi} + قرض {loan})."
            if lang == "ar"
            else f"Committed total deductions are {total} (GOSI {gosi} + loan {loan})."
        )
        if stated and _fmt_amount(stated[-1].replace(",", "")) == total:
            return f"Yes. {base}" if lang != "ar" else f"نعم. {base}"
        if stated:
            return f"{base} You mentioned {stated[-1]} — that does not match."
        return base
    if re.search(r"gosi", lower) and gosi:
        return (
            f"بند GOSI المعتمد هو {gosi}. لن أخترع نسبة نظامية أبعد من هذا البند."
            if lang == "ar"
            else (
                f"The committed GOSI line is {gosi}. "
                "I will not invent a statutory rate beyond that line."
            )
        )
    if net and _is_payroll_followup(raw):
        return (
            f"صافي الراتب المعتمد هو {net}."
            if lang == "ar"
            else f"Committed net pay is {net}."
        )
    return None


_PROFILE_DIGEST_RE = re.compile(
    r"\b(employee_no|department|manager|job_title|full_name)\s*=\s*([^,]+)",
    re.I,
)
def _nested_label(value: Any) -> str | None:
    if isinstance(value, dict):
        text = value.get("name") or value.get("full_name") or value.get("label")
        return str(text).strip() if text else None
    if isinstance(value, str) and value.strip():
        return value.split(" — ", 1)[-1].strip()
    return None


def profile_from_payload(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    emp = data.get("employee_no")
    if emp not in (None, ""):
        out["employee_no"] = str(emp)
    dept = _nested_label(data.get("org_unit")) or data.get("department")
    if dept:
        out["department"] = str(dept)
    manager = _nested_label(data.get("manager")) or data.get("manager_label")
    if manager:
        out["manager"] = str(manager)
    if data.get("job_title"):
        out["job_title"] = str(data["job_title"])
    if data.get("full_name"):
        out["full_name"] = str(data["full_name"])
    return out


def profile_from_tools(completed_tools: list | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        args = item.get("tool_args") if isinstance(item.get("tool_args"), dict) else {}
        api = str(args.get("api_name") or args.get("name") or args.get("api") or "")
        blob = f"{args} {api} {item.get('tool_name') or ''}"
        if "get_my_profile" not in blob and "profile" not in blob.lower():
            data = _unwrap_tool_json(item.get("result"))
            parsed = profile_from_payload(data)
            if "employee_no" not in parsed:
                continue
            out.update(parsed)
            continue
        out.update(profile_from_payload(_unwrap_tool_json(item.get("result"))))
    return out


def profile_from_state(
    last_results: list[dict] | None,
    completed_tools: list | None = None,
) -> dict[str, str]:
    from_tools = profile_from_tools(completed_tools)
    if from_tools:
        return from_tools
    out: dict[str, str] = {}
    for row in reversed(last_results or []):
        if not isinstance(row, dict):
            continue
        digest = str(row.get("digest") or "")
        if "employee_no=" not in digest and "get_my_profile" not in digest:
            continue
        for match in _PROFILE_DIGEST_RE.finditer(digest):
            out[match.group(1).lower()] = match.group(2).strip()
        if out:
            break
    return out


def render_resolve_grounded(text: str, payload: Any) -> str | None:
    """Restate a resolve_entity payload. Invents no job title or department."""
    data = payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    if data.get("error") and not data.get("unauthorized"):
        return None
    if data.get("unauthorized"):
        return str(
            data.get("message")
            or "Not authorized to look up other employees."
        ).strip()
    if data.get("action") == "disambiguate" or (
        not data.get("found") and data.get("candidates")
    ):
        names = []
        for row in data.get("candidates") or []:
            if not isinstance(row, dict):
                continue
            label = (
                row.get("full_name")
                or row.get("name")
                or row.get("employee_no")
            )
            if label:
                names.append(str(label))
        if names:
            return (
                f"Multiple records match. Which did you mean: "
                + "; ".join(names[:5])
                + "?"
            )
        return str(data.get("message") or "").strip() or None
    if data.get("found") and isinstance(data.get("record"), dict):
        rec = data["record"]
        name = rec.get("full_name") or rec.get("name")
        emp = rec.get("employee_no")
        dept = _nested_label(rec.get("org_unit")) or rec.get("department")
        title = rec.get("job_title") or rec.get("position")
        if isinstance(title, dict):
            title = title.get("name") or title.get("label")
        bits = []
        if name:
            bits.append(str(name))
        if emp:
            bits.append(f"employee {emp}")
        if title:
            bits.append(str(title))
        if dept:
            bits.append(str(dept))
        if bits:
            return ", ".join(bits) + "."
    if data.get("found") is False:
        return str(data.get("message") or "No matching employee for that query.").strip()
    return None


def render_profile_grounded(text: str, profile: dict[str, str]) -> str | None:
    """Answer a profile ask from the host record. Invents no department."""
    if not profile:
        return None
    raw = (text or "").strip()
    if not _is_profile_ask(raw):
        return None
    lower = raw.lower()
    emp = profile.get("employee_no")
    dept = profile.get("department")
    manager = profile.get("manager")
    if re.search(r"employee number|employee no|what number|رقم الموظف", lower) and emp:
        return f"Your employee number is {emp}."
    if re.search(r"department|قسم", lower) and dept:
        if re.search(r"did i mention|i mention", lower):
            return (
                f"You did not mention a department. "
                f"Your record shows {dept}."
            )
        return f"You are in the {dept} department."
    if re.search(r"manager|مدير", lower) and manager:
        return f"Your manager is {manager}."
    return None


def render_empty_payslip_answer(text: str) -> str:
    """Honest empty-payslip copy. Echoes figures the user typed; invents none."""
    lang = "ar" if detect_lang(text) == "ar" else "en"
    stated = [
        m.group(0)
        for m in _USER_AMOUNT_RE.finditer(_western_digits(text or ""))
    ]
    if lang == "ar":
        base = (
            "لم أجد قسائم معتمدة، لذلك لا يوجد صافي راتب أو استقطاعات "
            "أو قسط قرض من قسيمة."
        )
        if stated:
            return f"{base} ذكرت {stated[-1]} — لا أستطيع تأكيد هذا الرقم."
        return base
    base = (
        "No committed payslips were found, so I do not have net pay, "
        "deductions, GOSI, or a loan installment from a payslip."
    )
    if stated:
        return f"{base} You mentioned {stated[-1]} — I cannot confirm that figure."
    return base


def is_payslip_download_ask(text: str) -> bool:
    raw = (text or "").strip()
    return bool(
        raw and (
            contains_any_phrase(raw, _PAYSLIP_DOWNLOAD_PHRASES)
            or any_needle(raw, PAYSLIP_DOWNLOAD_AR)
        )
    )


def is_notification_faq(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or not (
        has_word(raw, "notification")
        or has_word(raw, "notifications")
        or any_needle(raw, NOTIFICATION_AR)
    ):
        return False
    return bool(
        has_any_word(raw, _SHOW_OPEN_WORDS)
        or contains_any_phrase(raw, _SHOW_OPEN_PHRASES)
        or any_needle(raw, SHOW_OPEN_AR)
        or normalize_text(raw) in {"notifications", "notification"}
    )


def render_thanks(text: str, facts: list[dict[str, str]] | None = None) -> str:
    lang = "ar" if detect_lang(text) == "ar" else "en"
    base = THANKS_TEXT[lang]
    if not facts:
        return base
    fact = facts[-1]
    if lang == "ar":
        return f"{base} سأتذكر {fact['key']} {fact['value']}."
    return (
        f"You're welcome. I'll keep remembering your {fact['key']} "
        f"{fact['value']}."
    )


def render_clock(text: str, today: date | None = None) -> str:
    day = today or date.today()
    lang = detect_lang(text)
    month = day.strftime("%B")
    if (
        has_word(text or "", "month")
        or any_needle(text or "", MONTH_ASK_AR)
    ) and "date" not in (text or "").lower():
        if lang == "ar":
            return f"نحن في {month} {day.year}."
        return f"We are in {month} {day.year}."
    if lang == "ar":
        return f"اليوم {day.day} {month} {day.year}."
    return f"Today is {month} {day.day}, {day.year}."


def render_notification_faq(text: str) -> str:
    return NOTIFICATION_TEXT["ar" if detect_lang(text) == "ar" else "en"]


def last_dates_in_history(
    history: list[dict] | None,
    today: date | None = None,
) -> list[date]:
    """Dates mentioned in recent assistant turns (most recent last)."""
    day = today or date.today()
    found: list[date] = []
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        for match in _DATE_IN_TEXT_RE.finditer(str(msg.get("content") or "")):
            month = _MONTHS.get(match.group(1).lower())
            if not month:
                continue
            year = int(match.group(3) or day.year)
            try:
                found.append(date(year, month, int(match.group(2))))
            except ValueError:
                continue
    return found


def is_date_deixis(text: str) -> bool:
    raw = (text or "").strip()
    return bool(
        raw
        and _DEIXIS_RE.search(raw)
        and contains_any_phrase(raw, ("end of month", "end of the month"))
    )


def render_date_deixis(
    text: str,
    history: list[dict] | None = None,
    today: date | None = None,
) -> str | None:
    if not is_date_deixis(text):
        return None
    day = today or date.today()
    dates = last_dates_in_history(history, day)
    if not dates:
        return None
    last = dates[-1]
    end = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
    match = _DEIXIS_RE.search(text or "")
    relation = (match.group(1) if match else "before").lower()
    is_before = last <= end
    wants_before = relation.startswith("before") or relation.startswith("earlier")
    yes = is_before if wants_before else not is_before
    month = last.strftime("%B")
    clause = (
        f"{month} {last.day} is before the end of {end.strftime('%B')}"
        if is_before
        else f"{month} {last.day} is after the end of {end.strftime('%B')}"
    )
    return f"{'Yes' if yes else 'No'}, {clause}."


def render_day_span(
    text: str,
    history: list[dict] | None = None,
    today: date | None = None,
) -> str | None:
    """Day count from the latest date already stated. Invents no date."""
    if not is_day_span_ask(text):
        return None
    day = today or date.today()
    dates = last_dates_in_history(history, day)
    if not dates:
        return None
    target = dates[-1]
    delta = (target - day).days
    span = f"{day.strftime('%B')} {day.day} to {target.strftime('%B')} {target.day}"
    if detect_lang(text) == "ar":
        if delta > 0:
            return f"ذلك بعد {delta} يوم ({span})."
        if delta == 0:
            return f"ذلك اليوم ({span})."
        return f"ذلك قبل {abs(delta)} يوم ({span})."
    if delta > 0:
        unit = "day" if delta == 1 else "days"
        return f"That is {delta} {unit} from today ({span})."
    if delta == 0:
        return f"That is today ({span})."
    unit = "day" if delta == -1 else "days"
    return f"That was {abs(delta)} {unit} ago ({span})."


def try_zero_llm_answer(
    text: str,
    *,
    today: date | None = None,
    facts: list[dict[str, str]] | None = None,
    history: list[dict] | None = None,
    newly_stored: bool = False,
    last_results: list[dict] | None = None,
    open_question: dict | None = None,
) -> dict[str, Any] | None:
    """Return ``{decision, text}`` when the utterance is a 0-LLM surface."""
    from ai.engine.cognition.turn.memory_recall import (
        is_memory_use,
        render_fact_ack,
        render_recall,
    )
    from ai.engine.cognition.turn.report_clarify import try_report_clarify

    raw = (text or "").strip()
    if not raw:
        return None
    # Broad "full salary report" → clarify aspect/audience before any tools.
    report_hit = try_report_clarify(
        raw,
        history=history,
        last_results=last_results,
        open_question=open_question,
    )
    if report_hit is not None:
        return report_hit
    known = list(facts or [])
    if is_thanks(raw):
        return {
            "decision": "answer",
            "text": render_thanks(raw, known),
            "gate": "thanks",
        }
    if is_clock_ask(raw):
        return {"decision": "answer", "text": render_clock(raw, today), "gate": "clock"}
    if is_notification_faq(raw):
        return {
            "decision": "answer",
            "text": render_notification_faq(raw),
            "gate": "notification_faq",
        }
    if is_payroll_schedule_ask(raw):
        lang = "ar" if detect_lang(raw) == "ar" else "en"
        return {
            "decision": "answer",
            "text": PAYROLL_SCHEDULE_TEXT[lang],
            "gate": "payroll_schedule",
        }
    if is_payslip_download_ask(raw):
        lang = "ar" if detect_lang(raw) == "ar" else "en"
        return {
            "decision": "answer",
            "text": PAYSLIP_DOWNLOAD_TEXT[lang],
            "gate": "payslip_download",
        }
    deny = last_directory_deny(last_results)
    if deny and should_replay_directory_deny(raw, deny):
        return {
            "decision": "answer",
            "text": render_directory_deny(deny, raw),
            "gate": "directory_deny",
        }
    profile = profile_from_state(last_results)
    if profile and _is_profile_ask(raw):
        grounded = render_profile_grounded(raw, profile)
        if grounded:
            return {
                "decision": "answer",
                "text": grounded,
                "gate": "profile_recall",
            }
    lines = payslip_lines_from_state(last_results)
    if (
        lines
        and _is_payroll_followup(raw)
        and not _is_payroll_policy(raw)
    ):
        grounded = render_payslip_grounded(raw, lines)
        if grounded:
            return {
                "decision": "answer",
                "text": grounded,
                "gate": "payslip_recall",
            }
    if last_payslip_was_empty(last_results, history) and _is_payroll_followup(raw):
        return {
            "decision": "answer",
            "text": render_empty_payslip_answer(raw),
            "gate": "empty_payslip_recall",
        }
    deixis = render_date_deixis(raw, history, today)
    if deixis:
        return {"decision": "answer", "text": deixis, "gate": "date_deixis"}
    span = render_day_span(raw, history, today)
    if span:
        return {"decision": "answer", "text": span, "gate": "day_span"}
    if known and is_memory_use(raw, known):
        return {"decision": "answer", "text": render_recall(raw, known), "gate": "memory_recall"}
    if newly_stored and known:
        return {"decision": "answer", "text": render_fact_ack(raw, known), "gate": "memory_store"}
    return None
