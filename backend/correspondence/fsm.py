"""Correspondence workflow state machine (Phase OF-5).

The CORE of the e-Office Correspondence engine: submit/approve/reject/send_back/
cancel/resubmit transitions with DQ gating, approver routing, governance-event
emission, and notifications.

Layering: this module NEVER imports ``people``. Approvers are resolved via
``routing.resolve_step_approvers`` (which reaches ``people.Employee`` through
``apps.get_model``), and the DQ gate is invoked through
``dq.typed_gate.check_instances`` with a ``model_label`` string.
"""

import copy
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from catalog.audit_utils import emit_governance_event
from dq.typed_gate import check_instances

from .exceptions import (
    CommentRequired,
    InvalidTransition,
    NotActorError,
    SubmissionBlocked,
)
from .models import ACTIONABLE, Correspondence, CorrespondenceEvent
from .notifications import notify
from .policies import PolicyNotFound, freeze_policy, resolve_policy
from .registry import allocate_reference_no
from .routing import apply_delegation, resolve_step_approvers

DEFAULT_PREFIX = 'CRS'


# ── condition evaluation ───────────────────────────────────────────────────

def _condition_met(condition, payload) -> bool:
    """Evaluate a step ``condition`` JSON like ``{"days": {">": 5}}`` against
    ``payload``. All fields/operators must pass (AND). Missing field -> False;
    empty/None condition -> True. Supports ``> < >= <= == !=`` (``==``/``!=``
    compare as strings)."""
    if not condition:
        return True
    payload = payload or {}
    for field, operators in condition.items():
        value = payload.get(field)
        if value is None:
            return False
        for op, expected in (operators or {}).items():
            if not _compare(op, value, expected):
                return False
    return True


def _compare(op, actual, expected) -> bool:
    if op == '>':
        return actual > expected
    if op == '<':
        return actual < expected
    if op == '>=':
        return actual >= expected
    if op == '<=':
        return actual <= expected
    if op == '==':
        return str(actual) == str(expected)
    if op == '!=':
        return str(actual) != str(expected)
    return False


# ── timeline / audit helpers ───────────────────────────────────────────────

def _add_event(corr, by, event_type, from_status, to_status, payload=None):
    """Create + save the next-seeded ``CorrespondenceEvent``. Caller owns the
    transaction."""
    last = (
        CorrespondenceEvent.objects.filter(correspondence=corr)
        .order_by('-seq')
        .first()
    )
    seq = (last.seq + 1) if last else 1
    return CorrespondenceEvent.objects.create(
        correspondence=corr,
        seq=seq,
        actor=by,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        payload=payload or {},
    )


def _governance(corr, by, action, old_status=None):
    """Emit a best-effort governance event for a status change. ``old_status``
    is captured by the caller before mutating ``corr.status``."""
    emit_governance_event(
        entity_type='correspondence',
        entity_id=corr.id,
        action=action,
        before={'status': old_status} if old_status is not None else {},
        after={'status': corr.status},
        user=by,
    )


# ── approver-chain construction ────────────────────────────────────────────

def _step_fields(step):
    """Normalize a ``WorkflowPolicyStep`` (object) or a frozen snapshot dict
    into a plain dict of routing fields."""
    if isinstance(step, dict):
        return {
            'order': step.get('order'),
            'role': step.get('role'),
            'intent': step.get('intent'),
            'specific_user_id': step.get('specific_user_id'),
            'skip_if_self': step.get('skip_if_self', False),
            'auto_approve': step.get('auto_approve', False),
            'can_skip': step.get('can_skip', False),
            'condition': step.get('condition'),
        }
    return {
        'order': step.order,
        'role': step.role,
        'intent': step.intent,
        'specific_user_id': step.specific_user_id,
        'skip_if_self': step.skip_if_self,
        'auto_approve': step.auto_approve,
        'can_skip': step.can_skip,
        'condition': step.condition,
    }


def _resolve_user_ids(fields, *, corr, by):
    """Resolve approvers for a step then apply active delegations."""
    step = SimpleNamespace(
        role=fields['role'],
        specific_user_id=fields['specific_user_id'],
        skip_if_self=fields['skip_if_self'],
    )
    user_ids = resolve_step_approvers(
        step=step, requester=by, org_unit=corr.org_unit,
    )
    return apply_delegation(
        user_ids, corr_type=corr.corr_type, org_unit=corr.org_unit,
    )


