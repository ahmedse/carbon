# File: people/tests/test_profile.py
# P3 — Employee profile enrichment tests (design §3.2).
#
# Covers:
#   1. New bilingual identity + Kuwait HR profile fields round-trip through
#      the API (serializer exposes them).
#   2. New fields are optional — a minimal payload still succeeds (backwards
#      compatibility with existing employees/API clients).
#   3. Governed-enum codes: an invalid ``nationality_code`` -> 400; a code
#      that IS in the set passes (mdm.ReferenceSet).
#   4. Missing reference set is lenient (no crash on unseeded reference data).
#   5. A ``basic_salary`` patch emits a ``salary_change`` PersonnelEvent.

from datetime import date

import pytest

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue

from people.models import Employee, PersonnelEvent

PEOPLE_API = '/carbon-api/people/'
EMPLOYEES_URL = PEOPLE_API + 'employees/'


# ── Fixtures (mirrors test_chronicle.py) ─────────────────────────────────

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


def _employee_payload(org_unit, employee_no='E-1', full_name='Alice'):
    return {
        'org_unit': org_unit.id,
        'employee_no': employee_no,
        'full_name': full_name,
        'nationality': 'Kuwaiti',
        'basic_salary': '1000.000',
        'join_date': '2026-01-01',
    }


# ── 1. Serializer exposes the new P3 fields ──────────────────────────────

@pytest.mark.django_db
def test_serializer_round_trips_new_profile_fields(auth, create_user, org_a):
    manager = _make_employee(org_a, employee_no='E-MGR', full_name='Boss')
    client = auth(create_user('profile_roundtrip', is_superuser=True))

    payload = _employee_payload(org_a, employee_no='E-P3-1', full_name='Fatima Al-Sabah')
    payload.update({
        'name_en_given': 'Fatima',
        'name_en_family': 'Al-Sabah',
        'name_ar_given': 'فاطمة',
        'name_ar_family': 'الصباح',
        'civil_id': '284051234567',
        'date_of_birth': '1990-05-15',
        'gender': 'female',
        'kuwaitization': True,
        'manager': manager.pk,
    })
    resp = client.post(EMPLOYEES_URL, payload, format='json')
    assert resp.status_code == 201

    data = resp.json()
    for field in (
        'name_en_given', 'name_en_family', 'name_ar_given', 'name_ar_family',
        'civil_id', 'date_of_birth', 'gender', 'kuwaitization', 'manager',
    ):
        assert field in data
    assert data['name_en_given'] == 'Fatima'
    assert data['name_en_family'] == 'Al-Sabah'
    assert data['name_ar_given'] == 'فاطمة'
    assert data['name_ar_family'] == 'الصباح'
    assert data['civil_id'] == '284051234567'
    assert data['date_of_birth'] == '1990-05-15'
    assert data['gender'] == 'female'
    assert data['kuwaitization'] is True
    assert data['manager'] == manager.pk
    assert data['nationality_code'] == ''
    assert data['employment_type_code'] == ''
    assert data['contract_type_code'] == ''

    # DB round-trip: stored values match what the API returned.
    employee = Employee.objects.get(pk=data['id'])
    assert employee.name_en_given == 'Fatima'
    assert employee.civil_id == '284051234567'
    assert employee.manager_id == manager.pk


# ── 2. New fields are optional (backwards compatible) ────────────────────

@pytest.mark.django_db
def test_blank_new_fields_allowed(auth, create_user, org_a):
    client = auth(create_user('profile_minimal', is_superuser=True))
    resp = client.post(
        EMPLOYEES_URL,
        _employee_payload(org_a, employee_no='E-MIN', full_name='Bob'),
        format='json',
    )
    assert resp.status_code == 201

    data = resp.json()
    assert data['name_en_given'] == ''
    assert data['name_en_family'] == ''
    assert data['name_ar_given'] == ''
    assert data['name_ar_family'] == ''
    assert data['civil_id'] == ''
    assert data['date_of_birth'] is None
    assert data['gender'] == ''
    assert data['nationality_code'] == ''
    assert data['employment_type_code'] == ''
    assert data['contract_type_code'] == ''
    assert data['kuwaitization'] is False
    assert data['manager'] is None


# ── 3. Governed-enum codes validated against mdm.ReferenceSet ─────────────

@pytest.mark.django_db
def test_invalid_nationality_code_rejected(auth, create_user, org_a):
    ref_set = ReferenceSet.objects.create(name='nationality', slug='nationality')
    ReferenceValue.objects.create(reference_set=ref_set, code='KW', label='Kuwaiti')
    ReferenceValue.objects.create(reference_set=ref_set, code='EG', label='Egyptian')

    client = auth(create_user('profile_rs_invalid', is_superuser=True))

    bad = _employee_payload(org_a, employee_no='E-RS-BAD', full_name='Bad')
    bad['nationality_code'] = 'XX'
    resp = client.post(EMPLOYEES_URL, bad, format='json')
    assert resp.status_code == 400
    body = resp.json()
    assert body['error'] == 'ValidationError'
    assert 'nationality_code' in body['message']

    good = _employee_payload(org_a, employee_no='E-RS-OK', full_name='Good')
    good['nationality_code'] = 'KW'
    resp = client.post(EMPLOYEES_URL, good, format='json')
    assert resp.status_code == 201
    assert resp.json()['nationality_code'] == 'KW'


# ── 4. Missing reference set is lenient ──────────────────────────────────

@pytest.mark.django_db
def test_missing_reference_set_is_lenient(auth, create_user, org_a):
    client = auth(create_user('profile_lenient', is_superuser=True))
    payload = _employee_payload(org_a, employee_no='E-LEN', full_name='Lenny')
    payload['nationality_code'] = 'XYZ'  # no 'nationality' set exists -> skip
    resp = client.post(EMPLOYEES_URL, payload, format='json')
    assert resp.status_code == 201
    assert resp.json()['nationality_code'] == 'XYZ'


# ── 5. Salary change emits salary_change chronicle event ──────────────────

@pytest.mark.django_db
def test_salary_patch_emits_salary_change(auth, create_user, org_a):
    employee = _make_employee(org_a)
    client = auth(create_user('chronicle_salary', is_superuser=True))

    resp = client.patch(
        EMPLOYEES_URL + f'{employee.pk}/', {'basic_salary': '2500.000'},
        format='json',
    )
    assert resp.status_code == 200

    event = PersonnelEvent.objects.get(
        entity_type='Employee', entity_id=employee.pk,
        event_kind='salary_change',
    )
    assert event.before['basic_salary'] == '1000.000'
    assert event.after['basic_salary'] == '2500.000'
