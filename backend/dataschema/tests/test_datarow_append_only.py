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


def _superuser_request(query):
    """Request stand-in. The reused test database cannot insert accounts_user."""
    from types import SimpleNamespace
    from django.http import QueryDict

    return SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, is_superuser=True, pk=1, id=1, username='de'),
        query_params=QueryDict(query),
    )


@pytest.mark.django_db
def test_de_search_matches_values_not_keys():
    """DE-SEARCH: a miss returns nothing; a value token returns that row."""
    from core.models import Module
    from dataschema.models import DataRow, DataTable
    from dataschema.views import DataRowViewSet

    module = Module.objects.create(name='DE-Search-Module')
    table = DataTable.objects.create(title='Electricity', name='de_kwh', module=module)
    DataRow.objects.create(data_table=table, values={'month': '7/1/2025', 'kwh': 1027668})
    DataRow.objects.create(data_table=table, values={'month': '8/1/2025', 'kwh': 993673})

    def listed(query):
        view = DataRowViewSet()
        view.request = _superuser_request(query)
        view.action = 'list'
        return list(view.get_queryset())

    assert listed(f'data_table={table.pk}&search=zzzz-no-such-month') == []
    hit = listed(f'data_table={table.pk}&search=1027668')
    assert len(hit) == 1
    assert hit[0].values['kwh'] == 1027668
    narrowed = listed(f'data_table={table.pk}&field__kwh=993673')
    assert len(narrowed) == 1
    assert narrowed[0].values['month'] == '8/1/2025'


@pytest.mark.django_db
def test_de_append_patch_is_refused():
    """DE-APPEND: patching values is a 409 and the stored row stays."""
    from types import SimpleNamespace
    from rest_framework.test import APIRequestFactory

    from core.models import Module
    from dataschema.models import DataRow, DataTable
    from dataschema.views import DataRowViewSet

    module = Module.objects.create(name='DE-Append-Module')
    table = DataTable.objects.create(title='Electricity', name='de_append', module=module)
    row = DataRow.objects.create(data_table=table, values={'kwh': 100})

    factory = APIRequestFactory()
    django_request = factory.patch(
        f'/rows/{row.pk}/', {'values': {'kwh': 999}}, format='json',
    )
    django_request.user = SimpleNamespace(
        is_authenticated=True, is_superuser=True, pk=1, id=1, username='de',
    )
    view = DataRowViewSet()
    view.action_map = {'patch': 'partial_update'}
    view.kwargs = {'pk': row.pk}
    view.format_kwarg = None
    request = view.initialize_request(django_request)
    request.user = django_request.user
    view.request = request
    view.get_object = lambda: row
    response = view.partial_update(request, pk=row.pk)

    assert response.status_code == 409
    assert response.data['code'] == 'append_only'
    row.refresh_from_db()
    assert row.values['kwh'] == 100


@pytest.mark.django_db
def test_indexes_declared_on_meta():
    from dataschema.models import DataRow
    index_names = {i.name for i in DataRow._meta.indexes}
    assert 'datarow_table_id_idx' in index_names
    assert 'datarow_table_time_idx' in index_names
