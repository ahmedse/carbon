import io

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from inbound import registry
from inbound.models import InboundBatch
from inbound.parse import parse_csv


PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'


def _csv(text, name='t.csv'):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = name
    return buf


@pytest.fixture
def fake_cartridge():
    def smoke(rows, **_k):
        return {
            'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0,
            'sample': rows[:5], 'reject_rows': [],
        }

    def commit(rows, **_k):
        return {'written': len(rows)}

    registry.register(
        kind='typed_object',
        key='test.widget',
        label='Widget',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke,
        commit=commit,
    )
    yield
    # keep people cartridges; only drop the test key
    registry._REGISTRY.pop('test.widget', None)


@pytest.fixture
def preparer(create_user, create_scoped_role):
    user = create_user('prep')
    create_scoped_role(user, 'people_data_owners_group')
    return user


@pytest.fixture
def committer(create_user, create_scoped_role):
    user = create_user('cmt')
    create_scoped_role(user, 'people_lead')
    return user


@pytest.mark.django_db
def test_parse_csv_headers_and_count():
    """DMS-COR-PIPE DMS-PRF-03: envelope sample stays at 20; row_count is the file."""
    body = "code,name\n" + "".join(f"A{i},N{i}\n" for i in range(25))
    parsed = parse_csv(body.encode("utf-8"))
    assert parsed["headers"] == ["code", "name"]
    assert parsed["row_count"] == 25
    assert len(parsed["sample"]) == 20
    assert len(parsed["rows"]) == 25


@pytest.mark.django_db
def test_unknown_target_400(preparer, get_token_for_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'nope.x'}, format='json')
    assert res.status_code == 400


@pytest.mark.django_db
def test_unmapped_required_blocks_smoke(preparer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    assert res.status_code == 201
    bid = res.data['id']
    upload = _csv('code,name\nA,Alpha\n')
    res = client.post(f'{PREFIX}/batches/{bid}/file/', {'file': upload}, format='multipart')
    assert res.status_code == 200
    res = client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'name': 'code'}}, format='json')
    # 'code' is required and mapped via name→code, should be ok
    assert res.status_code == 200
    res = client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'name': ''}}, format='json')
    assert res.status_code == 400
    # DMS-REL-03: the batch stays draft and a corrected map can still be smoked.
    res = client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    assert res.status_code == 200
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['status'] == InboundBatch.STATUS_SMOKED


@pytest.mark.django_db
def test_commit_without_smoke_409(preparer, committer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(committer)}')
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 409


@pytest.mark.django_db
def test_same_user_commit_403(preparer, get_token_for_user, fake_cartridge):
    # people_data_owners have prepare not commit — use people_lead as both
    from accounts.models import ScopedRole
    from django.contrib.auth.models import Group
    user = preparer
    g, _ = Group.objects.get_or_create(name='people_lead')
    ScopedRole.objects.create(user=user, group=g, is_active=True)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 403


@pytest.mark.django_db
def test_two_person_commit(preparer, committer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 1
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(committer)}')
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert res.data['status'] == InboundBatch.STATUS_COMMITTED


@pytest.mark.django_db
def test_template_roundtrip(preparer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/templates/', {
        'name': 'Widget default',
        'kind': 'typed_object',
        'target_key': 'test.widget',
        'mapping': {'columns': {'code': 'code'}},
    }, format='json')
    assert res.status_code == 201
    res = client.get(f'{PREFIX}/templates/?target_key=test.widget')
    assert res.status_code == 200
    names = {row['name'] for row in res.data}
    assert 'Widget default' in names


@pytest.mark.django_db
def test_targets_lists_people_cartridges(preparer, get_token_for_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.get(f'{PREFIX}/batches/targets/?kind=typed_object')
    assert res.status_code == 200
    keys = {row['key'] for row in res.data}
    assert 'people.employee_snapshot' in keys
