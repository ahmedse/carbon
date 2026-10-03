"""DMS-COR-LEAVE: opening balance upserts; history does not increment used_days."""
import io
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.inbound_cartridges import _clean, _date
from people.models import Employee, LeaveEntitlement, LeaveRecord


PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'


def _csv(text):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = 't.csv'
    return buf


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='HR', slug='hr-inb', code='HR', org_type='department')


@pytest.fixture
def leave_annual(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type-inb')
    return ReferenceValue.objects.create(reference_set=rs, code='annual', label='Annual')


@pytest.fixture
def prep_cmt(create_user, create_scoped_role):
    prep = create_user('inb_prep')
    cmt = create_user('inb_cmt')
    create_scoped_role(prep, 'people_data_owners_group')
    create_scoped_role(cmt, 'people_lead')
    return prep, cmt


def _auth(client, user, get_token_for_user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.mark.django_db
def test_employee_snapshot_smoke_zero_writes(prep_cmt, org, get_token_for_user):
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid = res.data['id']
    body = 'Code,FullNameEn,Cost Center,Salary\n1067,Bilagot,HR,100.000\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
        },
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 1
    assert res.data['smoke']['sample'][0]['key'] == '1067'
    assert 'employee_no' not in res.data['smoke']['sample'][0]
    assert Employee.objects.count() == 0


@pytest.mark.django_db
def test_employee_snapshot_commit_idempotent(prep_cmt, org, get_token_for_user):
    prep, cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid = res.data['id']
    body = (
        'Code,FullNameEn,Cost Center,Salary,Manager\n'
        '1067,Bilagot,HR,100.000,1712\n'
        '1712,Mohammad,HR,200.000,\n'
    )
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
            'Manager': 'manager_employee_no',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert Employee.objects.count() == 2
    emp = Employee.objects.get(employee_no='1067')
    assert emp.manager.employee_no == '1712'

    # second batch updates, no dupes
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid2 = res.data['id']
    body2 = 'Code,FullNameEn,Cost Center,Salary\n1067,Bilagot Updated,HR,150.000\n'
    client.post(f'{PREFIX}/batches/{bid2}/file/', {'file': _csv(body2)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid2}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid2}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid2}/commit/', {}, format='json')
    assert res.status_code == 200
    assert Employee.objects.count() == 2
    assert Employee.objects.get(employee_no='1067').full_name == 'Bilagot Updated'
    assert Employee.objects.get(employee_no='1067').basic_salary == Decimal('150.000')


@pytest.mark.django_db
def test_leave_opening_balance_upsert(prep_cmt, org, leave_annual, get_token_for_user):
    prep, cmt = prep_cmt
    emp = Employee.objects.create(
        org_unit=org, employee_no='1067', full_name='Bilagot',
        basic_salary=Decimal('100.000'),
    )
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_opening_balance',
    }, format='json')
    bid = res.data['id']
    body = 'emp,year,type,entitled,used\n1067,2026,annual,30,4\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'emp': 'employee_no', 'year': 'year', 'type': 'leave_type',
            'entitled': 'entitled_days', 'used': 'used_days',
        },
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert LeaveEntitlement.objects.count() == 0
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    ent = LeaveEntitlement.objects.get(employee=emp, year=2026, leave_type=leave_annual)
    assert ent.entitled_days == Decimal('30')
    assert ent.used_days == Decimal('4')


@pytest.mark.django_db
def test_leave_history_does_not_add_used_days(prep_cmt, org, leave_annual, get_token_for_user):
    """DMS-COR-LEAVE"""
    prep, cmt = prep_cmt
    emp = Employee.objects.create(
        org_unit=org, employee_no='1067', full_name='Bilagot',
        basic_salary=Decimal('100.000'),
    )
    LeaveEntitlement.objects.create(
        employee=emp, year=2026, leave_type=leave_annual,
        entitled_days=Decimal('30'), used_days=Decimal('5'),
    )
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_history',
    }, format='json')
    bid = res.data['id']
    body = 'emp,type,start,end,days\n1067,annual,2026-01-10,2026-01-12,3\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'emp': 'employee_no', 'type': 'leave_type',
            'start': 'start_date', 'end': 'end_date', 'days': 'days',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert LeaveRecord.objects.count() == 1
    ent = LeaveEntitlement.objects.get(employee=emp, year=2026)
    assert ent.used_days == Decimal('5')


