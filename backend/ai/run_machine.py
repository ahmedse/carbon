"""P3-07a — Durable run machine (host-side state machine).

A closed, auditable state-transition surface for the plan/run lifecycle,
decoupled from the legacy ``Run.status`` / ``RunStep.status`` free-text
strings that the engine and frontend already own.

Canonical lifecycle (spec)::

    planned → awaiting_approval → ready → executing
        → succeeded | failed | outcome_unknown
        → awaiting_reconciliation | cancelled

This module is **pure**: it defines the states, the closed transition table,
and transition helpers. It imports nothing from Django or the engine — the
durable persistence hooks live in ``ai/plans_service.py`` (``begin_step`` /
``advance_step`` / ``reconcile_outcome`` / ``preflight``).

The closed transition table is the single source of truth; the property test
(``ai/tests/test_run_machine.py``) enumerates it and asserts that every edge
outside the table is rejected and every edge inside it is accepted.
"""

from __future__ import annotations

from typing import Any

# ── Canonical states ────────────────────────────────────────────────────────

RUN_PLANNED = "planned"
RUN_AWAITING_APPROVAL = "awaiting_approval"
RUN_READY = "ready"
RUN_EXECUTING = "executing"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"
RUN_OUTCOME_UNKNOWN = "outcome_unknown"
RUN_AWAITING_RECONCILIATION = "awaiting_reconciliation"
RUN_CANCELLED = "cancelled"

RUN_STATES: frozenset[str] = frozenset(
    {
        RUN_PLANNED,
        RUN_AWAITING_APPROVAL,
        RUN_READY,
        RUN_EXECUTING,
        RUN_SUCCEEDED,
        RUN_FAILED,
        RUN_OUTCOME_UNKNOWN,
        RUN_AWAITING_RECONCILIATION,
        RUN_CANCELLED,
    }
)

# Step states mirror the run states exactly (a step may also pass through
# ``awaiting_approval`` when per-step consent is required — spec note).
STEP_STATES: frozenset[str] = RUN_STATES

# Terminal states: no outgoing edge, never re-enter the machine.
TERMINAL_STATES: frozenset[str] = frozenset(
    {RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED}
)

# Outcome → the state a step/run lands in immediately after execution.
OUTCOME_STATES: dict[str, str] = {
    "succeeded": RUN_SUCCEEDED,
    "failed": RUN_FAILED,
    "outcome_unknown": RUN_OUTCOME_UNKNOWN,
}

# ── Closed transition tables ────────────────────────────────────────────────
#
# The table is CLOSED: any (current, target) pair NOT present here is an
# illegal transition and is rejected. ``cancelled`` is reachable from every
# non-terminal state (a kill switch or user cancel may stop a run at any
# point before a terminal success/failure).

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    RUN_PLANNED: frozenset({RUN_AWAITING_APPROVAL, RUN_CANCELLED}),
    RUN_AWAITING_APPROVAL: frozenset({RUN_READY, RUN_CANCELLED}),
    RUN_READY: frozenset({RUN_EXECUTING, RUN_CANCELLED}),
    RUN_EXECUTING: frozenset(
        {RUN_SUCCEEDED, RUN_FAILED, RUN_OUTCOME_UNKNOWN, RUN_CANCELLED}
    ),
    RUN_OUTCOME_UNKNOWN: frozenset({RUN_AWAITING_RECONCILIATION, RUN_CANCELLED}),
    RUN_AWAITING_RECONCILIATION: frozenset(
        {RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED}
    ),
    RUN_SUCCEEDED: frozenset(),
    RUN_FAILED: frozenset(),
    RUN_CANCELLED: frozenset(),
}

# Step table differs only at the entry: a step may go ``planned → ready``
# directly (no consent gate) or via ``awaiting_approval`` when consent is
# required.
STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    RUN_PLANNED: frozenset({RUN_READY, RUN_AWAITING_APPROVAL, RUN_CANCELLED}),
    RUN_AWAITING_APPROVAL: frozenset({RUN_READY, RUN_CANCELLED}),
    RUN_READY: frozenset({RUN_EXECUTING, RUN_CANCELLED}),
    RUN_EXECUTING: frozenset(
        {RUN_SUCCEEDED, RUN_FAILED, RUN_OUTCOME_UNKNOWN, RUN_CANCELLED}
    ),
    RUN_OUTCOME_UNKNOWN: frozenset({RUN_AWAITING_RECONCILIATION, RUN_CANCELLED}),
    RUN_AWAITING_RECONCILIATION: frozenset(
        {RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED}
    ),
    RUN_SUCCEEDED: frozenset(),
    RUN_FAILED: frozenset(),
    RUN_CANCELLED: frozenset(),
}

_TRANSITIONS: dict[str, dict[str, frozenset[str]]] = {
    "run": RUN_TRANSITIONS,
    "step": STEP_TRANSITIONS,
}


class InvalidStateTransition(Exception):
    """Raised when a state transition is not in the closed transition table."""


def _table(kind: str) -> dict[str, frozenset[str]]:
    try:
        return _TRANSITIONS[kind]
    except KeyError:
        raise ValueError(
            f"Unknown transition kind {kind!r}; expected 'run' or 'step'."
        ) from None


def can_transition(current: str, new: str, *, kind: str = "run") -> bool:
    """Return True when ``current → new`` is a legal edge for ``kind``."""
    return new in _table(kind).get(current, frozenset())


def allowed_targets(current: str, *, kind: str = "run") -> frozenset[str]:
    """Return the set of states reachable from ``current`` in one step."""
    return _table(kind).get(current, frozenset())


def is_terminal(state: str) -> bool:
    """Return True when ``state`` is a terminal state (no outgoing edge)."""
    return state in TERMINAL_STATES


def assert_transition(current: str, new: str, *, kind: str = "run") -> None:
    """Raise :class:`InvalidStateTransition` when ``current → new`` is illegal."""
    if not can_transition(current, new, kind=kind):
        raise InvalidStateTransition(
            f"Illegal {kind} transition {current!r} → {new!r}."
        )


def transition(
    instance: Any,
    new: str,
    *,
    kind: str = "run",
    field: str = "state",
) -> Any:
    """Validate ``instance.{field} → new`` and assign it (no save).

    Callers persist via ``instance.save(update_fields=[field, "updated_at"])``
    so the write is explicit and auditable. Raises
    :class:`InvalidStateTransition` on an illegal edge.
    """
    current = getattr(instance, field)
    assert_transition(current, new, kind=kind)
    setattr(instance, field, new)
    return instance


def validate_state(value: str, *, kind: str = "run") -> bool:
    """Return True when ``value`` is a known state for ``kind``.

    Run and step share the same state alphabet, so ``kind`` is accepted for
    symmetry but not used beyond validating it is a known kind.
    """
    _table(kind)  # raises on unknown kind
    return value in RUN_STATES
