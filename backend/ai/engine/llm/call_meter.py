"""Context-local LLM call meter — PV2-0A log-only instrumentation.

Pure stdlib; no Django or host imports. ``route_chat`` records each provider
call against the active meter and stage (via contextvars).
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field

_active_meter: contextvars.ContextVar[CallMeter | None] = contextvars.ContextVar(
    "llm_call_meter", default=None,
)
_active_stage: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_call_stage", default="unattributed",
)


@dataclass
class LLMCallRecord:
    stage: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    model: str


@dataclass
class CallMeter:
    records: list[LLMCallRecord] = field(default_factory=list)
    # Enclosing meter + the stage active when this scope opened; each record
    # is also rolled up there so turn totals include nested (step) calls.
    parent: CallMeter | None = field(default=None, repr=False, compare=False)
    parent_stage: str = "unattributed"

    @property
    def total(self) -> int:
        return len(self.records)

    def by_stage(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for rec in self.records:
            counts[rec.stage] = counts.get(rec.stage, 0) + 1
        return counts

    def total_ms(self) -> float:
        return sum(rec.latency_ms for rec in self.records)

    def record(
        self,
        *,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        stage: str | None = None,
    ) -> None:
        self.records.append(
            LLMCallRecord(
                stage=stage if stage is not None else _active_stage.get(),
                latency_ms=float(latency_ms),
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                model=str(model or ""),
            )
        )
        if self.parent is not None:
            self.parent.record(
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
                stage=self.parent_stage,
            )


@contextmanager
def meter_scope():
    """Activate a fresh meter for the block; the enclosing meter is restored on exit."""
    meter = CallMeter(parent=_active_meter.get(), parent_stage=_active_stage.get())
    token = _active_meter.set(meter)
    try:
        yield meter
    finally:
        _active_meter.reset(token)


def current_meter() -> CallMeter | None:
    return _active_meter.get()


@contextmanager
def stage(name: str):
    token = _active_stage.set(name)
    try:
        yield
    finally:
        _active_stage.reset(token)


def record_call(
    latency_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> None:
    meter = _active_meter.get()
    if meter is None:
        return
    meter.record(
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
    )
