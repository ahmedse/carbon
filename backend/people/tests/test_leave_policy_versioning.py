from people.tests.ref_helpers import ensure_ref
# File: people/tests/test_leave_policy_versioning.py
# LPR-3A — LeavePolicyVersion snapshot + fork semantics tests.
#
# Covers:
#   (a) snapshot_policy returns a JSON-safe dict with the configurable fields;
#   (b) fork_policy first call → version_number == 1, effective_from set;
#   (c) fork_policy second call → version_number == 2, prior version closed;
#   (d) get_version_history ascending; latest_version returns version 2;
#   (e) GET /leave-policies/<id>/versions/ + POST fork through the API;
#   (f) LeaveEntitlement.policy_version round-trips through the serializer.

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.leave_policy_service import (
    fork_policy,
    get_version_history,
    latest_version,
    snapshot_policy,
)
from people.models import Employee, LeaveEntitlement, LeavePolicy, LeavePolicyVersion
from people.serializers import LeaveEntitlementSerializer

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
VERSIONS_URL = f'{PREFIX}/people/leave-policies/'


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


# ── (a) snapshot_policy is JSON-safe with expected keys ────────────────────

@pytest.mark.django_db
def test_snapshot_policy_json_safe(leave_type, org):
    policy = _make_policy(
        leave_type,
        default_entitled_days=Decimal('30.00'),
        applies_to_contract_types=['permanent'],
    )
    policy.applies_to_org_units.add(org)

    snap = snapshot_policy(policy)

    # JSON-serializable (no Decimal/date leakage).
    json.dumps(snap)

    expected_keys = {
        'leave_type', 'default_entitled_days', 'max_carryover_days',
        'is_carryover_allowed', 'accrual_method', 'gender_restriction',
        'requires_approval', 'min_service_days', 'name', 'description',
        'status', 'applies_to_contract_types', 'applies_to_org_units',
    }
    assert expected_keys <= set(snap.keys())
    assert snap['leave_type'] == 'annual'
    assert snap['default_entitled_days'] == '30.00'
    assert snap['name'] == 'Annual Standard'
    assert snap['status'] == 'active'
    assert snap['applies_to_contract_types'] == ['permanent']
    assert snap['applies_to_org_units'] == [org.id]


# ── (b) fork_policy first call → version 1 ─────────────────────────────────

@pytest.mark.django_db
def test_fork_policy_first_version(leave_type):
    policy = _make_policy(leave_type)
    v1 = fork_policy(policy, change_summary='initial')

    assert v1.version_number == 1
    assert v1.effective_from == timezone.localdate()
    assert v1.effective_to is None
    assert v1.snapshot['name'] == 'Annual Standard'
    assert LeavePolicyVersion.objects.filter(policy=policy).count() == 1


# ── (c) fork_policy second call closes the prior open version ──────────────

@pytest.mark.django_db
def test_fork_policy_second_closes_prior(leave_type):
    policy = _make_policy(leave_type)
    v1 = fork_policy(policy, effective_from=date(2026, 1, 1), change_summary='initial')
    v2 = fork_policy(policy, effective_from=date(2026, 2, 1), change_summary='revised')

    v1.refresh_from_db()
    assert v2.version_number == 2
    assert v2.effective_to is None
    assert v1.effective_to == date(2026, 1, 31)
    assert LeavePolicyVersion.objects.filter(policy=policy).count() == 2


# ── (d) history ascending + latest_version ─────────────────────────────────

@pytest.mark.django_db
def test_version_history_and_latest(leave_type):
    policy = _make_policy(leave_type)
    v1 = fork_policy(policy, effective_from=date(2026, 1, 1))
    v2 = fork_policy(policy, effective_from=date(2026, 2, 1))

    history = get_version_history(policy)
    assert [v.version_number for v in history] == [1, 2]

    latest = latest_version(policy)
    assert latest is not None
    assert latest.version_number == 2
    assert latest.pk == v2.pk
    assert v1.pk == history[0].pk


# ── (e) GET/POST versions API ──────────────────────────────────────────────

@pytest.mark.django_db
def test_versions_api_list_and_fork(auth, create_user, leave_type):
    policy = _make_policy(leave_type)
    fork_policy(policy, change_summary='initial')

    client = auth(create_user('lp_admin', is_superuser=True))
    url = f'{VERSIONS_URL}{policy.id}/versions/'

    resp = client.get(url)
    assert resp.status_code == 200, resp.content
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['version_number'] == 1

    resp = client.post(url, {'change_summary': 'second version'}, format='json')
    assert resp.status_code == 201, resp.content
    assert resp.json()['version_number'] == 2
    assert resp.json()['change_summary'] == 'second version'

    resp = client.get(url)
    assert resp.status_code == 200, resp.content
    assert resp.json()['count'] == 2


# ── (f) entitlement policy_version round-trips through serializer ──────────

@pytest.mark.django_db
def test_entitlement_policy_version_roundtrip(leave_type, female_employee):
    policy = _make_policy(leave_type)
    v1 = fork_policy(policy, change_summary='initial')

    ent = LeaveEntitlement.objects.create(
        employee=female_employee, year=date.today().year, leave_type=leave_type,
        entitled_days=Decimal('30.00'), policy=policy, policy_version=v1,
    )

    data = LeaveEntitlementSerializer(ent).data
    assert data['policy_version'] == v1.id
    assert data['policy_version_number'] == 1
    assert data['policy'] == policy.id
