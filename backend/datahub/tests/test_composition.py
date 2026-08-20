"""Composition tests — 1 Dataset = N tables (Sprint 29 P1B).

Covers: DatasetVersionMember model + tables property, create_version multi-table
path + single-table back-compat, cross-member contract schema union, per-member
health mirror, the multi-table API, and the steward field.
"""
import pytest
from django.db import IntegrityError

from datahub.ingest import create_version
from datahub.models import DataContract, DataContractViolation, DatasetVersion
from datahub.services import check_contract, mirror_health_to_catalog

DATASETS_URL = '/carbon-api/datahub/datasets/'
VERSIONS_URL = '/carbon-api/datahub/datasets/{id}/versions/'


def _table_for(dataset, version_number, fields=None, rows=None):
    """Materialize a DataTable (+ optional fields/rows) for a dataset."""
    from dataschema.models import DataField, DataRow, DataTable
    table = DataTable.objects.create(
        name=f'{dataset.slug}_v{version_number}',
        title=dataset.name,
        module=dataset.module,
    )
    for order, (name, ftype) in enumerate((fields or [('name', 'string')]),
                                          start=1):
        DataField.objects.create(
            data_table=table, name=name, type=ftype, order=order)
    for row in (rows or []):
        DataRow.objects.create(data_table=table, values=row)
    return table


def _two_tables(dataset, v):
    """Two tables with different completeness → different health scores."""
    t1 = _table_for(dataset, v, fields=[('a', 'string'), ('b', 'string')],
                    rows=[{'a': 'x', 'b': 'y'}, {'a': 'z', 'b': None}])
    t2 = _table_for(dataset, v + 1, fields=[('c', 'string')],
                    rows=[{'c': 'w'}, {'c': 'q'}])
    return t1, t2


# ── 1. Model: tables property + unique_together ────────────────────────────

