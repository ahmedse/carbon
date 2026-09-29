"""DMS-COR-CART: a cartridge declaration is not a handler."""
import pytest
from django.conf import settings
from rest_framework.test import APIClient

from inbound import registry
from inbound.models import InboundBatch, InboundCartridge

PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'


def _fields():
    return [{'name': 'code', 'label': 'Code', 'required': True}]


@pytest.fixture
def definer(create_user):
    user = create_user('cart_def')
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=['is_superuser', 'is_staff'])
    return user


@pytest.fixture
def people_lead(create_user, create_scoped_role):
    user = create_user('cart_lead')
    create_scoped_role(user, 'people_lead')
    return user


@pytest.mark.django_db
def test_studio_label_survives_reregister():
    """DMS-COR-CART"""
    registry.register(
        kind='typed_object', key='test.widget', label='Widget',
        fields=_fields(), smoke=lambda rows, **_k: {}, commit=lambda rows, **_k: {},
    )
    row = InboundCartridge.objects.get(key='test.widget')
    row.label = 'Studio name'
    row.save(update_fields=['label', 'updated_at'])
    registry.register(
        kind='typed_object', key='test.widget', label='Widget',
        fields=_fields(), smoke=lambda rows, **_k: {}, commit=lambda rows, **_k: {},
    )
    row.refresh_from_db()
    assert row.label == 'Studio name'
    assert registry._REGISTRY['test.widget']['label'] == 'Studio name'


@pytest.mark.django_db
def test_people_lead_cannot_define(people_lead, get_token_for_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(people_lead)}')
    res = client.post(f'{PREFIX}/cartridges/', {
        'key': 'eduos.room',
        'label': 'Room',
        'fields': _fields(),
    }, format='json')
    assert res.status_code == 403


@pytest.mark.django_db
def test_unbound_cartridge_cannot_receive_a_batch(definer, get_token_for_user, create_user, create_scoped_role):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(definer)}')
    res = client.post(f'{PREFIX}/cartridges/', {
        'key': 'eduos.room',
        'label': 'Room',
        'fields': _fields(),
    }, format='json')
    assert res.status_code == 201
    assert res.data['bound'] is False
    assert res.data['owner_app'] == 'eduos'
    preparer = create_user('cart_prep')
    create_scoped_role(preparer, 'people_data_owners_group')
    prep = APIClient()
    prep.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = prep.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'eduos.room',
    }, format='json')
    assert res.status_code == 400
    assert 'no handler' in res.data['detail']


@pytest.mark.django_db
def test_disable_hides_target_and_delete_of_bound_is_refused(definer, get_token_for_user):
    registry.register(
        kind='typed_object', key='test.widget', label='Widget',
        fields=_fields(), smoke=lambda rows, **_k: {}, commit=lambda rows, **_k: {},
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(definer)}')
    row = InboundCartridge.objects.get(key='test.widget')
    res = client.delete(f'{PREFIX}/cartridges/{row.id}/')
    assert res.status_code == 409
    res = client.patch(f'{PREFIX}/cartridges/{row.id}/', {'enabled': False}, format='json')
    assert res.status_code == 200
    assert res.data['enabled'] is False
    res = client.get(f'{PREFIX}/batches/targets/?kind=typed_object')
    assert res.status_code == 200
    assert 'test.widget' not in {item['key'] for item in res.data}


@pytest.mark.django_db
def test_delete_unbound_with_no_batches(definer, get_token_for_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(definer)}')
    res = client.post(f'{PREFIX}/cartridges/', {
        'key': 'eduos.room',
        'label': 'Room',
        'fields': _fields(),
    }, format='json')
    cid = res.data['id']
    res = client.get(f'{PREFIX}/cartridges/{cid}/')
    assert res.status_code == 200
    assert res.data['batch_count'] == 0
    res = client.delete(f'{PREFIX}/cartridges/{cid}/')
    assert res.status_code == 204
    assert not InboundCartridge.objects.filter(key='eduos.room').exists()


@pytest.mark.django_db
def test_retrieve_lists_the_batches_for_the_key(definer, get_token_for_user):
    """DMS-COR-CART observe: the declaration shows the batches that used the key."""
    registry.register(
        kind='typed_object', key='test.widget', label='Widget',
        fields=_fields(), smoke=lambda rows, **_k: {}, commit=lambda rows, **_k: {},
    )
    InboundBatch.objects.create(
        kind='typed_object',
        target_key='test.widget',
        status='committed',
        original_filename='opening.csv',
        smoke={'reject': 0, 'insert': 1},
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(definer)}')
    row = InboundCartridge.objects.get(key='test.widget')
    detail = client.get(f'{PREFIX}/cartridges/{row.id}/')
    assert detail.status_code == 200
    assert detail.data['recent_batches'][0]['original_filename'] == 'opening.csv'
    assert detail.data['recent_batches'][0]['status'] == 'committed'
    assert detail.data['recent_batches'][0]['reject'] == 0
    listed = client.get(f'{PREFIX}/cartridges/')
    body = listed.data['results'] if isinstance(listed.data, dict) else listed.data
    summary = next(item for item in body if item['key'] == 'test.widget')
    assert summary['batch_count'] == 1
    assert summary['recent_batches'] == []