def _build_chain(steps, *, corr, by):
    """Build the ``approver_chain`` from ordered, active steps. Condition-failed
    steps become ``decision='skip'``/``skipped='condition'``; others carry their
    resolved ``user_ids`` and step flags."""
    chain = []
    for step in steps:
        fields = _step_fields(step)
        if not _condition_met(fields['condition'], corr.payload):
            chain.append({
                'order': fields['order'],
                'role': fields['role'],
                'intent': fields['intent'],
                'user_ids': [],
                'skipped': 'condition',
                'decision': 'skip',
            })
            continue
        chain.append({
            'order': fields['order'],
            'role': fields['role'],
            'intent': fields['intent'],
            'user_ids': _resolve_user_ids(fields, corr=corr, by=by),
            'auto_approve': fields['auto_approve'],
            'can_skip': fields['can_skip'],
            'skip_if_self': fields['skip_if_self'],
        })
    return chain


def _advance(chain, from_step, now):
    """Auto-pass condition-skipped / auto-approve / empty-approver steps and
    return ``(current_step, current_approver_ids)`` for the next actionable
    step, or ``(len(chain), [])`` if none remain. Mutates chain in place."""
    i = from_step + 1
    while i < len(chain):
        entry = chain[i]
        if entry.get('decision') == 'skip':
            i += 1
            continue
        if entry.get('auto_approve') or not entry.get('user_ids'):
            entry['decision'] = 'auto'
            entry['decided_at'] = now.isoformat()
            i += 1
            continue
        return i, list(entry['user_ids'])
    return len(chain), []


# ── transitions ────────────────────────────────────────────────────────────

def submit_correspondence(*, corr, by, subject=None, subject_label=None,
                          prefix=DEFAULT_PREFIX):
    """draft -> submitted | approved. Freezes policy, allocates the reference
    number, gates the subject through DQ, builds the approver chain and hands
    off to the first actionable step."""
    with transaction.atomic():
        if corr.status != 'draft':
            raise InvalidTransition(
                f'Cannot submit from status {corr.status!r} (expected draft)'
            )

        policy = resolve_policy(corr_type=corr.corr_type, org_unit=corr.org_unit)
        frozen = freeze_policy(policy)
        corr.policy_id = frozen['policy_id']
        corr.policy_version = frozen['policy_version']
        corr.policy_snapshot = frozen['policy_snapshot']
        corr.reference_no = allocate_reference_no(
            corr_type=corr.corr_type,
            org_unit=corr.org_unit,
            numbering_format=policy.numbering_format,
            prefix=prefix,
        )

        # DQ write gate on the subject instance.
        if subject_label and subject is not None:
            verdict = check_instances(subject_label, [subject], mode='write')
            if verdict['summary']['blocked'] > 0:
                failures = [
                    failure
                    for rv in verdict['row_verdicts']
                    for failure in rv.get('failures', [])
                ]
                raise SubmissionBlocked(failures)

        now = timezone.now()
        steps = policy.steps.filter(is_active=True).order_by('order')
        chain = _build_chain(steps, corr=corr, by=by)
        current_step, current_approver_ids = _advance(chain, -1, now)
        corr.approver_chain = chain

        if current_approver_ids:
            corr.status = 'submitted'
            corr.current_step = current_step
            corr.current_approver_ids = current_approver_ids
        else:
            corr.status = 'approved'
            corr.resolved_at = now
            corr.current_step = len(chain)
            corr.current_approver_ids = []

        corr.save()
        _add_event(corr, by, 'submitted', 'draft', corr.status)
        _governance(corr, by, 'submit', old_status='draft')

        if corr.status == 'submitted':
            notify(
                corr,
                user_ids=corr.current_approver_ids,
                type='awaiting_action',
                title=f'Action needed on {corr.reference_no}',
                body=corr.title,
            )
        return corr


