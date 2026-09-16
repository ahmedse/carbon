"""P3-07b — Durable append-only step journal + workflow/activity split.

A step journal entry is a single, immutable event in a run's execution
history.  The journal — not the free-text ``RunStep.status`` — is the single
source of truth for deterministic replay: folding the events in
``sequence`` order reconstructs exactly one ``step_state``/``status`` pair
for the step, regardless of how many times the fold is run.

Host-side: imports Django only.  The engine never imports this module
(RULE_20 / ADR-0007).

Event vocabulary (RULE_23): product terms only, never engine class names.
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

# ── Closed journal event vocabulary (product terms, RULE_23) ────────────────

EVENT_STEP_QUEUED = "step_queued"
EVENT_STEP_STARTED = "step_started"
EVENT_STEP_RETRIED = "step_retried"
EVENT_STEP_COMPLETED = "step_completed"
EVENT_STEP_FAILED = "step_failed"
EVENT_STEP_CONSENT_REQUESTED = "step_consent_requested"
EVENT_STEP_CONSENT_GRANTED = "step_consent_granted"
EVENT_STEP_CONSENT_DECLINED = "step_consent_declined"
EVENT_OUTCOME_UNKNOWN = "outcome_unknown"

# W-7 per-step controls — user-initiated workflow-control markers. These are
# NON-EFFECT events: they re-queue or transition a step's control state but
# never commit a host effect, so the deterministic replay fold ignores them
# for effect reconstruction (see ``CONTROL_JOURNAL_EVENTS``).
EVENT_STEP_SKIPPED = "step_skipped"
EVENT_STEP_CANCELLED = "step_cancelled"
EVENT_STEP_PAUSED = "step_paused"
EVENT_STEP_RESUMED = "step_resumed"

# ADR-0034 / W-3 — control-flow decisions (non-effect; journaled for replay).
EVENT_GUARD_EVAL = "guard_eval"
EVENT_EDGE_CHOSEN = "edge_chosen"
EVENT_LOOP_ITER = "loop_iter"
EVENT_HEAL_PROPOSED = "heal_proposed"
EVENT_COMPENSATION_QUEUED = "compensation_queued"
EVENT_WAIT_FIRED = "wait_fired"

STEP_JOURNAL_EVENTS: frozenset[str] = frozenset(
    {
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_RETRIED,
        EVENT_STEP_COMPLETED,
        EVENT_STEP_FAILED,
        EVENT_STEP_CONSENT_REQUESTED,
        EVENT_STEP_CONSENT_GRANTED,
        EVENT_STEP_CONSENT_DECLINED,
        EVENT_OUTCOME_UNKNOWN,
        EVENT_STEP_SKIPPED,
        EVENT_STEP_CANCELLED,
        EVENT_STEP_PAUSED,
        EVENT_STEP_RESUMED,
        EVENT_GUARD_EVAL,
        EVENT_EDGE_CHOSEN,
        EVENT_LOOP_ITER,
        EVENT_HEAL_PROPOSED,
        EVENT_COMPENSATION_QUEUED,
        EVENT_WAIT_FIRED,
    }
)

# W-7 control markers: non-effect events the replay fold treats as no-ops for
# effect reconstruction (they never commit or re-run a host effect). ``retry``
# is deliberately excluded — it is already a first-class fold transition
# (increments ``retry_count`` and re-queues the step to ``pending``).
CONTROL_JOURNAL_EVENTS: frozenset[str] = frozenset(
    {
        EVENT_STEP_SKIPPED,
        EVENT_STEP_CANCELLED,
        EVENT_STEP_PAUSED,
        EVENT_STEP_RESUMED,
        EVENT_GUARD_EVAL,
        EVENT_EDGE_CHOSEN,
        EVENT_LOOP_ITER,
        EVENT_HEAL_PROPOSED,
        EVENT_COMPENSATION_QUEUED,
        EVENT_WAIT_FIRED,
    }
)

# Terminal *committed* events: a step whose journal ends in one of these has a
# committed outcome and must NEVER be re-executed (exactly-one-effect).  Note
# ``step_failed`` is deliberately excluded — a failed activity has NOT
# committed and may be retried under the bounded RETRY_* policy.
TERMINAL_JOURNAL_EVENTS: frozenset[str] = frozenset(
    {
        EVENT_STEP_COMPLETED,
        EVENT_STEP_CONSENT_DECLINED,
    }
)

# ── Workflow / activity split ──────────────────────────────────────────────

# A step is an *activity* when it performs a non-deterministic side effect
# (an LLM call or a host call).  A *workflow* step is pure deterministic
# orchestration — sequencing / phase / consent routing — replayable with no
# side effects.  Only activities are retried, emit ``outcome_unknown`` on
# timeout, and consume the consent gate.
STEP_KIND_WORKFLOW = "workflow"
STEP_KIND_ACTIVITY = "activity"

STEP_KINDS: frozenset[str] = frozenset({STEP_KIND_WORKFLOW, STEP_KIND_ACTIVITY})


class StepJournalEntry(AppScopeMixin):
    """One append-only journal event for a run step.

    ``sequence`` is a monotonically increasing per-run counter that gives the
    journal a deterministic, total ordering — the replay fold depends on it.
    ``payload`` carries event-specific detail (e.g. the retry ``attempt`` or
    the dispatch ``operation_id`` for an ``outcome_unknown``).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    run_id = models.TextField(db_index=True)
    step_id = models.TextField()
    event_type = models.TextField()
    sequence = models.IntegerField()
    payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        ordering = ["run_id", "sequence"]
        indexes = [
            models.Index(
                fields=["run_id", "sequence"], name="ai_journal_run_seq_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run_id", "sequence"],
                name="ai_journal_run_seq_uniq",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<StepJournalEntry run_id={self.run_id!r} step_id={self.step_id!r} "
            f"seq={self.sequence} event={self.event_type!r}>"
        )
