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

from accounts.capabilities import has_capability
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
from .routing import (
    apply_delegation,
    resolve_step_approvers,
    users_with_capability,
)

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

def _lock_correspondence(corr):
    """Lock and refresh ``corr`` in place. Must run inside ``transaction.atomic()``.

    Serializes concurrent step decisions on the same correspondence so a
    duplex approve cannot both pass the actionable-status guard and emit
    duplicate timeline events (J-LV-11). Preserves the caller's instance
    identity so ignored return values of approve()/reject()/… still see
    the post-transition state.
    """
    Correspondence.objects.select_for_update().get(pk=corr.pk)
    corr.refresh_from_db()
    return corr


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
            'fallback_role': step.get('fallback_role', ''),
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
        'fallback_role': step.fallback_role,
        'intent': step.intent,
        'specific_user_id': step.specific_user_id,
        'skip_if_self': step.skip_if_self,
        'auto_approve': step.auto_approve,
        'can_skip': step.can_skip,
        'condition': step.condition,
    }


def _approvers_for_role(role, fields, *, corr, by):
    """Approvers for one role, after ``skip_if_self`` and delegation."""
    step = SimpleNamespace(
        role=role,
        specific_user_id=fields['specific_user_id'],
        skip_if_self=False,
    )
    candidates = resolve_step_approvers(
        step=step, requester=by, org_unit=corr.org_unit,
    )
    user_ids = candidates
    if fields['skip_if_self'] and by is not None:
        user_ids = [uid for uid in user_ids if uid != by.id]
    user_ids = apply_delegation(
        user_ids, corr_type=corr.corr_type, org_unit=corr.org_unit,
    )
    return user_ids, bool(candidates)


def _resolve_user_ids(fields, *, corr, by):
    """Resolve a step's approvers, falling back to the declared backup role.

    Returns ``(user_ids, role_is_filled, routed_via)``. ``role_is_filled``
    says whether the role named anyone at all, BEFORE ``skip_if_self`` dropped
    the requester — "the policy says this approver sits their own request out"
    and "nobody holds this role" both end in an empty list but mean opposite
    things, and only the first one may pass unapproved.

    When the primary role is unfilled and the policy names a ``fallback_role``
    (leave goes to HR for an employee with no manager), the backup answers and
    ``routed_via`` records that it did.
    """
    user_ids, role_is_filled = _approvers_for_role(
        fields['role'], fields, corr=corr, by=by,
    )
    if role_is_filled:
        return user_ids, True, 'role'

    fallback = str(fields.get('fallback_role') or '').strip()
    if not fallback:
        return user_ids, False, 'role'
    user_ids, fallback_is_filled = _approvers_for_role(
        fallback, fields, corr=corr, by=by,
    )
    return user_ids, fallback_is_filled, 'fallback' if fallback_is_filled else 'role'


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
        user_ids, role_is_filled, routed_via = _resolve_user_ids(
            fields, corr=corr, by=by,
        )
        entry = {
            'order': fields['order'],
            'role': fields['role'],
            'intent': fields['intent'],
            'user_ids': user_ids,
            'auto_approve': fields['auto_approve'],
            'can_skip': fields['can_skip'],
            'skip_if_self': fields['skip_if_self'],
        }
        if routed_via == 'fallback':
            # Who actually holds this step, so the timeline does not claim the
            # manager approved when HR stood in for a vacant role.
            entry['routed_via'] = 'fallback'
            entry['acting_role'] = fields['fallback_role']
        if not user_ids and not role_is_filled:
            entry['unrouted'] = True
        chain.append(entry)
    return chain


def _advance(chain, from_step, now):
    """Auto-pass the steps the POLICY waives and stop at the next actionable
    one. Returns ``(current_step, current_approver_ids)``, or
    ``(len(chain), [])`` when the chain is exhausted. Mutates chain in place.

    A step is waived only when the policy says so: a failed condition, an
    ``auto_approve`` step, or ``skip_if_self`` dropping the requester from a
    role somebody does hold. An ``unrouted`` step — the role exists but nobody
    fills it (an employee with no manager) — is NOT waived: it becomes the
    current step with no approvers, so the request waits instead of being
    granted an approval nobody gave. ``_reroute`` picks it up once the role is
    filled.
    """
    i = from_step + 1
    while i < len(chain):
        entry = chain[i]
        if entry.get('decision') == 'skip':
            i += 1
            continue
        if entry.get('unrouted'):
            return i, []
        if entry.get('auto_approve') or not entry.get('user_ids'):
            entry['decision'] = 'auto'
            entry['decided_at'] = now.isoformat()
            i += 1
            continue
        return i, list(entry['user_ids'])
    return len(chain), []


def _snapshot_step(corr, order):
    """The frozen policy step for ``order`` (routing fields, not live policy)."""
    for step in (corr.policy_snapshot or {}).get('steps') or []:
        if step.get('order') == order:
            return step
    return None


