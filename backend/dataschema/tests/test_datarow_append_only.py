"""Tests for DataRow append-only enforcement and index declarations."""
import pytest

from django.db import IntegrityError


@pytest.mark.django_db
def test_insert_succeeds():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module')
    table = DataTable.objects.create(title='T', name='t', module=module)
    row = DataRow.objects.create(data_table=table, values={'x': 1})
    assert row.pk is not None


@pytest.mark.django_db
def test_update_values_raises():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module-2')
    table = DataTable.objects.create(title='T2', name='t2', module=module)
    row = DataRow.objects.create(data_table=table, values={'x': 1})
    row.values = {'x': 2}
    with pytest.raises(IntegrityError, match='append-only'):
        row.save()


@pytest.mark.django_db
def test_update_without_update_fields_raises():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module-3')
    table = DataTable.objects.create(title='T3', name='t3', module=module)
    row = DataRow.objects.create(data_table=table, values={'x': 1})
    with pytest.raises(IntegrityError, match='append-only'):
        row.save()  # no update_fields → blocked


@pytest.mark.django_db
def test_update_allowed_fields_succeeds():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module-4')
    table = DataTable.objects.create(title='T4', name='t4', module=module)
    row = DataRow.objects.create(data_table=table, values={'x': 1})
    row.is_archived = True
    row.save(update_fields=['is_archived', 'updated_at'])  # allowed — must not raise


@pytest.mark.django_db
def test_update_immutable_field_with_update_fields_raises():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module-5')
    table = DataTable.objects.create(title='T5', name='t5', module=module)
    row = DataRow.objects.create(data_table=table, values={'x': 1})
    row.values = {'x': 99}
    with pytest.raises(IntegrityError, match='immutable'):
        row.save(update_fields=['values'])


@pytest.mark.django_db
def test_key_normalisation_on_insert():
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    module = Module.objects.create(name='AppOnly-Module-6')
    table = DataTable.objects.create(title='T6', name='t6', module=module)
    row = DataRow.objects.create(data_table=table, values={'RepCode': 'R-1', 'Amount': 9})
    row.refresh_from_db()
    assert 'repcode' in row.values
    assert 'amount' in row.values


@pytest.mark.django_db
def test_indexes_declared_on_meta():
    from dataschema.models import DataRow
    index_names = {i.name for i in DataRow._meta.indexes}
    assert 'datarow_table_id_idx' in index_names
    assert 'datarow_table_time_idx' in index_names
