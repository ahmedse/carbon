"""Numeric grounding for tool answers (ADR-0049 P6).

A number in the reply must appear in the tool payload. Counts of result
rows are allowed. This does not call a model.

The payload is raw host data; the reply is prose. The same figure can be
written two ways — ``16800.000`` vs ``16,800``, western vs Arabic-Indic
digits, a fraction vs its percent, a value rounded to fewer decimals.
Grounding compares the *value*, not the spelling, so a reformatted figure
still grounds while a figure the payload never carried is still rejected.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

#: ASCII form of the Arabic-Indic and Extended Arabic-Indic digit sets.
_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩" "۰۱۲۳۴۵۶۷۸۹",
    "0123456789" "0123456789",
)

#: Characters that group thousands but carry no value of their own.
_GROUPING_CHARS = ("\u066c", "\u00a0", "\u202f", "\u2009", "\u2007", "\u2060", " ")

#: Percent signs (western, Arabic, fullwidth) that scale a fraction to a percent.
_PERCENT_SIGNS = ("%", "\u066a", "\uff05")

# A plain literal: digits with at most one dot. Used to read raw JSON.
_PLAIN_NUMBER = r"(?<![\w.])(\d+(?:\.\d+)?)(?!\w|\.\d)"
# A written literal: digits with grouping/decimal separators (western and Arabic).
_TEXT_NUMBER = r"(?<![\w.])(\d+(?:[.,\u066b\u066c]\d+)*)(?!\w|\.\d)"


def _split_datetime_t(blob: str) -> str:
    """``2026-09-25T18:48`` → ``2026-09-25 18:48``.

    ISO-8601 glues the day and the hour to ``T``, so a word-boundary scan
    misses both, and a summary that restates the date or time fails as
    ungrounded.
    """
    chars = list(blob)
    for i in range(1, len(chars) - 1):
        if chars[i] == "T" and chars[i - 1].isdigit() and chars[i + 1].isdigit():
            chars[i] = " "
    return "".join(chars)


def _as_payload(payload: Any) -> Any:
    """Tool rows are often a JSON string of the same host wrap."""
    if not isinstance(payload, str):
        return payload
    stripped = payload.strip()
    if not stripped or stripped[0] not in "{[":
        return payload
    try:
        return json.loads(stripped)
    except (TypeError, ValueError):
        return payload


def _flatten_numbers(payload: Any) -> set[str]:
    parsed = _as_payload(payload)
    found: set[str] = set()
    try:
        blob = json.dumps(parsed, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = str(parsed)
    blob = _split_datetime_t(blob)
    for match in re.finditer(_PLAIN_NUMBER, blob):
        found.add(match.group(1))
        if "." in match.group(1):
            found.add(match.group(1).split(".", 1)[0])
    if isinstance(parsed, list):
        found.add(str(len(parsed)))
    if isinstance(parsed, dict):
        # Host GET wrap is {status_code, data}. A restatement that prints
        # the row count is still grounded (module docstring: counts allowed).
        for key in ("results", "items", "rows", "breakdown", "data"):
            rows = parsed.get(key)
            if isinstance(rows, list):
                found.add(str(len(rows)))
        count = parsed.get("count")
        if count is not None:
            found.add(str(count))
    return found


def _canonical_number(token: str | None) -> str | None:
    """The value behind a written numeral, or ``None`` when it has no value.

    ``16,800.000`` / ``16800`` / ``١٦٬٨٠٠`` / ``16800.00`` all return
    ``16800``. Grouping separators are read by convention (comma as
    thousands, dot as decimal, Arabic ``٬``/``٫`` likewise); the leading
    grouping ambiguity of a single ``1,043`` is read as thousands because
    that is what the digit grouping means. Formatting is discarded, the
    value is kept exact.
    """
    if not token:
        return None
    value = str(token).translate(_DIGIT_TRANSLATION)
    value = value.replace("\u066b", ".")
    for char in _GROUPING_CHARS:
        value = value.replace(char, "")
    if not any(char.isdigit() for char in value):
        return None

    dots = value.count(".")
    commas = value.count(",")
    if dots and commas:
        if value.rfind(",") > value.rfind("."):
            # ``1.250,50``: comma is the decimal mark, dot groups thousands.
            value = value.replace(".", "")
            value = value.replace(",", ".", 1) if value.count(",") == 1 else value.replace(",", "")
        else:
            value = value.replace(",", "")
    elif commas:
        parts = value.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and 0 < len(parts[0]) <= 3:
            value = value.replace(",", "")  # ``1,043`` groups thousands
        elif len(parts) == 2:
            value = value.replace(",", ".")  # ``0,15`` is a decimal
        else:
            value = value.replace(",", "")

    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    output = format(number.normalize(), "f")
    return "0" if output == "-0" else output


def _scaled(canonical: str | None, divisor: Decimal) -> str | None:
    """``canonical / divisor`` as a canonical string, or ``None``."""
    if canonical is None:
        return None
    try:
        return format((Decimal(canonical) / divisor).normalize(), "f")
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def _canonical_keys(payload: Any) -> set[str]:
    """Canonical values a payload carries, including a percent's fraction.

    A payload that states ``15%`` also grounds a reply that states ``0.15``.
    """
    parsed = _as_payload(payload)
    try:
        blob = json.dumps(parsed, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = str(parsed)
    blob = _split_datetime_t(blob)
    keys: set[str] = set()
    for match in re.finditer(_TEXT_NUMBER, blob):
        canonical = _canonical_number(match.group(1))
        if canonical is not None:
            keys.add(canonical)
        if blob[match.end():match.end() + 1] in _PERCENT_SIGNS:
            fraction = _scaled(canonical, Decimal(100))
            if fraction is not None:
                keys.add(fraction)
    return keys


def _rounds_to(canonical: str | None, keys: set[str]) -> bool:
    """True when a payload value rounds to ``canonical`` at its own precision.

    Rounding is accepted only where the payload carries the extra precision
    that implies it. A sub-unit payload value (a rate like ``0.15``) is never
    rounded down/up to an integer — that would turn ``0.15`` into ``0``.
    """
    if canonical is None:
        return False
    try:
        written = Decimal(canonical)
    except (InvalidOperation, ValueError):
        return False
    written_places = -written.as_tuple().exponent
    for key in keys:
        try:
            source = Decimal(key)
        except (InvalidOperation, ValueError):
            continue
        if source == written:
            return True
        if source.as_tuple().exponent >= written.as_tuple().exponent:
            continue  # the payload does not carry more precision
        if abs(source) < 1 and written_places == 0:
            continue  # never round a rate to 0 or 1
        try:
            if source.quantize(written, rounding=ROUND_HALF_UP) == written:
                return True
        except InvalidOperation:
            continue
    return False


def ungrounded_numbers(text: str | None, payloads: list[Any] | None) -> list[str]:
    """Numbers in ``text`` that are not in any payload. Empty when honest."""
    allowed: set[str] = set()
    canonical: set[str] = set()
    for payload in payloads or []:
        allowed |= _flatten_numbers(payload)
        canonical |= _canonical_keys(payload)
    raw = text or ""
    bad: list[str] = []
    for match in re.finditer(_TEXT_NUMBER, raw):
        token = match.group(1)
        head = token.split(".", 1)[0]
        if token in allowed or head in allowed:
            continue
        value = _canonical_number(token)
        if value is not None and value in canonical:
            continue
        tail = raw[match.end():match.end() + 3].lstrip()
        if tail[:1] in _PERCENT_SIGNS:
            fraction = _scaled(value, Decimal(100))
            if fraction is not None and fraction in canonical:
                continue
        if _rounds_to(value, canonical):
            continue
        bad.append(token)
    return bad


def strip_ungrounded_numbers(text: str | None, payloads: list[Any] | None) -> str:
    """Drop numerals the payloads do not contain. Words stay."""
    bad = set(ungrounded_numbers(text, payloads))
    if not bad or not text:
        return text or ""

    def _repl(match: re.Match) -> str:
        return "" if match.group(1) in bad else match.group(0)

    cleaned = re.sub(_TEXT_NUMBER, _repl, text)
    return " ".join(cleaned.split())
