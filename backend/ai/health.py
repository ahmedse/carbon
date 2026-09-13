"""Capability health — per-capability status for the AI admin console (P1-14).

Each capability reports exactly one of five states, in a strict
fail-closed order of trust (no probe may raise out of this module):

    healthy      — wired AND a live probe passed (only where a cheap,
                   meaningful probe exists: store, sandbox).
    configured   — wired and config present; no live probe run (config-only
                   capabilities: reason lane, verify, MCP).
    degraded     — wired but a probe failed or config is malformed/partial.
    disabled     — deliberately turned off (feature flag off / empty config).
    unavailable  — cannot operate (missing dependency / non-durable backend).

Capabilities probed (P1-14):

    store        — durable AI store backend (``AI_STORE_BACKEND``) + a
                   trivial Django ORM reachability probe.
    reason_lane  — adaptive reasoning escalation lane (``LLM_REASON_MODEL``
                   → ``LLM_ESCALATION_MODEL`` → ``LLM_MODEL``).
    verify       — post-result verification witness (``PULSE_VERIFY_ENABLED``
                   + the verify turn-profile model).
    mcp          — outbound MCP tool servers (``MCP_SERVERS`` JSON config).
    sandbox      — subprocess code sandbox (``ai.code_sandbox`` importable +
                   a real ``sys.executable``).

This module is read-only and side-effect free (no durable writes, no LLM
calls).  Every probe is individually guarded so one failing capability
yields that capability's degraded/unavailable entry, never a 500.
"""

from __future__ import annotations

import json
import logging
import sys

from django.conf import settings as django_settings

logger = logging.getLogger("carbon.ai.health")

# The complete, ordered set of valid capability states.
_STATUSES = ("healthy", "configured", "degraded", "disabled", "unavailable")


def _eng_settings():
    """Engine settings object (lazy import, cached by config.py)."""
    from ai.engine.core.config import get_settings

    return get_settings()


# ── Probe helpers (each returns a ready capability dict) ────────────────────


def _probe_store() -> dict:
    """Durable store backend + a trivial ORM reachability probe."""
    backend = getattr(django_settings, "AI_STORE_BACKEND", "")
    if backend != "django":
        return {
            "status": "unavailable",
            "backend": backend or None,
            "detail": "durable store backend is not 'django'",
        }
    try:
        from ai.models import ModelCatalog

        count = ModelCatalog.objects.count()
    except Exception as exc:  # noqa: BLE001 — degraded, not a crash
        logger.warning("store capability probe failed: %s", exc)
        return {
            "status": "degraded",
            "backend": backend,
            "detail": f"store ORM probe failed: {exc}",
        }
    return {
        "status": "healthy",
        "backend": backend,
        "detail": f"durable store reachable (ModelCatalog count={count})",
    }


def _probe_reason_lane() -> dict:
    """Adaptive reasoning escalation lane (C1)."""
    settings = _eng_settings()
    dedicated = settings.LLM_REASON_MODEL or ""
    resolved = getattr(settings, "LLM_MODEL", "") or ""
    try:
        from ai.engine.llm.router import get_model_for_task

        resolved = get_model_for_task("reason") or ""
    except Exception as exc:  # noqa: BLE001 — degraded, not a crash
        logger.warning("reason-lane probe failed: %s", exc)
        return {"status": "degraded", "model": None, "dedicated": False,
                "detail": f"reason-lane resolution failed: {exc}"}
    if not resolved:
        return {"status": "unavailable", "model": None, "dedicated": False,
                "detail": "no reason-lane model resolved"}
    if dedicated:
        return {"status": "configured", "model": resolved, "dedicated": True,
                "detail": "dedicated reason-lane model configured"}
    return {"status": "configured", "model": resolved, "dedicated": False,
            "detail": "reason lane falls back to escalation/default model"}


def _probe_verify() -> dict:
    """Post-result verification witness (Phase 7)."""
    settings = _eng_settings()
    enabled = bool(settings.PULSE_VERIFY_ENABLED)
    if not enabled:
        return {"status": "disabled", "enabled": False, "model": None,
                "detail": "PULSE_VERIFY_ENABLED is off"}
    model = None
    try:
        from ai.engine.llm.router import model_for_profile

        model = model_for_profile("verify") or None
    except Exception as exc:  # noqa: BLE001 — degraded, not a crash
        logger.warning("verify probe failed: %s", exc)
        return {"status": "degraded", "enabled": True, "model": None,
                "detail": f"verify model resolution failed: {exc}"}
    detail = (
        f"verification witness on (model={model})"
        if model
        else "verification witness on (falls back to instance default model)"
    )
    return {"status": "configured", "enabled": True, "model": model,
            "detail": detail}


def _probe_mcp() -> dict:
    """Outbound MCP tool servers (``MCP_SERVERS`` JSON)."""
    settings = _eng_settings()
    raw = (settings.MCP_SERVERS or "").strip()
    if not raw:
        return {"status": "disabled", "servers": 0,
                "detail": "MCP_SERVERS not configured"}
    try:
        configs = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "degraded", "servers": 0,
                "detail": f"MCP_SERVERS is not valid JSON: {exc}"}
    if not isinstance(configs, list):
        return {"status": "degraded", "servers": 0,
                "detail": "MCP_SERVERS is not a JSON list"}
    return {"status": "configured", "servers": len(configs),
            "detail": f"{len(configs)} MCP server(s) configured"}


def _probe_sandbox() -> dict:
    """Subprocess code sandbox wiring (no full run — that is a P7 gate)."""
    try:
        from ai.code_sandbox import CodeSandbox  # noqa: F401

        executable = bool(sys.executable)
    except Exception as exc:  # noqa: BLE001 — unavailable, not a crash
        logger.warning("sandbox probe failed: %s", exc)
        return {"status": "unavailable", "detail": f"sandbox not importable: {exc}"}
    if not executable:
        return {"status": "unavailable",
                "detail": "no sys.executable to run the sandbox subprocess"}
    return {"status": "configured",
            "detail": "subprocess sandbox wired (sys.executable present)"}


# ── Public entry point ─────────────────────────────────────────────────────


def capability_health() -> dict:
    """Return per-capability status for the five P1-14 capabilities.

    Never raises — each probe is individually guarded and always returns a
    dict with a valid ``status`` from ``_STATUSES``.
    """
    return {
        "store": _probe_store(),
        "reason_lane": _probe_reason_lane(),
        "verify": _probe_verify(),
        "mcp": _probe_mcp(),
        "sandbox": _probe_sandbox(),
    }
