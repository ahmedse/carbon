"""Official People inbound templates + leave smoke reject/accept (DMS templates)."""
import io
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from rest_framework.test import APIClient

from inbound.models import InboundTemplate
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.inbound_cartridges import BALANCE_FIELDS, EMPLOYEE_FIELDS, HISTORY_FIELDS
from people.models import Employee
from people.official_inbound_templates import (
    OFFICIAL_TEMPLATES,
    ensure_official_inbound_templates,
    identity_columns,
)


PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'
EXAMPLES = Path(settings.BASE_DIR).parent / 'docs' / 'migration' / 'examples'


def _csv(text):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = 't.csv'
    return buf


def _auth(client, user, get_token_for_user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='HR', slug='hr-tpl', code='HR', org_type='department')


@pytest.fixture
def leave_annual(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type-tpl')
    return ReferenceValue.objects.create(reference_set=rs, code='annual', label='Annual')


@pytest.fixture
def prep_cmt(create_user, create_scoped_role):
    prep = create_user('tpl_prep')
    cmt = create_user('tpl_cmt')
    create_scoped_role(prep, 'people_data_owners_group')
    create_scoped_role(cmt, 'people_lead')
    return prep, cmt


@pytest.mark.django_db
def test_ensure_official_templates_idempotent_and_identity_map():
    """B1–B3: one official row per cartridge; identity columns; second run no-op."""
    first = ensure_official_inbound_templates()
    assert first['created'] == 3
    assert first['existing'] == 0
    assert first['expected'] == 3

    by_key = {spec['target_key']: spec for spec in OFFICIAL_TEMPLATES}
    for row in InboundTemplate.objects.filter(
        name__in=[s['name'] for s in OFFICIAL_TEMPLATES],
    ):
        spec = by_key[row.target_key]
        expected = identity_columns(spec['fields'])
        assert row.kind == 'typed_object'
        assert row.mapping.get('columns') == expected
        assert set(row.mapping['columns']) == {f['name'] for f in spec['fields']}
        assert all(k == v for k, v in row.mapping['columns'].items())

    # Operator customization must stick (R8).
    snap = InboundTemplate.objects.get(
        name='People · Employee snapshot',
        target_key='people.employee_snapshot',
    )
    snap.mapping = {'columns': {'Code': 'employee_no'}, 'crosswalks': {}}
    snap.save(update_fields=['mapping', 'updated_at'])

    second = ensure_official_inbound_templates()
    assert second['created'] == 0
    assert second['existing'] == 3
    snap.refresh_from_db()
    assert snap.mapping['columns'] == {'Code': 'employee_no'}

    call_command('ensure_people_inbound_templates')
    assert InboundTemplate.objects.filter(
        name='People · Employee snapshot',
        target_key='people.employee_snapshot',
    ).count() == 1


def test_entrypoint_hooks_ensure_people_inbound_templates():
    """Fresh deploy path (entrypoint after migrate) calls create-only ensure — not AppConfig.ready()."""
    entrypoint = Path(settings.BASE_DIR) / 'entrypoint.sh'
    text = entrypoint.read_text(encoding='utf-8')
    assert 'ensure_people_inbound_templates' in text
    assert 'ensure_nibras_admins' in text
    apps_py = Path(settings.BASE_DIR) / 'people' / 'apps.py'
    apps_text = apps_py.read_text(encoding='utf-8')
    assert 'ensure_official_inbound_templates' not in apps_text
    assert 'ensure_people_inbound_templates' not in apps_text


@pytest.mark.django_db
def test_official_templates_listed_for_target(prep_cmt, get_token_for_user):
    """B8: Map SearchSelect source lists official name for matching target_key."""
    ensure_official_inbound_templates()
    prep, _ = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.get(
        f'{PREFIX}/templates/',
        {'kind': 'typed_object', 'target_key': 'people.leave_opening_balance'},
    )
    assert res.status_code == 200
    rows = res.data if isinstance(res.data, list) else res.data.get('results', [])
    names = {row['name'] for row in rows}
    assert 'People · Leave opening balance' in names
    assert 'People · Employee snapshot' not in names


@pytest.mark.django_db
def test_example_csv_headers_match_cartridge_fields():
    """B5b: template + bulk headers match declared field names in order."""
    pairs = [
        ('people-employee-snapshot', EMPLOYEE_FIELDS),
        ('people-leave-opening-balance', BALANCE_FIELDS),
        ('people-leave-history', HISTORY_FIELDS),
    ]
    for stem, fields in pairs:
        expected = ','.join(f['name'] for f in fields)
        for suffix in ('.template.csv', '.bulk.csv'):
            path = EXAMPLES / f'{stem}{suffix}'
            header = path.read_text(encoding='utf-8').splitlines()[0].strip()
            assert header == expected, f'{path.name}: {header!r} != {expected!r}'


@pytest.mark.django_db
def test_leave_balance_smoke_rejects_unknown_employee(prep_cmt, leave_annual, get_token_for_user):
    """B4: absent employee_no → reject; reason employee not found."""
    prep, _ = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_opening_balance',
    }, format='json')
    bid = res.data['id']
    body = (
        'employee_no,year,leave_type,entitled_days,used_days,carried_forward\n'
        'DMSDEV9101,2026,annual,30,0,0\n'
    )
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': identity_columns(BALANCE_FIELDS),
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['reject'] >= 1
    assert Employee.objects.count() == 0
    reasons = ' '.join(r.get('reason', '') for r in res.data['smoke'].get('reject_rows') or [])
    assert 'employee not found' in reasons


@pytest.mark.django_db
def test_leave_balance_smoke_accepts_known_employee(
    prep_cmt, org, leave_annual, get_token_for_user,
):
    """B5: existing employee + valid leave_type → reject == 0."""
    prep, _ = prep_cmt
    Employee.objects.create(
        org_unit=org, employee_no='DMSDEV9101', full_name='Sample DMS',
        basic_salary=Decimal('200.000'),
    )
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_opening_balance',
    }, format='json')
    bid = res.data['id']
    body = (
        'employee_no,year,leave_type,entitled_days,used_days,carried_forward\n'
        'DMSDEV9101,2026,annual,30,4,0\n'
    )
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': identity_columns(BALANCE_FIELDS),
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['reject'] == 0
    assert res.data['smoke']['insert'] + res.data['smoke']['update'] == 1


@pytest.mark.django_db
def test_leave_history_smoke_rejects_unknown_employee(prep_cmt, leave_annual, get_token_for_user):
    """B4 for history cartridge."""
    prep, _ = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_history',
    }, format='json')
    bid = res.data['id']
    body = (
        'employee_no,leave_type,start_date,end_date,days,status\n'
        'DMSDEV9200,annual,2026-01-10,2026-01-12,3,approved\n'
    )
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': identity_columns(HISTORY_FIELDS),
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['reject'] >= 1
    reasons = ' '.join(r.get('reason', '') for r in res.data['smoke'].get('reject_rows') or [])
    assert 'employee not found' in reasons
