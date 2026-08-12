"""
Host API call discipline (N1).

Brings the validate→execute→retry discipline used by the SQL path
(``knowledge_graph/retry_loop.py``) to the host REST API path
(``agent/tools.py::execute_call_host_api`` → ``HostAPIExecutor.call_api_direct``).

Design goals
------------
- **Additive & gated.** All behaviour is opt-in via ``API_DISCIPLINE_ENABLED``.
  When the flag is off, callers run the legacy single-shot path unchanged.
- **Read-only.** This module only ever re-runs the *execute* callable it is
  handed. It never constructs mutations. Non-GET endpoints still go through the
  confirmation flow in ``execute_call_host_api`` and never reach here.
- **Safe v1.** Without a ``repair_fn``, only transient/unknown errors are
  retried (with backoff). Parameter-shaped errors (404/400/422) are only
  retried when a caller supplies a repair function, so a plain re-run is never
  wasted on an error a re-run cannot fix.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("pulse.agent.api_discipline")


# ── Error classification ──────────────────────────────────────────────────────

class APIErrorCategory(str, Enum):
    """Coarse classification of a host API failure, mirroring SQL ErrorCategory."""
    AUTH = "auth"            # 401/403 — never retry (RBAC / expired token)
    NOT_FOUND = "not_found"  # 404 — only repairable (re-resolve id/path)
    BAD_PARAM = "bad_param"  # 400/422 — only repairable (fix params/body)
    TRANSIENT = "transient"  # 5xx / connect / timeout — retry with backoff
    UNKNOWN = "unknown"      # unclassified — retry conservatively with backoff


# Never worth retrying, regardless of repair capability.
_NON_RETRYABLE = {APIErrorCategory.AUTH}
# Retryable by simply re-running the same call.
_TRANSIENT_RETRY = {APIErrorCategory.TRANSIENT, APIErrorCategory.UNKNOWN}
# Retryable only when the caller can change the request first.
_REPAIRABLE = {APIErrorCategory.NOT_FOUND, APIErrorCategory.BAD_PARAM}


def classify_api_error(error_str: str | None) -> APIErrorCategory:
    """Map a host API error string to an :class:`APIErrorCategory`."""
    e = (error_str or "").lower()
    if "401" in e or "unauthorized" in e or "403" in e or "forbidden" in e:
        return APIErrorCategory.AUTH
    if "404" in e or "not found" in e:
        return APIErrorCategory.NOT_FOUND
    if "400" in e or "422" in e or "unprocessable" in e or "bad request" in e:
        return APIErrorCategory.BAD_PARAM
    if any(
        s in e
        for s in (
            "500", "502", "503", "504",
            "timed out", "timeout",
            "cannot connect", "connection refused", "service unavailable",
        )
    ):
        return APIErrorCategory.TRANSIENT
    return APIErrorCategory.UNKNOWN


def _is_error(result: object) -> bool:
    """A tool result is an error iff it is a dict carrying an ``error`` key."""
    return isinstance(result, dict) and "error" in result


# ── Pre-execution validation ──────────────────────────────────────────────────

def validate_api_call(executor, api_name: str) -> Optional[dict]:
    """Validate an API call before execution.

    Returns an error dict if the call is structurally invalid, otherwise
    ``None``. Mirrors the ``validate_sql`` gate on the SQL path: catch obvious
    problems before spending an HTTP round-trip.
    """
    entry = executor.get_catalog_entry(api_name)
    if not entry:
        return {"error": f"Unknown API endpoint: '{api_name}'. Check the api_catalog."}
    method = str(entry.get("method", "")).upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return {
            "error": (
                f"API endpoint '{api_name}' has an invalid HTTP method "
                f"({entry.get('method')!r})."
            )
        }
    return None


# ── Retry loop ────────────────────────────────────────────────────────────────

@dataclass
class APIAttempt:
    """A single API execution attempt."""
    result: dict
    category: str = ""   # empty for success; APIErrorCategory value on failure


@dataclass
class APIOutcome:
    """Complete execution history for one API call."""
    attempts: list[APIAttempt] = field(default_factory=list)
    final_result: Optional[dict] = None
    succeeded: bool = False
    retry_count: int = 0


class APIRetryLoop:
    """Execute an API call with bounded, error-driven retries.

    Parameters
    ----------
    max_retries:
        Maximum number of retries *after* the first attempt.
    backoff_ms:
        Base backoff in milliseconds; scaled linearly by attempt number.
    """

    def __init__(self, max_retries: int, backoff_ms: int = 0):
        self.max_retries = max(0, int(max_retries))
        self.backoff_ms = max(0, int(backoff_ms))

    async def run(
        self,
        execute_fn: Callable[[], Awaitable[dict]],
        repair_fn: Optional[Callable[[APIErrorCategory], Awaitable[bool]]] = None,
    ) -> APIOutcome:
        """Run *execute_fn*, retrying on retryable failures.

        ``execute_fn`` must return a result dict (an error is signalled by an
        ``error`` key) and must not raise. ``repair_fn`` — when supplied — is
        awaited before a repairable retry to mutate the request for the next
        try; it receives the classified error category and must return ``True``
        if it actually applied a repair (so the retry is worthwhile) or ``False``
        to stop retrying.
        """
        outcome = APIOutcome()

        for attempt_num in range(self.max_retries + 1):
            result = await execute_fn()

            if not _is_error(result):
                outcome.attempts.append(APIAttempt(result=result))
                outcome.final_result = result
                outcome.succeeded = True
                outcome.retry_count = attempt_num
                return outcome

            category = classify_api_error(result.get("error"))
            outcome.attempts.append(APIAttempt(result=result, category=category.value))

            if attempt_num >= self.max_retries or category in _NON_RETRYABLE:
                break

            if category in _REPAIRABLE:
                # Repairable errors only retry if a repair is actually applied.
                if repair_fn is None:
                    break
                try:
                    repaired = await repair_fn(category)
                except Exception as e:  # repair is best-effort; never fatal
                    logger.warning("api_discipline: repair_fn failed: %s", e)
                    repaired = False
                if not repaired:
                    break
            elif category not in _TRANSIENT_RETRY:
                break

            if self.backoff_ms:
                await asyncio.sleep((self.backoff_ms / 1000.0) * (attempt_num + 1))

            outcome.retry_count = attempt_num + 1
            logger.info(
                "api_discipline: retry %d/%d after %s error",
                attempt_num + 1, self.max_retries, category.value,
            )

        outcome.final_result = (
            outcome.attempts[-1].result if outcome.attempts else {"error": "no attempts"}
        )
        outcome.succeeded = False
        return outcome
