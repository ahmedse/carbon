"""Django model for the durable Human Task Inbox (P3-09).

A :class:`HumanTask` is the durable record of a *pending human approval* — the
inbox item an operator/auditor inspects and a designated authority approves or
declines.  Approving a task mints a bound :class:`ai.models.approval.ApprovalGrant`
(the P3-06 business-approval concept) pinning the exact material effect.

The three authorization concepts stay strictly separate (P3-06):

=========================  ==============================  ==============================
Concept                    Code location                  Meaning
=========================  ==============================  ==============================
Authorization              :mod:`ai.pdp`                  *Can* the principal act?
**Business approval**      :mod:`ai.models.approval`      *Has a human approved this
                                                          specific effect?* (grant)
**Human task**             **this module**                *Is there a durable, un-expired
                                                          approval request awaiting a
                                                          designated authority?*
User consent               ``CommandBoundary`` stage 7    *Is the human confirming right
                                                          now?* (RULE_21, per-action)
=========================  ==============================  ==============================

The task carries every dimension needed to mint a fully-bound grant on approval:
consequence, objects+revisions, before/after, evidence, reversibility, required
authority, expiry, alternatives — plus the grant-pinning tuple
``(process_version, capability, capability_version, canonical_args,
object_revisions, evidence_digest, effect_limits)``.

This module is host-side: it imports Django only.  The engine never imports it
(RULE_20 / ADR-0007); the boundary reads the inbox at the host-side grant stage.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import models
from django.utils import timezone

from .base import AppScopeMixin, generate_uuid

# ── Closed ``status`` vocabulary ──────────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DECLINED = "declined"
STATUS_EXPIRED = "expired"
STATUS_CANCELLED = "cancelled"
VALID_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_APPROVED, STATUS_DECLINED, STATUS_EXPIRED, STATUS_CANCELLED}
)
# Statuses a task is *inert* in — no approve/decline is allowed.
TERMINAL_STATUSES = frozenset(
    {STATUS_APPROVED, STATUS_DECLINED, STATUS_EXPIRED, STATUS_CANCELLED}
)

# ── Closed ``reversibility`` vocabulary ───────────────────────────────────
REVERSIBLE = "reversible"
IRREVERSIBLE = "irreversible"
PARTIALLY_REVERSIBLE = "partially_reversible"
REVERSIBLE_WITH_SIDE_EFFECTS = "reversible_with_side_effects"
VALID_REVERSIBILITY = frozenset(
    {REVERSIBLE, IRREVERSIBLE, PARTIALLY_REVERSIBLE, REVERSIBLE_WITH_SIDE_EFFECTS}
)


def compute_evidence_digest(evidence: Any) -> str:
    """Return a stable ``sha256:…`` digest over the evidence the approver saw.

    The digest is computed over a canonical, sorted, compact JSON encoding so
    that two structurally-equal evidence bags always hash identically.  It is
    stored on the task and copied verbatim into the bound
    :class:`~ai.models.approval.ApprovalGrant.evidence_digest`, so a task and the
    effect it authorizes agree on the *exact* evidence tuple.
    """
    payload = json.dumps(
        evidence or {}, sort_keys=True, separators=(",", ":"), default=str
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HumanTask(AppScopeMixin):
    """A durable, human-approval inbox item.

    Inherits :class:`AppScopeMixin` for CBAC partitioning.  ``id`` is a UUID
    string pk via ``generate_uuid``.  ``run_id``/``step_id`` are plain string
    columns mirroring how :class:`ai.models.core.RunStep` links to ``Run`` —
    no Django ``ForeignKey`` is introduced, keeping the layer relocatable.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    # ── Linkage (mirrors RunStep → Run) ──────────────────────────────────
    run_id = models.TextField(db_index=True, blank=True, default="")
    step_id = models.TextField(blank=True, default="")
    process_instance = models.CharField(
        max_length=36, null=True, blank=True, db_index=True,
    )

    # ── Grant-pinning dimensions (exact ApprovalGrant contract) ──────────
    capability = models.TextField(db_index=True, default="")
    process_version = models.TextField(default="")
    capability_version = models.TextField(default="")
    canonical_args = models.JSONField(default=dict)
    object_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    object_type = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    effect_limits = models.JSONField(default=dict)

    # ── Rich consequence fields ──────────────────────────────────────────
    consequence = models.TextField()
    objects_revisions_json = models.JSONField(default=dict)  # {object_id: revision}
    before_json = models.JSONField(default=dict)
    after_json = models.JSONField(default=dict)
    evidence_json = models.JSONField(default=dict)
    evidence_digest = models.TextField(default="")
    reversibility = models.TextField()
    required_authority = models.TextField(db_index=True)  # capability/role key
    expires_at = models.DateTimeField()
    alternatives_json = models.JSONField(default=list)

    # ── Lifecycle ────────────────────────────────────────────────────────
    status = models.TextField(default=STATUS_PENDING, db_index=True)
    grant_id = models.TextField(null=True, blank=True, db_index=True)
    decided_by = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "expires_at"], name="ai_humantask_inbox_idx"
            ),
            models.Index(
                fields=["required_authority", "status"],
                name="ai_humantask_authority_idx",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<HumanTask id={self.id!r} capability={self.capability!r} "
            f"status={self.status!r} required_authority={self.required_authority!r}>"
        )

    def is_expired(self, now=None) -> bool:
        """True when the task's ``expires_at`` is not in the future."""
        now = now or timezone.now()
        return self.expires_at <= now

    def is_pending(self, now=None) -> bool:
        """True when the task is still actionable (pending and un-expired)."""
        return self.status == STATUS_PENDING and not self.is_expired(now)
