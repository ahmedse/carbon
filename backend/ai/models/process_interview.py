"""Django model for the process-owner interview kit — :class:`ProcessInterview` (P3-04).

Durable provenance for the interview that fills a process definition: the
question bank, the recorded answers (each carrying ``who`` / ``when``), and the
owner's final signature (``signed_by`` / ``signed_at`` / ``signature_digest``).

Provenance is deliberately kept OUT of the ``ProcessDefinition.definition``
document — the definition schema declares ``additionalProperties:false``, so
adding an ad-hoc top-level ``provenance`` key would break the contract. This
model is the durable side-channel instead.

This module is host-side; the engine never imports it (RULE_20 / ADR-0007).
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

STATUS_OPEN = "open"
STATUS_SIGNED = "signed"
VALID_STATUSES = frozenset({STATUS_OPEN, STATUS_SIGNED})


class ProcessInterview(AppScopeMixin):
    """Durable interview transcript + signature for one process definition.

    ``answers`` is a JSON list of provenance records::

        {"question_id": "sla", "answer": "...", "answered_by": "...",
         "answered_at": "<iso-8601>"}

    ``questions`` is the question bank snapshot used when the interview was
    created (so a later pack edit cannot retroactively rewrite history).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    process_id = models.TextField(db_index=True)
    questions = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    status = models.TextField(default=STATUS_OPEN, db_index=True)
    signed_by = models.TextField(default="")
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_digest = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["process_id", "-created_at"]
        indexes = [
            models.Index(
                fields=["process_id", "status"],
                name="ai_interview_lookup_idx",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<ProcessInterview id={self.id!r} process_id={self.process_id!r} "
            f"status={self.status!r} signed_by={self.signed_by!r}>"
        )
