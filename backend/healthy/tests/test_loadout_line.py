"""Tests for LoadoutLine typed child table and updated LoadoutService."""
import pytest
from django.db.models import Sum

from healthy.services import LoadoutService


@pytest.mark.django_db
def test_generate_sheet_creates_typed_lines(create_user):
    user = create_user('loadout_user')
    svc = LoadoutService()
    sheet = svc.generate_sheet(
        '2026-08-25', 'R-1042',
        line_items=[
            {'item_code': 'SKU-101', 'item_name': 'Tomatoes', 'qty_recommended': 90},
            {'item_code': 'SKU-307', 'item_name': 'Eggs',     'qty_recommended': 120},
        ],
        user=user,
    )
    assert sheet.lines.count() == 2
    codes = list(sheet.lines.values_list('item_code', flat=True))
    assert 'SKU-101' in codes
    assert 'SKU-307' in codes


@pytest.mark.django_db
def test_lines_are_queryable_by_item_code(create_user):
    user = create_user('loadout_user_2')
    svc = LoadoutService()
    svc.generate_sheet(
        '2026-08-25', 'R-1055',
        line_items=[
            {'item_code': 'SKU-101', 'qty_recommended': 45},
            {'item_code': 'SKU-203', 'qty_recommended': 10},
        ],
        user=user,
    )
    from healthy.models import LoadoutLine
    sku101 = LoadoutLine.objects.filter(item_code='SKU-101').first()
    assert sku101 is not None
    assert sku101.qty_recommended == 45


@pytest.mark.django_db
def test_lines_aggregatable(create_user):
    user = create_user('loadout_user_3')
    svc = LoadoutService()
    svc.generate_sheet(
        '2026-09-01', 'R-1042',
        line_items=[{'item_code': 'SKU-101', 'qty_recommended': 90}],
        user=user,
    )
    svc.generate_sheet(
        '2026-09-01', 'R-1055',
        line_items=[{'item_code': 'SKU-101', 'qty_recommended': 45}],
        user=user,
    )
    from healthy.models import LoadoutLine
    total = LoadoutLine.objects.filter(item_code='SKU-101').aggregate(t=Sum('qty_recommended'))['t']
    assert total == 135


@pytest.mark.django_db
def test_submit_actuals_updates_lines(create_user):
    user = create_user('loadout_user_4')
    svc = LoadoutService()
    sheet = svc.generate_sheet(
        '2026-08-25', 'R-2000',
        line_items=[
            {'item_code': 'SKU-101', 'qty_recommended': 90},
            {'item_code': 'SKU-307', 'qty_recommended': 120},
        ],
        user=user,
    )
    updated = svc.submit_actuals(sheet, {'SKU-101': 80, 'SKU-307': 100})
    assert updated == 2
    sheet.refresh_from_db()
    sku101 = sheet.lines.get(item_code='SKU-101')
    assert sku101.qty_actual == 80


@pytest.mark.django_db
def test_regenerate_sheet_replaces_lines(create_user):
    user = create_user('loadout_user_5')
    svc = LoadoutService()
    svc.generate_sheet('2026-09-08', 'R-3000',
                       line_items=[{'item_code': 'SKU-OLD', 'qty_recommended': 5}],
                       user=user)
    sheet = svc.generate_sheet('2026-09-08', 'R-3000',
                               line_items=[{'item_code': 'SKU-NEW', 'qty_recommended': 10}],
                               user=user)
    codes = list(sheet.lines.values_list('item_code', flat=True))
    assert codes == ['SKU-NEW']


@pytest.mark.django_db
def test_items_without_item_code_are_skipped(create_user):
    user = create_user('loadout_user_6')
    svc = LoadoutService()
    sheet = svc.generate_sheet(
        '2026-09-15', 'R-4000',
        line_items=[
            {'item_code': 'SKU-101', 'qty_recommended': 10},
            {'qty_recommended': 5},   # no item_code — must be skipped
        ],
        user=user,
    )
    assert sheet.lines.count() == 1
