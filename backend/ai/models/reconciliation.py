"""Durable escalation record for inconclusive outcome reconciliation (P3-08).

When the reconciliation worker (``ai/reconciliation.py``) cannot
deterministically resolve an ``outcome_unknown`` step's authoritative
read-back, it records an escalation here. The future Human Task Inbox
(P3-09, NOT built yet) will surface these rows to an ``operator`` role —
this module stores the durable record ONLY, no UI.

Host-side: imports Django only. The engine never imports this module
(RULE_20 / ADR-0007).
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

# Authoritative read-back statuses (the reconciler's closed vocabulary).
READBACK_COMMITTED = "committed"   # downstream effect verified present
READBACK_ABSENT = "absent"         # downstream effect definitively absent/failed
READBACK_UNKNOWN = "unknown"       # inconclusive → escalate (fail-closed)


class ReconciliationEscalation(AppScopeMixin):
    """One durable operator-inbox item per inconclusive step.

    Keyed uniquely on ``(run_id, step_id)`` so the scheduler can run
    repeatedly without stacking duplicate escalations for the same step.
    ``AppScopeMixin`` provides CBAC tenant/org scope (``app_identifier`` /
    ``org_unit_id`` / ``host_user_id`` / ``visibility``).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    run_id = models.TextField(db_index=True)
    step_id = models.TextField()
    process_id = models.TextField(default="")
    operation_id = models.TextField(default="")
    read_back_status = models.TextField(default=READBACK_UNKNOWN)
    read_back_detail = models.TextField(blank=True, default="")
    reason = models.TextField(blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run_id", "step_id"],
                name="ai_reconcile_step_uniq",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<ReconciliationEscalation id={self.id!r} run_id={self.run_id!r} "
            f"step_id={self.step_id!r} status={self.read_back_status!r}>"
        )