def _decide(corr, by, *, decision, event_type, governance_action, action_label,
            verb, comment=None):
    """Shared step-decision transition for approve/acknowledge/review. Marks the
    current step with ``decision`` and advances to the next actionable step
    exactly like ``approve`` — but never sets ``decision='approved'`` on the step
    for non-approval intents (an internal memo is *acknowledged*, not approved)."""
    with transaction.atomic():
        if corr.status not in ACTIONABLE:
            raise InvalidTransition(
                f'Cannot {action_label} from status {corr.status!r}'
            )
        if by.id not in corr.current_approver_ids:
            raise NotActorError(
                f'User {by.id} is not a current approver of {corr.reference_no}'
            )

        old_status = corr.status
        now = timezone.now()
        chain = copy.deepcopy(corr.approver_chain or [])
        step = dict(chain[corr.current_step])
        step['decision'] = decision
        step['decided_by'] = by.id
        step['decided_at'] = now.isoformat()
        step['comment'] = comment or ''
        chain[corr.current_step] = step

        current_step, current_approver_ids = _advance(chain, corr.current_step, now)
        corr.approver_chain = chain

        if current_approver_ids:
            corr.status = 'in_review'
            corr.current_step = current_step
            corr.current_approver_ids = current_approver_ids
        else:
            corr.status = 'approved'
            corr.resolved_at = now
            corr.current_step = len(chain)
            corr.current_approver_ids = []

        corr.save()
        _add_event(corr, by, event_type, old_status, corr.status,
                   {'comment': comment or ''})
        _governance(corr, by, governance_action, old_status=old_status)

        notify(
            corr,
            user_ids=[corr.requester_id],
            type='status_changed',
            title=f'Your request {corr.reference_no} was {verb}',
            body=corr.title,
        )
        if corr.status == 'in_review':
            notify(
                corr,
                user_ids=corr.current_approver_ids,
                type='awaiting_action',
                title=f'Action needed on {corr.reference_no}',
                body=corr.title,
            )
        return corr


def approve(corr, by, comment=None):
    """submitted|in_review -> in_review|approved. The current approver marks the
    step approved and the workflow advances to the next actionable step."""
    return _decide(
        corr, by, decision='approved', event_type='approved',
        governance_action='approve', action_label='approve',
        verb='approved', comment=comment,
    )


def acknowledge(corr, by, comment=None):
    """Mark the current step acknowledged and advance (never "approved")."""
    return _decide(
        corr, by, decision='acknowledged', event_type='acknowledged',
        governance_action='acknowledge', action_label='acknowledge',
        verb='acknowledged', comment=comment,
    )


def review(corr, by, comment=None):
    """Mark the current step reviewed and advance (never "approved")."""
    return _decide(
        corr, by, decision='reviewed', event_type='reviewed',
        governance_action='review', action_label='review',
        verb='reviewed', comment=comment,
    )


def act(corr, by, intent, comment=None):
    """Generic action dispatcher for the approve/acknowledge/review family so the
    API layer needs a single action route rather than one per intent."""
    if intent == 'approve':
        return approve(corr, by, comment)
    if intent == 'acknowledge':
        return acknowledge(corr, by, comment)
    if intent == 'review':
        return review(corr, by, comment)
    raise InvalidTransition(f'Unsupported action intent {intent!r}')


def reject(corr, by, comment):
    """submitted|in_review -> rejected. A comment is required."""
    comment = (comment or '').strip()
    if not comment:
        raise CommentRequired('A comment is required to reject a request')

    with transaction.atomic():
        if corr.status not in ACTIONABLE:
            raise InvalidTransition(
                f'Cannot reject from status {corr.status!r}'
            )
        if by.id not in corr.current_approver_ids:
            raise NotActorError(
                f'User {by.id} is not a current approver of {corr.reference_no}'
            )

        old_status = corr.status
        now = timezone.now()
        chain = copy.deepcopy(corr.approver_chain or [])
        step = dict(chain[corr.current_step])
        step['decision'] = 'rejected'
        step['decided_by'] = by.id
        step['decided_at'] = now.isoformat()
        step['comment'] = comment
        chain[corr.current_step] = step
        corr.approver_chain = chain
        corr.status = 'rejected'
        corr.resolved_at = now
        corr.current_approver_ids = []
        corr.save()

        _add_event(corr, by, 'rejected', old_status, corr.status,
                   {'comment': comment})
        _governance(corr, by, 'reject', old_status=old_status)

        notify(
            corr,
            user_ids=[corr.requester_id],
            type='status_changed',
            title=f'Your request {corr.reference_no} was rejected',
            body=comment,
        )
        return corr


