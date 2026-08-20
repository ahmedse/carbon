"""End-to-end API tests: CRUD, lifecycle, contract, ingest (Phase P1)."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from catalog.models import DataContract, DataContractViolation, Dataset, DatasetVersion

DATASETS_URL = '/carbon-api/catalog/datasets/'
ERP_URL = '/carbon-api/catalog/datasets/{id}/ingest/erp/'
UPLOAD_URL = '/carbon-api/catalog/datasets/{id}/ingest/upload/'
VERSIONS_URL = '/carbon-api/catalog/datasets/{id}/versions/'
APPROVE_URL = '/carbon-api/catalog/datasets/{id}/versions/{vid}/approve/'
REJECT_URL = '/carbon-api/catalog/datasets/{id}/versions/{vid}/reject/'
CONTRACT_URL = '/carbon-api/catalog/datasets/{id}/contract/'
VIOLATIONS_URL = '/carbon-api/catalog/datasets/{id}/contract/violations/'

ERP_ROWS = [
    {'name': 'Amina', 'age': 30, 'department': 'Finance'},
    {'name': 'Omar', 'age': 28, 'department': 'IT'},
]


def _ingest(client, ds):
    resp = client.post(ERP_URL.format(id=ds.id),
                            {'rows': ERP_ROWS, 'source_ref': 'erp-2024-01'},
                            format='json')
    assert resp.status_code == 201, resp.content
    return resp.json()


# ── Dataset CRUD ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_and_list_datasets(auth_client, module_a, domain):
    client = auth_client()
    resp = client.post(DATASETS_URL, {
        'name': 'Payroll Master',
        'slug': 'payroll-master-api',
        'module': module_a.id,
        'domain': domain.id,
        'classification': 'confidential',
        'description': 'HR payroll',
    }, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body['name'] == 'Payroll Master'
    assert body['status'] == 'draft'
    assert body['classification'] == 'confidential'

    resp = client.get(DATASETS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]['slug'] == 'payroll-master-api'


@pytest.mark.django_db
def test_patch_dataset(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-patch')
    resp = client.patch(f"{DATASETS_URL}{ds.id}/", {
        'name': 'Payroll Updated',
    }, format='json')
    assert resp.status_code == 200, resp.content
    assert resp.json()['name'] == 'Payroll Updated'


@pytest.mark.django_db
def test_delete_is_soft_archive(auth_client, module_a, make_dataset):
    client = auth_client()
    """Named requirement — DELETE archives; the row survives with status=archived."""
    ds = make_dataset(module_a, slug='payroll-archive')
    assert client.delete(f"{DATASETS_URL}{ds.id}/").status_code == 204

    ds.refresh_from_db()
    assert ds.status == 'archived'

    # Hidden from default catalog listing
    ids = [i['id'] for i in client.get(DATASETS_URL).json()]
    assert str(ds.id) not in ids
    # Visible with the include_archived flag
    ids = [i['id'] for i in
           client.get(DATASETS_URL + '?include_archived=true').json()]
    assert str(ds.id) in ids


@pytest.mark.django_db
def test_dataset_filters(auth_client, module_a, module_b, domain, make_dataset):
    client = auth_client()
    ds1 = make_dataset(module_a, slug='payroll-f1', classification='confidential')
    make_dataset(module_b, slug='payroll-f2', classification='public')

    resp = client.get(DATASETS_URL, {'module': module_a.id})
    ids = [i['id'] for i in resp.json()]
    assert str(ds1.id) in ids and len(ids) == 1

    resp = client.get(DATASETS_URL, {'classification': 'public'})
    assert len(resp.json()) == 1
    assert resp.json()[0]['slug'] == 'payroll-f2'

    resp = client.get(DATASETS_URL, {'domain': domain.id})
    assert resp.json() == []  # no datasets tied to the domain


# ── Version lifecycle (named test #2) ──────────────────────────────────────

@pytest.mark.django_db
def test_version_lifecycle_approve_sets_current(
        auth_client, module_a, make_dataset):
    client = auth_client()
    """Named test #2 — pending → approved sets current_version; rejected does not."""
    ds = make_dataset(module_a, slug='payroll-lifecycle')

    v1 = _ingest(client, ds)
    assert v1['status'] == 'pending'
    assert v1['version_number'] == 1
    assert v1['health_score'] is not None
    assert v1['dq_job_id']  # DQ seam wired

    # Approve v1 → becomes current
    resp = client.post(APPROVE_URL.format(id=ds.id, vid=v1['id']))
    assert resp.status_code == 200, resp.content
    assert resp.json()['status'] == 'approved'

    ds.refresh_from_db()
    assert str(ds.current_version_id) == v1['id']
    assert ds.status == 'active'

    # Reject v2 → current_version stays on v1
    v2 = _ingest(client, ds)
    assert v2['version_number'] == 2
    resp = client.post(REJECT_URL.format(id=ds.id, vid=v2['id']),
                            {'reason': 'Duplicate of v1'}, format='json')
    assert resp.status_code == 200, resp.content
    assert resp.json()['status'] == 'rejected'
    assert resp.json()['rejection_reason'] == 'Duplicate of v1'

    ds.refresh_from_db()
    assert str(ds.current_version_id) == v1['id']


