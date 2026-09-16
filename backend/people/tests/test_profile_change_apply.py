from people.tests.ref_helpers import ensure_ref
# people/tests/test_profile_change_apply.py
# NSR-5A — approved profile_change correspondence applies allowlisted Employee
# fields; reject does not mutate; unknown keys are ignored.

from datetime import date
from types import SimpleNamespace

import pytest

from catalog.models import GovernanceEvent
from correspondence import fsm
from correspondence.models import Correspondence
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, PersonnelEvent
from people.profile_change_service import (
    PROFILE_CHANGE_ALLOWLIST,
    extract_allowlisted_updates,
)


@pytest.fixture
def profile_workflow(db, create_user):
    """Org, profile_change corr_type, requester + HR approver, linked employee."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    pc_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='profile_change', label='Profile Change',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('pc_apply_requester')
    hr_user = create_user('pc_apply_hr')
    employee = Employee.objects.create(
        org_unit=org,
        employee_no='E-PC-APPLY',
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
    return SimpleNamespace(
        org=org,
        corr_type=pc_type,
        requester_user=requester_user,
        hr_user=hr_user,
        employee=employee,
    )


def _submitted_profile_change(wf, changes, reference_no):
    return Correspondence.objects.create(
        corr_type=wf.corr_type,
        subject_type='people.Employee',
        subject_id=wf.employee.pk,
        org_unit=wf.org,
        requester=wf.requester_user,
        title='Profile change request',
        payload={'changes': changes},
        status='submitted',
        reference_no=reference_no,
        current_step=0,
        current_approver_ids=[wf.hr_user.id],
        approver_chain=[
            {
                'order': 0,
                'role': 'hr',
                'intent': 'approve',
                'user_ids': [wf.hr_user.id],
            },
        ],
    )


# ── unit: allowlist extraction ─────────────────────────────────────────────

def test_extract_allowlist_keeps_known_ignores_unknown():
    changes = {
        'name_en_given': {'from': 'A', 'to': 'B'},
        'mobile_number': {'from': '0100', 'to': '0111'},
        'basic_salary': {'to': '9999.000'},
        'marital_status': {'to': 'married'},
        'date_of_birth': {'to': '1990-05-15'},
    }
    updates = extract_allowlisted_updates(changes)
    assert set(updates) <= PROFILE_CHANGE_ALLOWLIST
    assert updates['name_en_given'] == 'B'
    assert updates['date_of_birth'] == date(1990, 5, 15)
    assert 'mobile_number' not in updates
    assert 'basic_salary' not in updates
    assert 'marital_status' not in updates


def test_extract_allowlist_skips_malformed_entries():
    assert extract_allowlisted_updates({
        'full_name': 'not-a-dict',
        'gender': {'from': 'male'},  # missing "to"
    }) == {}


# ── approve mutates allowlisted fields ─────────────────────────────────────

@pytest.mark.django_db
def test_approve_applies_allowlisted_fields(profile_workflow):
    ensure_ref('nationality', 'KWT', 'Kuwaiti')
    wf = profile_workflow
    corr = _submitted_profile_change(
        wf,
        {
            'name_en_given': {'from': 'Before', 'to': 'Ahmed'},
            'name_en_family': {'from': 'Name', 'to': 'Hassan'},
            'full_name': {'from': 'Before Name', 'to': 'Ahmed Hassan'},
            'nationality': {'from': 'Egyptian', 'to': 'KWT'},
            'date_of_birth': {'to': '1990-05-15'},
            # unknown / unsafe — must be ignored
            'mobile_number': {'to': '0111'},
            'basic_salary': {'to': '9999.000'},
        },
        'PC-APPLY-APPROVE-1',
    )
    wf.employee.refresh_from_db()
    old_salary = wf.employee.basic_salary

    fsm.approve(corr, wf.hr_user)

    corr.refresh_from_db()
    wf.employee.refresh_from_db()
    assert corr.status == 'approved'
    assert wf.employee.name_en_given == 'Ahmed'
    assert wf.employee.name_en_family == 'Hassan'
    assert wf.employee.full_name == 'Ahmed Hassan'
    assert wf.employee.nationality.code == 'KWT'
    assert wf.employee.date_of_birth == date(1990, 5, 15)
    assert wf.employee.basic_salary == old_salary

    chronicle = PersonnelEvent.objects.filter(
        entity_type='Employee', entity_id=wf.employee.pk, event_kind='profile_updated',
    )
    assert chronicle.exists()
    gov = GovernanceEvent.objects.filter(
        entity_type='Employee', entity_id=wf.employee.pk, action='profile_change_applied',
    )
    assert gov.exists()


@pytest.mark.django_db
def test_approve_unknown_keys_only_does_not_mutate(profile_workflow):
    wf = profile_workflow
    before_name = wf.employee.full_name
    corr = _submitted_profile_change(
        wf,
        {
            'mobile_number': {'from': '0100', 'to': '0111'},
            'marital_status': {'to': 'married'},
            'basic_salary': {'to': '5000.000'},
        },
        'PC-APPLY-UNKNOWN-1',
    )

    fsm.approve(corr, wf.hr_user)

    corr.refresh_from_db()
    wf.employee.refresh_from_db()
    assert corr.status == 'approved'
    assert wf.employee.full_name == before_name
    assert str(wf.employee.basic_salary) == '1000.000'
    assert not PersonnelEvent.objects.filter(
        entity_type='Employee', entity_id=wf.employee.pk, event_kind='profile_updated',
    ).exists()


# ── reject must not mutate ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_reject_does_not_mutate_employee(profile_workflow):
    wf = profile_workflow
    corr = _submitted_profile_change(
        wf,
        {
            'name_en_given': {'from': 'Before', 'to': 'ShouldNotApply'},
            'full_name': {'to': 'Should Not Apply'},
        },
        'PC-APPLY-REJECT-1',
    )

    fsm.reject(corr, wf.hr_user, 'Incomplete documentation')

    corr.refresh_from_db()
    wf.employee.refresh_from_db()
    assert corr.status == 'rejected'
    assert wf.employee.name_en_given == 'Before'
    assert wf.employee.full_name == 'Before Name'
    assert not PersonnelEvent.objects.filter(
        entity_type='Employee', entity_id=wf.employee.pk, event_kind='profile_updated',
    ).exists()


@pytest.mark.django_db
def test_cancel_does_not_mutate_employee(profile_workflow):
    wf = profile_workflow
    corr = _submitted_profile_change(
        wf,
        {'full_name': {'to': 'Cancelled Name'}},
        'PC-APPLY-CANCEL-1',
    )
    # Cancel is requester-driven from actionable status.
    fsm.cancel(corr, wf.requester_user)

    corr.refresh_from_db()
    wf.employee.refresh_from_db()
    assert corr.status == 'cancelled'
    assert wf.employee.full_name == 'Before Name'
