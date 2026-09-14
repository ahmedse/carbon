"""Django model for the autonomy dial — :class:`AutonomyOverride` (P3-05a).

A per-``(process_id, step_id, org_unit)`` override of the autonomy level the
process definition declares for a step. The definition's step ``autonomy`` is
the default; an override raises or lowers it for a specific org unit.

``autonomy`` is one of the six process-schema levels (``observe``, ``propose``,
``act_confirm``, ``act_notify``, ``act_silent``, ``human_only`` — declared in
``ai.models.process.VALID_AUTONOMY``). The PDP's runtime 3-level dial
(``ai.pdp._AUTONOMY_LEVELS``) is a *different, narrower* mapping; reconciling the
two is deferred to P3-07a. The registry stores/validates the full 6-level dial.

This module is host-side; the engine never imports it (RULE_20 / ADR-0007).
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

AUTONOMY_HUMAN_ONLY = "human_only"


class AutonomyOverride(AppScopeMixin):
    """One autonomy-dial override for a step × org unit (durable, host-side)."""

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    process_id = models.TextField(db_index=True)
    step_id = models.TextField()
    org_unit = models.TextField(default="")
    autonomy = models.TextField(default=AUTONOMY_HUMAN_ONLY)
    set_by = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["process_id", "step_id", "org_unit"]
        indexes = [
            models.Index(
                fields=["process_id", "step_id"],
                name="ai_autonomy_lookup_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["process_id", "step_id", "org_unit"],
                name="ai_autonomy_override_unique",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<AutonomyOverride id={self.id!r} process_id={self.process_id!r} "
            f"step_id={self.step_id!r} org_unit={self.org_unit!r} "
            f"autonomy={self.autonomy!r}>"
        )
