import io

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from inbound import registry, services
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
        sample = [
            {'row': i, 'key': (row.get('code') or ''), 'verdict': 'insert', 'reason': ''}
            for i, row in enumerate(rows, start=1)
        ][:5]
        return {
            'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0,
            'sample': sample, 'reject_rows': [],
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
def test_committed_batch_keeps_smoke_and_refuses_resmoke(
    preparer, committer, get_token_for_user, fake_cartridge,
):
    """Committed reopen is read-only: the persisted smoke envelope survives, re-smoke is 409.

    The People Import studio renders `smoke.sample` for a committed batch and
    must not be gated by a fresh smoke. This locks the server contract behind it.
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    smoke = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert smoke.data['smoke']['insert'] == 1
    assert smoke.data['smoke']['sample']

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(committer)}')
    committed = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert committed.status_code == 200
    assert committed.data['status'] == InboundBatch.STATUS_COMMITTED

    # Re-read keeps the smoke envelope (the UI renders the sample read-only).
    reread = client.get(f'{PREFIX}/batches/{bid}/')
    assert reread.data['smoke']['insert'] == 1
    assert reread.data['smoke']['sample']
    assert reread.data['smoke']['commit'] == {'written': 1}

    # A committed batch cannot be re-smoked.
    resmoke = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert resmoke.status_code == 409


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


@pytest.mark.django_db
def test_batch_rows_paginates_and_bounds(preparer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    body = 'code\n' + ''.join(f'A{i}\n' for i in range(1, 46))
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    smoke = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert smoke.data['smoke']['insert'] == 45

    res = client.get(f'{PREFIX}/batches/{bid}/rows/?page=1&page_size=20')
    assert res.status_code == 200
    assert res.data['count'] == 45
    assert res.data['page'] == 1
    assert res.data['page_size'] == 20
    assert len(res.data['results']) == 20
    first = res.data['results'][0]
    assert first['row'] == 1
    assert first['key'] == 'A1'
    assert first['verdict'] == 'insert'
    assert first['reason'] == ''
    assert first['values'] == {'code': 'A1'}

    # A page past the sample still returns rows (this is the 21+ gap).
    res = client.get(f'{PREFIX}/batches/{bid}/rows/?page=3&page_size=20')
    assert len(res.data['results']) == 5
    assert res.data['results'][0]['row'] == 41
    assert res.data['results'][-1]['row'] == 45

    # page floors at 1; page_size clamps to the max bound.
    res = client.get(f'{PREFIX}/batches/{bid}/rows/?page=0&page_size=9999')
    assert res.data['page'] == 1
    assert res.data['page_size'] == services.MAX_PAGE_SIZE
    assert len(res.data['results']) == 45

    bad = client.get(f'{PREFIX}/batches/{bid}/rows/?page=nope&page_size=10')
    assert bad.status_code == 400


@pytest.mark.django_db
def test_batch_rows_no_file_400(preparer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    res = client.get(f"{PREFIX}/batches/{res.data['id']}/rows/")
    assert res.status_code == 400


@pytest.mark.django_db
def test_batch_rows_forbidden_without_permission(create_user, get_token_for_user, fake_cartridge):
    nobody = create_user('nobody')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(nobody)}')
    res = client.get(f'{PREFIX}/batches/1/rows/')
    assert res.status_code == 403


@pytest.mark.django_db
def test_batch_rows_works_for_committed_batch(preparer, committer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = res.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\nB\nC\n')}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(committer)}')
    committed = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert committed.data['status'] == InboundBatch.STATUS_COMMITTED

    res = client.get(f'{PREFIX}/batches/{bid}/rows/?page=1&page_size=50')
    assert res.status_code == 200
    assert res.data['count'] == 3
    assert [row['row'] for row in res.data['results']] == [1, 2, 3]
    # The committed batch is still readable and keeps the persisted verdicts.
    assert res.data['results'][0]['verdict'] == 'insert'
    assert res.data['results'][0]['reason'] == ''


@pytest.mark.django_db
def test_template_examples_index_and_download(preparer, get_token_for_user, fake_cartridge):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    res = client.get(f'{PREFIX}/templates/examples/')
    assert res.status_code == 200
    slugs = {row['slug'] for row in res.data}
    assert 'people-employee-snapshot' in slugs
    row = next(item for item in res.data if item['slug'] == 'people-employee-snapshot')
    assert 'employee_no' in row['columns']

    download = client.get(f'{PREFIX}/templates/examples/people-employee-snapshot/')
    assert download.status_code == 200
    assert download['Content-Type'].startswith('text/csv')
    assert b'employee_no' in download.content

    missing = client.get(f'{PREFIX}/templates/examples/not-a-template/')
    assert missing.status_code == 404
