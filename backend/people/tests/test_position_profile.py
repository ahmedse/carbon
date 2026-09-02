# File: people/tests/test_position_profile.py
# P4 — Position lifecycle (status/FTE/job family) + employee→position
# incumbent-link tests (design §3.3 / P4 row).
#
# Covers:
#   1. status/fte/job_family_code round-trip through the API and DB.
#   2. Defaults on a minimal payload: status='filled', fte='1.00'.
#   3. A status transition open→filled emits a 'position_filled' PersonnelEvent.
#   4. Governed job_family codes validated against mdm.ReferenceSet ('job_family').
#   5. Employee.position links an incumbent (reverse 'incumbents' queryset works).
#   6. Employee.position round-trips in the serializer on create.

from datetime import date
from decimal import Decimal

import pytest

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue

from people.models import Employee, PersonnelEvent, Position

PEOPLE_API = '/carbon-api/people/'
POSITIONS_URL = PEOPLE_API + 'positions/'
EMPLOYEES_URL = PEOPLE_API + 'employees/'


# ── Fixtures (mirrors test_profile.py) ─────────────────────────────────

@pytest.fixture
def org_a(db):
    return OrgUnit.objects.create(name='Org A', slug='org-a')


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


def _make_employee(org_unit, employee_no='E-1', full_name='Alice'):
    return Employee.objects.create(
        org_unit=org_unit, employee_no=employee_no, full_name=full_name,
        nationality='Kuwaiti', basic_salary='1000.000',
        join_date=date(2026, 1, 1),
    )


def _position_payload(org_unit, code='P-1', title='Driller'):
    return {'org_unit': org_unit.id, 'code': code, 'title': title}


def _employee_payload(org_unit, employee_no='E-1', full_name='Alice'):
    return {
        'org_unit': org_unit.id,
        'employee_no': employee_no,
        'full_name': full_name,
        'nationality': 'Kuwaiti',
        'basic_salary': '1000.000',
        'join_date': '2026-01-01',
    }


# ── 1. status/fte/job_family round-trip ────────────────────────────────

@pytest.mark.django_db
def test_position_round_trips_status_fte_job_family(auth, create_user, org_a):
    client = auth(create_user('position_roundtrip', is_superuser=True))

    payload = _position_payload(org_a)
    payload.update({'status': 'open', 'fte': '1.50', 'job_family_code': 'JF'})
    resp = client.post(POSITIONS_URL, payload, format='json')
    assert resp.status_code == 201

    data = resp.json()
    assert data['status'] == 'open'
    assert data['fte'] == '1.50'
    assert data['job_family_code'] == 'JF'

    # DB round-trip: stored values match what the API returned.
    position = Position.objects.get(pk=data['id'])
    assert position.status == 'open'
    assert position.fte == Decimal('1.50')
    assert position.job_family_code == 'JF'


# ── 2. Defaults are filled / 1.00 FTE ──────────────────────────────────

@pytest.mark.django_db
def test_position_defaults_filled_and_fte_one(auth, create_user, org_a):
    client = auth(create_user('position_defaults', is_superuser=True))

    resp = client.post(POSITIONS_URL, _position_payload(org_a), format='json')
    assert resp.status_code == 201

    data = resp.json()
    assert data['status'] == 'filled'
    assert data['fte'] == '1.00'
    assert Decimal(data['fte']) == Decimal('1.00')
    assert data['job_family_code'] == ''


# ── 3. Status transition open→filled emits position_filled ─────────────

@pytest.mark.django_db
def test_position_status_transition_emits_position_filled(auth, create_user, org_a):
    position = Position.objects.create(
        org_unit=org_a, code='P-1', title='Driller', status='open',
    )
    client = auth(create_user('position_transition', is_superuser=True))

    resp = client.patch(
        POSITIONS_URL + f'{position.pk}/', {'status': 'filled'},
        format='json',
    )
    assert resp.status_code == 200

    event = PersonnelEvent.objects.get(
        entity_type='Position', entity_id=position.pk,
        event_kind='position_filled',
    )
    assert event.after['status'] == 'filled'


# ── 4. Governed job_family validation ──────────────────────────────────

@pytest.mark.django_db
def test_position_invalid_job_family_code_rejected(auth, create_user, org_a):
    ref_set = ReferenceSet.objects.create(name='job_family', slug='job_family')
    ReferenceValue.objects.create(reference_set=ref_set, code='ENG', label='Engineering')

    client = auth(create_user('position_rs_invalid', is_superuser=True))

    bad = _position_payload(org_a, code='P-BAD')
    bad['job_family_code'] = 'NOPE'
    resp = client.post(POSITIONS_URL, bad, format='json')
    assert resp.status_code == 400
    body = resp.json()
    assert body['error'] == 'ValidationError'
    assert 'job_family_code' in body['message']


# ── 5. Employee→position incumbent link ────────────────────────────────

@pytest.mark.django_db
def test_employee_position_link_sets_incumbent(auth, create_user, org_a):
    position = Position.objects.create(
        org_unit=org_a, code='P-1', title='Driller', status='open',
    )
    employee = _make_employee(org_a)
    client = auth(create_user('position_incumbent', is_superuser=True))

    resp = client.patch(
        EMPLOYEES_URL + f'{employee.pk}/', {'position': position.pk},
        format='json',
    )
    assert resp.status_code == 200

    employee.refresh_from_db()
    assert employee.position_id == position.pk
    assert position.incumbents.filter(pk=employee.pk).exists()

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='profile_updated',
    )
    assert event.before['position_id'] is None
    assert event.after['position_id'] == position.pk


# ── 6. Employee serializer round-trips position on create ──────────────

@pytest.mark.django_db
def test_employee_position_round_trips_in_serializer(auth, create_user, org_a):
    position = Position.objects.create(
        org_unit=org_a, code='P-1', title='Driller', status='open',
    )
    client = auth(create_user('position_serializer', is_superuser=True))

    payload = _employee_payload(org_a, employee_no='E-P4-1', full_name='Sara')
    payload['position'] = position.pk
    resp = client.post(EMPLOYEES_URL, payload, format='json')
    assert resp.status_code == 201
    assert resp.json()['position'] == position.pk