def _reroute(corr):
    """Re-resolve the current step when it had no approver at submit time.

    An unrouted request is not stuck forever: the moment the role is filled
    (HR assigns the employee a manager, a delegation opens), the next action
    on the request resolves the approver and the normal chain continues. No
    admin has to reach into the record.
    """
    chain = copy.deepcopy(corr.approver_chain or [])
    if not 0 <= corr.current_step < len(chain):
        return False
    entry = chain[corr.current_step]
    if not entry.get('unrouted'):
        return False
    fields = _step_fields(_snapshot_step(corr, entry.get('order')) or entry)
    user_ids, _, routed_via = _resolve_user_ids(
        fields, corr=corr, by=corr.requester,
    )
    if not user_ids:
        return False
    entry['user_ids'] = user_ids
    if routed_via == 'fallback':
        entry['routed_via'] = 'fallback'
        entry['acting_role'] = fields['fallback_role']
    entry.pop('unrouted', None)
    corr.approver_chain = chain
    corr.current_approver_ids = user_ids
    corr.save(update_fields=['approver_chain', 'current_approver_ids'])
    notify(
        corr,
        user_ids=user_ids,
        type='awaiting_action',
        title=f'Action needed on {corr.reference_no}',
        body=corr.title,
    )
    return True


def _require_current_approver(corr, by):
    """Actor gate for a step decision, re-routing an unrouted step first."""
    if by.id in corr.current_approver_ids:
        return
    if _reroute(corr) and by.id in corr.current_approver_ids:
        return
    raise NotActorError(
        f'User {by.id} is not a current approver of {corr.reference_no}'
    )


def _settle(corr, chain, current_step, current_approver_ids, now, *,
            active_status):
    """Write the routing outcome onto ``corr``: still open, or approved.

    Open means a step remains — whether or not its approver is resolved yet.
    Keying this off the approver list is what let an unroutable step read as
    an approval.
    """
    corr.approver_chain = chain
    if current_step < len(chain):
        corr.status = active_status
        corr.current_step = current_step
        corr.current_approver_ids = current_approver_ids
    else:
        corr.status = 'approved'
        corr.resolved_at = now
        corr.current_step = len(chain)
        corr.current_approver_ids = []


def _notify_open_step(corr):
    """Tell whoever must act — or flag a request nobody can act on."""
    if corr.current_approver_ids:
        notify(
            corr,
            user_ids=corr.current_approver_ids,
            type='awaiting_action',
            title=f'Action needed on {corr.reference_no}',
            body=corr.title,
        )
        return
    chain = corr.approver_chain or []
    entry = chain[corr.current_step] if corr.current_step < len(chain) else {}
    notify(
        corr,
        user_ids=users_with_capability('correspondence:admin'),
        type='routing_gap',
        title=f'{corr.reference_no} has no approver',
        body=(
            f"No user holds the '{entry.get('role') or 'approver'}' role for "
            f'this request, so it is waiting. Assign one and it routes '
            f'automatically.'
        ),
    )


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
        _settle(corr, chain, current_step, current_approver_ids, now,
                active_status='submitted')

        corr.save()
        _add_event(corr, by, 'submitted', 'draft', corr.status)
        _governance(corr, by, 'submit', old_status='draft')

        if corr.status == 'submitted':
            _notify_open_step(corr)
        return corr


def _decide(corr, by, *, decision, event_type, governance_action, action_label,
            verb, comment=None):
    """Shared step-decision transition for approve/acknowledge/review. Marks the
    current step with ``decision`` and advances to the next actionable step
    exactly like ``approve`` — but never sets ``decision='approved'`` on the step
    for non-approval intents (an internal memo is *acknowledged*, not approved)."""
    with transaction.atomic():
        corr = _lock_correspondence(corr)
        if corr.status not in ACTIONABLE:
            raise InvalidTransition(
                f'Cannot {action_label} from status {corr.status!r}'
            )
        _require_current_approver(corr, by)

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
        _settle(corr, chain, current_step, current_approver_ids, now,
                active_status='in_review')

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
            _notify_open_step(corr)
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
        _require_current_approver(corr, by)

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
        _require_current_approver(corr, by)

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
        _settle(corr, chain, current_step, current_approver_ids, now,
                active_status='submitted')

        corr.save()
        _add_event(corr, by, 'resubmitted', old_status, corr.status)
        _governance(corr, by, 'resubmit', old_status=old_status)

        if corr.status == 'submitted':
            _notify_open_step(corr)
        return corr


def archive(corr, by):
    """Requester (or a correspondence:admin) archives a terminal
    correspondence -> archived. Terminal states only (approved/rejected/
    cancelled/expired); archiving an already-archived corr is an
    InvalidTransition, mirroring ``cancel``."""
    with transaction.atomic():
        if by.id != corr.requester_id and not has_capability(by, 'correspondence:admin'):
            raise NotActorError(
                'Only the requester or a correspondence admin may archive a request'
            )
        if corr.status not in ('approved', 'rejected', 'cancelled', 'expired'):
            raise InvalidTransition(
                f'Cannot archive from status {corr.status!r}'
            )

        old_status = corr.status
        corr.status = 'archived'
        corr.resolved_at = timezone.now()
        corr.current_approver_ids = []
        corr.save()

        _add_event(corr, by, 'archived', old_status, corr.status)
        _governance(corr, by, 'archive', old_status=old_status)

        notify(
            corr,
            user_ids=[corr.requester_id],
            type='status_changed',
            title=f'{corr.reference_no} was archived',
            body=corr.title,
        )
        return corr
