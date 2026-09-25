"""DRF roster analytics — same aggregator as Pulse, Plane A on HTTP."""
from datetime import date

import pytest

from mdm.models import OrgUnit
from people.models import Employee

ANALYTICS = '/carbon-api/people/analytics/'


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='Headcount Org', slug='hc-org', org_type='company')


@pytest.fixture
def roster(org):
    Employee.objects.create(
        org_unit=org, employee_no='HC-1', full_name='One',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    Employee.objects.create(
        org_unit=org, employee_no='HC-2', full_name='Two',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=False,
    )
    return org


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_http_analytics_returns_declared_fields(roster, auth, create_user):
    client = auth(create_user('hc_admin', is_superuser=True))
    resp = client.get(ANALYTICS, {'dimension': 'is_active'})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['dimension'] == 'is_active'
    assert data['total'] == 2
    labels = {row['label'] for row in data['breakdown']}
    assert 'True' in labels or True in {row['label'] for row in data['breakdown']}
    assert set(data['breakdown'][0]) >= {'label', 'count', 'pct'}
    assert 'average' not in data
    assert all('amount' not in row for row in data['breakdown'])


@pytest.mark.django_db
def test_http_analytics_403_without_people_view(roster, auth, create_user):
    user = create_user('hc_ess')
    resp = auth(user).get(ANALYTICS, {'dimension': 'is_active'})
    assert resp.status_code == 403
    assert '1000' not in str(resp.json())


@pytest.mark.django_db
def test_http_analytics_unknown_dimension_400(roster, auth, create_user):
    resp = auth(create_user('hc_admin2', is_superuser=True)).get(
        ANALYTICS, {'dimension': 'salary'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_http_matches_summarize_headcount(roster, auth, create_user):
    from people.headcount import summarize_headcount

    user = create_user('hc_admin3', is_superuser=True)
    code, payload = summarize_headcount(user, {'dimension': 'is_active'})
    resp = auth(user).get(ANALYTICS, {'dimension': 'is_active'})
    assert resp.status_code == code
    assert resp.json()['total'] == payload['total']
    assert resp.json()['breakdown'] == payload['breakdown']
