import csv
import io

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from inbound import registry, services
from inbound.models import InboundBatch, InboundTemplate
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
def test_batch_rows_prefers_structured_results_over_sample(
    preparer, get_token_for_user, fake_cartridge,
):
    """The full results list wins over the <=20 sample and carries issues.

    A reject_rows entry without ``issues`` must not erase the structured issues
    the results list already provided (legacy envelopes have no issues).
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\nB\nC\n')}, format='multipart')
    batch = InboundBatch.objects.get(id=bid)
    batch.smoke = {
        'insert': 2, 'update': 0, 'skip': 0, 'reject': 1,
        'sample': [{'row': 1, 'key': 'A', 'verdict': 'insert', 'reason': ''}],
        'results': [
            {'row': 1, 'key': 'A', 'verdict': 'insert', 'reason': ''},
            {'row': 2, 'key': 'B', 'verdict': 'reject', 'reason': 'code unresolved',
             'issues': [{'field': 'code', 'message': 'code unresolved', 'fix': 'Use a known code.'}]},
            {'row': 3, 'key': 'C', 'verdict': 'insert', 'reason': ''},
        ],
        'reject_rows': [{'row': 2, 'key': 'B', 'verdict': 'reject', 'reason': 'code unresolved'}],
    }
    batch.save(update_fields=['smoke'])

    res = client.get(f'{PREFIX}/batches/{bid}/rows/?page=1&page_size=50')
    assert res.status_code == 200
    assert res.data['smoked'] is True
    by_row = {row['row']: row for row in res.data['results']}
    assert by_row[3]['verdict'] == 'insert'
    assert by_row[3]['issues'] == []
    assert by_row[2]['issues'][0]['field'] == 'code'
    assert by_row[2]['issues'][0]['fix'] == 'Use a known code.'


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


@pytest.mark.django_db
def test_batches_list_q_and_status_filters(preparer, get_token_for_user, fake_cartridge):
    """Defect 1: the list sends q + active filters to the API, not the client."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')

    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    b_mapped = res.data['id']
    client.post(f'{PREFIX}/batches/{b_mapped}/file/', {'file': _csv('code\nA\n', name='alpha.csv')}, format='multipart')
    client.put(f'{PREFIX}/batches/{b_mapped}/mapping/', {'columns': {'code': 'code'}}, format='json')

    res = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    b_draft = res.data['id']
    client.post(f'{PREFIX}/batches/{b_draft}/file/', {'file': _csv('code\nB\n', name='beta.csv')}, format='multipart')

    def ids(query):
        r = client.get(f'{PREFIX}/batches/?kind=typed_object{query}')
        assert r.status_code == 200
        data = r.data if isinstance(r.data, list) else r.data['results']
        return {row['id'] for row in data}

    assert ids('&q=alpha') == {b_mapped}
    assert ids('&status=draft') == {b_draft}
    assert ids('&status=mapped') == {b_mapped}
    assert ids('&q=beta&status=draft') == {b_draft}


@pytest.mark.django_db
def test_batch_scoping_owner_vs_peer_vs_admin(
    preparer, committer, create_user, create_scoped_role, get_token_for_user, fake_cartridge,
):
    """Defect 2: a prepare-only peer must not read or mutate another user's batch."""
    owner = APIClient()
    owner.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = owner.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']
    owner.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')

    peer_user = create_user('peer')
    create_scoped_role(peer_user, 'people_data_owners_group')
    peer = APIClient()
    peer.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(peer_user)}')

    # Detail, mutate (smoke), rejects export and rows are all out of scope.
    assert peer.get(f'{PREFIX}/batches/{bid}/').status_code == 404
    assert peer.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json').status_code == 404
    assert peer.get(f'{PREFIX}/batches/{bid}/rejects/').status_code == 404
    assert peer.get(f'{PREFIX}/batches/{bid}/rows/').status_code == 404

    # The peer's list never includes the owner's batch — no invisible rows.
    listed = peer.get(f'{PREFIX}/batches/?kind=typed_object')
    peer_ids = {row['id'] for row in (listed.data if isinstance(listed.data, list) else listed.data['results'])}
    assert bid not in peer_ids

    # The owner sees their own batch.
    own = owner.get(f'{PREFIX}/batches/?kind=typed_object')
    own_ids = {row['id'] for row in (own.data if isinstance(own.data, list) else own.data['results'])}
    assert bid in own_ids

    # A committer keeps full visibility (two-person rule).
    cmt = APIClient()
    cmt.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(committer)}')
    assert cmt.get(f'{PREFIX}/batches/{bid}/').status_code == 200

    # Staff/admin keep full visibility.
    admin = create_user('boss', is_staff=True, is_superuser=True)
    adm = APIClient()
    adm.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
    assert adm.get(f'{PREFIX}/batches/{bid}/').status_code == 200


