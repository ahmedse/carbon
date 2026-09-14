"""P3-07b — Durable append-only run journal (workflow/activity split).

``RunJournalEntry`` is the single source of truth for a run's *activities*
(LLM calls and host calls).  It is append-only: entries are never mutated —
progress is recorded by appending the next ``status`` with the next monotonic
``sequence``.  The deterministic workflow driver (``ai.workflow``) folds the
entries in ``sequence`` order to reconstruct exactly one current status per
activity, no matter how many times the fold is replayed.

This is the *run-level* journal (activity granularity).  The step-level event
journal (``ai.models.step_journal.StepJournalEntry``) records the finer event
vocabulary (queued / started / retried / completed …) that the replay fold and
consent routing use; the two are complementary and never overlap.

Host-side: imports Django only.  The engine never imports this module
(RULE_20 / ADR-0007).
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

# ── Closed activity-kind vocabulary ────────────────────────────────────────

ACTIVITY_KIND_LLM = "llm"
ACTIVITY_KIND_HOST = "host"

ACTIVITY_KINDS: frozenset[str] = frozenset(
    {ACTIVITY_KIND_LLM, ACTIVITY_KIND_HOST}
)

# ── Closed activity-status vocabulary ──────────────────────────────────────

STATUS_PLANNED = "planned"
STATUS_DISPATCHED = "dispatched"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_OUTCOME_UNKNOWN = "outcome_unknown"
STATUS_SKIPPED = "skipped"

ACTIVITY_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_PLANNED,
        STATUS_DISPATCHED,
        STATUS_SUCCEEDED,
        STATUS_FAILED,
        STATUS_OUTCOME_UNKNOWN,
        STATUS_SKIPPED,
    }
)


class RunJournalEntry(AppScopeMixin):
    """One append-only journal record for a single activity (LLM/host call).

    ``sequence`` is a monotonic per-run counter giving the journal a total
    deterministic order; the driver folds entries by it.  ``attempt`` is the
    0-based dispatch attempt (bounded by the retry cap).  ``operation_id`` is
    the stable downstream-effect id shared with ``RunStep.operation_id`` for
    authoritative read-back (P3-08).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    run_id = models.TextField(db_index=True)
    step_id = models.TextField()
    step_index = models.IntegerField()
    activity_kind = models.TextField()
    sequence = models.IntegerField()
    operation_id = models.TextField(default="")
    canonical_inputs_json = models.JSONField(null=True, blank=True)
    status = models.TextField(default=STATUS_PLANNED)
    result_json = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    attempt = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["sequence"]
        indexes = [
            models.Index(
                fields=["run_id", "step_id"], name="ai_runjournal_step_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run_id", "step_id", "sequence"],
                name="ai_runjournal_seq_uniq",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<RunJournalEntry run_id={self.run_id!r} step_id={self.step_id!r} "
            f"seq={self.sequence} kind={self.activity_kind!r} "
            f"status={self.status!r}>"
        )
