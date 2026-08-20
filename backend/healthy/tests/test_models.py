"""Model-level tests for the Healthy Foods Factory app (Phase P4-A)."""
import pytest
from django.db import IntegrityError

from healthy.models import ERPSnapshot, LoadoutSheet, RepHealthCard


@pytest.mark.django_db
def test_erp_snapshot_defaults():
    snap = ERPSnapshot.objects.create(source_view='readable.invoice_lines')
    assert snap.status == 'running'
    assert snap.extract_params == {}
    assert snap.row_count is None
    assert snap.dataset_version_id is None
    assert 'readable.invoice_lines' in str(snap)


@pytest.mark.django_db
def test_loadout_sheet_unique_per_week_and_rep():
    LoadoutSheet.objects.create(week_start='2026-08-17', rep_code='R-1042')
    with pytest.raises(IntegrityError):
        LoadoutSheet.objects.create(week_start='2026-08-17', rep_code='R-1042')


@pytest.mark.django_db
def test_loadout_sheet_defaults_and_str():
    sheet = LoadoutSheet.objects.create(
        week_start='2026-08-17', rep_code='R-1042', rep_name='Amina',
    )
    assert sheet.line_items == []
    assert 'R-1042' in str(sheet)
    assert '2026-08-17' in str(sheet)


@pytest.mark.django_db
def test_rep_health_card_unique_per_week_and_rep():
    RepHealthCard.objects.create(week_start='2026-08-17', rep_code='R-1042')
    with pytest.raises(IntegrityError):
        RepHealthCard.objects.create(week_start='2026-08-17', rep_code='R-1042')


@pytest.mark.django_db
def test_rep_health_card_fields_and_str():
    card = RepHealthCard.objects.create(
        week_start='2026-08-17', rep_code='R-1042',
        churn_probability=0.23, active_customer_count=84,
        visit_coverage=0.85, avg_order_value=1820.0,
    )
    assert card.churn_probability == 0.23
    assert 'R-1042' in str(card)
