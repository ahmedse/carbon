"""Host-side Human Task Inbox service (P3-09).

``TaskInbox`` is the durable-approval-task service: it creates rich inbox items
from a boundary ``requires_grant``/``human_task`` step, lists pending tasks,
and — on an explicit human action — approves (minting a bound
:class:`~ai.models.approval.ApprovalGrant` via the P3-06 field contract) or
declines.  Approving is **never** implicit (RULE_21): the only path to a grant
is a call to :meth:`TaskInbox.approve` by a principal holding the task's
``required_authority`` capability.

Fail-closed invariants (Principle 1):

* authority is validated with :func:`accounts.capabilities.has_capability` —
  a principal without the required capability is refused;
* an expired task is refused (and marked expired);
* a non-pending task is refused (idempotent approve never re-mints a grant);
* the grant is minted with the *exact* pinned tuple carried by the task, so any
  material change to consequence/objects/evidence/expiry invalidates it.

The engine never imports this module (RULE_20 / ADR-0007).  The boundary only
receives the enqueuer callable by constructor injection (``task_enqueuer=``).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.capabilities import has_capability
from ai.governance.review_authority import (
    DEFAULT_REQUIRED_AUTHORITY,
    resolve_required_authority,
)
from ai.models.approval import STATUS_ACTIVE, ApprovalGrant, canonicalize_args
from ai.models.human_task import (
    IRREVERSIBLE,
    STATUS_APPROVED,
    STATUS_DECLINED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    VALID_REVERSIBILITY,
    HumanTask,
    compute_evidence_digest,
)

logger = logging.getLogger("carbon.ai.task_inbox")

# Defaults for the boundary enqueuer seam (documented, policy-overridable).
DEFAULT_REVERSIBILITY = IRREVERSIBLE  # conservative fail-closed default
DEFAULT_TASK_TTL = timedelta(days=7)


# ── Fail-closed exceptions (map 1:1 to HTTP in the API layer) ─────────────

class TaskInboxError(Exception):
    """Base class for all fail-closed inbox refusals."""


class TaskNotFound(TaskInboxError):
    def __init__(self, task_id: Any) -> None:
        super().__init__(f"task {task_id!r} not found")
        self.task_id = task_id


class TaskExpired(TaskInboxError):
    def __init__(self, task_id: Any) -> None:
        super().__init__(f"task {task_id!r} is expired")
        self.task_id = task_id


class TaskNotPending(TaskInboxError):
    def __init__(self, task_id: Any, status: str) -> None:
        super().__init__(f"task {task_id!r} is not pending (status={status!r})")
        self.task_id = task_id
        self.status = status


class UnauthorizedApprover(TaskInboxError):
    def __init__(self, task_id: Any, required_authority: str) -> None:
        super().__init__(
            f"principal lacks required authority {required_authority!r} "
            f"for task {task_id!r}"
        )
        self.task_id = task_id
        self.required_authority = required_authority


class InvalidTask(TaskInboxError):
    """The supplied task fields are not a valid, mint-able approval request."""


# ── The service ───────────────────────────────────────────────────────────

class TaskInbox:
    """Durable human-approval task service (host-side)."""

    # ── creation ─────────────────────────────────────────────────────────

    def create_task(
        self,
        *,
        consequence: str,
        objects_revisions: dict | None = None,
        before: dict | None = None,
        after: dict | None = None,
        evidence: dict | None = None,
        evidence_digest: str | None = None,
        reversibility: str,
        required_authority: str,
        expires_at,
        alternatives: list | None = None,
        run_id: str | None = None,
        step_id: str | None = None,
        capability: str = "",
        process_version: str = "",
        capability_version: str = "",
        canonical_args: dict | None = None,
        object_id: str | None = None,
        object_type: str | None = None,
        process_instance: str | None = None,
        effect_limits: dict | None = None,
        app_identifier: str = "carbon",
        org_unit_id: Any = None,
        host_user_id: Any = None,
        visibility: str = "private",
    ) -> HumanTask:
        """Create and persist a pending inbox task, validating the closed vocab.

        ``evidence_digest`` may be supplied explicitly (the boundary already
        carries one); when omitted it is computed over ``evidence`` so the
        later minted grant and the re-run effect agree on the exact tuple.
        """
        if not consequence or not str(consequence).strip():
            raise InvalidTask("consequence is required")
        if reversibility not in VALID_REVERSIBILITY:
            raise InvalidTask(
                f"reversibility {reversibility!r} must be one of "
                f"{sorted(VALID_REVERSIBILITY)}"
            )
        if not required_authority:
            raise InvalidTask("required_authority is required")

        objects_revisions = dict(objects_revisions or {})
        evidence = dict(evidence or {})
        digest = evidence_digest or compute_evidence_digest(evidence)

        return HumanTask.objects.create(
            app_identifier=app_identifier,
            org_unit_id=org_unit_id,
            host_user_id=host_user_id,
            visibility=visibility,
            run_id=run_id or "",
            step_id=step_id or "",
            process_instance=process_instance or None,
            capability=capability or "",
            process_version=process_version or "",
            capability_version=capability_version or "",
            canonical_args=canonicalize_args(canonical_args or {}),
            object_id=object_id or None,
            object_type=object_type or None,
            effect_limits=dict(effect_limits or {}),
            consequence=consequence,
            objects_revisions_json=objects_revisions,
            before_json=dict(before or {}),
            after_json=dict(after or {}),
            evidence_json=evidence,
            evidence_digest=digest,
            reversibility=reversibility,
            required_authority=required_authority,
            expires_at=expires_at,
            alternatives_json=list(alternatives or []),
            status=STATUS_PENDING,
        )

    # ── reading ──────────────────────────────────────────────────────────

    def list_pending(self, user=None, now=None):
        """Return actionable pending tasks, oldest-first.

        When ``user`` is supplied the queryset is CBAC-scoped via
        ``accounts.ai_scoping.scope_ai_queryset`` (superusers/global admins see
        all; otherwise visibility + org-subtree narrowing) and further narrowed
        to tasks whose ``required_authority`` the principal holds — unless they
        are an ``ai:operator`` / ``ai:auditor`` (console readers see the full
        scoped inbox).  Expired tasks are excluded at read time regardless of
        whether ``expire_stale`` has run.
        """
        now = now or timezone.now()
        qs = HumanTask.objects.filter(
            status=STATUS_PENDING, expires_at__gt=now
        )
        if user is not None:
            from accounts.ai_scoping import scope_ai_queryset
            from accounts.capabilities import (
                AI_AUDITOR,
                AI_OPERATOR,
                get_user_capabilities,
                has_any_capability,
            )

            qs = scope_ai_queryset(qs, user)
            if not has_any_capability(user, {AI_OPERATOR.key, AI_AUDITOR.key}):
                caps = get_user_capabilities(user)
                if "*" in caps:
                    pass
                else:
                    qs = qs.filter(required_authority__in=caps)
        return qs.order_by("created_at")

    def get(self, task_id: Any) -> HumanTask:
        """Return a single task or raise :class:`TaskNotFound` (fail-closed)."""
        try:
            return HumanTask.objects.get(pk=task_id)
        except HumanTask.DoesNotExist:
            raise TaskNotFound(task_id)

    # ── deciding (RULE_21: explicit human action only) ──────────────────

    def _mark_expired_outside_atomic(self, task_id: Any, now) -> None:
        """Fail-closed expiry pre-check, run OUTSIDE the decide transaction.

        Persists ``status=expired`` then raises :class:`TaskExpired`.  This must
        not run inside the caller's ``transaction.atomic``: the raised exception
        rolls that transaction back and would silently undo the status write,
        leaving the task stuck ``pending``.  Doing it here makes the "expired
        task is refused (and marked expired)" side effect durable.
        """
        task = self.get(task_id)
        if task.is_expired(now):
            HumanTask.objects.filter(pk=task_id, status=STATUS_PENDING).update(
                status=STATUS_EXPIRED
            )
            raise TaskExpired(task_id)

    def approve(self, user, task_id: Any, now=None) -> HumanTask:
        """Approve a pending task, minting a bound ``ApprovalGrant``.

        Fail-closed on: not found, expired, not pending, or wrong authority.
        Idempotent: re-approving an already-approved task returns the existing
        decision and never mints a second grant.
        """
        now = now or timezone.now()
        self._mark_expired_outside_atomic(task_id, now)
        with transaction.atomic():
            try:
                task = HumanTask.objects.select_for_update().get(pk=task_id)
            except HumanTask.DoesNotExist:
                raise TaskNotFound(task_id)
            return self._decide_locked(task, user, approve=True, now=now)

    def decline(self, user, task_id: Any, reason: str = "", now=None) -> HumanTask:
        """Decline a pending task (no grant is minted).

        Fail-closed on: not found, expired, not pending, or wrong authority.
        Idempotent: re-declining an already-declined task is a no-op.
        """
        now = now or timezone.now()
        self._mark_expired_outside_atomic(task_id, now)
        with transaction.atomic():
            try:
                task = HumanTask.objects.select_for_update().get(pk=task_id)
            except HumanTask.DoesNotExist:
                raise TaskNotFound(task_id)
            return self._decide_locked(
                task, user, approve=False, reason=reason, now=now
            )

    def _decide_locked(
        self,
        task: HumanTask,
        user,
        *,
        approve: bool,
        reason: str = "",
        now=None,
    ) -> HumanTask:
        """Shared decide path for an already-locked task (fail-closed)."""
        now = now or timezone.now()

        # Idempotency: a terminal decision is returned as-is, never re-applied.
        if approve and task.status == STATUS_APPROVED and task.grant_id:
            return task
        if not approve and task.status == STATUS_DECLINED:
            return task

        if task.is_expired(now):
            task.status = STATUS_EXPIRED
            task.save(update_fields=["status", "updated_at"])
            raise TaskExpired(task.id)

        if task.status != STATUS_PENDING:
            raise TaskNotPending(task.id, task.status)

        if not has_capability(user, task.required_authority):
            raise UnauthorizedApprover(task.id, task.required_authority)

        if approve:
            grant = self._mint_grant(task, user)
            task.status = STATUS_APPROVED
            task.grant_id = grant.id
        else:
            task.status = STATUS_DECLINED
            task.decline_reason = reason or ""
        task.decided_by = self._principal(user)
        task.decided_at = now
        task.save()
        return task

    def _mint_grant(self, task: HumanTask, user) -> ApprovalGrant:
        """Mint the bound ``ApprovalGrant`` from the task's exact pinned tuple.

        The grant is created in the task's CBAC scope and pins every material
        dimension: process_version, capability, capability_version,
        canonical_args, object_revisions, evidence_digest, effect_limits,
        object identity, and expiry.
        """
        return ApprovalGrant.objects.create(
            app_identifier=task.app_identifier,
            org_unit_id=task.org_unit_id,
            host_user_id=task.host_user_id,
            visibility=task.visibility,
            process_instance=task.process_instance or None,
            object_id=task.object_id or None,
            object_type=task.object_type or None,
            process_version=task.process_version or "",
            capability=task.capability or "",
            capability_version=task.capability_version or "",
            canonical_args=task.canonical_args,
            object_revisions=task.objects_revisions_json,
            evidence_digest=task.evidence_digest or "",
            effect_limits=task.effect_limits,
            expires_at=task.expires_at,
            status=STATUS_ACTIVE,
            granted_by=self._principal(user),
        )

    def expire_stale(self, now=None) -> int:
        """Mark every past-expiry pending task expired (idempotent).

        Returns the number of tasks transitioned to ``expired``.
        """
        now = now or timezone.now()
        return HumanTask.objects.filter(
            status=STATUS_PENDING, expires_at__lte=now
        ).update(status=STATUS_EXPIRED)

    @staticmethod
    def _principal(user) -> str:
        return getattr(user, "username", None) or str(getattr(user, "pk", ""))


# ── Boundary enqueuer seam (host-side; wired via ``task_enqueuer=``) ──────

async def enqueue_inbox_task(command, *, now=None) -> str | None:
    """Enqueue a durable :class:`HumanTask` for a grant-required command.

    This is the host-side enqueuer the boundary calls when a ``requires_grant``
    capability has no matching grant yet — routing the effect to the inbox
    instead of hard-refusing.  It returns the new task ``id`` (or ``None`` when
    the command carries no capability, so the boundary still refuses).

    The rich fields not carried by :class:`~ai.command_boundary.Command`
    (consequence, before/after, reversibility, authority, expiry) are
    constructed with conservative, documented defaults — the canonical
    before/after snapshot, evidence digest, and pinned grant tuple all
    round-trip through the task so an approved grant authorizes exactly this
    effect.
    """
    from asgiref.sync import sync_to_async

    capability = getattr(command, "capability", "") or ""
    if not capability:
        return None

    now = now or timezone.now()
    from ai.instance_registry import resolve_default_app_identifier

    inbox = TaskInbox()
    task = await sync_to_async(inbox.create_task, thread_sensitive=True)(
        run_id=getattr(command, "run_id", None) or None,
        step_id=getattr(command, "step_id", None) or None,
        consequence=(
            f"Human approval required for "
            f"{getattr(command, 'action', '') or getattr(command, 'tool', '')} "
            f"on {getattr(command, 'objects', None) or []}"
        ),
        objects_revisions=dict(getattr(command, "object_revisions", None) or {}),
        before={},
        after={
            "params": canonicalize_args(dict(getattr(command, "params", None) or {})),
            "objects": list(getattr(command, "objects", None) or []),
        },
        evidence={"evidence_digest": getattr(command, "evidence_digest", "") or ""},
        evidence_digest=getattr(command, "evidence_digest", "") or "",
        reversibility=DEFAULT_REVERSIBILITY,
        required_authority=resolve_required_authority(capability),
        expires_at=now + DEFAULT_TASK_TTL,
        alternatives=[],
        capability=capability,
        process_version=getattr(command, "process_version", "") or "",
        capability_version=getattr(command, "capability_version", "") or "",
        canonical_args=dict(getattr(command, "params", None) or {}),
        object_id=getattr(command, "object_id", "") or None,
        object_type=getattr(command, "object_type", "") or None,
        process_instance=getattr(command, "process_instance", "") or None,
        effect_limits={},
        app_identifier=resolve_default_app_identifier(),
        visibility="global",
    )
    logger.info("enqueued human task %s for capability %s", task.id, capability)
    return task.id


__all__ = [
    "TaskInbox",
    "TaskInboxError",
    "TaskNotFound",
    "TaskExpired",
    "TaskNotPending",
    "UnauthorizedApprover",
    "InvalidTask",
    "enqueue_inbox_task",
    "DEFAULT_REQUIRED_AUTHORITY",
    "DEFAULT_REVERSIBILITY",
    "DEFAULT_TASK_TTL",
]
