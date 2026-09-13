"""Django model for PDP v1 decisions (P2-07).

One row is written per ``PolicyDecisionPoint.decide()`` call so every
authorization decision is queryable for audit. Follows the vendored
``app_label="ai"`` convention and inherits :class:`AppScopeMixin` for CBAC
partitioning (app_identifier / org_unit_id / host_user_id / visibility).
"""

from django.db import models

from .base import AppScopeMixin, generate_uuid


class PolicyDecisionRow(AppScopeMixin):
    """A single persisted PDP authorization decision (P2-07).

    ``decision`` stores the string value of :class:`ai.engine.ports.policy.Decision`
    (``allow`` / ``allow_with_confirmation`` / ``ask`` / ``defer`` / ``refuse``).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    principal = models.TextField(db_index=True)
    action = models.TextField(db_index=True)
    resource_objects = models.JSONField(default=list)
    decision = models.TextField(db_index=True)
    reason = models.TextField(default="")
    policy_version = models.TextField(default="")
    autonomy = models.TextField(default="human_only")
    process_state = models.JSONField(null=True, blank=True)
    budget = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]

    def __repr__(self) -> str:
        return (
            f"<PolicyDecisionRow id={self.id!r} {self.principal!r} "
            f"{self.action!r} -> {self.decision!r}>"
        )
