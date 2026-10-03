"""ID2 — idempotent commit (row lock + replay-return) and the durable run ledger.

These tests exercise real Postgres ``select_for_update`` behaviour: the
concurrency test uses ``django_db(transaction=True)`` so the row lock and the
host write really commit instead of living inside the test's outer transaction.
"""

from __future__ import annotations

import io
import threading
import time
from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import connections
from rest_framework.test import APIClient

from accounts.models import ScopedRole
from catalog.models import GovernanceEvent
from inbound import registry
from inbound.models import InboundBatch, InboundCommitRun
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveRecord


PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'
WIDGET_KEY = 'test.widget_run'


def _csv(text, name='t.csv'):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = name
    return buf


def _auth(client, user, get_token_for_user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='HR', slug='hr-runs', code='HR', org_type='department')


@pytest.fixture
def leave_annual(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type-runs')
    return ReferenceValue.objects.create(reference_set=rs, code='annual', label='Annual')


@pytest.fixture
def preparer(create_user, create_scoped_role):
    user = create_user('runs_prep')
    create_scoped_role(user, 'people_data_owners_group')
    return user


@pytest.fixture
def committer(create_user, create_scoped_role):
    user = create_user('runs_cmt')
    create_scoped_role(user, 'people_lead')
    return user


@pytest.fixture
def widget_cartridge():
    def smoke(rows, **_k):
        return {
            'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0,
            'sample': [], 'reject_rows': [],
        }

    def commit(rows, *, progress=None, **_k):
        for i, _row in enumerate(rows, start=1):
            if progress:
                progress(i, i)
        return {'written': len(rows), 'reconcile': {'widgets': len(rows)}}

    registry.register(
        kind='typed_object', key=WIDGET_KEY, label='Widget',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke, commit=commit,
    )
    yield
    registry._REGISTRY.pop(WIDGET_KEY, None)


def _create_smoked(client, get_token_for_user, prep, target_key, body, columns):
    _auth(client, prep, get_token_for_user)
    res = client.post(
        f'{PREFIX}/batches/', {'kind': 'typed_object', 'target_key': target_key}, format='json',
    )
    assert res.status_code == 201, res.data
    bid = res.data['id']
    res = client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    assert res.status_code == 200, res.data
    res = client.put(f'{PREFIX}/batches/{bid}/mapping/', {'columns': columns}, format='json')
    assert res.status_code == 200, res.data
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200, res.data
    return bid


def _commit(client, user, bid, get_token_for_user, allow_partial=False):
    _auth(client, user, get_token_for_user)
    return client.post(
        f'{PREFIX}/batches/{bid}/commit/', {'allow_partial': allow_partial}, format='json',
    )


# ---------------------------------------------------------------------------
# ID2 backend contract
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_commit_replay_returns_prior_result(
    preparer, committer, org, get_token_for_user,
):
    """A second commit is an idempotent replay: prior result, no second write."""
    client = APIClient()
    bid = _create_smoked(
        client, get_token_for_user, preparer,
        'people.employee_snapshot',
        'employee_no,full_name,org_unit,basic_salary\nE1,One,HR,100.000\n',
        {
            'employee_no': 'employee_no', 'full_name': 'full_name',
            'org_unit': 'org_unit', 'basic_salary': 'basic_salary',
        },
    )
    first = _commit(client, committer, bid, get_token_for_user)
    assert first.status_code == 200, first.data
    assert Employee.objects.count() == 1
    events_after_first = GovernanceEvent.objects.filter(entity_type='Employee').count()

    second = _commit(client, committer, bid, get_token_for_user)
    assert second.status_code == 200, second.data
    assert second.data['status'] == InboundBatch.STATUS_COMMITTED
    # Prior result is returned: same written count, not a fresh write.
    assert second.data['commit_run']['written'] == 1
    assert Employee.objects.count() == 1
    assert GovernanceEvent.objects.filter(entity_type='Employee').count() == events_after_first
    # Replay reuses the existing run; it does not append a second ledger row.
    assert InboundCommitRun.objects.filter(batch_id=bid).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_commit_single_write(
    preparer, committer, get_token_for_user,
):
    """Two concurrent commits → exactly one host write; both return the result."""
    writes = {'n': 0, 'lock': threading.Lock()}

    def smoke(rows, **_k):
        return {'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0, 'sample': [], 'reject_rows': []}

    def commit(rows, *, progress=None, **_k):
        with writes['lock']:
            writes['n'] += 1
        # Widen the race window so the second request really hits the row lock.
        time.sleep(0.4)
        return {'written': len(rows), 'reconcile': {'widgets': len(rows)}}

    registry.register(
        kind='typed_object', key='test.concurrent', label='Concurrent',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke, commit=commit,
    )
    try:
        client = APIClient()
        bid = _create_smoked(
            client, get_token_for_user, preparer, 'test.concurrent',
            'code\nA\n', {'code': 'code'},
        )
        token = get_token_for_user(committer)
        barrier = threading.Barrier(2)
        results: dict[int, object] = {}

        def worker(index):
            local = APIClient()
            local.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            try:
                barrier.wait(timeout=5)
                res = local.post(
                    f'{PREFIX}/batches/{bid}/commit/', {}, format='json',
                )
                results[index] = (res.status_code, dict(res.data))
            except Exception as exc:  # noqa: BLE001 — surface in the assert
                results[index] = ('error', repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        assert set(results) == {0, 1}, results
        for index in (0, 1):
            status_code, data = results[index]
            assert status_code == 200, (index, data)
            assert data['status'] == InboundBatch.STATUS_COMMITTED
            assert data['commit_run']['written'] == 1
        assert writes['n'] == 1
    finally:
        registry._REGISTRY.pop('test.concurrent', None)


@pytest.mark.django_db
def test_retry_after_error_no_duplicate_rows(
    preparer, committer, get_token_for_user,
):
    """A failed mid-loop commit rolls back; retry writes exactly one row."""
    from inbound.exceptions import InboundError

    state = {'attempts': 0}

    def smoke(rows, **_k):
        return {'insert': len(rows), 'update': 0, 'skip': 0, 'reject': 0, 'sample': [], 'reject_rows': []}

    def commit(rows, *, batch=None, user=None, smoke=None, progress=None, **_k):
        state['attempts'] += 1
        # A real host write that must roll back when the attempt fails.
        from inbound.models import InboundTemplate
        InboundTemplate.objects.create(
            name='retry-canary', kind='typed_object', target_key='test.retry', mapping={},
        )
        if state['attempts'] == 1:
            raise InboundError('host commit failed mid-loop', status=500)
        return {'written': len(rows), 'reconcile': {'widgets': len(rows)}}

    registry.register(
        kind='typed_object', key='test.retry', label='Retry',
        fields=[{'name': 'code', 'label': 'Code', 'required': True}],
        smoke=smoke, commit=commit,
    )
    try:
        from inbound.models import InboundTemplate

        client = APIClient()
        bid = _create_smoked(
            client, get_token_for_user, preparer, 'test.retry',
            'code\nA\n', {'code': 'code'},
        )
        failed = _commit(client, committer, bid, get_token_for_user)
        assert failed.status_code == 500, failed.data
        # The canary write rolled back with the failed transaction.
        assert not InboundTemplate.objects.filter(name='retry-canary').exists()
        assert InboundCommitRun.objects.filter(
            batch_id=bid, status=InboundCommitRun.STATUS_FAILED,
        ).count() == 1

        retried = _commit(client, committer, bid, get_token_for_user)
        assert retried.status_code == 200, retried.data
        assert InboundTemplate.objects.filter(name='retry-canary').count() == 1
        assert retried.data['commit_run']['written'] == 1
    finally:
        registry._REGISTRY.pop('test.retry', None)


@pytest.mark.django_db
def test_no_duplicate_governance_events(
    preparer, committer, org, get_token_for_user,
):
    """One commit writes one event per row; replay/concurrent write none."""
    client = APIClient()
    bid = _create_smoked(
        client, get_token_for_user, preparer, 'people.employee_snapshot',
        'employee_no,full_name,org_unit,basic_salary\n'
        'E1,One,HR,100.000\nE2,Two,HR,200.000\n',
        {
            'employee_no': 'employee_no', 'full_name': 'full_name',
            'org_unit': 'org_unit', 'basic_salary': 'basic_salary',
        },
    )
    first = _commit(client, committer, bid, get_token_for_user)
    assert first.status_code == 200, first.data
    assert GovernanceEvent.objects.filter(entity_type='Employee').count() == 2

    replay = _commit(client, committer, bid, get_token_for_user)
    assert replay.status_code == 200
    assert GovernanceEvent.objects.filter(entity_type='Employee').count() == 2


@pytest.mark.django_db
def test_leave_history_no_duplicate_records_on_retry(
    preparer, committer, org, leave_annual, get_token_for_user,
):
    """Replaying a leave-history commit adds no LeaveRecord."""
    Employee.objects.create(
        org_unit=org, employee_no='E1', full_name='One',
        basic_salary=Decimal('100.000'),
    )
    client = APIClient()
    bid = _create_smoked(
        client, get_token_for_user, preparer, 'people.leave_history',
        'employee_no,leave_type,start_date,end_date,days\n'
        'E1,annual,2026-01-10,2026-01-12,3\n',
        {
            'employee_no': 'employee_no', 'leave_type': 'leave_type',
            'start_date': 'start_date', 'end_date': 'end_date', 'days': 'days',
        },
    )
    first = _commit(client, committer, bid, get_token_for_user)
    assert first.status_code == 200, first.data
    assert LeaveRecord.objects.count() == 1

    replay = _commit(client, committer, bid, get_token_for_user)
    assert replay.status_code == 200
    assert LeaveRecord.objects.count() == 1


@pytest.mark.django_db
def test_commit_run_record_persists_and_is_readable(
    preparer, committer, widget_cartridge, get_token_for_user,
):
    """The run record persists and the read endpoint returns status/log/written."""
    client = APIClient()
    bid = _create_smoked(
        client, get_token_for_user, preparer, WIDGET_KEY,
        'code\nA\n', {'code': 'code'},
    )
    res = _commit(client, committer, bid, get_token_for_user)
    assert res.status_code == 200, res.data
    run = res.data['commit_run']
    assert run['status'] == InboundCommitRun.STATUS_DONE
    assert run['progress'] == 100
    assert run['written'] == 1
    assert run['reconcile'] == {'widgets': 1}
    assert run['log']

    detail = client.get(f'{PREFIX}/batches/{bid}/commit-runs/{run["id"]}/')
    assert detail.status_code == 200, detail.data
    assert detail.data['status'] == InboundCommitRun.STATUS_DONE
    assert detail.data['written'] == 1
    assert detail.data['requested_by_username'] == 'runs_cmt'
    assert detail.data['prepared_by_username'] == 'runs_prep'
    assert detail.data['committed_by_username'] == 'runs_cmt'

    listed = client.get(f'{PREFIX}/batches/{bid}/commit-runs/')
    assert listed.status_code == 200
    assert [row['id'] for row in listed.data] == [run['id']]


@pytest.mark.django_db
def test_commit_run_log_is_batched(
    monkeypatch, preparer, committer, widget_cartridge, get_token_for_user,
):
    """Log/publish lines are bounded by the batch interval, never one per row."""
    published = []
    monkeypatch.setattr(
        'ai.ops_progress.publish_op_progress_sync',
        lambda *args, **kwargs: published.append((args, kwargs)),
    )
    row_count = 500
    body = 'code\n' + ''.join(f'A{i}\n' for i in range(row_count))
    client = APIClient()
    bid = _create_smoked(
        client, get_token_for_user, preparer, WIDGET_KEY, body, {'code': 'code'},
    )
    res = _commit(client, committer, bid, get_token_for_user)
    assert res.status_code == 200, res.data
    run = res.data['commit_run']
    # At most one emit per 50 rows plus the queued/running/done bookends.
    assert len(run['log']) <= row_count // 50 + 5
    assert len(run['log']) < row_count
    # A live running frame really went out over the existing transport.
    assert any(
        args[0] == 'import' and args[2] == 'running' and kwargs.get('percent') is not None
        for args, kwargs in published
    )
    assert any(args[2] == 'done' for args, _ in published)
