"""Parse planner/demo period aliases into (year, month).

Shared by call_host_api slug resolution so invented labels like
``demo-oct-2026`` resolve to real payroll-run PKs instead of crashing
Django with ``Field 'id' expected a number``.
"""
from __future__ import annotations

import re
from calendar import month_abbr
from typing import Any


_MONTHS = {name.lower()[:3]: i for i, name in enumerate(month_abbr) if name}


def parse_period_alias(token: str) -> tuple[int, int] | None:
    """Return ``(year, month)`` from aliases like ``demo-oct-2026`` / ``2026-10``."""
    if not token:
        return None
    t = str(token).strip().lower().replace("_", "-")
    m = re.search(r"(20\d{2})[-/](\d{1,2})", t)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return year, month
    m = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*-?(20\d{2})",
        t,
    )
    if m:
        return int(m.group(2)), _MONTHS[m.group(1)[:3]]
    return None


def item_matches_period(item: dict[str, Any], year: int, month: int) -> bool:
    """True when a list-row ``period_start`` (date or ISO string) is year/month."""
    if not isinstance(item, dict):
        return False
    raw = item.get("period_start") or item.get("period") or item.get("start_date")
    if raw is None:
        return False
    text = str(raw)
    # ISO date YYYY-MM-DD or datetime
    m = re.match(r"(20\d{2})-(\d{1,2})", text)
    if not m:
        return False
    return int(m.group(1)) == year and int(m.group(2)) == month
