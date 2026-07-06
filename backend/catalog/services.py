# catalog/services.py
from dataschema.models import DataTable, DataField
from .models import AssetProfile


def ensure_asset_profiles():
    """Idempotently create one AssetProfile per DataTable and per DataField."""
    have_tables = set(AssetProfile.objects.filter(data_table__isnull=False).values_list('data_table_id', flat=True))
    have_fields = set(AssetProfile.objects.filter(data_field__isnull=False).values_list('data_field_id', flat=True))
    new = []
    for tid in DataTable.objects.exclude(id__in=have_tables).values_list('id', flat=True):
        new.append(AssetProfile(data_table_id=tid))
    for fid in DataField.objects.exclude(id__in=have_fields).values_list('id', flat=True):
        new.append(AssetProfile(data_field_id=fid))
    if new:
        AssetProfile.objects.bulk_create(new)
    return len(new)
