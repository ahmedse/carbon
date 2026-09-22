# correspondence/tests/test_api.py
# OF-7 — engine REST API (list/inbox/detail/act/policies).

from datetime import date
from types import SimpleNamespace
import uuid

import pytest
from django.conf import settings
from django.urls import reverse

from accounts.capabilities import has_capability
from catalog.models import GovernanceEvent
from correspondence.fsm import submit_correspondence
from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee


PREFIX = f'/{settings.API_PREFIX.strip("/")}'


@pytest.fixture
def workflow(db, create_user):
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
    manager_user = create_user('api_manager')
    requester_user = create_user('api_requester')
    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-API-MGR', full_name='Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
    )
    Employee.objects.create(
        org_unit=org, employee_no='E-API-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp,
    )
    policy = WorkflowPolicy.objects.create(
        name='Leave Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, manager_user=manager_user,
        requester_user=requester_user, manager_emp=manager_emp,
        policy=policy,
    )


def _draft(corr_type, org, requester, **overrides):
    kwargs = dict(
        reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
        corr_type=corr_type, org_unit=org, requester=requester,
        title='Leave request', payload={}, status='draft',
    )
    kwargs.update(overrides)
    return Correspondence.objects.create(**kwargs)


def _auth(api_client, user, get_token_for_user):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client


# ── list / self-scoping ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_list_is_self_scoped(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/')
    assert resp.status_code == 200
    data = resp.json()
    # Pagination is disabled during pytest → plain list response.
    assert len(data) == 1
    assert data[0]['id'] == corr.id

    # The manager did NOT submit anything → empty list.
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/')
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.django_db
def test_inbox_returns_only_awaiting_mine(
    workflow, api_client, get_token_for_user, create_user,
):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    # Manager sees it in their inbox.
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/inbox/')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['id'] == corr.id

    # A non-approver does NOT see it.
    outsider = create_user('api_outsider')
    _auth(api_client, outsider, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/inbox/')
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.django_db
def test_history_lists_acted_items_and_detail_visible(
    workflow, api_client, get_token_for_user, create_user,
):
    """Team History: any/all decisions by me; detail still readable after act."""
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.manager_user, get_token_for_user)
    # Not yet decided → empty history.
    resp = api_client.get(f'{PREFIX}/correspondence/history/')
    assert resp.status_code == 200
    assert resp.json() == []

    assert api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    ).status_code == 200

    # Leaves inbox, appears in history, detail still 200 for the actor.
    assert api_client.get(f'{PREFIX}/correspondence/inbox/').json() == []
    hist = api_client.get(f'{PREFIX}/correspondence/history/')
    assert hist.status_code == 200
    assert [row['id'] for row in hist.json()] == [corr.id]
    assert hist.json()[0]['status'] == 'approved'
    detail = api_client.get(f'{PREFIX}/correspondence/{corr.id}/')
    assert detail.status_code == 200

    # Outsider still cannot see history or detail.
    outsider = create_user('api_hist_outsider')
    _auth(api_client, outsider, get_token_for_user)
    assert api_client.get(f'{PREFIX}/correspondence/history/').json() == []
    assert api_client.get(f'{PREFIX}/correspondence/{corr.id}/').status_code == 403


@pytest.mark.django_db
def test_detail_includes_events_and_chain(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/{corr.id}/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == corr.id
    assert len(data['events']) >= 1
    assert data['approver_chain'] == corr.approver_chain


# ── actions ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_approve_by_manager(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'approved'


@pytest.mark.django_db
def test_second_approve_returns_4xx(workflow, api_client, get_token_for_user):
    """J-LV-11 sequential: second approve is not a second 200.

    After terminal approve, ``current_approver_ids`` is cleared so CBAC returns
    403 before the FSM. Concurrent duplex is covered by the FSM row-lock test
    (second caller reaches InvalidTransition → 409).
    """
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.manager_user, get_token_for_user)
    first = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    )
    second = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    )
    assert first.status_code == 200
    assert first.json()['status'] == 'approved'
    assert second.status_code in (403, 409)
    assert second.status_code != 200


