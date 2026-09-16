"""W-4 — per-node retry policy helpers (pure, RULE_20).

Policies live on ``WorkflowNode.retry``::

    {"max_attempts": 3, "backoff": "exponential",
     "base_ms": 1000, "max_ms": 8000, "retry_on": ["transient"]}

Backoff is deterministic (no jitter) so replays stay reproducible — matches
the host ``PlansService._retry_backoff_delay`` schedule.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DEFAULT_RETRY",
    "normalize_retry_policy",
    "classify_error",
    "should_retry",
    "backoff_seconds",
]

DEFAULT_RETRY: dict[str, Any] = {
    "max_attempts": 3,
    "backoff": "exponential",
    "base_ms": 1000,
    "max_ms": 8000,
    "retry_on": ["transient"],
}


def normalize_retry_policy(raw: dict | None) -> dict[str, Any]:
    """Merge caller policy onto defaults; clamp unsafe values."""
    out = dict(DEFAULT_RETRY)
    if not raw:
        return out
    if "max_attempts" in raw:
        try:
            out["max_attempts"] = max(1, min(int(raw["max_attempts"]), 8))
        except (TypeError, ValueError):
            pass
    if "base_ms" in raw:
        try:
            out["base_ms"] = max(0, int(raw["base_ms"]))
        except (TypeError, ValueError):
            pass
    if "max_ms" in raw:
        try:
            out["max_ms"] = max(out["base_ms"], int(raw["max_ms"]))
        except (TypeError, ValueError):
            pass
    if "backoff" in raw and raw["backoff"] in (
        "exponential", "exponential_jitter", "fixed", "none",
    ):
        # exponential_jitter accepted but treated as exponential (deterministic)
        out["backoff"] = (
            "exponential" if raw["backoff"] == "exponential_jitter"
            else raw["backoff"]
        )
    if "retry_on" in raw and isinstance(raw["retry_on"], (list, tuple)):
        out["retry_on"] = [str(x) for x in raw["retry_on"]] or list(
            DEFAULT_RETRY["retry_on"]
        )
    return out


def classify_error(error: Any) -> str:
    """Map a tool/LLM error into ``transient`` | ``permanent`` | ``timeout``.

    String heuristics only — no provider imports (RULE_20). Host code may
    pre-classify and pass an already-normalized class.
    """
    if error is None:
        return "permanent"
    if isinstance(error, dict):
        kind = error.get("error_kind") or error.get("class") or error.get("type")
        if kind in ("transient", "permanent", "timeout"):
            return str(kind)
        error = error.get("error") or error.get("message") or str(error)
    text = str(error).lower()
    if text.startswith("[timeout]") or any(t in text for t in (
        "timeout", "timed out", "deadline exceeded", "read timed out",
    )):
        return "timeout"
    if any(t in text for t in (
        "rate limit", "429", "503", "502", "504", "temporarily",
        "unavailable", "connection reset", "connection refused",
        "econnreset", "empty response", "try again",
    )):
        return "transient"
    return "permanent"


def should_retry(policy: dict | None, error: Any, attempt: int) -> bool:
    """True when another attempt is allowed after ``attempt`` failures (0-based).

    ``attempt`` is the number of failures so far (0 = first failure, about to
    retry for the first time). Total tries will be ``max_attempts``.
    """
    p = normalize_retry_policy(policy)
    max_attempts = int(p["max_attempts"])
    # attempt 0 → 1 failure already happened; allow retry while
    # failures < max_attempts (i.e. attempt index < max_attempts - 1)
    if attempt >= max_attempts - 1:
        return False
    kind = classify_error(error)
    retry_on = p.get("retry_on") or ["transient"]
    return kind in retry_on or "*" in retry_on or "all" in retry_on


def backoff_seconds(policy: dict | None, attempt: int) -> float:
    """Sleep duration before the next retry (``attempt`` is 1-based retry #)."""
    p = normalize_retry_policy(policy)
    if p.get("backoff") == "none":
        return 0.0
    base = float(p["base_ms"]) / 1000.0
    cap = float(p["max_ms"]) / 1000.0
    n = max(int(attempt), 1)
    if p.get("backoff") == "fixed":
        return min(base, cap)
    # exponential: base * 2^(n-1)
    return min(base * (2 ** (n - 1)), cap)
