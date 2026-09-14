# correspondence/tests/test_fsm.py
# OF-5 — correspondence state machine + notifications.

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from django.utils import timezone

from catalog.models import GovernanceEvent
from correspondence.exceptions import (
    CommentRequired,
    InvalidTransition,
    NotActorError,
    SubmissionBlocked,
)
from correspondence.fsm import (
    approve,
    archive,
    cancel,
    reject,
    resubmit,
    send_back,
    submit_correspondence,
)
from correspondence.models import (
    Correspondence,
    Notification,
    WorkflowPolicy,
    WorkflowPolicyStep,
)
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee


# ── fixtures / helpers ──────────────────────────────────────────────────────

@pytest.fixture
def leave_workflow(db, create_user):
    """Org, leave_request corr_type, manager + requester employees, and a
    single-step (manager) workflow policy."""
    ref_set = ReferenceSet.objects.create(
        name='Correspondence Type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=ref_set, code='leave_request', label='Leave Request',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    manager_user = create_user('fsm_manager')
    requester_user = create_user('fsm_requester')
    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-FSM-MGR', full_name='Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
    )
    Employee.objects.create(
        org_unit=org, employee_no='E-FSM-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp,
    )
    policy = WorkflowPolicy.objects.create(
        name='Leave Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    step = WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, manager_user=manager_user,
        requester_user=requester_user, manager_emp=manager_emp,
        policy=policy, step=step,
    )


def _draft(corr_type, org, requester, **overrides):
    kwargs = dict(
        reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
        corr_type=corr_type, org_unit=org, requester=requester,
        title='Leave request', payload={}, status='draft',
    )
    kwargs.update(overrides)
    return Correspondence.objects.create(**kwargs)


# ── happy path ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_happy_path_single_step(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)

    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    assert corr.status == 'submitted'
    assert corr.reference_no
    assert corr.reference_no.startswith('CRS-')
    assert len(corr.approver_chain) == 1
    assert corr.current_approver_ids == [wf.manager_user.id]
    assert corr.policy_id == wf.policy.id
    assert corr.policy_version == '1.0.0'


@pytest.mark.django_db
def test_approve_by_manager(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    corr = approve(corr, wf.manager_user)

    assert corr.status == 'approved'
    assert corr.resolved_at is not None
    assert corr.current_approver_ids == []
    # decision recorded on the step
    assert corr.approver_chain[0]['decision'] == 'approved'
    assert corr.approver_chain[0]['decided_by'] == wf.manager_user.id


@pytest.mark.django_db
def test_approve_by_non_approver_raises(leave_workflow, create_user):
    wf = leave_workflow
    outsider = create_user('fsm_outsider')
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    with pytest.raises(NotActorError):
        approve(corr, outsider)


# ── reject ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_reject_requires_comment(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    with pytest.raises(CommentRequired):
        reject(corr, wf.manager_user, None)
    with pytest.raises(CommentRequired):
        reject(corr, wf.manager_user, '   ')

    corr = reject(corr, wf.manager_user, 'Invalid request')

    assert corr.status == 'rejected'
    assert corr.resolved_at is not None
    assert corr.current_approver_ids == []
    assert corr.approver_chain[0]['decision'] == 'rejected'


# ── send_back + resubmit ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_send_back_and_resubmit(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)
    ref_no = corr.reference_no

    with pytest.raises(CommentRequired):
        send_back(corr, wf.manager_user, '')

    corr = send_back(corr, wf.manager_user, 'Fix the dates')
    assert corr.status == 'sent_back'
    assert corr.current_approver_ids == []

    corr = resubmit(corr, wf.requester_user)
    assert corr.status == 'submitted'
    assert corr.current_approver_ids == [wf.manager_user.id]
    # reference number is preserved (no re-allocation)
    assert corr.reference_no == ref_no


# ── cancel ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_cancel_by_requester_and_non_requester(leave_workflow, create_user):
    wf = leave_workflow
    outsider = create_user('fsm_cancel_outsider')
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    with pytest.raises(NotActorError):
        cancel(corr, outsider)

    corr = cancel(corr, wf.requester_user)
    assert corr.status == 'cancelled'
    assert corr.resolved_at is not None
    assert corr.current_approver_ids == []


# ── archive ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_archive_by_requester_and_non_requester(leave_workflow, create_user):
    wf = leave_workflow
    outsider = create_user('fsm_archive_outsider')
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)
    corr = approve(corr, wf.manager_user)
    assert corr.status == 'approved'

    with pytest.raises(NotActorError):
        archive(corr, outsider)

    # Cannot archive a non-terminal status.
    pending = _draft(wf.corr_type, wf.org, wf.requester_user)
    pending = submit_correspondence(corr=pending, by=wf.requester_user)
    with pytest.raises(InvalidTransition):
        archive(pending, wf.requester_user)

    corr = archive(corr, wf.requester_user)
    assert corr.status == 'archived'
    assert corr.resolved_at is not None
    assert corr.current_approver_ids == []

    # Idempotence: archiving an already-archived corr is an InvalidTransition.
    with pytest.raises(InvalidTransition):
        archive(corr, wf.requester_user)


