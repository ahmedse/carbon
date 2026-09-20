"""Pulse UX telemetry hooks (Track D4) — structured, fail-soft.

Emits low-cardinality events for Agent/Chat UX remediation (scope route,
deixis, consent, rerun). Never raises; never logs PII or full message bodies.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ai.pulse_ux")


def emit_ux(event: str, **fields: Any) -> None:
    """Record a Pulse UX event. Safe to call from request/SSE paths."""
    name = (event or "").strip()
    if not name:
        return
    safe = {
        k: v
        for k, v in fields.items()
        if v is not None and k not in ("message", "body", "text", "content")
    }
    try:
        logger.info("pulse_ux event=%s %s", name, safe)
    except Exception:  # noqa: BLE001 — telemetry must never break the product
        pass
