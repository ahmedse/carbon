"""Django model for durable business approval — :class:`ApprovalGrant` (P3-06).

A grant is the *business approval* concept, strictly separate from the other two
authorization concepts that already exist:

=========================  ==============================  ==============================
Concept                    Code location                  Meaning
=========================  ==============================  ==============================
Authorization              :mod:`ai.pdp`                  *Can* the principal take this
                                                          action? (default-deny)
**Business approval**      **this module**                *Has a human approved this
                                                          specific effect?* (grant)
User consent               ``CommandBoundary`` stage 7    *Is the human confirming right
                           (``consent``) / RULE_21       now?* (per-action)
=========================  ==============================  ==============================

A grant binds *every* material dimension of the effect it authorizes. Any change
to any of them invalidates the grant (fail-closed): the grant only authorizes the
exact ``(process_version, capability_version, canonical_args, object_revisions,
evidence_digest)`` tuple within its ``effect_limits`` and before ``expires_at``.

This module is host-side: it imports Django only. The engine never imports it
(RULE_20 / ADR-0007); the host reads the grant at the boundary ``grant`` stage.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone

from .base import AppScopeMixin, generate_uuid

# Allowed ``status`` values (Text, documented not enforced by a constraint).
STATUS_ACTIVE = "active"
STATUS_CONSUMED = "consumed"
STATUS_REVOKED = "revoked"
STATUS_SUPERSEDED = "superseded"
VALID_STATUSES = frozenset(
    {STATUS_ACTIVE, STATUS_CONSUMED, STATUS_REVOKED, STATUS_SUPERSEDED}
)


def canonicalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic, sorted/key-normalized form of ``args``.

    The canonical form is what a grant is minted against and what a request is
    compared against: dict keys are coerced to strings and sorted recursively;
    list items are canonicalized in place (order preserved, but each element
    normalized). Two structurally-equal argument bags therefore hash/compare
    identically regardless of insertion order or int/str key spelling.
    """
    if isinstance(args, dict):
        return {
            str(key): canonicalize_args(value)
            for key, value in sorted(args.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(args, (list, tuple)):
        return [canonicalize_args(item) for item in args]
    return args


class ApprovalGrant(AppScopeMixin):
    """A durable, human-minted approval for a specific material effect.

    Inherits :class:`AppScopeMixin` for CBAC partitioning (``app_identifier`` /
    ``org_unit_id`` / ``host_user_id`` / ``visibility``). ``id`` is a UUID
    string pk via ``generate_uuid``.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    # Future FK → ProcessInstance (P3-07a). Until then a UUID string, with a
    # generic ``object_id``/``object_type`` pair so P3-06 is testable standalone.
    process_instance = models.CharField(
        max_length=36, null=True, blank=True, db_index=True,
    )
    object_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    object_type = models.CharField(max_length=128, null=True, blank=True, db_index=True)

    # ── Pinned dimensions of the authorized effect ────────────────────────
    process_version = models.TextField(default="")
    capability = models.TextField(db_index=True)
    capability_version = models.TextField(default="")
    canonical_args = models.JSONField(default=dict)
    object_revisions = models.JSONField(default=dict)
    evidence_digest = models.TextField(default="")
    effect_limits = models.JSONField(default=dict)

    # ── Lifecycle ─────────────────────────────────────────────────────────
    expires_at = models.DateTimeField()  # required — expired grants are inert
    status = models.TextField(default=STATUS_ACTIVE, db_index=True)
    granted_by = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["capability", "status", "expires_at"],
                name="ai_approval_active_idx",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<ApprovalGrant id={self.id!r} capability={self.capability!r} "
            f"process_version={self.process_version!r} status={self.status!r}>"
        )

    def is_expired(self, now=None) -> bool:
        """True when the grant's ``expires_at`` is not in the future."""
        now = now or timezone.now()
        return self.expires_at <= now

    @classmethod
    def find_active(
        cls,
        *,
        capability: str,
        process_version: str,
        capability_version: str,
        canonical_args: dict[str, Any],
        object_revisions: dict[str, Any],
        evidence_digest: str,
        object_id: str | None = None,
        object_type: str | None = None,
        process_instance: str | None = None,
        now=None,
    ) -> "ApprovalGrant | None":
        """Return the single active, unexpired, fully-matching grant or ``None``.

        Fail-closed by construction: *every* pinned dimension must match exactly.
        Any mismatch on ``(process_version, capability_version, canonical_args,
        object_revisions, evidence_digest)`` — or a mismatched object identity —
        returns ``None`` so the caller refuses.
        """
        now = now or timezone.now()
        qs = cls.objects.filter(
            status=STATUS_ACTIVE,
            expires_at__gt=now,
            capability=capability,
            process_version=process_version,
            capability_version=capability_version,
            canonical_args=canonical_args,
            object_revisions=object_revisions,
            evidence_digest=evidence_digest,
        )
        if process_instance:
            qs = qs.filter(process_instance=process_instance)
        if object_id:
            qs = qs.filter(object_id=object_id)
        if object_type:
            qs = qs.filter(object_type=object_type)
        return qs.first()

    def revoke(self, *, now=None) -> None:
        """Mark the grant revoked (idempotent, timezone-aware)."""
        now = now or timezone.now()
        self.status = STATUS_REVOKED
        self.revoked_at = now
        self.save(update_fields=["status", "revoked_at"])
