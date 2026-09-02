# File: people/tests/test_chronicle.py
# P1 — PersonnelEvent chronicle tests.
#
# Covers:
#   1. Employee create → 'hired', patch → 'profile_updated' / 'transferred',
#      delete → 'deactivated' (soft).
#   2. Position create → 'position_opened', delete → 'position_closed'.
#   3. Best-effort emission: a failing chronicle write NEVER rolls back the
#      mutation (mutation succeeds, event is dropped, CRITICAL logged).
#   4. Timeline endpoints ordered by effective_date desc and RULE_12 scoped.

from datetime import date

import pytest

from mdm.models import OrgUnit

from people.models import Employee, PersonnelEvent, Position

PEOPLE_API = '/carbon-api/people/'
EMPLOYEES_URL = PEOPLE_API + 'employees/'
POSITIONS_URL = PEOPLE_API + 'positions/'


# ── Fixtures (mirrors test_api.py) ─────────────────────────────────────────

@pytest.fixture
def org_a(db):
    return OrgUnit.objects.create(name='Org A', slug='org-a')


@pytest.fixture
def org_b(db):
    return OrgUnit.objects.create(name='Org B', slug='org-b')


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


def _employee_payload(org_unit, employee_no='E-1', full_name='Alice'):
    return {
        'org_unit': org_unit.id,
        'employee_no': employee_no,
        'full_name': full_name,
        'nationality': 'Kuwaiti',
        'basic_salary': '1000.000',
        'join_date': '2026-01-01',
    }


def _position_payload(org_unit, code='POS-1', title='Engineer'):
    return {
        'org_unit': org_unit.id,
        'code': code,
        'title': title,
        'grade': 'G1',
    }


# ── 1. Employee chronicle emissions ────────────────────────────────────────

@pytest.mark.django_db
def test_employee_create_emits_hired(auth, create_user, org_a):
    client = auth(create_user('chronicle_hire', is_superuser=True))
    resp = client.post(EMPLOYEES_URL, _employee_payload(org_a), format='json')
    assert resp.status_code == 201

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=resp.json()['id'],
    )
    assert event.event_kind == 'hired'
    assert event.before is None
    assert event.after['full_name'] == 'Alice'
    assert event.after['org_unit_id'] == org_a.id


@pytest.mark.django_db
def test_employee_patch_emits_profile_updated(auth, create_user, org_a):
    employee = _make_employee(org_a)
    client = auth(create_user('chronicle_patch', is_superuser=True))
    resp = client.patch(
        EMPLOYEES_URL + f'{employee.pk}/', {'full_name': 'Alice Smith'},
        format='json',
    )
    assert resp.status_code == 200

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='profile_updated',
    )
    assert event.before['full_name'] == 'Alice'
    assert event.after['full_name'] == 'Alice Smith'


@pytest.mark.django_db
def test_employee_patch_org_change_emits_transferred(auth, create_user, org_a, org_b):
    employee = _make_employee(org_a)
    client = auth(create_user('chronicle_transfer', is_superuser=True))
    resp = client.patch(
        EMPLOYEES_URL + f'{employee.pk}/', {'org_unit': org_b.id},
        format='json',
    )
    assert resp.status_code == 200

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='transferred',
    )
    assert event.before['org_unit_id'] == org_a.id
    assert event.after['org_unit_id'] == org_b.id


@pytest.mark.django_db
def test_employee_delete_emits_deactivated(auth, create_user, org_a):
    employee = _make_employee(org_a)
    client = auth(create_user('chronicle_deactivate', is_superuser=True))
    resp = client.delete(EMPLOYEES_URL + f'{employee.pk}/')
    assert resp.status_code == 204
    employee.refresh_from_db()
    assert employee.is_active is False

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='deactivated',
    )
    assert event.before['is_active'] is True
    assert event.after is None
    assert event.notes == 'Soft delete (is_active=False)'


# ── 2. Position chronicle emissions ────────────────────────────────────────

@pytest.mark.django_db
def test_position_create_emits_position_opened(auth, create_user, org_a):
    client = auth(create_user('chronicle_pos_open', is_superuser=True))
    resp = client.post(POSITIONS_URL, _position_payload(org_a), format='json')
    assert resp.status_code == 201

    event = PersonnelEvent.objects.get(
        entity_type='Position', entity_id=resp.json()['id'],
    )
    assert event.event_kind == 'position_opened'
    assert event.before is None
    assert event.after['code'] == 'POS-1'


@pytest.mark.django_db
def test_position_delete_emits_position_closed(auth, create_user, org_a):
    position = Position.objects.create(
        org_unit=org_a, code='POS-1', title='Engineer', grade='G1',
    )
    client = auth(create_user('chronicle_pos_close', is_superuser=True))
    resp = client.delete(POSITIONS_URL + f'{position.pk}/')
    assert resp.status_code == 204
    assert not Position.objects.filter(pk=position.pk).exists()

    event = PersonnelEvent.objects.get(
        entity_type='Position', entity_id=position.pk,
        event_kind='position_closed',
    )
    assert event.before['code'] == 'POS-1'
    assert event.after is None


# ── 3. Best-effort: emission failure never rolls back the mutation ─────────

@pytest.mark.django_db
def test_event_emission_failure_does_not_rollback_mutation(
    auth, create_user, org_a, monkeypatch,
):
    def _boom(*args, **kwargs):
        raise RuntimeError('chronicle unavailable')

    monkeypatch.setattr(
        'people.models.PersonnelEvent.objects.create', _boom,
    )

    client = auth(create_user('chronicle_failure', is_superuser=True))
    resp = client.post(EMPLOYEES_URL, _employee_payload(org_a), format='json')

    assert resp.status_code == 201
    assert Employee.objects.filter(employee_no='E-1').exists()
    assert PersonnelEvent.objects.count() == 0


# ── 4. Timeline endpoints: ordering + RULE_12 scoping ──────────────────────

@pytest.mark.django_db
def test_timeline_endpoint_ordered_and_scoped(auth, create_user, create_scoped_role, org_a, org_b):
    employee = _make_employee(org_a)
    PersonnelEvent.objects.create(
        entity_type='Employee', entity_id=employee.pk, event_kind='hired',
        effective_date=date(2026, 1, 1),
        before=None, after={'full_name': 'Alice'},
    )
    PersonnelEvent.objects.create(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='profile_updated', effective_date=date(2026, 5, 1),
        before={'full_name': 'Alice'}, after={'full_name': 'Alice Smith'},
    )

    # Admin sees both events, ordered by effective_date desc.
    client = auth(create_user('chronicle_admin', is_superuser=True))
    resp = client.get(EMPLOYEES_URL + f'{employee.pk}/timeline/')
    assert resp.status_code == 200
    kinds = [e['event_kind'] for e in resp.json()]
    assert kinds == ['profile_updated', 'hired']

    # Non-admin from another org → 404 (RULE_12).
    outsider = create_user('chronicle_outsider')
    create_scoped_role(outsider, 'viewers_group', org_unit=org_b)
    outsider_client = auth(outsider)
    resp = outsider_client.get(EMPLOYEES_URL + f'{employee.pk}/timeline/')
    assert resp.status_code == 404