@pytest.mark.django_db
def test_template_scoping_and_overwrite_guard(
    preparer, create_user, create_scoped_role, get_token_for_user, fake_cartridge,
):
    """Defects 2 + 5: templates are owner-scoped and cannot be silently overwritten."""
    payload = {
        'name': 'Shared widget',
        'kind': 'typed_object',
        'target_key': 'test.widget',
        'mapping': {'columns': {'code': 'code'}},
    }
    owner = APIClient()
    owner.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = owner.post(f'{PREFIX}/templates/', payload, format='json')
    assert created.status_code == 201
    tpl_id = created.data['id']
    assert created.data['owner_username'] == 'prep'

    peer_user = create_user('peer_tpl')
    create_scoped_role(peer_user, 'people_data_owners_group')
    peer = APIClient()
    peer.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(peer_user)}')

    # The peer cannot see the owner's personal template, but shared/official is visible.
    InboundTemplate.objects.create(
        name='Official widget', kind='typed_object', target_key='test.widget', mapping={}, owner=None,
    )
    listed = peer.get(f'{PREFIX}/templates/?target_key=test.widget')
    names = {row['name'] for row in (listed.data if isinstance(listed.data, list) else listed.data['results'])}
    assert 'Shared widget' not in names
    assert 'Official widget' in names

    # Overwriting another user's template by name is refused.
    res = peer.post(f'{PREFIX}/templates/', payload, format='json')
    assert res.status_code == 403
    # Overwriting an official/shared (ownerless) row is refused too.
    res = peer.post(f'{PREFIX}/templates/', {**payload, 'name': 'Official widget'}, format='json')
    assert res.status_code == 403
    # A new name is fine.
    res = peer.post(f'{PREFIX}/templates/', {**payload, 'name': 'Peer own'}, format='json')
    assert res.status_code == 201

    # The owner may overwrite their own template in place (same id, same owner).
    res = owner.post(
        f'{PREFIX}/templates/',
        {**payload, 'mapping': {'columns': {'code': 'code', 'name': 'code'}}},
        format='json',
    )
    assert res.status_code == 201
    assert res.data['id'] == tpl_id
    assert res.data['owner_username'] == 'prep'

    # The create-only official seed row is untouched.
    official = InboundTemplate.objects.get(name='Official widget')
    assert official.owner_id is None


@pytest.mark.django_db
def test_smoke_refuses_cross_kind(
    preparer, create_user, create_scoped_role, get_token_for_user, fake_cartridge,
):
    """Defect 3: a product steward must not smoke a typed People batch."""
    owner = APIClient()
    owner.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = owner.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']
    owner.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    owner.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': {'code': 'code'}}, format='json')

    steward_user = create_user('prod_steward')
    create_scoped_role(steward_user, 'datahub_lead')
    steward = APIClient()
    steward.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(steward_user)}')
    # Full visibility (commit path) so the batch is reachable…
    assert steward.get(f'{PREFIX}/batches/{bid}/').status_code == 200
    # …but the destination kind gate refuses the smoke.
    res = steward.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 403