@pytest.mark.django_db
def test_approve_by_non_approver_403(
    workflow, api_client, get_token_for_user, create_user,
):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    outsider = create_user('api_outsider2')
    _auth(api_client, outsider, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_reject_requires_comment(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/reject/', {}, format='json',
    )
    assert resp.status_code == 400

    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/reject/',
        {'comment': 'Invalid request'}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'rejected'


@pytest.mark.django_db
def test_send_back_and_resubmit(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/send-back/', {}, format='json',
    )
    assert resp.status_code == 400

    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/send-back/',
        {'comment': 'Fix the dates'}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'sent_back'

    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/resubmit/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_edit_then_resubmit_leave_subject(workflow, api_client, get_token_for_user):
    """sent_back → edit payload (+ LeaveRecord sync) → resubmit with DQ subject."""
    from datetime import date as date_cls
    from decimal import Decimal

    from people.models import LeaveEntitlement, LeaveRecord
    from mdm.models import ReferenceSet, ReferenceValue

    wf = workflow
    leave_set, _ = ReferenceSet.objects.get_or_create(
        name='leave_type', defaults={'slug': 'leave-type'},
    )
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=leave_set, code='annual',
        defaults={'label': 'Annual Leave'},
    )
    emp = Employee.objects.get(user=wf.requester_user)
    LeaveEntitlement.objects.get_or_create(
        employee=emp, year=2026, leave_type=annual,
        defaults={'entitled_days': Decimal('30'), 'used_days': Decimal('0')},
    )
    record = LeaveRecord.objects.create(
        employee=emp,
        leave_type=annual,
        start_date=date_cls(2026, 10, 6),
        end_date=date_cls(2026, 10, 6),
        days=Decimal('1'),
        status='draft',
    )
    corr = _draft(
        wf.corr_type, wf.org, wf.requester_user,
        subject_type='people.LeaveRecord',
        subject_id=record.pk,
        title='Leave request annual 2026-10-06→2026-10-06',
        payload={
            'leave_type': 'annual',
            'start_date': '2026-10-06',
            'end_date': '2026-10-06',
            'days': '1',
            'note': '',
        },
    )
    submit_correspondence(corr=corr, by=wf.requester_user, subject=record,
                          subject_label='people.LeaveRecord')

    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/send-back/',
        {'comment': 'change day'}, format='json',
    ).status_code == 200

    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/edit/',
        {
            'payload': {
                'leave_type': 'annual',
                'start_date': '2026-10-07',
                'end_date': '2026-10-07',
                'days': '1',
                'note': 'moved',
            },
        },
        format='json',
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['status'] == 'sent_back'
    assert body['payload']['start_date'] == '2026-10-07'
    assert any(e['event_type'] == 'edited' for e in body['events'])
    record.refresh_from_db()
    assert record.start_date == date_cls(2026, 10, 7)
    assert record.end_date == date_cls(2026, 10, 7)

    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/resubmit/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_cancel_by_requester_and_non_requester(
    workflow, api_client, get_token_for_user, create_user,
):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    outsider = create_user('api_cancel_outsider')
    _auth(api_client, outsider, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/cancel/', {}, format='json',
    )
    assert resp.status_code == 403

    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/cancel/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'cancelled'


