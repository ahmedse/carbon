# correspondence/tests/test_generic_submit.py
# OF-15 — generic payload-only create endpoint (POST /correspondence/).

from datetime import date
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
CREATE_URL = f'{PREFIX}/correspondence/'


@pytest.fixture
def memo_workflow(db, create_user):
    """org, internal_memo corr_type, requester employee, admin superuser, and
    a single-step (any_admin/acknowledge) policy."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='internal_memo', label='Internal Memo',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('gen_requester')
    admin_user = create_user('gen_admin', is_superuser=True)
    Employee.objects.create(
        org_unit=org, employee_no='E-GEN-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
    )
    policy = WorkflowPolicy.objects.create(
        name='Internal Memo Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='any_admin', intent='acknowledge',
        is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, requester_user=requester_user,
        admin_user=admin_user, policy=policy,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return api_client


def _payload(wf, **overrides):
    data = {
        'corr_type': 'internal_memo',
        'title': 'Team announcement',
        'payload': {'body': 'Hello'},
        'org_unit': wf.org.id,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_create_submits_payload_only_correspondence(
    memo_workflow, api_client, get_token_for_user,
):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf), format='json')

    assert resp.status_code == 201
    data = resp.json()
    assert data['subject_type'] == ''
    assert data['subject_id'] is None
    assert data['requester'] == wf.requester_user.id
    assert data['title'] == 'Team announcement'
    assert data['status'] == 'submitted'
    # reference_no was allocated on submit (no longer the DRAFT placeholder).
    assert data['reference_no'] and not data['reference_no'].startswith('DRAFT')
    # routed to the any_admin pool (superuser admin).
    assert wf.admin_user.id in data['current_approver_ids']


@pytest.mark.django_db
def test_create_missing_corr_type_400(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf, corr_type=''), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_missing_title_400(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf, title=''), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_unknown_corr_type_400(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf, corr_type='nope'), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_unknown_org_unit_400(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf, org_unit=999999), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_omitted_org_unit_uses_employee_profile(
    memo_workflow, api_client, get_token_for_user,
):
    wf = memo_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf, org_unit=None), format='json')

    assert resp.status_code == 201
    assert resp.json()['org_unit'] == wf.org.id


@pytest.mark.django_db
def test_create_missing_org_unit_without_profile_400(
    memo_workflow, api_client, get_token_for_user,
):
    wf = memo_workflow
    _auth(api_client, wf.admin_user, get_token_for_user)

    resp = api_client.post(
        CREATE_URL,
        {
            'corr_type': 'internal_memo',
            'title': 'Team announcement',
            'payload': {'body': 'Hello'},
        },
        format='json',
    )

    assert resp.status_code == 400
    assert resp.json()['detail'] == 'org_unit is required'


@pytest.mark.django_db
def test_create_without_submit_capability_403(
    memo_workflow, api_client, get_token_for_user, create_user,
):
    wf = memo_workflow
    # No Employee profile → no auto-derived correspondence:submit.
    outsider = create_user('gen_outsider')
    _auth(api_client, outsider, get_token_for_user)

    resp = api_client.post(CREATE_URL, _payload(wf), format='json')

    assert resp.status_code == 403
