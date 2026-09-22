# people/tests/test_profile_change_journey_e2e.py
# NSR-5A prove — full HTTP journey: me/profile-change → HR inbox → approve →
# Employee allowlisted fields applied (parity with leave journey e2e).
#
#     python -m pytest people/tests/test_profile_change_journey_e2e.py -q

from datetime import date
from types import SimpleNamespace

import pytest
from django.conf import settings

from catalog.models import GovernanceEvent
from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, PersonnelEvent
from people.tests.ref_helpers import ensure_ref

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
ME_URL = f'{PREFIX}/people/me/'
PROFILE_CHANGE_URL = ME_URL + 'profile-change/'
INBOX_URL = f'{PREFIX}/correspondence/inbox/'


@pytest.fixture
def workflow(db, create_user, create_scoped_role):
    """profile_change corr type, requester employee, HR (people_lead) policy."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='profile_change', label='Profile Change',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('pc_j_requester')
    hr_user = create_user('pc_j_hr')
    create_scoped_role(hr_user, 'people_lead')

    requester_emp = Employee.objects.create(
        org_unit=org,
        employee_no='E-PC-JOURNEY',
        full_name='Before Name',
        name_en_given='Before',
        name_en_family='Name',
        nationality=ensure_ref('nationality', 'EGY', 'Egyptian'),
        gender=ensure_ref('gender', 'male'),
        basic_salary='1000.000',
        join_date=date(2026, 1, 1),
        user=requester_user,
        is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Profile Change Default',
        corr_type=corr_type,
        org_unit=None,
        version='1.0.0',
        is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='hr', intent='approve', is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type,
        org=org,
        requester_user=requester_user,
        hr_user=hr_user,
        requester_emp=requester_emp,
        policy=policy,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return api_client


def _changes_allowlisted():
    ensure_ref('nationality', 'KWT', 'Kuwaiti')
    return {
        'name_en_given': {'from': 'Before', 'to': 'Ahmed'},
        'name_en_family': {'from': 'Name', 'to': 'Hassan'},
        'full_name': {'from': 'Before Name', 'to': 'Ahmed Hassan'},
        'nationality': {'from': 'EGY', 'to': 'KWT'},
        'date_of_birth': {'from': None, 'to': '1990-05-15'},
        # Unsafe / non-columns — must not apply
        'basic_salary': {'to': '9999.000'},
        'mobile_number': {'to': '0111'},
    }


@pytest.mark.django_db
def test_submit_hr_inbox_approve_applies_employee(workflow, api_client, get_token_for_user):
    wf = workflow
    old_salary = str(wf.requester_emp.basic_salary)

    _auth(api_client, wf.requester_user, get_token_for_user)
    submitted = api_client.post(
        PROFILE_CHANGE_URL,
        {'changes': _changes_allowlisted()},
        format='json',
    )
    assert submitted.status_code == 201, submitted.content
    body = submitted.json()
    corr_id = body['id']
    assert body['status'] == 'submitted'
    assert body['subject_type'] == 'people.Employee'
    assert body['subject_id'] == wf.requester_emp.pk
    assert wf.hr_user.id in body['current_approver_ids']

    # Employee unchanged until approve.
    wf.requester_emp.refresh_from_db()
    assert wf.requester_emp.full_name == 'Before Name'
    assert str(wf.requester_emp.basic_salary) == old_salary

    _auth(api_client, wf.hr_user, get_token_for_user)
    inbox = api_client.get(INBOX_URL)
    assert inbox.status_code == 200, inbox.content
    data = inbox.json()
    if isinstance(data, dict):
        data = data.get('results', [])
    assert any(item['id'] == corr_id for item in data)

    approve = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/approve/',
        {'comment': 'verified'},
        format='json',
    )
    assert approve.status_code == 200, approve.content
    assert approve.json()['status'] == 'approved'

    wf.requester_emp.refresh_from_db()
    assert wf.requester_emp.name_en_given == 'Ahmed'
    assert wf.requester_emp.name_en_family == 'Hassan'
    assert wf.requester_emp.full_name == 'Ahmed Hassan'
    assert wf.requester_emp.nationality.code == 'KWT'
    assert wf.requester_emp.date_of_birth == date(1990, 5, 15)
    assert str(wf.requester_emp.basic_salary) == old_salary

    assert PersonnelEvent.objects.filter(
        entity_type='Employee',
        entity_id=wf.requester_emp.pk,
        event_kind='profile_updated',
    ).exists()
    assert GovernanceEvent.objects.filter(
        entity_type='Employee',
        entity_id=wf.requester_emp.pk,
        action='profile_change_applied',
    ).exists()


@pytest.mark.django_db
def test_hr_reject_does_not_apply_employee(workflow, api_client, get_token_for_user):
    wf = workflow

    _auth(api_client, wf.requester_user, get_token_for_user)
    submitted = api_client.post(
        PROFILE_CHANGE_URL,
        {
            'changes': {
                'full_name': {'from': 'Before Name', 'to': 'Should Not Apply'},
                'name_en_given': {'to': 'Nope'},
            },
        },
        format='json',
    )
    assert submitted.status_code == 201, submitted.content
    corr_id = submitted.json()['id']

    _auth(api_client, wf.hr_user, get_token_for_user)
    reject = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/reject/',
        {'comment': 'docs incomplete'},
        format='json',
    )
    assert reject.status_code == 200, reject.content
    assert reject.json()['status'] == 'rejected'

    wf.requester_emp.refresh_from_db()
    assert wf.requester_emp.full_name == 'Before Name'
    assert wf.requester_emp.name_en_given == 'Before'
    assert not PersonnelEvent.objects.filter(
        entity_type='Employee',
        entity_id=wf.requester_emp.pk,
        event_kind='profile_updated',
    ).exists()


@pytest.mark.django_db
def test_inbox_only_for_hr_not_requester(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    submitted = api_client.post(
        PROFILE_CHANGE_URL,
        {'changes': {'full_name': {'to': 'X'}}},
        format='json',
    )
    assert submitted.status_code == 201, submitted.content
    corr_id = submitted.json()['id']

    inbox = api_client.get(INBOX_URL)
    assert inbox.status_code == 200
    data = inbox.json()
    if isinstance(data, dict):
        data = data.get('results', [])
    assert not any(item['id'] == corr_id for item in data)

    _auth(api_client, wf.hr_user, get_token_for_user)
    hr_inbox = api_client.get(INBOX_URL)
    assert hr_inbox.status_code == 200
    hr_data = hr_inbox.json()
    if isinstance(hr_data, dict):
        hr_data = hr_data.get('results', [])
    assert any(item['id'] == corr_id for item in hr_data)