def _smoke_batch(client, body, columns, target_key='people.employee_snapshot'):
    """Create → upload → map, returning the batch id. Smoke is left to the caller."""
    res = client.post(
        f'{PREFIX}/batches/',
        {'kind': 'typed_object', 'target_key': target_key},
        format='json',
    )
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': columns}, format='json')
    return bid


@pytest.mark.django_db
def test_employee_snapshot_smoke_records_structured_result_per_row(
    prep_cmt, org, get_token_for_user,
):
    """A pass row has an OK result; a failing row names the field and the fix."""
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    body = (
        'Code,FullNameEn,Cost Center,Salary\n'
        '1067,Bilagot,HR,100.000\n'
        '1999,,HR,\n'
    )
    bid = _smoke_batch(client, body, {
        'Code': 'employee_no',
        'FullNameEn': 'full_name',
        'Cost Center': 'org_unit',
        'Salary': 'basic_salary',
    })
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    smoke = res.data['smoke']

    assert len(smoke['results']) == 2
    by_row = {row['row']: row for row in smoke['results']}

    ok = by_row[1]
    assert ok['verdict'] == 'insert'
    assert ok['reason'] == ''
    assert 'issues' not in ok

    bad = by_row[2]
    assert bad['verdict'] == 'reject'
    assert bad['reason']
    fields = {item['field'] for item in bad['issues']}
    assert fields == {'full_name', 'basic_salary'}
    assert all(item['fix'] for item in bad['issues'])
    assert [row['row'] for row in smoke['reject_rows']] == [2]
    assert smoke['reject_rows'][0]['issues'] == bad['issues']

    # The raw CSV header never leaks into the envelope.
    assert 'Code' not in ok
    # Verdict vocabulary stays stable: insert/update/reject for this cartridge.
    assert {row['verdict'] for row in smoke['results']} == {'insert', 'reject'}


@pytest.mark.django_db
def test_employee_snapshot_rows_join_smoke_beyond_the_sample(prep_cmt, org, get_token_for_user):
    """Every file row carries its smoke verdict, not only the <=20 sample."""
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    lines = ['Code,FullNameEn,Cost Center,Salary']
    for i in range(1, 26):
        lines.append(f'DMSDEV9{i:03d},Employee {i},HR,{100 + i}.000')
    bid = _smoke_batch(client, '\n'.join(lines) + '\n', {
        'Code': 'employee_no',
        'FullNameEn': 'full_name',
        'Cost Center': 'org_unit',
        'Salary': 'basic_salary',
    })
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 25
    assert len(res.data['smoke']['results']) == 25
    assert len(res.data['smoke']['sample']) == 20

    # Row 21 is past the sample and still carries the run's verdict.
    rows = client.get(f'{PREFIX}/batches/{bid}/rows/?page=3&page_size=10')
    assert rows.status_code == 200
    assert rows.data['smoked'] is True
    assert rows.data['results'][0]['row'] == 21
    assert rows.data['results'][0]['verdict'] == 'insert'
    assert rows.data['results'][0]['reason'] == ''


@pytest.mark.django_db
def test_batch_rows_reports_not_smoked(prep_cmt, org, get_token_for_user):
    """Before smoke every row reads 'not smoked', never a false pass."""
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    bid = _smoke_batch(
        client,
        'Code,FullNameEn,Cost Center,Salary\n1067,Bilagot,HR,100.000\n',
        {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
        },
    )
    rows = client.get(f'{PREFIX}/batches/{bid}/rows/')
    assert rows.status_code == 200
    assert rows.data['smoked'] is False
    assert rows.data['results'][0]['verdict'] == ''
    assert rows.data['results'][0]['issues'] == []


@pytest.mark.django_db
def test_employee_snapshot_commit_accepts_example_template_date_format(
    prep_cmt, org, get_token_for_user,
):
    """Regression: the shipped example template uses M/D/YYYY join_date.

    A raw string in ``Employee.join_date`` raised an unhandled
    ``django.core.exceptions.ValidationError`` mid-commit, which the DRF
    handler surfaced as a generic 500. With one good row and one reject,
    ``allow_partial`` must commit the good row (with a real date) and leave
    the reject out.
    """
    prep, cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    body = (
        'employee_no,full_name,org_unit,join_date,basic_salary\n'
        'DMSDEV9101,,,1/1/2024,0\n'
        'DMSDEV9102,Sample002 DMS,HR,1/2/2024,210\n'
    )
    bid = _smoke_batch(client, body, {
        'employee_no': 'employee_no',
        'full_name': 'full_name',
        'org_unit': 'org_unit',
        'join_date': 'join_date',
        'basic_salary': 'basic_salary',
    })
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 1
    assert res.data['smoke']['reject'] == 1

    _auth(client, cmt, get_token_for_user)
    res = client.post(
        f'{PREFIX}/batches/{bid}/commit/', {'allow_partial': True}, format='json',
    )
    assert res.status_code == 200, res.data
    assert Employee.objects.count() == 1
    assert Employee.objects.get(employee_no='DMSDEV9102').join_date == date(2024, 1, 2)


