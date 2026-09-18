"""LLM assist coder — optional Pulse call; always fails closed to heuristic."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from gradevance.services.coders import get_coder, register_coder
from gradevance.services.pipeline import _SegDraft

logger = logging.getLogger(__name__)


def _try_pulse_codes(seg: _SegDraft, anchors: list[dict]) -> list[dict] | None:
    """Best-effort Pulse path. Returns None → caller falls back to heuristic.

    Enabled only when GRADEVANCE_LLM_CODER_ENABLED is true AND a callable
    ``ai.engine`` helper is importable. Never raises into the pipeline.
    """
    if not bool(getattr(settings, "GRADEVANCE_LLM_CODER_ENABLED", False)):
        return None
    try:
        # Soft import — Pulse layout varies by brand; absence is not an error.
        from ai.engine.agent import run_sync  # type: ignore
    except Exception:
        return None
    try:
        prompt = {
            "task": "gradevance_lct_code",
            "text": seg.text[:2000],
            "anchors": [
                {"id": a.get("id"), "value": a.get("value"), "dimension": a.get("dimension")}
                for a in (anchors or [])[:40]
            ],
        }
        out: Any = run_sync(prompt)  # may not exist / may raise
        codes = out.get("codes") if isinstance(out, dict) else None
        if not isinstance(codes, list) or not codes:
            return None
        cleaned: list[dict] = []
        for c in codes:
            if not isinstance(c, dict) or not c.get("dimension") or not c.get("value"):
                continue
            cleaned.append(
                {
                    "dimension": c["dimension"],
                    "value": c["value"],
                    "confidence": min(float(c.get("confidence") or 0.5), 0.85),
                    "evidence": {"method": "llm_assist", "source": "pulse"},
                }
            )
        return cleaned or None
    except Exception as exc:
        logger.info("llm_assist Pulse unavailable: %s", exc)
        return None


def llm_assist_coder(seg: _SegDraft, anchors: list[dict], lct_enabled: bool) -> list[dict]:
    pulse = _try_pulse_codes(seg, anchors)
    if pulse is not None:
        return pulse
    coded = get_coder("heuristic_anchor")(seg, anchors, lct_enabled)
    for c in coded:
        evidence = dict(c.get("evidence") or {})
        evidence["llm"] = "unavailable_fallback_heuristic"
        c["evidence"] = evidence
        c["confidence"] = min(float(c.get("confidence") or 0.5), 0.65)
    return coded


register_coder("llm_assist", llm_assist_coder)
