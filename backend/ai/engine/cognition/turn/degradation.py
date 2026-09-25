"""Typed, visible degradation (ADR-0053).

A stage that fails says so. It never hands the turn to text that looks like
an answer. Exact data may still be shown; the sentence and the caveat tell
the user which part failed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("pulse.cognition.turn.degradation")


@dataclass(frozen=True)
class Degradation:
    stage: str   # understand | act | write
    cause: str   # understand_error | malformed_decision | act_error | model_error | empty_output | invalid_output | ungrounded

    def to_dict(self) -> dict:
        return {"stage": self.stage, "cause": self.cause}


def record(ledger, degradation: Degradation) -> None:
    """Log it and put it on the turn's signals, where the Arbiter and the ledger see it."""
    logger.warning("pulse degraded stage=%s cause=%s", degradation.stage, degradation.cause)
    signals = getattr(ledger, "decision_signals", None)
    if isinstance(signals, list):
        signals.append({"gate": "degraded", "fired": True, **degradation.to_dict()})


def sentence(degradation: Degradation, language: str = "en") -> str:
    """One honest sentence for the user. Names the failed part, not internals."""
    if degradation.stage == "write":
        if language == "ar":
            return (
                "جلبت البيانات، لكن تعذّر عليّ كتابة الملخص هذه المرة. "
                "الجداول والرسوم أدناه دقيقة."
            )
        return (
            "I fetched the data, but I could not write the summary this time. "
            "The tables and charts below are exact."
        )
    if language == "ar":
        return "تعذّر عليّ فهم هذه الرسالة الآن. أعد المحاولة بعد لحظة."
    return "I could not process that message just now. Please try again in a moment."


def caveat(degradation: Degradation) -> dict:
    return {"level": "warning", "text": f"Pulse degraded: {degradation.stage} ({degradation.cause})."}
