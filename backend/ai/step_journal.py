"""P3-07b — Deterministic step journal service (host-side).

The append-only journal and the pure replay fold that reconstructs a step's
state from its events.  Host-side only: imports Django ORM + the pure
``ai.run_machine`` state alphabet; the engine never imports this module
(RULE_20 / ADR-0007).

The fold (:meth:`StepJournal.reconstruct`) is the single source of truth for
replay — it maps the *sequence* of journal events to one deterministic
``(step_state, status, retry_count, outcome, consent)`` snapshot.  Replay and
resume consume that snapshot; they never re-derive state from free-text
``RunStep.status`` heuristics.
"""

from __future__ import annotations

from django.db.models import Max

from ai import run_machine
from ai.models.step_journal import (
    CONTROL_JOURNAL_EVENTS,
    EVENT_OUTCOME_UNKNOWN,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_CONSENT_DECLINED,
    EVENT_STEP_CONSENT_GRANTED,
    EVENT_STEP_FAILED,
    EVENT_STEP_QUEUED,
    EVENT_STEP_RETRIED,
    EVENT_STEP_STARTED,
    EVENT_STEP_CONSENT_REQUESTED,
    STEP_JOURNAL_EVENTS,
    TERMINAL_JOURNAL_EVENTS,
    StepJournalEntry,
)

# Legacy engine status string used for an executing step (mirrors the
# host service's ``running`` status).
STATUS_RUNNING = "running"

# Event kind → (step_state, legacy status) the fold lands on.  Workflow
# pre-execution states (``ready``) are intentionally un-journaled: the fold
# treats ``step_queued → step_started`` as ``planned → executing`` directly,
# so an interrupted pre-execution step reconstructs as ``planned`` (safe to
# re-queue).
_STATE_BY_EVENT: dict[str, tuple[str, str]] = {
    EVENT_STEP_QUEUED: (run_machine.RUN_PLANNED, "pending"),
    EVENT_STEP_STARTED: (run_machine.RUN_EXECUTING, STATUS_RUNNING),
    EVENT_STEP_COMPLETED: (run_machine.RUN_SUCCEEDED, "completed"),
    EVENT_STEP_FAILED: (run_machine.RUN_FAILED, "failed"),
    EVENT_STEP_CONSENT_REQUESTED: (
        run_machine.RUN_AWAITING_APPROVAL,
        "awaiting_approval",
    ),
    EVENT_OUTCOME_UNKNOWN: (run_machine.RUN_OUTCOME_UNKNOWN, STATUS_RUNNING),
}

_OUTCOME_BY_EVENT: dict[str, str] = {
    EVENT_STEP_COMPLETED: "succeeded",
    EVENT_STEP_FAILED: "failed",
    EVENT_OUTCOME_UNKNOWN: "outcome_unknown",
}


def canonical_step_id(step) -> str:
    """Canonical journal key for a step: ``step_id`` when set, else ``step_index``.

    Steps created through ``PlansService.begin_step`` carry a stable
    ``step_id``; steps materialized directly (``create_plan`` / ``fork_plan``
    / templates) leave ``step_id`` empty and are keyed by ``step_index``.
    This keeps the journal key unambiguous for both shapes.
    """
    sid = getattr(step, "step_id", "")
    if sid:
        return str(sid)
    return str(getattr(step, "step_index", ""))


class StepJournal:
    """Append-only journal + deterministic replay fold."""

    @staticmethod
    def next_sequence(run_id: str) -> int:
        """Next monotonic sequence number for ``run_id`` (single-writer per run)."""
        agg = StepJournalEntry.objects.filter(run_id=run_id).aggregate(
            m=Max("sequence")
        )
        return (agg["m"] or 0) + 1

    @classmethod
    def append(cls, run_id, step_id, event_type, payload=None):
        """Append one journal event; returns the persisted row.

        Rejects events outside the closed product-term vocabulary (RULE_23).
        """
        if event_type not in STEP_JOURNAL_EVENTS:
            raise ValueError(
                f"Unknown step journal event {event_type!r}; expected one of "
                f"{sorted(STEP_JOURNAL_EVENTS)}."
            )
        sequence = cls.next_sequence(run_id)
        return StepJournalEntry.objects.create(
            run_id=str(run_id),
            step_id=str(step_id),
            event_type=event_type,
            sequence=sequence,
            payload=payload or {},
        )

    @staticmethod
    def for_step(run_id, step_id) -> list:
        """Return a step's journal entries, ascending by sequence."""
        return list(
            StepJournalEntry.objects.filter(
                run_id=str(run_id), step_id=str(step_id)
            ).order_by("sequence")
        )

    @staticmethod
    def reconstruct(entries) -> dict:
        """Fold journal entries (ascending sequence) → deterministic state.

        Pure function: the same event sequence always yields the same dict.
        Returns ``{step_state, status, retry_count, outcome, consent,
        last_event, committed}`` where ``committed`` is True only when the
        last event is a terminal *committed* outcome (``step_completed`` /
        ``step_consent_declined``) — the exactly-one-effect guard.
        """
        step_state = run_machine.RUN_PLANNED
        status = "pending"
        retry_count = 0
        outcome = ""
        consent = None
        last_event = None

        for entry in entries:
            if entry.event_type in CONTROL_JOURNAL_EVENTS:
                # W-7 workflow-control markers (skip/cancel/pause/resume) are
                # non-effect events: they never commit or re-run a host effect,
                # so they are transparent to the exactly-one-effect fold. Skip
                # them without touching ``last_event`` so ``committed`` still
                # reflects the last real effect outcome.
                continue
            last_event = entry.event_type
            if entry.event_type == EVENT_STEP_RETRIED:
                retry_count += 1
                step_state, status = run_machine.RUN_PLANNED, "pending"
                continue
            if entry.event_type == EVENT_STEP_CONSENT_GRANTED:
                consent = "granted"
                step_state, status = (
                    run_machine.RUN_AWAITING_APPROVAL,
                    "awaiting_approval",
                )
                continue
            if entry.event_type == EVENT_STEP_CONSENT_DECLINED:
                consent = "declined"
                step_state, status, outcome = (
                    run_machine.RUN_CANCELLED,
                    "skipped",
                    "declined",
                )
                continue
            mapped = _STATE_BY_EVENT.get(entry.event_type)
            if mapped is not None:
                step_state, status = mapped
                outcome = _OUTCOME_BY_EVENT.get(entry.event_type, "")

        return {
            "step_state": step_state,
            "status": status,
            "retry_count": retry_count,
            "outcome": outcome,
            "consent": consent,
            "last_event": last_event,
            "committed": last_event in TERMINAL_JOURNAL_EVENTS,
        }
