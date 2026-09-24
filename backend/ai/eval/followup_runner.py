"""P9 follow-up bank. Resolution comes from ConversationState, not a history scan.

Score is the fraction of cases that hold. The gate is ≥ 0.95.
"""
from __future__ import annotations

import os
from typing import Any, Callable


def _cases() -> list[tuple[str, Callable[[], bool]]]:
    from ai.engine.cognition.dialogue.deixis import should_gate_deixis
    from ai.engine.cognition.turn.ess_read import LEAVE_BALANCE_API, bound_ess_self_api

    history = [
        {"role": "user", "content": "عن الإجازات"},
        {"role": "assistant", "content": "رصيد الإجازة…"},
    ]
    state_row = [{"api": LEAVE_BALANCE_API}]

    def binds_prior_api() -> bool:
        return bound_ess_self_api(
            "تقرير شامل", history=history, prior_api=LEAVE_BALANCE_API,
        ) == LEAVE_BALANCE_API

    def history_alone_does_not_bind() -> bool:
        return bound_ess_self_api("تقرير شامل", history=history) is None

    def deixis_uses_last_results() -> bool:
        question = should_gate_deixis(
            "check that one for me",
            conversation_history=None,
            last_results=state_row,
        )
        return bool(question) and "leave balance" in question.casefold()

    def deixis_ignores_transcript_without_state() -> bool:
        # v21 passes no transcript, so the question cannot name a scanned topic.
        question = should_gate_deixis(
            "check that one for me",
            conversation_history=None,
            last_results=None,
        ) or ""
        folded = question.casefold()
        return "leave balance" not in folded and "إجاز" not in question

    return [
        ("fu-prior-api", binds_prior_api),
        ("fu-no-history-bind", history_alone_does_not_bind),
        ("fu-deixis-state", deixis_uses_last_results),
        ("fu-deixis-no-transcript", deixis_ignores_transcript_without_state),
    ]


def score() -> dict[str, Any]:
    """Run the bank under v21. Restores ``PULSE_UNDERSTAND`` afterward."""
    previous = os.environ.get("PULSE_UNDERSTAND")
    os.environ["PULSE_UNDERSTAND"] = "v21"
    misses: list[dict[str, str]] = []
    passed = 0
    try:
        cases = _cases()
        for case_id, check in cases:
            try:
                ok = bool(check())
            except Exception as exc:  # noqa: BLE001 — one case must not hide the rest
                ok = False
                misses.append({"id": case_id, "error": str(exc)})
                continue
            if ok:
                passed += 1
            else:
                misses.append({"id": case_id})
        n = len(cases)
    finally:
        if previous is None:
            os.environ.pop("PULSE_UNDERSTAND", None)
        else:
            os.environ["PULSE_UNDERSTAND"] = previous
    ratio = (passed / n) if n else 0.0
    return {
        "n": n,
        "passed": passed,
        "ratio": round(ratio, 3),
        "gate_pass": ratio >= 0.95 and not misses,
        "misses": misses,
    }
