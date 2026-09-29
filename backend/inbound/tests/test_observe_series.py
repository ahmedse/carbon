"""DMS-OBS-04: the series is the smoke envelope the batch already stored."""
import io
import json

import pytest
from django.conf import settings
from django.core.management import call_command
from rest_framework.test import APIClient

from inbound import registry
from inbound.models import InboundBatch
from inbound.observe import series_batches, write_smoke_series

PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'


@pytest.fixture
def widget():
    def smoke(rows, **_k):
        rejected = [row for row in rows if row.get('code') == 'bad']
        return {
            'insert': len(rows) - len(rejected),
            'update': 0,
            'skip': 0,
            'reject': len(rejected),
            'sample': rows[:5],
            'reject_rows': rejected,
        }

    registry.register(
        kind='typed_object',
        key='test.widget',
        label='Widget',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke,
        commit=lambda rows, **_k: {'written': len(rows)},
    )
    yield
    registry._REGISTRY.pop('test.widget', None)


@pytest.fixture
def preparer(create_user, create_scoped_role):
    user = create_user('obs_prep')
    create_scoped_role(user, 'people_data_owners_group')
    return user


@pytest.mark.django_db
def test_smoke_series_matches_the_saved_envelope(tmp_path, widget, preparer, get_token_for_user):
    """DMS-OBS-04"""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(preparer)}')
    created = client.post(
        f'{PREFIX}/batches/',
        {'kind': 'typed_object', 'target_key': 'test.widget'},
        format='json',
    )
    assert created.status_code == 201
    bid = created.data['id']
    upload = io.BytesIO(b'code\nok\nbad\n')
    upload.name = 'widgets.csv'
    assert client.post(f'{PREFIX}/batches/{bid}/file/', {'file': upload}, format='multipart').status_code == 200
    assert client.put(
        f'{PREFIX}/batches/{bid}/mapping/',
        {'columns': {'code': 'code'}},
        format='json',
    ).status_code == 200
    smoked = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert smoked.status_code == 200

    batch = InboundBatch.objects.get(pk=bid)
    path = tmp_path / 'inbound-series.json'
    write_smoke_series(path, [batch])
    row = json.loads(path.read_text(encoding='utf-8'))['rows'][0]
    assert row['batch_id'] == batch.id
    assert row['status'] == batch.status == 'smoked'
    assert row['target_key'] == 'test.widget'
    assert row['insert'] == batch.smoke['insert'] == 1
    assert row['reject'] == batch.smoke['reject'] == 1
    assert row['update'] == 0
    assert row['skip'] == 0
    assert path.is_relative_to(tmp_path)


@pytest.mark.django_db
def test_series_batches_keep_ten_newest_envelopes():
    """DMS-OBS-05: drafts and empty envelopes stay out. Limit is 10."""
    smoked_ids = []
    for _ in range(11):
        row = InboundBatch.objects.create(
            kind='typed_object', target_key='test.widget', status='smoked',
            smoke={'insert': 1, 'update': 0, 'skip': 0, 'reject': 0},
        )
        smoked_ids.append(row.id)
    draft = InboundBatch.objects.create(
        kind='typed_object', target_key='test.widget', status='draft',
        smoke={'insert': 9, 'update': 0, 'skip': 0, 'reject': 0},
    )
    InboundBatch.objects.create(
        kind='typed_object', target_key='test.widget', status='smoked', smoke={},
    )
    chosen = series_batches()
    ids = [batch.id for batch in chosen]
    assert len(ids) == 10
    assert ids == sorted(ids, reverse=True)
    assert min(smoked_ids) not in ids
    assert draft.id not in ids
    assert all(batch.smoke for batch in chosen)


@pytest.mark.django_db
def test_command_writes_tmp_and_skips_when_empty(tmp_path):
    """DMS-OBS-05: the command calls write_smoke_series. An empty selection creates nothing."""
    empty = tmp_path / 'empty.json'
    call_command('write_inbound_smoke_series', path=str(empty))
    if series_batches():
        assert empty.is_file()
    else:
        assert not empty.exists()

    InboundBatch.objects.create(
        kind='typed_object', target_key='test.widget', status='committed',
        smoke={'insert': 1, 'update': 0, 'skip': 0, 'reject': 1},
    )
    dest = tmp_path / 'series.json'
    call_command('write_inbound_smoke_series', path=str(dest))
    payload = json.loads(dest.read_text(encoding='utf-8'))
    assert payload['schema'] == 1
    assert payload['rows'][0]['insert'] == 1
    assert payload['rows'][0]['reject'] == 1
    assert dest.is_relative_to(tmp_path)


def test_writer_creates_a_missing_parent_directory(tmp_path):
    """DMS-OBS-05: the declared evidence directory may be absent."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    batch = SimpleNamespace(
        id=6, status='committed', target_key='people.leave_history',
        updated_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
        smoke={'insert': 1, 'update': 0, 'skip': 0, 'reject': 0},
    )
    path = tmp_path / 'evidence' / 'inbound-smoke-series.json'
    write_smoke_series(path, [batch])
    assert path.is_file()
    assert json.loads(path.read_text(encoding='utf-8'))['schema'] == 1
