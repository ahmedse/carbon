"""Shared helpers for TurnPipelineRunner and extracted stage modules."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

import logging

from ai.engine.cognition.turn.witnesses import TurnLedger

logger = logging.getLogger("pulse.cognition.turn.runner")

_BACKGROUND_LLM_STAGES = T("turn/runner_helpers.py::_BACKGROUND_LLM_STAGES")


def get_settings():
    """Resolve settings through ``turn.runner``.

    The stage modules (``runner_pre_s1`` … ``runner_s6``) were extracted from
    ``runner.py``; tests and adapters still monkeypatch
    ``ai.engine.cognition.turn.runner.get_settings``. Routing every stage through
    this one seam keeps that contract true after the split.
    """
    from ai.engine.cognition.turn import runner as _runner

    return _runner.get_settings()


def _signal(ledger: TurnLedger, gate: str, fired: bool, **detail) -> None:
    if ledger.decision_signals is None:
        ledger.decision_signals = []
    ledger.decision_signals.append(
        {"gate": gate, "fired": fired, "detail": detail or {}}
    )


def _commit_staged(ledger: TurnLedger, meter, staged):
    """L3: return the Arbiter winner's body, or None to keep walking the spine."""
    from ai.engine.cognition.turn.executor import pick_staged

    picked = pick_staged(ledger.decision_signals, staged)
    if picked is None:
        return None
    _finalize_meter(ledger, meter, picked.decision)
    return picked.response, ledger


def _finalize_meter(ledger: TurnLedger, meter, decision: str) -> None:
    from ai.engine.llm.call_meter import CallMeter

    try:
        from ai.engine.core.config import get_settings
        from ai.engine.cognition.turn.arbiter import shadow_compare

        mode = (getattr(get_settings(), "PULSE_ARBITER", "on") or "on").strip().lower()
        if mode == "legacy":
            ledger.turn_decision = decision
            ledger.arbiter_shadow = None
        else:
            shadow = shadow_compare(decision, ledger.decision_signals)
            ledger.arbiter_shadow = shadow
            ledger.turn_decision = shadow["arbiter"] if mode == "on" else decision
    except Exception:  # noqa: BLE001 — arbiter must never break a turn
        ledger.turn_decision = decision
        logger.debug("arbiter shadow skipped", exc_info=True)
    if not isinstance(meter, CallMeter):
        return
    by_stage = meter.by_stage()
    background = sum(by_stage.get(s, 0) for s in _BACKGROUND_LLM_STAGES)
    foreground = max(0, int(meter.total) - int(background))
    ledger.llm_calls_by_stage = by_stage
    ledger.llm_calls_measured = foreground
    ledger.llm_calls_background = background
    fired_gates = [
        s["gate"] for s in (ledger.decision_signals or []) if s.get("fired")
    ]
    logger.info(
        "[turn-decision] conv=%s decision=%s llm=%d bg=%d by_stage=%s fired=%s",
        ledger.conversation_id,
        decision,
        foreground,
        background,
        by_stage,
        fired_gates,
    )


def _audience_from_user_info(user_info: dict | None) -> list[str]:
    if not isinstance(user_info, dict):
        return ["ess"]
    aud = user_info.get("audience")
    if isinstance(aud, (list, tuple, set)) and aud:
        return [str(a) for a in aud]
    return ["ess"]


def _scoped_api_catalog(instance_config: dict | None, user_info: dict | None) -> list:
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    return filter_catalog_by_audience(
        (instance_config or {}).get("api_catalog") or [],
        _audience_from_user_info(user_info),
    )


def _scoped_navigation_routes(instance_config: dict | None, user_info: dict | None) -> list:
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    return filter_catalog_by_audience(
        (instance_config or {}).get("navigation_routes") or [],
        _audience_from_user_info(user_info),
    )


def _audience_persona(instance_config: dict | None, user_info: dict | None) -> str:
    from ai.engine.cognition.context_pack import compose_persona_for_audience

    return compose_persona_for_audience(
        instance_config,
        _audience_from_user_info(user_info),
    )
