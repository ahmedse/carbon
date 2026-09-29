"""DMS-COR-PRODUCT: product smoke writes no DataRow; commit writes the projected rows."""
import io

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from core.models import Module
from dataschema.models import DataField, DataRow, DataTable
from importexport.models import ImportJob
from inbound.adapters.dataschema import PREFIX
from inbound.models import InboundBatch


PREFIX_API = f'/{settings.API_PREFIX.strip("/")}/inbound'


def _csv(text, name='t.csv'):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = name
    return buf


@pytest.fixture
def product_table(db):
    module = Module.objects.create(name='DMS2 Product', scope=1)
    table = DataTable.objects.create(title='Transport Readings', name='transport_readings', module=module)
    DataField.objects.create(
        data_table=table, name='date', label='Date', type='string', required=True, order=1,
    )
    DataField.objects.create(
        data_table=table, name='distance', label='Distance (km)', type='number', required=False, order=2,
    )
    return table


@pytest.fixture
def steward(create_user, create_scoped_role):
    user = create_user('cat_steward')
    create_scoped_role(user, 'catalog_lead')
    return user


@pytest.fixture
def hub_lead(create_user, create_scoped_role):
    user = create_user('hub_lead')
    create_scoped_role(user, 'datahub_lead')
    return user


@pytest.fixture
def people_owner(create_user, create_scoped_role):
    user = create_user('hr_owner')
    create_scoped_role(user, 'people_data_owners_group')
    return user


def _key(table):
    return f'{PREFIX}{table.id}'


@pytest.mark.django_db
def test_targets_lists_active_table(steward, get_token_for_user, product_table):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(steward)}')
    res = client.get(f'{PREFIX_API}/batches/targets/?kind=data_product')
    assert res.status_code == 200
    keys = {row['key'] for row in res.data}
    assert _key(product_table) in keys


@pytest.mark.django_db
def test_people_owner_cannot_create_data_product(people_owner, get_token_for_user, product_table):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(people_owner)}')
    res = client.get(f'{PREFIX_API}/batches/targets/?kind=data_product')
    assert res.status_code == 403
    res = client.post(
        f'{PREFIX_API}/batches/',
        {'kind': 'data_product', 'target_key': _key(product_table)},
        format='json',
    )
    assert res.status_code == 403


@pytest.mark.django_db
def test_smoke_writes_zero_datarows(steward, get_token_for_user, product_table):
    """DMS-COR-PRODUCT"""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(steward)}')
    res = client.post(
        f'{PREFIX_API}/batches/',
        {'kind': 'data_product', 'target_key': _key(product_table)},
        format='json',
    )
    assert res.status_code == 201
    bid = res.data['id']
    res = client.post(
        f'{PREFIX_API}/batches/{bid}/file/',
        {'file': _csv('date,distance\n2026-01-01,100\n2026-01-02,\n')},
        format='multipart',
    )
    assert res.status_code == 200
    res = client.put(
        f'{PREFIX_API}/batches/{bid}/mapping/',
        {'columns': {'date': 'date', 'distance': 'distance'}},
        format='json',
    )
    assert res.status_code == 200
    res = client.post(f'{PREFIX_API}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 2
    assert res.data['smoke']['reject'] == 0
    assert DataRow.objects.filter(data_table=product_table).count() == 0
    assert ImportJob.objects.filter(data_table=product_table).count() == 0


@pytest.mark.django_db
def test_commit_creates_rows_and_import_job(steward, hub_lead, get_token_for_user, product_table):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(steward)}')
    res = client.post(
        f'{PREFIX_API}/batches/',
        {'kind': 'data_product', 'target_key': _key(product_table)},
        format='json',
    )
    bid = res.data['id']
    client.post(
        f'{PREFIX_API}/batches/{bid}/file/',
        {'file': _csv('date,distance\n2026-01-01,100\n')},
        format='multipart',
    )
    client.put(
        f'{PREFIX_API}/batches/{bid}/mapping/',
        {'columns': {'date': 'date', 'distance': 'distance'}},
        format='json',
    )
    res = client.post(f'{PREFIX_API}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert DataRow.objects.filter(data_table=product_table).count() == 0

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(hub_lead)}')
    res = client.post(f'{PREFIX_API}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert res.data['status'] == InboundBatch.STATUS_COMMITTED
    assert DataRow.objects.filter(data_table=product_table).count() == 1
    row = DataRow.objects.get(data_table=product_table)
    assert row.values['date'] == '2026-01-01'
    assert row.values['distance'] == 100
    job = ImportJob.objects.get(data_table=product_table)
    assert job.status == 'done'
    assert job.row_count == 1
    assert res.data['smoke']['commit']['import_job_id'] == job.id


@pytest.mark.django_db
def test_no_ingest_cap_403(create_user, get_token_for_user, product_table):
    user = create_user('viewer')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    res = client.post(
        f'{PREFIX_API}/batches/',
        {'kind': 'data_product', 'target_key': _key(product_table)},
        format='json',
    )
    assert res.status_code == 403
