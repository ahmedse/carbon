"""Watermark loop closure: incremental re-runs must not duplicate DataRows.

Repeated pipeline runs against an unchanged ERP extract must materialize zero
new rows (and no duplicate version); genuinely new rows between runs must be
appended to the same materialized table; full=True re-materializes fresh.
"""
import pytest

from healthy.services import HealthyPipelineService, RECORDED_SNAPSHOTS


def _sales_rows():
    return list(RECORDED_SNAPSHOTS['readable.items'])


@pytest.mark.django_db
def test_unchanged_rerun_adds_no_rows(create_user):
    from dataschema.models import DataRow

    user = create_user('wm_user_1')
    svc = HealthyPipelineService()
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    total = DataRow.objects.count()
    assert total == 3

    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    assert DataRow.objects.count() == total  # no duplicates


@pytest.mark.django_db
def test_unchanged_rerun_reuses_latest_version(create_user):
    from catalog.models import DatasetVersion

    user = create_user('wm_user_2')
    svc = HealthyPipelineService()
    first = svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    second = svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    assert second['version'].id == first['version'].id
    assert DatasetVersion.objects.filter(
        dataset=first['version'].dataset).count() == 1


@pytest.mark.django_db
def test_new_rows_between_runs_are_ingested(create_user, monkeypatch):
    from dataschema.models import DataRow, DataTable

    user = create_user('wm_user_3')
    svc = HealthyPipelineService()
    first = svc.run_pipeline('sales-lines', user=user, auto_approve=True)

    rows = _sales_rows()
    rows.append({'item_code': 'SKU-999', 'item_name': 'New SKU', 'movement_30d': 5,
                 'stock_on_hand': 10, 'shelf_life_days': 30, 'category': 'dry'})
    monkeypatch.setitem(RECORDED_SNAPSHOTS, 'readable.items', rows)

    second = svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    assert second['version'].id != first['version'].id
    table = DataTable.objects.get(pk=second['version'].data_table_id)
    assert DataRow.objects.filter(data_table=table).count() == 4
    assert DataRow.objects.filter(data_table=table, values__item_code='SKU-999').exists()
    # pre-existing rows were NOT re-copied into the materialized table
    assert DataRow.objects.filter(data_table=table, values__item_code='SKU-101').count() == 1


@pytest.mark.django_db
def test_full_rerun_rematerializes_fresh_table(create_user):
    from dataschema.models import DataRow

    user = create_user('wm_user_4')
    svc = HealthyPipelineService()
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    total = DataRow.objects.count()

    svc.run_pipeline('sales-lines', user=user, auto_approve=True, full=True)
    assert DataRow.objects.count() == 2 * total  # full rebuild snapshots again


@pytest.mark.django_db
def test_checkpoint_advances_only_on_new_rows(create_user, monkeypatch):
    from healthy.models import MaterializationCheckpoint

    user = create_user('wm_user_5')
    svc = HealthyPipelineService()
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    cp = MaterializationCheckpoint.objects.get(pipeline_key='sales-lines')
    after_first = cp.last_row_id
    assert after_first > 0

    # no-change re-run → checkpoint unchanged
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    cp.refresh_from_db()
    assert cp.last_row_id == after_first

    # a genuinely new row → checkpoint advances
    rows = _sales_rows()
    rows.append({'item_code': 'SKU-777', 'item_name': 'Fresh SKU', 'movement_30d': 1,
                 'stock_on_hand': 2, 'shelf_life_days': 7, 'category': 'produce'})
    monkeypatch.setitem(RECORDED_SNAPSHOTS, 'readable.items', rows)
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    cp.refresh_from_db()
    assert cp.last_row_id > after_first


@pytest.mark.django_db
def test_changed_extract_appends_only_new_rows(create_user, monkeypatch):
    """Extract loses a row and gains one → table holds 4 distinct rows."""
    from dataschema.models import DataRow

    user = create_user('wm_user_6')
    svc = HealthyPipelineService()
    svc.run_pipeline('sales-lines', user=user, auto_approve=True)

    rows = _sales_rows()[:2]
    rows.append({'item_code': 'SKU-555', 'item_name': 'Mixed SKU', 'movement_30d': 8,
                 'stock_on_hand': 4, 'shelf_life_days': 10, 'category': 'dairy'})
    monkeypatch.setitem(RECORDED_SNAPSHOTS, 'readable.items', rows)

    svc.run_pipeline('sales-lines', user=user, auto_approve=True)
    assert DataRow.objects.count() == 4