@pytest.mark.django_db
def test_version_numbering_increments(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-numbers')
    v1 = _ingest(client, ds)
    v2 = _ingest(client, ds)
    assert v1['version_number'] == 1
    assert v2['version_number'] == 2


@pytest.mark.django_db
def test_version_list_and_detail(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-versionlist')
    v = _ingest(client, ds)

    resp = client.get(VERSIONS_URL.format(id=ds.id))
    assert resp.status_code == 200
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['id'] == v['id']

    resp = client.get(
        f"{VERSIONS_URL.format(id=ds.id)}{v['id']}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body['schema_snapshot']  # captured at ingest
    assert 'completeness' in body['health_detail']
    assert 'contract_violations' in body


@pytest.mark.django_db
def test_version_create_from_existing_table(
        auth_client, module_a, make_dataset):
    client = auth_client()
    """POST /versions/ with an existing DataTable triggers DQ + health."""
    from dataschema.models import DataField, DataRow, DataTable
    ds = make_dataset(module_a, slug='payroll-fromtable')
    table = DataTable.objects.create(
        name='payroll_existing', title='Existing', module=module_a,
    )
    DataField.objects.create(data_table=table, name='name', type='string', order=1)
    DataRow.objects.create(data_table=table, values={'name': 'Amina'})

    resp = client.post(VERSIONS_URL.format(id=ds.id),
                            {'data_table': table.id}, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body['status'] == 'pending'
    assert body['row_count'] == 1
    assert body['dq_job_id']
    assert body['schema_snapshot']['name']['type'] == 'string'


# ── Contract (named tests #3, #4, #5) ──────────────────────────────────────

@pytest.mark.django_db
def test_contract_create_get_update(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-contract-api')
    resp = client.put(CONTRACT_URL.format(id=ds.id), {
        'required_fields': ['name', 'age'],
        'min_health_score': 0.9,
        'freshness_hours': 24,
        'consumer_apps': ['payroll-app'],
    }, format='json')
    assert resp.status_code == 200, resp.content
    contract = resp.json()
    assert contract['required_fields'] == ['name', 'age']
    assert contract['is_active'] is True

    # GET returns it
    resp = client.get(CONTRACT_URL.format(id=ds.id))
    assert resp.status_code == 200
    assert resp.json()['freshness_hours'] == 24

    # PUT updates
    resp = client.put(CONTRACT_URL.format(id=ds.id), {
        'required_fields': ['name'], 'min_health_score': 0.8,
    }, format='json')
    assert resp.status_code == 200
    assert resp.json()['required_fields'] == ['name']


@pytest.mark.django_db
def test_contract_schema_violation(auth_client, module_a, make_dataset):
    client = auth_client()
    """Named test #3 — missing required field → DataContractViolation."""
    ds = make_dataset(module_a, slug='payroll-schema-v')
    client.put(CONTRACT_URL.format(id=ds.id), {
        'required_fields': ['name', 'missing_field'],
    }, format='json')

    v = _ingest(client, ds)
    assert v['status'] == 'pending'

    violations = DataContractViolation.objects.filter(dataset_version__id=v['id'])
    assert violations.count() == 1
    assert violations.first().violation_type == 'schema'
    assert violations.first().detail == {
        'field': 'missing_field', 'expected': 'present', 'actual': 'missing'}

    # Violations surfaced on the endpoint
    resp = client.get(VIOLATIONS_URL.format(id=ds.id))
    assert resp.status_code == 200
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['violation_type'] == 'schema'


@pytest.mark.django_db
def test_contract_quality_violation(auth_client, module_a, make_dataset):
    client = auth_client()
    """Named test #4 — completeness below minimum SLA → violation."""
    ds = make_dataset(module_a, slug='payroll-quality-v')
    client.put(CONTRACT_URL.format(id=ds.id), {
        'min_completeness': 1.0,  # a null cell pushes completeness below 1.0
    }, format='json')

    # Ingest a row WITH a missing value → completeness < 1.0
    resp = client.post(ERP_URL.format(id=ds.id), {
        'rows': [{'name': 'Amina', 'age': None, 'department': 'Finance'}],
    }, format='json')
    assert resp.status_code == 201, resp.content
    v = resp.json()
    assert v['health_detail']['completeness'] < 1.0

    violations = list(
        DataContractViolation.objects.filter(dataset_version__id=v['id']))
    assert len(violations) == 1
    assert violations[0].violation_type == 'quality'
    assert violations[0].detail['dimension'] == 'completeness'


@pytest.mark.django_db
def test_contract_freshness_violation(auth_client, module_a, make_dataset):
    client = auth_client()
    """Named test #5 — a version older than freshness_hours → violation."""
    ds = make_dataset(module_a, slug='payroll-fresh-v')
    client.put(CONTRACT_URL.format(id=ds.id), {
        'freshness_hours': 1,
    }, format='json')

    v = _ingest(client, ds)
    # Fresh at ingest → no violation yet
    assert DataContractViolation.objects.filter(
        dataset_version__id=v['id']).count() == 0

    # Backdate the version past the SLA and re-evaluate
    DatasetVersion.objects.filter(id=v['id']).update(
        created_at=timezone.now() - timezone.timedelta(hours=5))
    version = DatasetVersion.objects.get(id=v['id'])
    from catalog.dataset_services import check_contract
    check_contract(version)

    violations = DataContractViolation.objects.filter(dataset_version__id=v['id'])
    assert violations.count() == 1
    assert violations.first().violation_type == 'freshness'


@pytest.mark.django_db
def test_clean_contract_has_no_violations(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-clean')
    client.put(CONTRACT_URL.format(id=ds.id), {
        'required_fields': ['name', 'age', 'department'],
        'min_completeness': 0.5,
        'min_health_score': 0.5,
    }, format='json')
    v = _ingest(client, ds)
    assert DataContractViolation.objects.filter(dataset_version__id=v['id']).count() == 0


# ── Ingest (named tests #8, #9) ────────────────────────────────────────────

@pytest.mark.django_db
def test_ingest_erp_snapshot(auth_client, module_a, make_dataset, domain):
    client = auth_client()
    """Named test #8 — ERP rows → DataTable + DataRows → version → health."""
    ds = make_dataset(module_a, slug='payroll-erp', domain=domain)

    v = _ingest(client, ds)
    assert v['status'] == 'pending'
    assert v['row_count'] == 2
    assert v['health_score'] is not None
    assert 0.0 <= v['health_score'] <= 1.0
    assert set(v['health_detail']) == {'completeness', 'validity', 'freshness'}
    assert v['lineage']['source']['type'] == 'erp_snapshot'
    assert v['lineage']['source']['ref'] == 'erp-2024-01'

    # Data materialized in dataschema
    from dataschema.models import DataRow, DataTable
    table = DatasetVersion.objects.get(id=v['id']).data_table
    assert table.title == 'Payroll Master — Version 1'
    assert DataRow.objects.filter(data_table=table).count() == 2
    # Schema snapshot mirrors the created DataFields
    assert set(v['schema_snapshot']) == {'name', 'age', 'department'}


@pytest.mark.django_db
def test_ingest_csv_upload(auth_client, module_a, make_dataset):
    client = auth_client()
    """Named test #9 — CSV upload flows through the same pipeline."""
    ds = make_dataset(module_a, slug='payroll-csv')
    csv_file = SimpleUploadedFile(
        'employees.csv', b"name,age,department\nAmina,30,Finance\nOmar,28,IT\n",
        content_type='text/csv',
    )
    resp = client.post(UPLOAD_URL.format(id=ds.id),
                            {'file': csv_file}, format='multipart')
    assert resp.status_code == 201, resp.content
    v = resp.json()
    assert v['version_number'] == 1
    assert v['row_count'] == 2
    assert v['health_score'] is not None
    assert v['lineage']['source']['type'] == 'csv_upload'
    assert v['lineage']['source']['ref'] == 'employees.csv'


@pytest.mark.django_db
def test_ingest_health_formula_exact(auth_client, module_a, make_dataset):
    client = auth_client()
    """Design §5.6 — health_score = 0.4·completeness + 0.4·validity + 0.2·freshness.

    2 columns × 1 row, one null cell:
      completeness = 1 - 1/2 = 0.5, validity = 1.0, freshness = 1.0
      health_score = 0.4·0.5 + 0.4·1.0 + 0.2·1.0 = 0.8
    """
    ds = make_dataset(module_a, slug='payroll-formula')
    resp = client.post(ERP_URL.format(id=ds.id), {
        'rows': [{'name': 'Amina', 'age': ''}],
    }, format='json')
    assert resp.status_code == 201, resp.content
    v = resp.json()
    assert v['health_detail']['completeness'] == 0.5
    assert v['health_detail']['validity'] == 1.0
    assert v['health_detail']['freshness'] == 1.0
    assert v['health_score'] == 0.8


@pytest.mark.django_db
def test_ingest_dq_job_stored(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-dqjob')
    v = _ingest(client, ds)
    assert v['dq_job_id']
    from dq.models import DQJob
    assert DQJob.objects.filter(pk=v['dq_job_id'], data_table_id=v['data_table']).exists()


@pytest.mark.django_db
def test_ingest_erp_empty_rows_rejected(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-empty')
    resp = client.post(ERP_URL.format(id=ds.id), {'rows': []}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_ingest_upload_missing_file(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-nofile')
    resp = client.post(UPLOAD_URL.format(id=ds.id), {}, format='multipart')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_auto_approve_flow(auth_client, module_a, make_dataset):
    client = auth_client()
    """auto_approve=true + clean contract → version approved + current set."""
    ds = make_dataset(module_a, slug='payroll-autoapprove')
    resp = client.post(ERP_URL.format(id=ds.id), {
        'rows': ERP_ROWS, 'auto_approve': True,
    }, format='json')
    assert resp.status_code == 201, resp.content
    v = resp.json()
    assert v['status'] == 'approved'
    ds.refresh_from_db()
    assert str(ds.current_version_id) == v['id']


@pytest.mark.django_db
def test_approve_fails_on_non_pending(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='payroll-twice')
    v = _ingest(client, ds)
    client.post(APPROVE_URL.format(id=ds.id, vid=v['id']))
    resp = client.post(APPROVE_URL.format(id=ds.id, vid=v['id']))
    assert resp.status_code == 400
