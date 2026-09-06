# correspondence/tests/test_of20_integration_walk.py
# OF-20 (QA) — end-to-end DRF test-client walk of the expanded e-office.
# TEMPORARY QA scaffolding: exercises the full HTTP journey (submit -> inbox ->
# acknowledge/approve) that the per-phase unit tests only cover in pieces.
# Not part of the permanent regression suite; delete after OF-20 sign-off.

from datetime import date
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
CORR_LIST = f'{PREFIX}/correspondence/'
CORR_INBOX = f'{PREFIX}/correspondence/inbox/'
NOTIFS = f'{PREFIX}/correspondence/notifications/'
ME_URL = f'{PREFIX}/people/me/'
LOAN_URL = ME_URL + 'loan/'
PROFILE_CHANGE_URL = ME_URL + 'profile-change/'


def _emp_corr_url(employee_id):
    return f'{PREFIX}/people/employees/{employee_id}/correspondence/'


@pytest.fixture
def of20_scene(db, create_user, create_scoped_role):
    """One org, three governed corr_types (internal_memo/loan_request/
    profile_change), a requester employee with a manager, plus hr (people_lead),
    finance (finance_group) and admin (superuser) users, and the three
    matching single/multi-step workflow policies."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    memo_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='internal_memo', label='Internal Memo',
    )
    loan_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='loan_request', label='Loan Request',
    )
    pc_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='profile_change', label='Profile Change',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )

    manager_user = create_user('of20_manager')
    requester_user = create_user('of20_requester')
    hr_user = create_user('of20_hr')
    finance_user = create_user('of20_finance')
    admin_user = create_user('of20_admin', is_superuser=True)
    create_scoped_role(hr_user, 'people_lead')          # people:manage -> people:view
    create_scoped_role(finance_user, 'finance_group')    # correspondence:finance

    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-OF20-MGR', full_name='Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
        is_active=True,
    )
    requester_emp = Employee.objects.create(
        org_unit=org, employee_no='E-OF20-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp, is_active=True,
    )

    # internal_memo -> any_admin/acknowledge (single step)
    memo_policy = WorkflowPolicy.objects.create(
        name='Memo Default', corr_type=memo_type, org_unit=None, version='1.0.0',
        is_active=True, numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=memo_policy, order=1, role='any_admin', intent='acknowledge',
        is_active=True,
    )

    # loan_request -> manager (skip_if_self) then finance (two steps)
    loan_policy = WorkflowPolicy.objects.create(
        name='Loan Default', corr_type=loan_type, org_unit=None, version='1.0.0',
        is_active=True, numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=loan_policy, order=1, role='manager', intent='approve',
        skip_if_self=True, is_active=True,
    )
    WorkflowPolicyStep.objects.create(
        policy=loan_policy, order=2, role='finance', intent='approve',
        is_active=True,
    )

    # profile_change -> hr/approve (single step)
    pc_policy = WorkflowPolicy.objects.create(
        name='Profile Change Default', corr_type=pc_type, org_unit=None,
        version='1.0.0', is_active=True, numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=pc_policy, order=1, role='hr', intent='approve', is_active=True,
    )

    return SimpleNamespace(
        org=org, memo_type=memo_type, loan_type=loan_type, pc_type=pc_type,
        manager_user=manager_user, requester_user=requester_user,
        requester_emp=requester_emp, hr_user=hr_user, finance_user=finance_user,
        admin_user=admin_user,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
    )
    return api_client


def _submit_memo(api_client, scene, title='OF-20 memo'):
    return api_client.post(
        CORR_LIST,
        {
            'corr_type': 'internal_memo',
            'title': title,
            'payload': {'body': 'walk'},
            'org_unit': scene.org.id,
        },
        format='json',
    )


# ── 1. generic memo: submit -> inbox -> acknowledge ────────────────────────

@pytest.mark.django_db
def test_walk_memo_submit_inbox_acknowledge(
    of20_scene, api_client, get_token_for_user,
):
    scene = of20_scene
    _auth(api_client, scene.requester_user, get_token_for_user)

    resp = _submit_memo(api_client, scene)
    assert resp.status_code == 201, resp.content          # POST /correspondence/ 201
    memo = resp.json()
    assert memo['status'] == 'submitted'
    assert memo['subject_type'] == ''
    assert scene.admin_user.id in memo['current_approver_ids']

    # inbox as the admin (current approver) contains the memo
    _auth(api_client, scene.admin_user, get_token_for_user)
    resp = api_client.get(CORR_INBOX)
    assert resp.status_code == 200                          # GET /inbox/ 200
    inbox_items = resp.json()
    inbox_items = inbox_items['results'] if isinstance(inbox_items, dict) else inbox_items
    assert any(c['id'] == memo['id'] for c in inbox_items)

    # acknowledge as admin advances to terminal approved
    resp = api_client.post(
        f'{PREFIX}/correspondence/{memo["id"]}/acknowledge/', {}, format='json',
    )
    assert resp.status_code == 200                          # POST /acknowledge/ 200
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['approver_chain'][0]['decision'] == 'acknowledged'


# ── 2. loan: submit -> manager approve -> finance approve ──────────────────

@pytest.mark.django_db
def test_walk_loan_manager_then_finance_approve(
    of20_scene, api_client, get_token_for_user,
):
    scene = of20_scene
    _auth(api_client, scene.requester_user, get_token_for_user)

    resp = api_client.post(
        LOAN_URL,
        {
            'loan_type': 'housing',
            'principal': '5000.000',
            'interest_rate': '3.5',
            'term_months': 12,
            'start_date': date(2026, 6, 1).isoformat(),
        },
        format='json',
    )
    assert resp.status_code == 201, resp.content          # POST /people/me/loan/ 201
    loan = resp.json()
    assert loan['status'] == 'submitted'
    assert loan['subject_type'] == 'people.Loan'
    assert scene.manager_user.id in loan['current_approver_ids']

    # manager approves -> advances to finance step
    _auth(api_client, scene.manager_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{loan["id"]}/approve/',
        {'comment': 'ok'}, format='json',
    )
    assert resp.status_code == 200, resp.content           # manager approve 200
    data = resp.json()
    assert data['status'] == 'in_review'                   # not yet terminal
    assert scene.finance_user.id in data['current_approver_ids']
    assert data['approver_chain'][0]['decision'] == 'approved'

    # finance approves -> terminal approved
    _auth(api_client, scene.finance_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{loan["id"]}/approve/',
        {'comment': 'funded'}, format='json',
    )
    assert resp.status_code == 200, resp.content           # finance approve 200
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['approver_chain'][1]['decision'] == 'approved'
    assert data['current_approver_ids'] == []


# ── 3. profile-change: submit -> hr approve ────────────────────────────────

@pytest.mark.django_db
def test_walk_profile_change_hr_approve(
    of20_scene, api_client, get_token_for_user,
):
    scene = of20_scene
    _auth(api_client, scene.requester_user, get_token_for_user)

    resp = api_client.post(
        PROFILE_CHANGE_URL,
        {'changes': {'mobile_number': {'from': '0100', 'to': '0111'}}},
        format='json',
    )
    assert resp.status_code == 201, resp.content          # POST profile-change 201
    pc = resp.json()
    assert pc['subject_type'] == 'people.Employee'
    assert pc['subject_id'] == scene.requester_emp.pk
    assert scene.hr_user.id in pc['current_approver_ids']

    # hr approves -> terminal approved
    _auth(api_client, scene.hr_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{pc["id"]}/approve/',
        {'comment': 'approved'}, format='json',
    )
    assert resp.status_code == 200, resp.content           # hr approve 200
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['approver_chain'][0]['decision'] == 'approved'


# ── 4. HR lists an employee's correspondence ───────────────────────────────

@pytest.mark.django_db
def test_walk_hr_lists_employee_correspondence(
    of20_scene, api_client, get_token_for_user,
):
    scene = of20_scene
    _auth(api_client, scene.requester_user, get_token_for_user)
    _submit_memo(api_client, scene, title='Leave-ish memo')

    _auth(api_client, scene.hr_user, get_token_for_user)
    resp = api_client.get(_emp_corr_url(scene.requester_emp.pk))
    assert resp.status_code == 200                          # GET employee corr 200
    data = resp.json()
    assert data['count'] >= 1
    assert all(c['requester'] == scene.requester_user.id for c in data['results'])


# ── 5. notifications: read + read-all ──────────────────────────────────────

@pytest.mark.django_db
def test_walk_notifications_read_and_read_all(
    of20_scene, api_client, get_token_for_user,
):
    scene = of20_scene
    # Two memos, each acknowledged, produce two status_changed notifications
    # for the requester.
    for i in range(2):
        _auth(api_client, scene.requester_user, get_token_for_user)
        resp = _submit_memo(api_client, scene, title=f'Notif memo {i}')
        assert resp.status_code == 201
        _auth(api_client, scene.admin_user, get_token_for_user)
        resp = api_client.post(
            f'{PREFIX}/correspondence/{resp.json()["id"]}/acknowledge/',
            {}, format='json',
        )
        assert resp.status_code == 200

    _auth(api_client, scene.requester_user, get_token_for_user)
    resp = api_client.get(NOTIFS)
    assert resp.status_code == 200                          # GET notifications 200
    data = resp.json()
    assert data['unread_count'] == 2
    assert len(data['results']) == 2

    # read one -> unread drops to 1
    nid = data['results'][0]['id']
    resp = api_client.post(f'{NOTIFS}{nid}/read/')
    assert resp.status_code == 200                          # POST read 200
    assert resp.json()['is_read'] is True

    resp = api_client.get(NOTIFS)
    assert resp.json()['unread_count'] == 1

    # read-all -> unread 0
    resp = api_client.post(f'{NOTIFS}read-all/')
    assert resp.status_code == 200                          # POST read-all 200
    assert resp.json()['updated'] == 1
    assert resp.json()['unread_count'] == 0
