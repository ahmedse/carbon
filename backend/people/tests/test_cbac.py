# File: people/tests/test_cbac.py
# CBAC + org-scoping regression tests for the People & Payroll app (NIR-1C).
#
# RULE_11: every authorization rule ships a regression test.
# Covers: (a) superuser full access, (b) people:view read-only, (c) no-cap 403,
# (d) org-scoped read filtering (RULE_12).

from datetime import date

import pytest

from mdm.models import OrgUnit

from people.models import Employee

PEOPLE_API = '/carbon-api/people/'
RULES_URL = PEOPLE_API + 'compliance-rules/'
EMPLOYEES_URL = PEOPLE_API + 'employees/'
PAYROLL_RUNS_URL = PEOPLE_API + 'payroll-runs/'

RULE_PAYLOAD = {
    'rule_id': 'kw-eosi-accrual',
    'version': '2026.1',
    'name': 'EOSI accrual',
    'category': 'eosi',
    'effective_date': '2026-01-01',
}


@pytest.fixture
def org_a(db):
    return OrgUnit.objects.create(name='Org A', slug='org-a')


@pytest.fixture
def org_b(db):
    return OrgUnit.objects.create(name='Org B', slug='org-b')


@pytest.fixture
def employee_a(org_a):
    return Employee.objects.create(
        org_unit=org_a, employee_no='E-A', full_name='Alice',
        basic_salary='1000.000', join_date=date(2026, 1, 1),
    )


@pytest.fixture
def employee_b(org_b):
    return Employee.objects.create(
        org_unit=org_b, employee_no='E-B', full_name='Bob',
        basic_salary='2000.000', join_date=date(2026, 1, 1),
    )


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


# ── Authentication (401) ────────────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('url', [RULES_URL, EMPLOYEES_URL, PAYROLL_RUNS_URL])
def test_unauthenticated_gets_401(api_client, url):
    assert api_client.get(url).status_code == 401


# ── (a) Superuser full access (GET 200 + POST 201) ─────────────────────────

@pytest.mark.django_db
def test_superuser_full_access(auth, create_user):
    client = auth(create_user('people_super', is_superuser=True))
    assert client.get(RULES_URL).status_code == 200
    resp = client.post(RULES_URL, RULE_PAYLOAD, format='json')
    assert resp.status_code == 201
    assert resp.json()['rule_id'] == 'kw-eosi-accrual'


@pytest.mark.django_db
def test_superuser_sees_all_employees(auth, create_user, employee_a, employee_b):
    client = auth(create_user('people_super2', is_superuser=True))
    resp = client.get(EMPLOYEES_URL)
    assert resp.status_code == 200
    employee_nos = {e['employee_no'] for e in resp.json()['results']}
    assert employee_nos == {'E-A', 'E-B'}


# ── (b) people:view-only user can read but not write ───────────────────────

@pytest.mark.django_db
def test_viewer_can_read_but_not_write(auth, create_user, create_scoped_role):
    user = create_user('people_viewer')
    create_scoped_role(user, 'viewers_group')
    client = auth(user)
    assert client.get(RULES_URL).status_code == 200
    assert client.get(EMPLOYEES_URL).status_code == 200
    resp = client.post(RULES_URL, RULE_PAYLOAD, format='json')
    assert resp.status_code == 403


# ── (c) No-capability user → 403 ───────────────────────────────────────────

@pytest.mark.django_db
def test_no_capability_user_gets_403(auth, create_user):
    client = auth(create_user('people_nothing'))
    assert client.get(RULES_URL).status_code == 403
    assert client.get(EMPLOYEES_URL).status_code == 403


# ── (d) Org-scoped user sees only own org_unit employees (RULE_12) ─────────

@pytest.mark.django_db
def test_org_scoped_user_sees_only_own_org(
    auth, create_user, create_scoped_role, org_a, employee_a, employee_b,
):
    user = create_user('people_org_viewer')
    create_scoped_role(user, 'viewers_group', org_unit=org_a)
    client = auth(user)
    resp = client.get(EMPLOYEES_URL)
    assert resp.status_code == 200
    employee_nos = [e['employee_no'] for e in resp.json()['results']]
    assert employee_nos == ['E-A']


@pytest.mark.django_db
def test_org_scoped_user_cannot_detail_outside_scope(
    auth, create_user, create_scoped_role, org_a, employee_b,
):
    user = create_user('people_org_viewer2')
    create_scoped_role(user, 'viewers_group', org_unit=org_a)
    client = auth(user)
    resp = client.get(EMPLOYEES_URL + f'{employee_b.pk}/')
    assert resp.status_code == 404
