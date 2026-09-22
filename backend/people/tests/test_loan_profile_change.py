# people/tests/test_loan_profile_change.py
# OF-15 — self-service loan + profile-change submission.

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, Loan

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
ME_URL = f'{PREFIX}/people/me/'
LOAN_URL = ME_URL + 'loan/'
PROFILE_CHANGE_URL = ME_URL + 'profile-change/'


@pytest.fixture
def workflow(db, create_user, create_scoped_role):
    """Org, loan_request/profile_change corr_types, requester + manager + hr +
    finance users, and the loan (manager→finance) + profile_change (hr) policies."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    loan_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='loan_request', label='Loan Request',
    )
    profile_change_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='profile_change', label='Profile Change',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    manager_user = create_user('loan_manager')
    requester_user = create_user('loan_requester')
    hr_user = create_user('loan_hr')
    finance_user = create_user('loan_finance')
    create_scoped_role(hr_user, 'people_lead')        # grants people:manage
    create_scoped_role(finance_user, 'finance_group')  # grants correspondence:finance

    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-LOAN-MGR', full_name='Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
        is_active=True,
    )
    requester_emp = Employee.objects.create(
        org_unit=org, employee_no='E-LOAN-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp, is_active=True,
    )

    loan_policy = WorkflowPolicy.objects.create(
        name='Loan Default', corr_type=loan_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=loan_policy, order=1, role='manager', intent='approve',
        skip_if_self=True, is_active=True,
    )
    WorkflowPolicyStep.objects.create(
        policy=loan_policy, order=2, role='finance', intent='approve',
        is_active=True,
    )

    profile_policy = WorkflowPolicy.objects.create(
        name='Profile Change Default', corr_type=profile_change_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=profile_policy, order=1, role='hr', intent='approve', is_active=True,
    )

    return SimpleNamespace(
        org=org, manager_user=manager_user, requester_user=requester_user,
        requester_emp=requester_emp, hr_user=hr_user, finance_user=finance_user,
        loan_type=loan_type, profile_change_type=profile_change_type,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return api_client


def _loan_payload(**overrides):
    data = {
        'loan_type': 'housing',
        'principal': '5000.000',
        'interest_rate': '3.5',
        'term_months': 12,
        'start_date': date(2026, 6, 1).isoformat(),
    }
    data.update(overrides)
    return data


# ── loan submission ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_loan_happy_path(workflow, api_client, get_token_for_user):
    from people.tests.ref_helpers import ensure_ref
    ensure_ref('loan_type', 'housing')
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(), format='json')

    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data['subject_type'] == 'people.Loan'
    assert data['status'] == 'submitted'  # first actionable step = manager
    assert wf.manager_user.id in data['current_approver_ids']

    loan = Loan.objects.get(pk=data['subject_id'])
    assert loan.employee_id == wf.requester_emp.id
    assert loan.status == 'draft'
    assert str(loan.principal) == '5000.000'
    assert loan.interest_rate == Decimal('3.500')
    assert loan.term_months == 12


@pytest.mark.django_db
def test_submit_loan_missing_loan_type_400(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(loan_type=''), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_loan_invalid_principal_400(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(principal='abc'), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_loan_nonpositive_principal_400(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(principal='0'), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_loan_negative_interest_400(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(interest_rate='-1'), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_loan_invalid_term_months_400(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LOAN_URL, _loan_payload(term_months=0), format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_edit_then_resubmit_loan_subject(workflow, api_client, get_token_for_user):
    """sent_back → edit payload (+ Loan sync) → resubmit with DQ subject."""
    from people.tests.ref_helpers import ensure_ref
    ensure_ref('loan_type', 'housing')
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LOAN_URL, _loan_payload(), format='json')
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']
    loan_id = resp.json()['subject_id']

    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'lower principal'}, format='json',
    ).status_code == 200

    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {
            'payload': {
                'loan_type': 'housing',
                'principal': '4000.000',
                'interest_rate': '2.0',
                'term_months': 10,
                'start_date': '2026-07-01',
                'notes': 'revised',
            },
        },
        format='json',
    )
    assert edit.status_code == 200, edit.content
    body = edit.json()
    assert body['status'] == 'sent_back'
    assert body['payload']['principal'] == '4000.000'
    loan = Loan.objects.get(pk=loan_id)
    assert loan.principal == Decimal('4000.000')
    assert loan.term_months == 10
    assert loan.status == 'draft'

    resub = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/resubmit/', {}, format='json',
    )
    assert resub.status_code == 200
    assert resub.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_edit_rehydrates_orphaned_loan_subject(workflow, api_client, get_token_for_user):
    from people.tests.ref_helpers import ensure_ref
    ensure_ref('loan_type', 'housing')
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LOAN_URL, _loan_payload(), format='json')
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']
    orphan_id = resp.json()['subject_id']

    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'fix'}, format='json',
    ).status_code == 200

    Loan.objects.filter(pk=orphan_id).delete()

    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {
            'payload': {
                'loan_type': 'housing',
                'principal': '3500.000',
                'interest_rate': '1.0',
                'term_months': 6,
                'start_date': '2026-08-01',
                'notes': 'rehydrate',
            },
        },
        format='json',
    )
    assert edit.status_code == 200, edit.content
    corr = Correspondence.objects.get(pk=corr_id)
    assert corr.subject_id != orphan_id
    restored = Loan.objects.get(pk=corr.subject_id)
    assert restored.principal == Decimal('3500.000')
    assert restored.status == 'draft'


@pytest.mark.django_db
def test_edit_then_resubmit_profile_change(workflow, api_client, get_token_for_user):
    """sent_back profile_change → edit allowlisted changes → resubmit (no Employee write)."""
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    payload = {
        'changes': {
            'full_name': {'from': 'Requester', 'to': 'Requester Updated'},
        },
    }
    resp = api_client.post(PROFILE_CHANGE_URL, payload, format='json')
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']
    emp_before = Employee.objects.get(pk=wf.requester_emp.pk)
    name_before = emp_before.full_name

    _auth(api_client, wf.hr_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'fix spelling'}, format='json',
    ).status_code == 200

    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {
            'payload': {
                'changes': {
                    'full_name': {'from': 'Requester', 'to': 'Requester Final'},
                    'nationality': {'from': '', 'to': 'KW'},
                },
            },
        },
        format='json',
    )
    assert edit.status_code == 200, edit.content
    body = edit.json()
    assert body['status'] == 'sent_back'
    assert body['payload']['changes']['full_name']['to'] == 'Requester Final'
    assert body['payload']['changes']['nationality']['to'] == 'KW'
    emp_before.refresh_from_db()
    assert emp_before.full_name == name_before  # no Employee write on edit

    resub = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/resubmit/', {}, format='json',
    )
    assert resub.status_code == 200
    assert resub.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_edit_profile_change_rejects_non_allowlisted(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        PROFILE_CHANGE_URL,
        {'changes': {'full_name': {'to': 'Temp'}}},
        format='json',
    )
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']

    _auth(api_client, wf.hr_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'no'}, format='json',
    ).status_code == 200

    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {'payload': {'changes': {'basic_salary': {'to': '9999'}}}},
        format='json',
    )
    assert edit.status_code == 400
    assert edit.json().get('error_kind') == 'field_not_allowed'


# ── profile-change submission ──────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_profile_change_happy_path(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    payload = {
        'changes': {
            'full_name': {'from': 'Requester', 'to': 'Requester New'},
            'nationality': {'from': '', 'to': 'KW'},
        },
    }
    resp = api_client.post(PROFILE_CHANGE_URL, payload, format='json')

    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data['subject_type'] == 'people.Employee'
    assert data['subject_id'] == wf.requester_emp.pk
    assert data['payload']['changes'] == payload['changes']
    # routed to the hr pool (people_lead grants people:manage).
    assert wf.hr_user.id in data['current_approver_ids']

    corr = Correspondence.objects.get(pk=data['id'])
    assert corr.subject_id == wf.requester_emp.pk


@pytest.mark.django_db
def test_submit_profile_change_empty_changes_400(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(PROFILE_CHANGE_URL, {'changes': {}}, format='json')

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_profile_change_bad_field_400(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(
        PROFILE_CHANGE_URL, {'changes': {'full_name': '0111'}}, format='json',
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_submit_profile_change_non_allowlisted_400(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(
        PROFILE_CHANGE_URL,
        {'changes': {'basic_salary': {'to': '9999'}}},
        format='json',
    )

    assert resp.status_code == 400
    assert resp.json().get('error_kind') == 'field_not_allowed'
