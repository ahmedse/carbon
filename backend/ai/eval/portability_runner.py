"""P15 portability bank. A second pack's process must brief without a brand id in core.

Score is the fraction of cases that hold. The gate is a clean run.
"""
from __future__ import annotations

from typing import Any, Callable

_EDUOS_PROCESS = "cohort.review.lifecycle"
_NIBRAS_PROCESS = "leave.request.lifecycle"


def _cases() -> list[tuple[str, Callable[[], bool]]]:
    from ai.engine.cognition.turn.process_brief import (
        format_process_briefing,
        process_ids,
    )

    def both_packs_are_discovered() -> bool:
        ids = set(process_ids())
        return _EDUOS_PROCESS in ids and _NIBRAS_PROCESS in ids

    def education_process_briefs() -> bool:
        text = format_process_briefing(_EDUOS_PROCESS, lang="en") or ""
        return _EDUOS_PROCESS in text and "human_only" in text and "submit" in text

    def missing_process_is_empty() -> bool:
        return format_process_briefing("not.a.real.process") is None

    return [
        ("port-discover", both_packs_are_discovered),
        ("port-brief", education_process_briefs),
        ("port-missing", missing_process_is_empty),
    ]


def score() -> dict[str, Any]:
    misses: list[dict[str, str]] = []
    passed = 0
    cases = _cases()
    for case_id, check in cases:
        try:
            ok = bool(check())
        except Exception as exc:  # noqa: BLE001 — one case must not hide the rest
            misses.append({"id": case_id, "error": str(exc)})
            continue
        if ok:
            passed += 1
        else:
            misses.append({"id": case_id})
    n = len(cases)
    return {
        "n": n,
        "passed": passed,
        "process_id": _EDUOS_PROCESS,
        "gate_pass": n > 0 and passed == n and not misses,
        "misses": misses,
    }