@pytest.mark.django_db
def test_employee_snapshot_smoke_rejects_unparseable_join_date(
    prep_cmt, org, get_token_for_user,
):
    """A genuinely bad date is a clean smoke reject, never a commit-time 500."""
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    bid = _smoke_batch(
        client,
        'employee_no,full_name,org_unit,join_date,basic_salary\n'
        'DMSDEV9103,Sample003 DMS,HR,not-a-date,220\n',
        {
            'employee_no': 'employee_no',
            'full_name': 'full_name',
            'org_unit': 'org_unit',
            'join_date': 'join_date',
            'basic_salary': 'basic_salary',
        },
    )
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['reject'] == 1
    issues = res.data['smoke']['reject_rows'][0]['issues']
    assert any(item['field'] == 'join_date' for item in issues)
    bad = next(item for item in issues if item['field'] == 'join_date')
    assert bad['message'] == 'join_date invalid'
    assert 'YYYY-MM-DD' in bad['fix'] and 'M/D/YYYY' in bad['fix']


class TestResilientDateParser:
    """Deterministic accepted-format precedence for inbound date cells."""

    def test_accepts_iso(self):
        assert _date('2024-01-02') == date(2024, 1, 2)

    def test_accepts_template_month_first(self):
        assert _date('1/2/2024') == date(2024, 1, 2)
        assert _date('1/2/24') == date(2024, 1, 2)

    def test_accepts_year_first_slash_and_dot(self):
        assert _date('2024/1/2') == date(2024, 1, 2)
        assert _date('2024.1.2') == date(2024, 1, 2)

    def test_accepts_template_order_with_dash_and_dot_separators(self):
        assert _date('1-2-2024') == date(2024, 1, 2)
        assert _date('1.2.2024') == date(2024, 1, 2)

    def test_ambiguous_value_uses_documented_month_first_order(self):
        # Documented template order is M/D/YYYY, so 03/04/2024 is 2024-03-04.
        assert _date('03/04/2024') == date(2024, 3, 4)

    def test_day_first_only_when_unambiguous(self):
        assert _date('25/12/2024') == date(2024, 12, 25)

    def test_strips_whitespace_and_leading_bom(self):
        assert _date('\ufeff 1/2/2024 ') == date(2024, 1, 2)
        assert _clean('\ufeff  2024-01-02  ') == '2024-01-02'

    def test_empty_and_garbage_are_none(self):
        assert _date(None) is None
        assert _date('') is None
        assert _date('   ') is None
        assert _date('\ufeff') is None
        assert _date('not-a-date') is None
        assert _date('13/13/2024') is None


@pytest.mark.django_db
def test_employee_snapshot_commit_accepts_resilient_dates_and_leaves_empty_none(
    prep_cmt, org, get_token_for_user,
):
    """Template, year-first and dot separators all commit; empty stays NULL."""
    prep, cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    body = (
        'employee_no,full_name,org_unit,join_date,basic_salary\n'
        'DMSDEV9201,Template Date,HR,1/2/2024,210\n'
        'DMSDEV9202,Year First,HR,2024.3.4,211\n'
        'DMSDEV9203,No Date,HR,,212\n'
    )
    bid = _smoke_batch(client, body, {
        'employee_no': 'employee_no',
        'full_name': 'full_name',
        'org_unit': 'org_unit',
        'join_date': 'join_date',
        'basic_salary': 'basic_salary',
    })
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 3
    assert res.data['smoke']['reject'] == 0

    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200, res.data
    assert Employee.objects.get(employee_no='DMSDEV9201').join_date == date(2024, 1, 2)
    assert Employee.objects.get(employee_no='DMSDEV9202').join_date == date(2024, 3, 4)
    assert Employee.objects.get(employee_no='DMSDEV9203').join_date is None
