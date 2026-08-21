"""Phase 24-D — DQ feedback event ledger.

One source-agnostic row per captured feedback signal from the DQ surface
(rule accept / reject / correct, DQResult outcome flags, drift events).

The row is *data*, never an action: nothing in ``ai/feedback/`` mutates
production rules (RULE_21 / requires_confirmation). The pipeline only
records signals into the KG ledger, flags retirement candidates for human
confirmation, and can be reverted (idempotent + revertible gate).

ADR-0008: no new Django apps — this model lives in the ``ai`` app.
The ``ai`` package imports nothing from domain apps (see ``ai/models/base.py``);
references to DQ rows are stored as plain IDs + name snapshots, resolved
lazily by callers (the DQ views/commands that capture them).
"""

import uuid

from django.db import models

EVENT_TYPES = [
    ("suggest_accepted", "Suggestion Accepted"),
    ("suggest_rejected", "Suggestion Rejected"),
    ("rule_corrected", "Rule Corrected"),
    ("result_always_pass", "Result Always-Pass"),
    ("result_false_positive", "Result False-Positive"),
    ("drift_detected", "Drift Detected"),
]

SOURCES = [
    ("suggest", "Suggest"),
    ("nl_check", "NL Check"),
    ("result", "DQ Result"),
    ("drift", "Drift"),
]

REVIEW_STATUSES = [
    ("pending", "Pending"),
    ("confirmed", "Confirmed"),
    ("dismissed", "Dismissed"),
]


class DqFeedbackEvent(models.Model):
    """Captured DQ feedback signal awaiting (or having received) pipeline effects."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_identifier = models.CharField(max_length=64, default="carbon", db_index=True)
    org_unit_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    event_type = models.CharField(max_length=24, choices=EVENT_TYPES)
    signal_type = models.CharField(
        max_length=20,
        help_text="Engine signal taxonomy: explicit_positive | explicit_negative | "
                  "correction | retire_candidate | drift",
    )
    quality_score = models.FloatField(default=0.7)
    source = models.CharField(max_length=16, choices=SOURCES)

    # References to DQ rows as plain IDs + snapshots (ai imports nothing from dq).
    suggestion_id = models.BigIntegerField(null=True, blank=True)
    rule_id = models.BigIntegerField(null=True, blank=True)
    rule_name = models.CharField(max_length=255, blank=True, default="")
    table_id = models.BigIntegerField(null=True, blank=True)
    table_name = models.CharField(max_length=255, blank=True, default="")
    field_name = models.CharField(max_length=255, blank=True, default="")
    message_id = models.CharField(
        max_length=64, blank=True, default="",
        help_text="AIMessage uuid (str) when the signal originates in the AI workspace.",
    )
    user_id = models.BigIntegerField(null=True, blank=True)

    payload = models.JSONField(
        default=dict, blank=True,
        help_text="Full context: suggestion definition, rule params, result stats, drift details.",
    )
    correction_text = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=255, unique=True)

    # Pipeline lifecycle (idempotent + revertible).
    applied_at = models.DateTimeField(null=True, blank=True)
    effect = models.JSONField(default=dict, blank=True)
    revert_payload = models.JSONField(default=dict, blank=True)

    # Retirement-candidate flagging (human confirms via confirm_review).
    needs_review = models.BooleanField(default=False)
    review_status = models.CharField(
        max_length=12, choices=REVIEW_STATUSES, default="pending")
    reviewed_by = models.CharField(max_length=64, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "applied_at"]),
            models.Index(fields=["rule_id", "applied_at"]),
            models.Index(fields=["table_id", "applied_at"]),
        ]
        verbose_name = "DQ Feedback Event"
        verbose_name_plural = "DQ Feedback Events"

    def __str__(self):
        scope = self.rule_name or self.field_name or self.table_name or "dq"
        return f"{self.event_type} · {scope} · {self.idempotency_key}"
