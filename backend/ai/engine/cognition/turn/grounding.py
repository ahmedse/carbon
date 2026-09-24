"""Numeric grounding for tool answers (ADR-0049 P6).

A number in the reply must appear in the tool payload. Counts of result
rows are allowed. This does not call a model.
"""
from __future__ import annotations

import json
import re
from typing import Any

def _flatten_numbers(payload: Any) -> set[str]:
    found: set[str] = set()
    try:
        blob = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = str(payload)
    for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", blob):
        found.add(match.group(1))
        if "." in match.group(1):
            found.add(match.group(1).split(".", 1)[0])
    if isinstance(payload, list):
        found.add(str(len(payload)))
    if isinstance(payload, dict):
        for key in ("results", "items", "rows"):
            rows = payload.get(key)
            if isinstance(rows, list):
                found.add(str(len(rows)))
        count = payload.get("count")
        if count is not None:
            found.add(str(count))
    return found


def ungrounded_numbers(text: str | None, payloads: list[Any] | None) -> list[str]:
    """Numbers in ``text`` that are not in any payload. Empty when honest."""
    allowed: set[str] = set()
    for payload in payloads or []:
        allowed |= _flatten_numbers(payload)
    bad: list[str] = []
    for match in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", text or ""):
        token = match.group(1)
        head = token.split(".", 1)[0]
        if token not in allowed and head not in allowed:
            bad.append(token)
    return bad


def strip_ungrounded_numbers(text: str | None, payloads: list[Any] | None) -> str:
    """Drop numerals the payloads do not contain. Words stay."""
    bad = set(ungrounded_numbers(text, payloads))
    if not bad or not text:
        return text or ""

    def _repl(match: re.Match) -> str:
        token = match.group(1)
        head = token.split(".", 1)[0]
        if token in bad or head in bad:
            return ""
        return match.group(0)

    cleaned = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", _repl, text)
    return " ".join(cleaned.split())
