"""Phase OF-6 — Correspondence + self-service CBAC capabilities.

Covers:
  - Active employee auto-derives self-service caps (my:access, correspondence:submit)
  - Manager (has direct_reports) auto-derives team:access
  - Non-employee gets no self-service caps
  - Open approver (correspondence:act) auto-derived from current_approver_ids
  - correspondence:admin implies act/submit/my/team via IMPLIES + people_lead group
"""

from decimal import Decimal

import pytest
from django.apps import apps

from accounts.capabilities import has_capability


# ── Lazy model helpers (avoid top-level cross-app imports) ──────────

def _org_unit(name):
    OrgUnit = apps.get_model('mdm', 'OrgUnit')
    return OrgUnit.objects.create(name=name, org_type='department')


def _corr_type():
    ReferenceSet = apps.get_model('mdm', 'ReferenceSet')
    ReferenceValue = apps.get_model('mdm', 'ReferenceValue')
    rs = ReferenceSet.objects.create(name='Correspondence Type OF6')
    return ReferenceValue.objects.create(
        reference_set=rs, code='leave', label='Leave Request'
    )


def _employee(org_unit, user, employee_no, manager=None):
    Employee = apps.get_model('people', 'Employee')
    return Employee.objects.create(
        org_unit=org_unit,
        employee_no=employee_no,
        full_name=f'Employee {employee_no}',
        user=user,
        basic_salary=Decimal('1000.000'),
        is_active=True,
        manager=manager,
    )


@pytest.mark.django_db
def test_active_employee_gets_self_service_caps(create_user):
    org = _org_unit('OF6 Unit A')
    user = create_user('of6_emp1')
    _employee(org, user, 'OF6-E001')

    assert has_capability(user, 'my:access') is True
    assert has_capability(user, 'correspondence:submit') is True


@pytest.mark.django_db
def test_manager_gets_team_access(create_user):
    org = _org_unit('OF6 Unit B')
    mgr_user = create_user('of6_mgr1')
    report_user = create_user('of6_rep1')

    mgr = _employee(org, mgr_user, 'OF6-M001')
    _employee(org, report_user, 'OF6-R001', manager=mgr)

    assert has_capability(mgr_user, 'team:access') is True


@pytest.mark.django_db
def test_non_employee_gets_no_self_service(create_user):
    user = create_user('of6_plain1')

    assert has_capability(user, 'my:access') is False
    assert has_capability(user, 'correspondence:submit') is False


@pytest.mark.django_db
def test_approver_gets_act_capability(create_user):
    org = _org_unit('OF6 Unit C')
    corr_type = _corr_type()
    approver = create_user('of6_approver1')
    requester = create_user('of6_requester1')

    # Derivation requires an active employee profile before consulting
    # open approvals — link the approver to one.
    _employee(org, approver, 'OF6-A001')

    Correspondence = apps.get_model('correspondence', 'Correspondence')
    Correspondence.objects.create(
        reference_no='OF6-0001',
        corr_type=corr_type,
        org_unit=org,
        requester=requester,
        title='Leave request',
        status='submitted',
        current_approver_ids=[approver.id],
    )

    assert has_capability(approver, 'correspondence:act') is True


@pytest.mark.django_db
def test_correspondence_admin_implies_act_and_my(create_user, create_scoped_role):
    user = create_user('of6_lead1', groups=['people_lead'])
    create_scoped_role(user, 'people_lead')

    assert has_capability(user, 'correspondence:admin') is True
    assert has_capability(user, 'correspondence:act') is True
    assert has_capability(user, 'my:access') is True