@pytest.mark.django_db
def test_archive_by_admin(leave_workflow, create_user):
    wf = leave_workflow
    admin = create_user('fsm_archive_admin', is_superuser=True)
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)
    corr = approve(corr, wf.manager_user)

    corr = archive(corr, admin)
    assert corr.status == 'archived'


# ── skip_if_self ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_skip_if_self_auto_approves(leave_workflow):
    wf = leave_workflow
    requester = wf.requester_user
    # Make the requester their own manager (only one employee profile remains).
    Employee.objects.filter(user=requester).delete()
    emp = Employee.objects.create(
        org_unit=wf.org, employee_no='E-SELF', full_name='Self Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester,
    )
    emp.manager = emp
    emp.save()
    wf.step.skip_if_self = True
    wf.step.save()

    corr = _draft(wf.corr_type, wf.org, requester)
    corr = submit_correspondence(corr=corr, by=requester)

    assert corr.status == 'approved'
    assert corr.current_approver_ids == []
    assert corr.resolved_at is not None


# ── auto_approve step ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_auto_approve_step(leave_workflow):
    wf = leave_workflow
    wf.step.auto_approve = True
    wf.step.save()

    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    assert corr.status == 'approved'
    assert corr.current_approver_ids == []
    assert corr.approver_chain[0]['decision'] == 'auto'


# ── gap-free numbering ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_gap_free_numbering(leave_workflow):
    wf = leave_workflow
    c1 = _draft(wf.corr_type, wf.org, wf.requester_user)
    c2 = _draft(wf.corr_type, wf.org, wf.requester_user)

    submit_correspondence(corr=c1, by=wf.requester_user)
    submit_correspondence(corr=c2, by=wf.requester_user)

    year = timezone.now().year
    assert c1.reference_no == f'CRS-{year}-0001'
    assert c2.reference_no == f'CRS-{year}-0002'


# ── DQ gate ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_dq_block_raises_submission_blocked(leave_workflow, monkeypatch):
    wf = leave_workflow

    def fake_check_instances(model_label, instances, mode='write'):
        return {
            'summary': {'blocked': 1, 'warned': 0, 'passed': 0},
            'row_verdicts': [
                {
                    'row_index': 0,
                    'verdict': 'block',
                    'failures': [
                        {'rule_id': 1, 'rule_name': 'R1', 'field': 'x',
                         'severity': 'error', 'message': 'bad value'},
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        'correspondence.fsm.check_instances', fake_check_instances,
    )

    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    with pytest.raises(SubmissionBlocked) as exc:
        submit_correspondence(
            corr=corr, by=wf.requester_user,
            subject=object(), subject_label='people.Employee',
        )

    assert len(exc.value.failures) == 1
    assert exc.value.failures[0]['message'] == 'bad value'


# ── governance events ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_governance_events_emitted(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)
    corr = approve(corr, wf.manager_user)

    events = GovernanceEvent.objects.filter(
        entity_type='correspondence', entity_id=corr.id,
    )
    actions = {e.action for e in events}
    assert {'submit', 'approve'} <= actions


# ── notifications ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_notification_created_on_submit(leave_workflow):
    wf = leave_workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    corr = submit_correspondence(corr=corr, by=wf.requester_user)

    note = Notification.objects.get(
        correspondence=corr, user=wf.manager_user,
    )
    assert note.type == 'awaiting_action'
    assert note.title == f'Action needed on {corr.reference_no}'
