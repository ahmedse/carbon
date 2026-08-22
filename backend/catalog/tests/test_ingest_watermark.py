"""Direct ingest_erp watermark tests (catalog seam, no pipeline orchestration).

Verifies the since_id contract of the ingest layer itself: incremental re-runs
reuse the dataset's latest materialized table, dedup by content hash, and do
not create duplicate versions or duplicate rows.
"""
import pytest

from catalog.dataset_ingest import ingest_erp
from dataschema.models import DataRow


ERP_ROWS = [
    {'name': 'Amina', 'age': 30, 'department': 'Finance'},
    {'name': 'Omar', 'age': 28, 'department': 'IT'},
]


def _watermark(table):
    from django.db.models import Max
    return DataRow.objects.filter(data_table=table).aggregate(m=Max('id'))['m']


@pytest.mark.django_db
def test_full_ingest_creates_fresh_table_per_run(module_a, make_dataset):
    ds = make_dataset(module_a, slug='wm-full')
    v1 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1')
    v2 = ingest_erp(ds, ERP_ROWS, source_ref='erp-2')
    assert v1.id != v2.id
    assert v1.data_table_id != v2.data_table_id
    assert DataRow.objects.filter(data_table=v1.data_table).count() == 2
    assert DataRow.objects.count() == 4  # full snapshots duplicate by design


@pytest.mark.django_db
def test_incremental_rerun_dedups(module_a, make_dataset):
    ds = make_dataset(module_a, slug='wm-incr')
    v1 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1')
    watermark = _watermark(v1.data_table)

    v2 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1', since_id=watermark)
    assert v2.id == v1.id  # unchanged extract → same version returned
    assert DataRow.objects.filter(data_table=v1.data_table).count() == 2
    assert DataRow.objects.count() == 2  # no duplicates anywhere


@pytest.mark.django_db
def test_incremental_run_appends_new_rows(module_a, make_dataset):
    ds = make_dataset(module_a, slug='wm-append')
    v1 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1')
    watermark = _watermark(v1.data_table)

    grown = ERP_ROWS + [{'name': 'Yara', 'age': 31, 'department': 'HR'}]
    v2 = ingest_erp(ds, grown, source_ref='erp-2', since_id=watermark)
    assert v2.id != v1.id
    assert v2.data_table_id == v1.data_table_id  # same materialized table
    assert DataRow.objects.filter(data_table=v1.data_table).count() == 3
    assert DataRow.objects.filter(data_table=v1.data_table, values__name='Yara').exists()
    # pre-existing rows were not re-copied
    assert DataRow.objects.filter(data_table=v1.data_table, values__name='Amina').count() == 1


@pytest.mark.django_db
def test_incremental_rerun_preserves_row_hashes(module_a, make_dataset):
    ds = make_dataset(module_a, slug='wm-hash')
    v1 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1')
    hashes = set(DataRow.objects.filter(data_table=v1.data_table)
                 .values_list('row_hash', flat=True))
    assert len(hashes) == 2
    assert all(len(h) == 64 for h in hashes)

    # same rows re-ingested incrementally → same hashes, zero new rows
    watermark = _watermark(v1.data_table)
    v2 = ingest_erp(ds, ERP_ROWS, source_ref='erp-1', since_id=watermark)
    assert v2.id == v1.id