def send_back(corr, by, comment):
    """submitted|in_review -> sent_back. A comment is required."""
    comment = (comment or '').strip()
    if not comment:
        raise CommentRequired('A comment is required to send a request back')

    with transaction.atomic():
        if corr.status not in ACTIONABLE:
            raise InvalidTransition(
                f'Cannot send back from status {corr.status!r}'
            )
        if by.id not in corr.current_approver_ids:
            raise NotActorError(
                f'User {by.id} is not a current approver of {corr.reference_no}'
            )

        old_status = corr.status
        now = timezone.now()
        chain = copy.deepcopy(corr.approver_chain or [])
        step = dict(chain[corr.current_step])
        step['decision'] = 'sent_back'
        step['decided_by'] = by.id
        step['decided_at'] = now.isoformat()
        step['comment'] = comment
        chain[corr.current_step] = step
        corr.approver_chain = chain
        corr.status = 'sent_back'
        corr.current_approver_ids = []
        corr.save()

        _add_event(corr, by, 'sent_back', old_status, corr.status,
                   {'comment': comment})
        _governance(corr, by, 'send_back', old_status=old_status)

        notify(
            corr,
            user_ids=[corr.requester_id],
            type='status_changed',
            title=f'Your request {corr.reference_no} was sent back',
            body=comment,
        )
        return corr


def cancel(corr, by):
    """Requester cancels from a non-terminal state -> cancelled."""
    with transaction.atomic():
        if by.id != corr.requester_id:
            raise NotActorError('Only the requester may cancel a request')
        if corr.status not in ('draft', 'submitted', 'in_review', 'sent_back'):
            raise InvalidTransition(
                f'Cannot cancel from status {corr.status!r}'
            )

        old_status = corr.status
        approver_ids = list(corr.current_approver_ids or [])
        corr.status = 'cancelled'
        corr.resolved_at = timezone.now()
        corr.current_approver_ids = []
        corr.save()

        _add_event(corr, by, 'cancelled', old_status, corr.status)
        _governance(corr, by, 'cancel', old_status=old_status)

        if approver_ids:
            notify(
                corr,
                user_ids=approver_ids,
                type='cancelled',
                title=f'{corr.reference_no} was cancelled',
                body=corr.title,
            )
        return corr


def resubmit(corr, by, subject=None, subject_label=None):
    """Requester resubmits a sent-back request. Re-runs routing against the
    frozen policy snapshot (no reference re-allocation, no policy re-freeze)."""
    with transaction.atomic():
        if by.id != corr.requester_id:
            raise NotActorError('Only the requester may resubmit a request')
        if corr.status != 'sent_back':
            raise InvalidTransition(
                f'Cannot resubmit from status {corr.status!r}'
            )

        if subject_label and subject is not None:
            verdict = check_instances(subject_label, [subject], mode='write')
            if verdict['summary']['blocked'] > 0:
                failures = [
                    failure
                    for rv in verdict['row_verdicts']
                    for failure in rv.get('failures', [])
                ]
                raise SubmissionBlocked(failures)

        old_status = corr.status
        now = timezone.now()
        steps = corr.policy_snapshot.get('steps', [])
        chain = _build_chain(steps, corr=corr, by=by)
        current_step, current_approver_ids = _advance(chain, -1, now)
        corr.approver_chain = chain

        if current_approver_ids:
            corr.status = 'submitted'
            corr.current_step = current_step
            corr.current_approver_ids = current_approver_ids
        else:
            corr.status = 'approved'
            corr.resolved_at = now
            corr.current_step = len(chain)
            corr.current_approver_ids = []

        corr.save()
        _add_event(corr, by, 'resubmitted', old_status, corr.status)
        _governance(corr, by, 'resubmit', old_status=old_status)

        if corr.status == 'submitted':
            notify(
                corr,
                user_ids=corr.current_approver_ids,
                type='awaiting_action',
                title=f'Action needed on {corr.reference_no}',
                body=corr.title,
            )
        return corr
