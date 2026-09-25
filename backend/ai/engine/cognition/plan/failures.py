"""Typed step failures.

Every failed step carries one class, and the class decides what happens next:

* ``transient``          — timeout / rate limit / 5xx. The only class a run retries.
* ``invalid_args``       — the host rejected the arguments; repaired once in-step.
* ``missing_binding``    — a path value the step needs was not bound (typed choice
                           or nothing to bind from). Never retried or replanned.
* ``blocked_dependency`` — a step it depends on did not complete. Not executed.
* ``no_effect``          — the tool returned data but executed nothing.
* ``permanent``          — any other deterministic error.

Pure helpers (RULE_20).
"""
from __future__ import annotations

from typing import Any

TRANSIENT = "transient"
INVALID_ARGS = "invalid_args"
MISSING_BINDING = "missing_binding"
BLOCKED_DEPENDENCY = "blocked_dependency"
NO_EFFECT = "no_effect"
PERMANENT = "permanent"

NO_EFFECT_ERROR = "Nothing was executed: this procedure has no runnable step, so the step produced no result."


def is_retryable(failure_class: str) -> bool:
    return failure_class == TRANSIENT


def is_replannable(failure_class: str) -> bool:
    """A veto worth one more attempt: nothing deterministic already decided it."""
    return failure_class in ("", PERMANENT, TRANSIENT)


def _returned_nothing(tool_output: Any) -> bool:
    return isinstance(tool_output, dict) and tool_output.get("executed") is False


def classify_step_failure(step: Any, result: Any, *, plan_source: str = "") -> str:
    """The class for ``result``. Marks a recipe-only return as ``no_effect``.

    Empty string when the step did not fail.
    """
    if getattr(result, "failure_class", ""):
        return result.failure_class
    if getattr(result, "paused", False):
        return ""
    if (
        not getattr(result, "error", None)
        and getattr(step, "tool_name", None) == "invoke_skill"
        and plan_source != "skill"
        and _returned_nothing(getattr(result, "tool_output", None))
    ):
        result.error = NO_EFFECT_ERROR
        result.critic_verdict = "veto"
        return NO_EFFECT
    error = getattr(result, "error", None)
    if not error and getattr(result, "critic_verdict", "") != "veto":
        return ""
    from ai.engine.cognition.plan.catalog_args import (
        READ_GAP,
        WRITE_HELD,
        is_invalid_argument_error,
    )
    from ai.engine.workflow.retry import classify_error

    text = str(error or "")
    if text == WRITE_HELD:
        return BLOCKED_DEPENDENCY
    if text == READ_GAP or is_invalid_argument_error(text):
        return INVALID_ARGS
    if text.startswith("[cancelled]"):
        return PERMANENT
    tool_output = getattr(result, "tool_output", None)
    if isinstance(tool_output, dict) and tool_output.get("error"):
        text = str(tool_output.get("error"))
    if classify_error(text) in ("transient", "timeout"):
        return TRANSIENT
    return PERMANENT
