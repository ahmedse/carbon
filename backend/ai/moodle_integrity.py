"""Live-assessment integrity guard for the Moodle Ask door.

The signed page snapshot is the only input. A turn refuses to teach when
the OPEN activity is a typed assessment module (``quiz`` / ``qbank`` /
``lesson``) or when a signed timing window for the open course is active.
It is a no-op otherwise, so ordinary teaching is unaffected.

This is deliberately not a message-phrase check: it never scans chat history
for words and never exposes the exam, its title, or its questions. The
vocabulary lives in ``domain_packs/aast-med/integrity.yaml``. This module is
not imported by ``engine/``.
"""
from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med" / "integrity.yaml"

_DEFAULT_ANSWER = (
    "A live assessment is open. Pulse does not answer, hint, or advise while "
    "an assessment is open."
)


@lru_cache(maxsize=1)
def _spec() -> dict[str, Any]:
    data = yaml.safe_load(_PACK.read_text(encoding="utf-8")) or {}
    modules = frozenset(
        str(module).strip().casefold()
        for module in (data.get("modules") or [])
        if str(module).strip()
    )
    return {
        "modules": modules,
        "answer": str(data.get("answer") or "").strip() or _DEFAULT_ANSWER,
    }


def _int_or_none(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _flag_on(bag: dict[str, Any], key: str) -> bool:
    value = bag.get(key)
    return value is not None and bool(value)


def _window_active(window: Any, now: int) -> bool:
    if not isinstance(window, dict):
        return False
    opens = _int_or_none(window.get("opens"))
    closes = _int_or_none(window.get("closes"))
    if opens is None and closes is None:
        return bool(window.get("open"))
    if opens is not None and now < opens:
        return False
    if closes is not None and now > closes:
        return False
    return True


def live_assessment_open(
    snapshot: dict[str, Any] | None,
    host_context: dict[str, Any] | None = None,
    *,
    now: int | None = None,
) -> bool:
    """True when the signed page says a live assessment is in front of the user."""
    spec = _spec()
    page = snapshot if isinstance(snapshot, dict) else {}
    host = host_context if isinstance(host_context, dict) else {}
    stamp = int(time.time()) if now is None else int(now)

    activity = page.get("activity") if isinstance(page.get("activity"), dict) else {}
    module = str(activity.get("module") or page.get("module") or "").strip().casefold()
    if activity and module in spec["modules"]:
        return True

    for bag in (page, host):
        if _flag_on(bag, "assessment_open"):
            return True
        assessment = bag.get("assessment") if isinstance(bag.get("assessment"), dict) else {}
        if _flag_on(assessment, "open"):
            return True
        if _window_active(assessment, stamp):
            return True
        if _window_active(bag.get("assessment_window"), stamp):
            return True
    return False


def integrity_answer() -> str:
    """The fixed refusal. It never names the activity or the course."""
    return _spec()["answer"]
