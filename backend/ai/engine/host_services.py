"""Host services the engine may call without importing the host.

The host registers concrete callables from ``AIConfig.ready``. Until a
callable is registered, each function fails closed to the same empty result
the call site already used when the host was unreachable.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable


class EnvelopeWriteError(Exception):
    """The answer writer failed. ``cause`` is typed."""

    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


_localdate: Callable[[], date] | None = None
_fill_write_body: Callable[..., dict] | None = None
_write_slots_for: Callable[..., list] | None = None
_format_host_actions: Callable[[list], str] | None = None
_synthesize_envelope: Callable[..., Any] | None = None
_fallback_envelope: Callable[..., Any] | None = None
_labeled_numeric_points: Callable[..., Any] | None = None
_active_process_definition: Callable[[str], dict | None] | None = None
_emit_ux: Callable[..., None] | None = None
_commit_proposal: Callable[..., Any] | None = None
_propose_plan: Callable[..., Any] | None = None
_daily_budget_override: Callable[[str], float | None] | None = None


def set_localdate(fn: Callable[[], date]) -> None:
    global _localdate
    _localdate = fn


def set_fill_write_body(fn: Callable[..., dict]) -> None:
    global _fill_write_body
    _fill_write_body = fn


def set_write_slots_for(fn: Callable[..., list]) -> None:
    global _write_slots_for
    _write_slots_for = fn


def set_format_host_actions(fn: Callable[[list], str]) -> None:
    global _format_host_actions
    _format_host_actions = fn


def set_synthesize_envelope(fn: Callable[..., Any]) -> None:
    global _synthesize_envelope
    _synthesize_envelope = fn


def set_fallback_envelope(fn: Callable[..., Any]) -> None:
    global _fallback_envelope
    _fallback_envelope = fn


def set_labeled_numeric_points(fn: Callable[..., Any]) -> None:
    global _labeled_numeric_points
    _labeled_numeric_points = fn


def set_active_process_definition(fn: Callable[[str], dict | None]) -> None:
    global _active_process_definition
    _active_process_definition = fn


def set_emit_ux(fn: Callable[..., None]) -> None:
    global _emit_ux
    _emit_ux = fn


def set_commit_proposal(fn: Callable[..., Any]) -> None:
    global _commit_proposal
    _commit_proposal = fn


def set_propose_plan(fn: Callable[..., Any]) -> None:
    global _propose_plan
    _propose_plan = fn


def set_daily_budget_override(fn: Callable[[str], float | None]) -> None:
    global _daily_budget_override
    _daily_budget_override = fn


def localdate() -> date:
    if _localdate is None:
        return date.today()
    return _localdate()


def fill_write_body(body, *, slots, text="", today=None):
    if _fill_write_body is None:
        return body if isinstance(body, dict) else {}
    return _fill_write_body(body, slots=slots, text=text, today=today)


def write_slots_for(api_name, api_catalog) -> list:
    if _write_slots_for is None:
        return []
    return _write_slots_for(api_name, api_catalog)


def format_host_actions(outputs: list) -> str:
    if _format_host_actions is None:
        return ""
    return _format_host_actions(outputs)


async def synthesize_envelope(**kwargs):
    if _synthesize_envelope is None:
        raise EnvelopeWriteError("model_error")
    return await _synthesize_envelope(**kwargs)


def fallback_envelope(usable, user_message):
    if _fallback_envelope is None:
        return None
    return _fallback_envelope(usable, user_message)


def labeled_numeric_points(rows):
    if _labeled_numeric_points is None:
        return None
    return _labeled_numeric_points(rows)


def active_process_definition(process_id: str) -> dict | None:
    if _active_process_definition is None:
        return None
    return _active_process_definition(process_id)


def emit_ux(event: str, **kwargs) -> None:
    if _emit_ux is None:
        return
    _emit_ux(event, **kwargs)


def commit_proposal(host_user_id, conversation_id):
    if _commit_proposal is None:
        return None
    return _commit_proposal(host_user_id, conversation_id)


def propose_plan(host_user_id, brief, *, conversation_id, prior_plan, revision):
    if _propose_plan is None:
        return None, None
    return _propose_plan(
        host_user_id,
        brief,
        conversation_id=conversation_id,
        prior_plan=prior_plan,
        revision=revision,
    )


def daily_budget_override(instance_id: str) -> float | None:
    if _daily_budget_override is None:
        return None
    return _daily_budget_override(instance_id)
