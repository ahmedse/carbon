# File: people/tests/test_eosi.py
# P5 — EOSI provision endpoint regression tests (RULE_11).
#
# Covers:
#   1. unauthenticated → 401
#   2. user without ``people:view`` → 403
#   3. authoritative ``category='eosi'`` rule happy path (string value + lineage)
#   4. no authoritative rule → 409 (no-fabrication guard)
#   5. invalid ``as_of`` → 400
#   6. org-scoped (RULE_12) non-admin cannot read another org's employee → 404

from datetime import date

import pytest

from people.models import ComplianceRule, Employee
from people.tests.test_api import auth, employee_a, employee_b, org_a, org_b  # noqa: F401

PEOPLE_API = '/carbon-api/people/'


def _eosi_rule(authoritative=True):
    """Create an authoritative (or non-authoritative) ``category='eosi'`` rule."""
    return ComplianceRule.objects.create(
        rule_id="kw-eosi-test",
        version="2026.1",
        name="[TEST ONLY] EOSI accrual",
        category="eosi",
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["basic_salary", "service_years"],
            "formula": {
                "type": "tiered_accrual",
                "params": {
                    "base_inputs": ["basic_salary"],
                    "years_input": "service_years",
                    "divisor": 26,
                    "tiers": [
                        {"up_to": 5, "days_per_year": 15},
                        {"up_to": None, "days_per_year": 30},
                    ],
                },
            },
        },
        is_authoritative=authoritative,
    )


def _employee(org, **kwargs):
    """Create an employee in ``org`` with the EOSI test profile (basic 780)."""
    defaults = dict(
        org_unit=org,
        employee_no='E-EOSI',
        full_name='EOSI Test',
        nationality='Kuwaiti',
        basic_salary='780.000',
        join_date=date(2024, 3, 1),
    )
    defaults.update(kwargs)
    return Employee.objects.create(**defaults)


def _eosi_url(employee):
    return f'{PEOPLE_API}employees/{employee.pk}/eosi/'


# ── 1. Authentication (401) ────────────────────────────────────────────────

@pytest.mark.django_db
def test_eosi_unauthenticated_401(api_client, employee_a):
    resp = api_client.get(_eosi_url(employee_a))
    assert resp.status_code == 401


# ── 2. No-capability user → 403 ────────────────────────────────────────────

@pytest.mark.django_db
def test_eosi_no_capability_403(auth, create_user, employee_a):
    client = auth(create_user('people_eosi_nothing'))
    assert client.get(_eosi_url(employee_a)).status_code == 403


# ── 3. Happy path (authoritative rule) ─────────────────────────────────────

@pytest.mark.django_db
def test_eosi_happy_path(auth, create_user, org_a):
    _eosi_rule(authoritative=True)
    emp = _employee(org_a)
    client = auth(create_user('people_eosi_ok', is_superuser=True))
    resp = client.get(_eosi_url(emp), {'as_of': '2026-03-01'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['value'] == '900.000'
    assert body['lineage']['rule_id'] == 'kw-eosi-test'
    assert body['as_of'] == '2026-03-01'


# ── 4. No authoritative rule → 409 (no-fabrication guard) ──────────────────

@pytest.mark.django_db
def test_eosi_no_authoritative_rule_409(auth, create_user, org_a):
    _eosi_rule(authoritative=False)
    emp = _employee(org_a)
    client = auth(create_user('people_eosi_na', is_superuser=True))
    resp = client.get(_eosi_url(emp))
    assert resp.status_code == 409
    assert 'detail' in resp.json()


# ── 5. Invalid as_of → 400 ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_eosi_invalid_as_of_400(auth, create_user, org_a):
    _eosi_rule(authoritative=True)
    emp = _employee(org_a)
    client = auth(create_user('people_eosi_bad', is_superuser=True))
    resp = client.get(_eosi_url(emp), {'as_of': 'not-a-date'})
    assert resp.status_code == 400


# ── 6. Org scoping (RULE_12) → 404 ─────────────────────────────────────────

@pytest.mark.django_db
def test_eosi_org_scoped_404(auth, create_user, create_scoped_role, org_a, employee_b):
    user = create_user('people_eosi_scoped')
    create_scoped_role(user, 'viewers_group', org_unit=org_a)
    client = auth(user)
    # employee_b belongs to org_b — outside the user's visible org units.
    resp = client.get(_eosi_url(employee_b))
    assert resp.status_code == 404