@pytest.mark.django_db
def test_rows_missing_file_is_400_not_500(preparer, get_token_for_user, fake_cartridge):
    """Defect 4: a file missing from disk is a clean 4xx, never a 500."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']
    batch = InboundBatch.objects.get(id=bid)
    batch.file.name = 'inbound/2026/01/this-file-was-deleted.csv'
    batch.save(update_fields=['file'])

    res = client.get(f'{PREFIX}/batches/{bid}/rows/')
    assert res.status_code == 400
    assert 'missing' in res.data['detail'].lower()


@pytest.mark.django_db
def test_upload_size_cap(monkeypatch, preparer, get_token_for_user, fake_cartridge):
    """Defect 6: an oversized upload is rejected before it is parsed/stored."""
    monkeypatch.setattr(services, 'MAX_UPLOAD_BYTES', 16)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']

    too_big = _csv('code\n' + ('A' * 64) + '\n')
    res = client.post(f'{PREFIX}/batches/{bid}/file/', {'file': too_big}, format='multipart')
    assert res.status_code == 413

    # The batch still accepts a within-limit file afterwards.
    res = client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv('code\nA\n')}, format='multipart')
    assert res.status_code == 200
    assert InboundBatch.objects.get(id=bid).headers == ['code']


@pytest.mark.django_db
def test_commit_is_atomic_on_failure(tmp_path, settings, preparer, committer):
    """Defect 7: a mid-loop host failure rolls back the partial host write."""
    settings.MEDIA_ROOT = str(tmp_path)

    def smoke(rows, **_k):
        return {'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0, 'sample': [], 'reject_rows': []}

    def commit(rows, **_k):
        InboundTemplate.objects.create(
            name='txn-canary', kind='typed_object', target_key='test.txn', mapping={},
        )
        raise RuntimeError('host commit failed mid-loop')

    registry.register(
        kind='typed_object',
        key='test.txn',
        label='Txn',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke,
        commit=commit,
    )
    try:
        batch = InboundBatch.objects.create(
            kind='typed_object', target_key='test.txn', prepared_by=preparer,
            status=InboundBatch.STATUS_SMOKED,
        )
        batch.file.save('txn.csv', ContentFile(b'code\nA\n'), save=True)
        batch.mapping = {'columns': {'code': 'code'}, 'crosswalks': {}}
        batch.smoke = {'insert': 1, 'update': 0, 'skip': 0, 'reject': 0, 'sample': [], 'reject_rows': []}
        batch.save()

        with pytest.raises(RuntimeError):
            services.run_commit(batch, committer)

        # The canary insert is rolled back and the batch is not marked committed.
        assert not InboundTemplate.objects.filter(name='txn-canary').exists()
        batch.refresh_from_db()
        assert batch.status == InboundBatch.STATUS_SMOKED
    finally:
        registry._REGISTRY.pop('test.txn', None)


@pytest.mark.django_db
def test_rejects_csv_neutralizes_formula_cells(preparer, get_token_for_user, fake_cartridge):
    """Defect 8: a reject cell cannot open as a formula in Excel."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = client.post(f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': 'test.widget'}, format='json')
    bid = created.data['id']
    batch = InboundBatch.objects.get(id=bid)
    batch.smoke = {
        'reject': 2,
        'reject_rows': [
            {'row': 1, 'key': '=HYPERLINK("http://evil")', 'reason': '+SUM(1)', 'verdict': 'reject'},
            {'row': 2, 'key': '@cmd', 'reason': '\t=1+1', 'verdict': 'reject'},
        ],
    }
    batch.save(update_fields=['smoke'])

    res = client.get(f'{PREFIX}/batches/{bid}/rejects/')
    assert res.status_code == 200
    rows = list(csv.reader(io.StringIO(res.content.decode('utf-8'))))
    assert len(rows) == 3
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(('=', '+', '-', '@', '\t', '\r'))
    all_cells = [cell for row in rows[1:] for cell in row]
    assert any(cell.startswith("'=") for cell in all_cells)
    assert any(cell.startswith("'+") for cell in all_cells)
    assert any(cell.startswith("'@") for cell in all_cells)