@pytest.mark.django_db
def test_archive_by_requester(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    # Approve to a terminal status.
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/approve/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'approved'

    # Requester archives the approved correspondence.
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/archive/', {}, format='json',
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'archived'
    assert data['resolved_at'] is not None

    corr.refresh_from_db()
    assert corr.status == 'archived'
    assert corr.resolved_at is not None
    assert GovernanceEvent.objects.filter(
        entity_type='correspondence', entity_id=corr.id, action='archive',
    ).exists()


@pytest.mark.django_db
def test_current_approver_can_retrieve_but_not_cancel_or_resubmit(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    # The manager is the current approver after submission and derives the
    # ``correspondence:act`` capability from their open approval.
    assert corr.current_approver_ids == [wf.manager_user.id]
    assert has_capability(wf.manager_user, 'correspondence:act') is True

    # Current approver can retrieve the detail (widened CanViewCorrespondence).
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/{corr.id}/')
    assert resp.status_code == 200
    assert resp.json()['id'] == corr.id

    # …but cancel remains requester-only (fsm NotActorError → 403).
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/cancel/', {}, format='json',
    )
    assert resp.status_code == 403

    # Move to 'sent_back' (a valid resubmit source) — the current approver
    # (manager) sends back to the requester. Client is already authed as manager.
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/send-back/',
        {'comment': 'Fix the dates'}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'sent_back'

    # The approver is still denied resubmit (fsm NotActorError → 403).
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/resubmit/', {}, format='json',
    )
    assert resp.status_code == 403

    # The requester can still resubmit (regression guard for the widened view).
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/resubmit/', {}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_invalid_transition_409(workflow, api_client, get_token_for_user):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)

    # Resubmit is only valid from 'sent_back'. The requester passes the
    # view permission, but fsm raises InvalidTransition → 409.
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/resubmit/', {}, format='json',
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_void_and_reopen_admin_gated(
    workflow, api_client, get_token_for_user, create_user, create_scoped_role,
):
    wf = workflow
    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)
    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/reject/',
        {'comment': 'reject for reopen test'},
        format='json',
    ).status_code == 200

    # Manager (approver, not admin) cannot void.
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/void/',
        {'comment': 'nope'},
        format='json',
    )
    assert resp.status_code == 403

    admin = create_user('api_void_admin')
    create_scoped_role(admin, 'people_lead')
    _auth(api_client, admin, get_token_for_user)

    # Comment required.
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/void/', {}, format='json',
    ).status_code == 400

    # Reopen first (from rejected).
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/reopen/',
        {'comment': 'reopen after fix'},
        format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'submitted'
    events = {e['event_type'] for e in resp.json()['events']}
    assert 'reopened' in events

    # Reject again then void.
    _auth(api_client, wf.manager_user, get_token_for_user)
    api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/reject/',
        {'comment': 'still no'},
        format='json',
    )
    _auth(api_client, admin, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/void/',
        {'comment': 'void permanently'},
        format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'archived'
    assert any(e['event_type'] == 'voided' for e in resp.json()['events'])


@pytest.mark.django_db
def test_inbox_requester_name_includes_employee_full_name(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    from people.models import Employee
    emp = Employee.objects.get(user=wf.requester_user)
    emp.full_name = 'Ada Lovelace'
    emp.save(update_fields=['full_name'])

    corr = _draft(wf.corr_type, wf.org, wf.requester_user)
    submit_correspondence(corr=corr, by=wf.requester_user)
    _auth(api_client, wf.manager_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/inbox/')
    assert resp.status_code == 200
    items = resp.json()
    if isinstance(items, dict):
        items = items.get('results') or []
    row = next(i for i in items if i['id'] == corr.id)
    assert 'Ada Lovelace' in (row.get('requester_name') or '')
    assert wf.requester_user.username in (row.get('requester_name') or '')


# ── policies ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_policies_admin_gated(
    workflow, api_client, get_token_for_user, create_user, create_scoped_role,
):
    wf = workflow

    # Non-admin → 403.
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/policies/')
    assert resp.status_code == 403

    # people_lead (global ScopedRole) → 200.
    admin = create_user('api_corr_admin')
    create_scoped_role(admin, 'people_lead')  # global: org_unit=None, module=None
    _auth(api_client, admin, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/policies/')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['id'] == wf.policy.id