@pytest.mark.django_db
def test_version_tables_returns_members_in_order(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-model')
    t1 = _table_for(ds, 1)
    t2 = _table_for(ds, 2)
    version = DatasetVersion.objects.create(
        dataset=ds, version_number=1, data_table=t1)
    from datahub.models import DatasetVersionMember
    DatasetVersionMember.objects.create(version=version, data_table=t1, order=1)
    DatasetVersionMember.objects.create(version=version, data_table=t2, order=0)

    # order ascending → t2 first
    assert version.tables == [t2, t1]


@pytest.mark.django_db
def test_member_unique_together_blocks_duplicate_table(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-unique')
    t1 = _table_for(ds, 1)
    version = DatasetVersion.objects.create(
        dataset=ds, version_number=1, data_table=t1)
    from datahub.models import DatasetVersionMember
    DatasetVersionMember.objects.create(version=version, data_table=t1, order=0)
    with pytest.raises(IntegrityError):
        DatasetVersionMember.objects.create(
            version=version, data_table=t1, order=1)


# ── 2. Back-compat: no members → tables == [data_table] ────────────────────

@pytest.mark.django_db
def test_version_tables_legacy_fallback(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-legacy')
    t1 = _table_for(ds, 1)
    version = DatasetVersion.objects.create(
        dataset=ds, version_number=1, data_table=t1)
    assert version.members.count() == 0
    assert version.tables == [t1]


# ── 3. create_version with a list of 2 tables ──────────────────────────────

@pytest.mark.django_db
def test_create_version_multi_table(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-multi')
    t1, t2 = _two_tables(ds, 1)

    version = create_version(
        ds, [t1, t2], source_type='api', source_ref='manual')

    members = list(version.members.all())
    assert len(members) == 2
    assert [m.order for m in members] == [0, 1]
    assert members[0].data_table == t1
    assert members[1].data_table == t2
    # Each member has its own schema snapshot + DQ trace
    assert 'a' in members[0].schema_snapshot
    assert 'c' in members[1].schema_snapshot
    assert members[0].dq_job_id  # DQ seam ran per table
    assert members[1].dq_job_id
    # Per-table health: t1 has a null cell (completeness < 1), t2 is complete
    assert members[0].health_score < members[1].health_score

    # Version-level aggregates
    assert version.data_table == t1
    assert version.row_count == 4  # 2 + 2
    assert version.health_score == pytest.approx(
        (members[0].health_score + members[1].health_score) / 2, abs=1e-4)
    assert set(version.schema_snapshot) == {'a', 'b', 'c'}


# ── 4. create_version single DataTable kwarg (old path) ────────────────────

@pytest.mark.django_db
def test_create_version_single_table_parity(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-single')
    t1, _ = _two_tables(ds, 1)

    version = create_version(
        ds, t1, source_type='api', source_ref='manual')

    assert version.data_table == t1
    assert version.members.count() == 1
    member = version.members.first()
    assert member.data_table == t1
    assert member.health_score == version.health_score
    assert version.row_count == 2
    assert set(version.schema_snapshot) == {'a', 'b'}


# ── 5. check_contract across members ───────────────────────────────────────

@pytest.mark.django_db
def test_check_contract_union_across_members(module_a, make_dataset):
    ds = make_dataset(module_a, slug='compose-contract')
    t1, t2 = _two_tables(ds, 1)
    version = create_version(ds, [t1, t2], source_type='api', source_ref='manual')

    contract = DataContract.objects.create(
        dataset=ds, required_fields=['a', 'b', 'c'])

    # a/b live in member 1, c in member 2 → zero schema violations
    violations = check_contract(version, contract=contract)
    assert [v.violation_type for v in violations] == []

    # A field in no member → exactly one schema violation
    contract.required_fields = ['a', 'b', 'c', 'missing_field']
    contract.save(update_fields=['required_fields'])
    violations = check_contract(version, contract=contract)
    schema_violations = [
        v for v in violations if v.violation_type == 'schema']
    assert len(schema_violations) == 1
    assert schema_violations[0].detail['field'] == 'missing_field'


# ── 6. mirror_health_to_catalog per member ─────────────────────────────────

@pytest.mark.django_db
def test_mirror_health_per_member(module_a, make_dataset):
    from catalog.models import AssetProfile
    ds = make_dataset(module_a, slug='compose-mirror')
    t1, t2 = _two_tables(ds, 1)
    version = create_version(ds, [t1, t2], source_type='api', source_ref='manual')

    # Tweak member 1 to 'failing' so the two profiles differ.
    member1 = version.members.get(data_table=t1)
    member1.health_score = 0.5
    member1.save(update_fields=['health_score'])

    mirror_health_to_catalog(version)

    ap1 = AssetProfile.objects.get(data_table=t1)
    ap2 = AssetProfile.objects.get(data_table=t2)
    assert ap1.quality_status == 'failing'
    assert ap2.quality_status == 'passing'  # t2 is complete → score ≥ 0.9


# ── 7. API: POST versions with data_tables list ────────────────────────────

@pytest.mark.django_db
def test_api_version_create_multi_table(auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='compose-api')
    t1 = _table_for(ds, 1)
    t2 = _table_for(ds, 2)

    resp = client.post(VERSIONS_URL.format(id=ds.id),
                       {'data_tables': [t1.id, t2.id]}, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert len(body['members']) == 2
    assert {m['data_table'] for m in body['members']} == {t1.id, t2.id}
    assert body['data_table'] == t1.id  # primary-table alias
    assert body['status'] == 'pending'


@pytest.mark.django_db
def test_api_version_create_data_tables_validation(
        auth_client, module_a, make_dataset):
    client = auth_client()
    ds = make_dataset(module_a, slug='compose-api-bad')
    t1 = _table_for(ds, 1)

    # Empty list → 400
    resp = client.post(VERSIONS_URL.format(id=ds.id),
                       {'data_tables': []}, format='json')
    assert resp.status_code == 400

    # Unknown id → 400
    resp = client.post(VERSIONS_URL.format(id=ds.id),
                       {'data_tables': [t1.id, 999999]}, format='json')
    assert resp.status_code == 400


# ── 8. Steward round-trips through DatasetSerializer ───────────────────────

@pytest.mark.django_db
def test_dataset_steward_roundtrip(auth_client, module_a, create_user):
    client = auth_client()
    steward = create_user('data_steward')
    resp = client.post(DATASETS_URL, {
        'name': 'Stewarded Dataset',
        'slug': 'compose-steward',
        'module': module_a.id,
        'steward': steward.id,
    }, format='json')
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body['steward'] == steward.id

    # Update round-trips too
    resp = client.patch(f"{DATASETS_URL}{body['id']}/",
                        {'steward': None}, format='json')
    assert resp.status_code == 200, resp.content
    assert resp.json()['steward'] is None
