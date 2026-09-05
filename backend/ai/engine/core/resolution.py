"""Tri-state resolution results — epistemic status is never silently discarded.

Single source of truth for the canonical tri-state result shape used at every
deterministic boundary (see ``uncertainty-provenance.md``).  Stdlib-only and
side-effect-free so any engine seam can reuse it without adding a dependency
(RULE_20).
"""
import json


def _clamp(value):
    """Clamp a numeric confidence into the [0.0, 1.0] interval."""
    value = float(value)
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def resolved(data, *, confidence=1.0, source=""):
    """Build a ``resolved`` result: understood and found, safe to proceed."""
    return {
        "status": "resolved",
        "data": data,
        "confidence": _clamp(confidence),
        "source": source,
    }


def no_match(reason, *, hint="", candidates=None):
    """Build a ``no_match`` result: did NOT understand — escalate, never act."""
    return {
        "status": "no_match",
        "reason": reason,
        "hint": hint,
        "candidates": candidates or [],
    }


def error(cause, *, detail=""):
    """Build an ``error`` result: understood, but the fetch/compute failed."""
    return {"status": "error", "cause": cause, "detail": detail}


def is_resolved(r) -> bool:
    """True iff ``r`` is a resolved result — the sanctioned success branch."""
    return isinstance(r, dict) and r.get("status") == "resolved"


def is_no_match(r) -> bool:
    """True iff ``r`` is a no_match result (did not understand)."""
    return isinstance(r, dict) and r.get("status") == "no_match"


def is_error(r) -> bool:
    """True iff ``r`` is an error result (understood, but failed)."""
    return isinstance(r, dict) and r.get("status") == "error"


def min_confidence(*results) -> float:
    """Min confidence across results (skip non-numeric; 1.0 if none found)."""
    confidences = [
        r["confidence"]
        for r in results
        if isinstance(r, dict)
        and isinstance(r.get("confidence"), (int, float))
        and not isinstance(r.get("confidence"), bool)
    ]
    if not confidences:
        return 1.0
    return _clamp(min(confidences))


def truthiness_guard(r) -> bool:
    """The ONLY sanctioned truthiness view: resolved is truthy, nothing else is."""
    return is_resolved(r)


def payload_status(raw):
    """Return the tri-state status of a raw tool-result payload, else None.

    Accepts a dict, a JSON string, or a host-executor envelope
    ``{"status_code": ..., "data": {...}}``. Returns one of
    ``"resolved" | "no_match" | "error"``, or ``None`` when the payload is not
    a recognised tri-state result.
    """
    data = raw
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return None
    if isinstance(data, dict) and "status_code" in data and "data" in data:
        data = data["data"]
    if isinstance(data, dict):
        status = data.get("status")
        if status in ("resolved", "no_match", "error"):
            return status
    return None
