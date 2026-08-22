"""Service-level tests: ERP extract, pipeline orchestration, load-out, dashboards."""
import pytest

from healthy.services import (
    PIPELINES, DashboardService, ERPSnapshotService, HealthyPipelineService,
    LoadoutService,
)


@pytest.mark.django_db
def test_extract_rows_uses_recorded_snapshot():
    rows = ERPSnapshotService().extract_rows('readable.invoice_lines')
    assert len(rows) == 3
    assert rows[0]['rep_code'] == 'R-1042'
    # snapshot is a copy — mutating it must not mutate the recorded source
    rows[0]['rep_code'] = 'MUTATED'
    assert ERPSnapshotService().extract_rows('readable.invoice_lines')[0]['rep_code'] == 'R-1042'


@pytest.mark.django_db
def test_extract_unknown_view_returns_empty():
    assert ERPSnapshotService().extract_rows('readable.does_not_exist') == []


@pytest.mark.django_db
def test_run_snapshot_records_done_without_dataset():
    snap, version = ERPSnapshotService().run_snapshot('readable.invoice_lines')
    assert snap.status == 'done'
    assert snap.row_count == 3
    assert snap.completed_at is not None
    assert version is None


@pytest.mark.django_db
def test_run_pipeline_produces_four_artifacts(create_user):
    from catalog.models import DatasetVersion
    from integrations.turnkey.models import PredictionRecord, TurnKeyModelLink

    user = create_user('pipeline_runner')
    result = HealthyPipelineService().run_pipeline('returns', user=user)

    assert result['snapshot'].status == 'done'
    assert isinstance(result['version'], DatasetVersion)
    assert isinstance(result['link'], TurnKeyModelLink)
    assert isinstance(result['prediction'], PredictionRecord)

    # Provenance chain is fully linked.
    assert result['snapshot'].dataset_version_id == result['version'].id
    assert result['link'].dataset_version_id == result['version'].id
    assert result['prediction'].model_link_id == result['link'].id
    assert result['link'].purpose == 'inference'


@pytest.mark.django_db
def test_run_pipeline_unknown_key_raises():
    with pytest.raises(ValueError):
        HealthyPipelineService().run_pipeline('does-not-exist')


@pytest.mark.django_db
def test_all_five_pipelines_run(create_user):
    from integrations.turnkey.models import PredictionRecord
    user = create_user('all_pipelines')
    for key in PIPELINES:
        HealthyPipelineService().run_pipeline(key, user=user)
    assert PredictionRecord.objects.count() == 5


@pytest.mark.django_db
def test_loadout_generate_and_submit_actuals(create_user):
    user = create_user('loadout_user')
    sheet = LoadoutService().generate_sheet(
        '2026-08-24', 'R-1042', rep_name='Amina',
        line_items=[{'item_code': 'SKU-101', 'qty_recommended': 10}],
        user=user,
    )
    assert sheet.lines.get(item_code='SKU-101').qty_recommended == 10
    assert sheet.rep_name == 'Amina'

    updated_count = LoadoutService().submit_actuals(sheet, {'SKU-101': 8})
    assert updated_count == 1
    assert sheet.lines.get(item_code='SKU-101').qty_actual == 8


@pytest.mark.django_db
def test_dashboard_summary_and_ar_queue(create_user):
    user = create_user('dash_user')
    HealthyPipelineService().run_pipeline('ar-aging', user=user)

    summary = DashboardService().summary()
    assert summary['pipelines'] == 5
    assert summary['snapshots'] == 1
    assert summary['predictions'] == 1
    assert summary['model_links'] == 1

    queue = DashboardService().ar_queue()
    assert len(queue) == 1
    assert queue[0]['customer_code'] == 'CUST-9007'
    assert queue[0]['risk_score'] == 0.85


@pytest.mark.django_db
def test_dashboard_slow_movers(create_user):
    user = create_user('slow_mover_user')
    HealthyPipelineService().run_pipeline('sales-lines', user=user)

    movers = DashboardService().slow_movers()
    assert len(movers) == 1
    assert movers[0]['item_code'] == 'SKU-203'
