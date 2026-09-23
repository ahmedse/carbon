"""Governed slot resolution for staged host writes (Chat + Agent, one seam).

An LLM-drafted request body is not trustworthy on two counts:

* **Governed values** — the operator says "إجازة عادية" and the model omits
  ``leave_type`` (or invents a synonym). Codes are owned by
  ``mdm.ReferenceValue``, so resolution goes through
  ``mdm.reference_resolve`` and a new spelling is a data change in MDM — never
  a regex in Chat, the planner or the UI.
* **Dates** — the model has no clock, so "1 أكتوبر القادم" arrives as
  ``2023-10-01``. Forward-dated request fields are grounded against the
  platform clock, so a past date is rolled to the intended occurrence.

Two entry points:

``normalize_write_body``
    Spec-free repair applied at the staging chokepoint
    (``create_pending_execution``): every surface that stages a host write
    gets governed codes and grounded dates.
``fill_write_body``
    Adds inference from the operator's own words for the slots an endpoint
    declares (``write_slots`` in the brand api_catalog), so a request that
    already named the leave type never re-asks for it.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_IN_TEXT = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_TOMORROW = re.compile(r"غدًا|غداً|غدا|بكرة|tomorrow", re.I)
_TODAY = re.compile(r"اليوم|today", re.I)
_ONE_DAY = re.compile(r"يوم\s*واحد|one\s*day|single\s*day", re.I)
# Unit is required. An optional day unit made "لمدة 3 شهور" look like 3 days.
_DAY_UNIT = r"يوم|أيام|ايام|day|days"
_MONTH_UNIT = r"شهر|أشهر|اشهر|شهور|شهرين|month|months"
_N_DAYS = re.compile(
    rf"(?:ليوم|لمدة|مدة|for)\s*(\d+)\s*(?:{_DAY_UNIT})"
    rf"|\b(\d+)\s*(?:{_DAY_UNIT})\b",
    re.I,
)
_N_MONTHS = re.compile(
    rf"(?:لمدة|مدة|for|over)\s*(\d+)\s*(?:{_MONTH_UNIT})"
    rf"|\b(\d+)\s*(?:{_MONTH_UNIT})\b",
    re.I,
)
# Principal / amount — prefer figures next to currency or loan wording.
_AMOUNT = re.compile(
    r"(?:(?:قرض|loan|principal|مبلغ|amount|sar|kwd|ريال|د\.?\s*ك)\s*)"
    r"([0-9]{2,}(?:[.,][0-9]+)?)"
    r"|([0-9]{2,}(?:[.,][0-9]+)?)\s*(?:sar|kwd|ريال|د\.?\s*ك|ر\.?\s*س)",
    re.I,
)
_RATE = re.compile(
    r"(?:interest|rate|فائدة|نسبة)\s*(?:of\s*)?([0-9]+(?:[.,][0-9]+)?)\s*%?"
    r"|([0-9]+(?:[.,][0-9]+)?)\s*%\s*(?:interest|rate|فائدة)?",
    re.I,
)
_HOURS = re.compile(
    r"(?:لمدة|مدة|for)?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:hour|hours|ساعة|ساعات)"
    r"|(?:ساعتين|ساعه\s*واحده|ساعة\s*واحدة|one\s*hour|two\s*hours)",
    re.I,
)

# Calendar localization (platform data, not domain logic).
_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1, "يناير": 1, "كانون الثاني": 1,
    "february": 2, "feb": 2, "فبراير": 2, "شباط": 2,
    "march": 3, "mar": 3, "مارس": 3, "آذار": 3, "اذار": 3,
    "april": 4, "apr": 4, "أبريل": 4, "ابريل": 4, "نيسان": 4,
    "may": 5, "مايو": 5, "أيار": 5, "ايار": 5,
    "june": 6, "jun": 6, "يونيو": 6, "يونية": 6, "حزيران": 6,
    "july": 7, "jul": 7, "يوليو": 7, "يوليه": 7, "تموز": 7,
    "august": 8, "aug": 8, "أغسطس": 8, "اغسطس": 8, "آب": 8,
    "september": 9, "sep": 9, "sept": 9, "سبتمبر": 9, "أيلول": 9, "ايلول": 9,
    "october": 10, "oct": 10, "أكتوبر": 10, "اكتوبر": 10, "اوكتوبر": 10,
    "تشرين الأول": 10,
    "november": 11, "nov": 11, "نوفمبر": 11, "تشرين الثاني": 11,
    "december": 12, "dec": 12, "ديسمبر": 12, "كانون الأول": 12,
}

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_DATE_FIELD = re.compile(r"(^|_)date$|_date$|^date$")


def _clean(text: Any) -> str:
    return str(text or "").translate(_ARABIC_DIGITS)


def _month_day_pattern() -> re.Pattern[str]:
    names = sorted(_MONTHS, key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(
        rf"(?:(\d{{1,2}})\s*(?:of\s*)?({alt})|({alt})\s*(\d{{1,2}}))",
        re.I,
    )


_MONTH_DAY = _month_day_pattern()


def is_date_field(field: str) -> bool:
    """``start_date`` / ``end_date`` / ``date`` — a date-bearing body key."""
    return bool(_DATE_FIELD.search(str(field or "").strip().casefold()))


def _next_occurrence(month: int, day: int, today: date) -> date | None:
    for year in (today.year, today.year + 1, today.year + 2):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None


def _roll_forward(value: date, today: date) -> date:
    """Keep month/day, move to the next year that is not in the past."""
    if value >= today:
        return value
    rolled = _next_occurrence(value.month, value.day, today)
    return rolled or value


def parse_date_expression(text: Any, *, today: date) -> date | None:
    """First date the text names, grounded to today's calendar.

    Understands ISO dates, "today"/"tomorrow" (Arabic + English) and
    day/month wording such as "1 أكتوبر" or "October 1".
    """
    raw = _clean(text)
    if not raw.strip():
        return None
    iso = _ISO_IN_TEXT.search(raw)
    if iso:
        try:
            return _roll_forward(
                date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))),
                today,
            )
        except ValueError:
            pass
    if _TOMORROW.search(raw):
        return today + timedelta(days=1)
    if _TODAY.search(raw):
        return today
    match = _MONTH_DAY.search(raw)
    if match:
        day_raw = match.group(1) or match.group(4)
        month_raw = match.group(2) or match.group(3)
        month = _MONTHS.get(str(month_raw or "").strip().casefold())
        try:
            day = int(day_raw)
        except (TypeError, ValueError):
            day = 0
        if month and 1 <= day <= 31:
            return _next_occurrence(month, day, today)
    return None


def ground_future_date(raw: Any, *, today: date) -> str | None:
    """Normalize a request date to a grounded ISO date, or None if unreadable.

    A model-supplied ISO date in the past (no clock in the prompt) keeps its
    month/day and moves to the next occurrence — the operator asked for a
    coming day, not a bygone one.
    """
    text = _clean(raw).strip()
    if not text:
        return None
    iso = _ISO.match(text)
    if iso:
        try:
            value = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
        return _roll_forward(value, today).isoformat()
    parsed = parse_date_expression(text, today=today)
    return parsed.isoformat() if parsed else None


def parse_days(text: Any) -> int | None:
    """Duration in days the text states, if any."""
    raw = _clean(text)
    if not raw.strip():
        return None
    if _ONE_DAY.search(raw):
        return 1
    match = _N_DAYS.search(raw)
    if not match:
        return None
    try:
        value = int(match.group(1) or match.group(2))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_months(text: Any) -> int | None:
    """Term in months the text states, if any."""
    raw = _clean(text)
    if not raw.strip():
        return None
    match = _N_MONTHS.search(raw)
    if not match:
        return None
    try:
        value = int(match.group(1) or match.group(2))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_amount(text: Any) -> float | None:
    """Principal / money amount the text states, if any."""
    raw = _clean(text)
    if not raw.strip():
        return None
    match = _AMOUNT.search(raw)
    if not match:
        # Fallback: bare 3+ digit number when loan/قرض is present.
        if not re.search(r"قرض|\bloan\b|\bprincipal\b|\bamount\b", raw, re.I):
            return None
        bare = re.search(r"\b([0-9]{3,}(?:[.,][0-9]+)?)\b", raw)
        if not bare:
            return None
        token = bare.group(1)
    else:
        token = match.group(1) or match.group(2)
    try:
        value = float(str(token).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_rate(text: Any) -> float | None:
    """Interest rate percent the text states, if any."""
    raw = _clean(text)
    if not raw.strip():
        return None
    match = _RATE.search(raw)
    if not match:
        return None
    try:
        value = float(str(match.group(1) or match.group(2)).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def parse_hours(text: Any) -> float | None:
    """Attendance permission hours the text states, if any."""
    raw = _clean(text)
    if not raw.strip():
        return None
    if re.search(r"ساعتين|two\s*hours", raw, re.I):
        return 2.0
    if re.search(r"ساعة\s*واحدة|ساعه\s*واحده|one\s*hour", raw, re.I):
        return 1.0
    match = _HOURS.search(raw)
    if not match:
        return None
    token = match.group(1)
    if not token:
        return None
    try:
        value = float(str(token).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _governed_code(field: str, raw: Any) -> str | None:
    """Resolve a governed body value to its code, or None when unresolvable.

    A model-supplied value is still prose ("إجازة عادية" for the ``annual``
    code), so an exact code/label/alias miss falls back to spotting a governed
    spelling inside the value before the field is dropped.
    """
    from mdm.reference_resolve import find_reference_in_text, resolve_reference

    value = resolve_reference(field, raw) or find_reference_in_text(field, raw)
    return value.code if value is not None else None


def _governed_from_text(field: str, text: Any) -> str | None:
    from mdm.reference_resolve import find_reference_in_text

    if field == "leave_type":
        from people.leave_type_resolve import find_leave_type_in_text

        value = find_leave_type_in_text(text)
    else:
        value = find_reference_in_text(field, text)
    return value.code if value is not None else None


def _is_governed_field(field: str) -> bool:
    from mdm.reference_resolve import is_reference_set

    return is_reference_set(field)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _forward_dated_fields(slots: list[dict[str, Any]] | None) -> set[str]:
    """Fields the endpoint declares as forward-dated (``future: true``).

    Grounding is opt-in: a backdated hire ``join_date`` is legitimate, a leave
    ``start_date`` in 2023 is a model with no clock.
    """
    return {
        str(slot.get("field") or "").strip()
        for slot in (slots or [])
        if slot.get("future")
    }


def normalize_write_body(
    body: Any,
    *,
    slots: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Repair a staged body: governed codes always, dates as declared.

    Governed fields (body keys that name a reference set) are mapped to codes;
    unresolvable values are dropped so the host answers with its governed
    "which value?" contract instead of writing junk. Date fields are validated,
    and grounded to the coming occurrence when the endpoint declares them
    forward-dated.
    """
    if not isinstance(body, dict):
        return {}
    today = today or date.today()
    forward = _forward_dated_fields(slots)
    out = dict(body)
    for field, value in list(out.items()):
        if _blank(value) or isinstance(value, (dict, list)):
            continue
        if _is_governed_field(field):
            code = _governed_code(field, value)
            if code:
                out[field] = code
            else:
                out.pop(field, None)
            continue
        if is_date_field(field):
            grounded = (
                ground_future_date(value, today=today) if field in forward
                else _iso_or_parsed(value, today=today)
            )
            if grounded:
                out[field] = grounded
            else:
                out.pop(field, None)
    _align_date_pair(out, mirror=_declares(slots, "end_date"))
    return out


