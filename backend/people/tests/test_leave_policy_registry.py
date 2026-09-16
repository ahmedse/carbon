from people.tests.ref_helpers import ensure_ref
# File: people/tests/test_leave_policy_registry.py
# LPR-1A — LeavePolicy registry model + API regression tests.
#
# Covers:
#   (a) create with the new registry fields returns them;
#   (b) list endpoint annotates ``employee_count``;
#   (c) propagate dry_run returns counts without writing;
#   (d) propagate (non-dry) creates entitlements for eligible employees;
#   (e) propagate does not overwrite an existing entitlement's days.

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeavePolicy

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
POLICIES_URL = f'{PREFIX}/people/leave-policies/'


@pytest.fixture
def leave_type(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type')
    return ReferenceValue.objects.create(
        reference_set=rs, code='annual', label='Annual Leave', sort_order=1,
    )


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )


@pytest.fixture
def female_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-F', full_name='Alice Active',
        basic_salary='1000.000', join_date=date.today() - timedelta(days=400),
        gender=ensure_ref('gender', 'female'), is_active=True,
    )


@pytest.fixture
def male_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-M', full_name='Bob Active',
        basic_salary='2000.000', join_date=date.today() - timedelta(days=400),
        gender=ensure_ref('gender', 'male'), is_active=True,
    )


@pytest.fixture
def inactive_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-I', full_name='Carol Inactive',
        basic_salary='3000.000', join_date=date.today() - timedelta(days=400),
        gender=ensure_ref('gender', 'female'), is_active=False,
    )


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


def _make_policy(leave_type, **overrides):
    fields = {
        'leave_type': leave_type,
        'name': 'Annual Standard',
        'description': 'Standard annual leave',
        'status': 'active',
        'default_entitled_days': Decimal('30.00'),
        'gender_restriction': 'any',
        'min_service_days': 0,
        'is_active': True,
    }
    fields.update(overrides)
    return LeavePolicy.objects.create(**fields)


# ── (a) create with new fields ─────────────────────────────────────────────

@pytest.mark.django_db
def test_create_policy_returns_registry_fields(auth, create_user, leave_type, org):
    client = auth(create_user('lp_admin', is_superuser=True))
    payload = {
        'leave_type': 'annual',
        'name': 'Annual Standard',
        'description': 'Standard annual leave',
        'status': 'active',
        'effective_from': '2026-01-01',
        'effective_to': '2026-12-31',
        'default_entitled_days': '30.00',
        'applies_to_org_units': [org.id],
        'applies_to_contract_types': ['permanent', 'contract'],
        'is_active': True,
    }
    resp = client.post(POLICIES_URL, payload, format='json')
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data['name'] == 'Annual Standard'
    assert data['description'] == 'Standard annual leave'
    assert data['status'] == 'active'
    assert data['effective_from'] == '2026-01-01'
    assert data['effective_to'] == '2026-12-31'
    assert data['leave_type'] == 'annual'
    assert data['leave_type_label'] == 'Annual Leave'
    assert data['applies_to_org_units'] == [org.id]
    assert data['applies_to_contract_types'] == ['permanent', 'contract']
    assert data['employee_count'] == 0

    persisted = LeavePolicy.objects.get(pk=data['id'])
    assert persisted.name == 'Annual Standard'
    assert persisted.status == 'active'
    assert list(persisted.applies_to_org_units.values_list('id', flat=True)) == [org.id]


# ── (b) list includes employee_count ───────────────────────────────────────

@pytest.mark.django_db
def test_list_annotates_employee_count(auth, create_user, leave_type, female_employee):
    policy = _make_policy(leave_type)
    LeaveEntitlement.objects.create(
        employee=female_employee, year=date.today().year,
        leave_type=leave_type, entitled_days=Decimal('30.00'),
    )
    client = auth(create_user('lp_viewer', is_superuser=True))
    resp = client.get(POLICIES_URL)
    assert resp.status_code == 200, resp.content
    results = resp.json()['results']
    row = next(r for r in results if r['id'] == policy.id)
    assert row['employee_count'] == 1


# ── (c) propagate dry_run returns counts, no write ─────────────────────────

@pytest.mark.django_db
def test_propagate_dry_run_no_write(
    auth, create_user, leave_type, female_employee, male_employee, inactive_employee,
):
    policy = _make_policy(leave_type, gender_restriction='female')
    client = auth(create_user('lp_prop', is_superuser=True))
    resp = client.post(
        f'{POLICIES_URL}{policy.id}/propagate/?dry_run=true',
        {'year': date.today().year}, format='json',
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['year'] == date.today().year
    assert data['eligible'] == 1
    assert data['will_create'] == 1
    assert data['will_update'] == 0
    assert data['skipped'] == 1
    assert LeaveEntitlement.objects.count() == 0


# ── (d) propagate non-dry creates entitlements ─────────────────────────────

@pytest.mark.django_db
def test_propagate_creates_entitlements(
    auth, create_user, leave_type, female_employee, male_employee, inactive_employee,
):
    policy = _make_policy(leave_type, gender_restriction='female')
    client = auth(create_user('lp_prop2', is_superuser=True))
    resp = client.post(
        f'{POLICIES_URL}{policy.id}/propagate/',
        {'year': date.today().year}, format='json',
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['eligible'] == 1
    assert data['created'] == 1
    assert data['updated'] == 0

    ents = LeaveEntitlement.objects.filter(
        year=date.today().year, leave_type=leave_type,
    )
    assert ents.count() == 1
    ent = ents.get()
    assert ent.employee_id == female_employee.id
    assert ent.entitled_days == Decimal('30.00')


# ── (e) propagate does not overwrite existing entitlement days ─────────────

@pytest.mark.django_db
def test_propagate_does_not_overwrite_existing(
    auth, create_user, leave_type, female_employee,
):
    policy = _make_policy(leave_type, default_entitled_days=Decimal('30.00'))
    LeaveEntitlement.objects.create(
        employee=female_employee, year=date.today().year,
        leave_type=leave_type, entitled_days=Decimal('45.00'),
    )
    client = auth(create_user('lp_prop3', is_superuser=True))
    resp = client.post(
        f'{POLICIES_URL}{policy.id}/propagate/',
        {'year': date.today().year}, format='json',
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['created'] == 0
    assert data['updated'] == 1

    ent = LeaveEntitlement.objects.get(
        employee=female_employee, year=date.today().year, leave_type=leave_type,
    )
    assert ent.entitled_days == Decimal('45.00')