def _declares(slots: list[dict[str, Any]] | None, field: str) -> bool:
    return any(
        str(slot.get("field") or "").strip() == field for slot in (slots or [])
    )


def _iso_or_parsed(raw: Any, *, today: date) -> str | None:
    """Keep a valid ISO date as-is (past allowed); else read the wording."""
    text = _clean(raw).strip()
    iso = _ISO.match(text)
    if iso:
        try:
            return date(
                int(iso.group(1)), int(iso.group(2)), int(iso.group(3)),
            ).isoformat()
        except ValueError:
            return None
    parsed = parse_date_expression(text, today=today)
    return parsed.isoformat() if parsed else None


def _align_date_pair(body: dict[str, Any], *, mirror: bool = False) -> None:
    """``end_date`` never precedes ``start_date``.

    ``mirror`` copies ``start_date`` into a declared-but-empty ``end_date``
    (a one-day request). Spec-free repair never invents the field, since the
    endpoint may not accept it.
    """
    start = body.get("start_date")
    end = body.get("end_date")
    if not isinstance(start, str) or not _ISO.match(start):
        return
    if not isinstance(end, str) or not _ISO.match(end):
        if mirror or "end_date" in body:
            body["end_date"] = start
        return
    if end < start:
        body["end_date"] = start


def write_slots_for(api_name: str, api_catalog: Any) -> list[dict[str, Any]]:
    """Declared ``write_slots`` for a catalog endpoint (empty when undeclared)."""
    name = str(api_name or "").strip()
    if not name or not isinstance(api_catalog, (list, tuple)):
        return []
    for entry in api_catalog:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        slots = entry.get("write_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []
    return []


def write_slots_for_endpoint(
    method: str, path: str, api_catalog: Any,
) -> list[dict[str, Any]]:
    """Declared slots for a raw ``method`` + ``path`` (staging-time lookup).

    The confirmation staging seam knows the endpoint, not the catalog name.
    """
    verb = str(method or "").strip().upper()
    target = str(path or "").strip()
    if not target or not isinstance(api_catalog, (list, tuple)):
        return []
    for entry in api_catalog:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("method") or "").strip().upper() != verb:
            continue
        if str(entry.get("path") or "").strip() != target:
            continue
        slots = entry.get("write_slots")
        return [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []
    return []


def consent_slot_specs(api_name: str, api_catalog: Any) -> list[dict[str, Any]]:
    """Operator-facing slot specs for a consent card (governed options included).

    The UI renders from this — it must not carry its own copy of the leave /
    loan / permission value lists.
    """
    specs: list[dict[str, Any]] = []
    for slot in write_slots_for(api_name, api_catalog):
        field = str(slot.get("field") or "").strip()
        if not field:
            continue
        governed = bool(slot.get("governed")) or _is_governed_field(field)
        kind = str(slot.get("type") or "").strip().casefold()
        if not kind:
            kind = "governed" if governed else ("date" if is_date_field(field) else "text")
        spec: dict[str, Any] = {
            "field": field,
            "label": str(slot.get("label") or field.replace("_", " ").title()),
            "type": "governed" if governed else kind,
            "required": bool(slot.get("required", True)),
        }
        if governed:
            from mdm.reference_resolve import reference_options

            spec["options"] = reference_options(field)
        specs.append(spec)
    return specs


def fill_write_body(
    body: Any,
    *,
    slots: list[dict[str, Any]] | None,
    text: str = "",
    today: date | None = None,
) -> dict[str, Any]:
    """Normalize, then fill declared slots the operator already stated.

    ``slots`` entries: ``{field, governed: bool, type: date|days, future: bool}``.
    A slot the request text answers is filled here so the consent card never
    asks for something the operator already said.
    """
    today = today or date.today()
    out = normalize_write_body(body, slots=slots, today=today)
    end_given = isinstance(body, dict) and not _blank(body.get("end_date"))
    seed = str(text or "")
    for slot in slots or []:
        field = str(slot.get("field") or "").strip()
        if not field or not _blank(out.get(field)):
            continue
        kind = str(slot.get("type") or "").strip().casefold()
        if slot.get("governed") or _is_governed_field(field):
            code = _governed_from_text(field, seed)
            if code:
                out[field] = code
            continue
        if kind == "date" or is_date_field(field):
            parsed = parse_date_expression(seed, today=today)
            if parsed:
                out[field] = parsed.isoformat()
            continue
        if kind == "days":
            # "لمدة 3 شهور" is a span, not 3 days. Calendar months from the
            # stated start; _stretch_end_to_days then keeps the end in step.
            months = parse_months(seed)
            if months and parse_days(seed) is None:
                start_raw = out.get("start_date")
                if isinstance(start_raw, str) and _ISO.match(start_raw):
                    start = date.fromisoformat(start_raw)
                    end = _add_months(start, months) - timedelta(days=1)
                    if end < start:
                        end = start
                    out["end_date"] = end.isoformat()
                    out[field] = (end - start).days + 1
                continue
            days = parse_days(seed)
            if days is None:
                days = _days_from_span(out)
            if days:
                out[field] = days
            continue
        if kind in ("months", "term_months") or field in ("term_months", "months"):
            months = parse_months(seed)
            if months:
                out[field] = months
            continue
        if kind in ("amount", "number", "principal") or field in (
            "principal", "amount",
        ):
            amount = parse_amount(seed)
            if amount is not None:
                out[field] = amount
            continue
        if kind == "hours" or field == "hours":
            hours = parse_hours(seed)
            if hours is not None:
                out[field] = hours
            continue
        if kind in ("rate", "interest_rate") or field in ("interest_rate", "rate"):
            rate = parse_rate(seed)
            if rate is not None:
                out[field] = rate
            continue
    _align_date_pair(out, mirror=_declares(slots, "end_date"))
    if not end_given:
        _stretch_end_to_days(out)
    return out


def _add_months(start: date, months: int) -> date:
    """Same day ``months`` ahead, clamped to the target month's last day."""
    import calendar

    index = start.month - 1 + months
    year = start.year + index // 12
    month = index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _stretch_end_to_days(body: dict[str, Any]) -> None:
    """A stated duration wins over a mirrored ``end_date``.

    "لمدة 3 أيام" from one start day must not stage a one-day span the host
    then rejects for a days/dates mismatch.
    """
    start = body.get("start_date")
    if not (isinstance(start, str) and _ISO.match(start)):
        return
    try:
        days = int(body.get("days"))
    except (TypeError, ValueError):
        return
    if days <= 1:
        return
    try:
        end = date.fromisoformat(start) + timedelta(days=days - 1)
    except ValueError:
        return
    body["end_date"] = end.isoformat()


def _days_from_span(body: dict[str, Any]) -> int | None:
    start = body.get("start_date")
    end = body.get("end_date") or start
    if not (isinstance(start, str) and _ISO.match(start)):
        return None
    if not (isinstance(end, str) and _ISO.match(end)):
        return None
    try:
        span = date.fromisoformat(end) - date.fromisoformat(start)
    except ValueError:
        return None
    return span.days + 1 if span.days >= 0 else None
