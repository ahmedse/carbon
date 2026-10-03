from __future__ import annotations

import time

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .exceptions import InboundError
from .models import InboundBatch, InboundCommitRun
from .parse import parse_csv, sha256_bytes
from .permissions import can_use_kind
from . import registry

# Bounded upload: the whole CSV is decoded in memory, so cap the bytes we read
# and reject anything larger before parsing. 25 MB is far beyond a People CSV.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _cartridge(batch: InboundBatch) -> dict:
    try:
        item = registry.get(batch.target_key)
    except KeyError as exc:
        raise InboundError(f'Unknown target {batch.target_key}', status=400) from exc
    if item.get('enabled') is False:
        raise InboundError('Cartridge is disabled', status=400)
    if item['kind'] != batch.kind:
        raise InboundError('Target kind does not match batch kind', status=400)
    return item


def create_batch(*, kind: str, target_key: str, user) -> InboundBatch:
    if not can_use_kind(user, kind):
        raise InboundError('Not allowed for this destination kind', status=403)
    try:
        item = registry.get(target_key)
    except KeyError as exc:
        from .models import InboundCartridge
        if InboundCartridge.objects.filter(key=target_key).exists():
            raise InboundError(
                'Cartridge has no handler yet. The owning app must register smoke and commit.',
                status=400,
            ) from exc
        raise InboundError(f'Unknown target {target_key}', status=400) from exc
    if item.get('enabled') is False:
        raise InboundError('Cartridge is disabled', status=400)
    if item['kind'] != kind:
        raise InboundError('kind does not match target', status=400)
    return InboundBatch.objects.create(
        kind=kind,
        target_key=target_key,
        prepared_by=user,
        prepared_at=timezone.now(),
    )


def attach_file(batch: InboundBatch, uploaded, encoding: str | None = None) -> InboundBatch:
    if batch.status == InboundBatch.STATUS_COMMITTED:
        raise InboundError('Committed batch cannot take a new file', status=409)
    # Read at most the cap + 1 byte so a huge upload cannot exhaust memory.
    raw = uploaded.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise InboundError(
            f'File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit',
            status=413,
        )
    digest = sha256_bytes(raw)
    # Storage idempotency: the exact same bytes are already stored on this
    # uncommitted batch (a re-submit / client retry), so do not write a second
    # storage object or re-derive the parse. Return the batch unchanged.
    if batch.sha256 and batch.sha256 == digest and batch.file:
        return batch
    parsed = parse_csv(raw, encoding=encoding or None)
    name = getattr(uploaded, 'name', 'upload.csv') or 'upload.csv'
    batch.file.save(name, ContentFile(raw), save=False)
    batch.original_filename = name
    batch.sha256 = digest
    batch.encoding = parsed['encoding']
    batch.delimiter = parsed['delimiter']
    batch.headers = parsed['headers']
    batch.sample = parsed['sample']
    batch.row_count = parsed['row_count']
    batch.status = InboundBatch.STATUS_DRAFT
    batch.smoke = {}
    batch.save()
    return batch


def _all_rows(batch: InboundBatch) -> list[dict]:
    if not batch.file:
        raise InboundError('No file on this batch', status=400)
    try:
        batch.file.open('rb')
        try:
            raw = batch.file.read()
        finally:
            batch.file.close()
    except FileNotFoundError as exc:
        raise InboundError('The stored file for this batch is missing on the server', status=400) from exc
    except OSError as exc:
        raise InboundError('The stored file for this batch could not be read', status=400) from exc
    parsed = parse_csv(raw, encoding=batch.encoding or None, delimiter=batch.delimiter or None)
    return parsed['rows']


# Full-row viewer bounds. The endpoint re-parses the file; it never stages rows.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _merge_verdict(index: dict[int, dict], entry) -> None:
    """Merge one persisted per-row entry, keeping the richest fields.

    ``results`` (full), ``reject_rows`` (every reject) and ``sample`` (<=20) all
    carry the same shape. A legacy or capped entry without ``issues`` must not
    erase structured issues an earlier source already provided.
    """
    if not isinstance(entry, dict) or entry.get('row') is None:
        return
    try:
        row_no = int(entry['row'])
    except (TypeError, ValueError):
        return
    current = index.get(row_no) or {'key': '', 'verdict': '', 'reason': '', 'issues': []}
    if entry.get('key'):
        current['key'] = entry['key']
    if entry.get('verdict'):
        current['verdict'] = entry['verdict']
    if entry.get('reason'):
        current['reason'] = entry['reason']
    issues = entry.get('issues')
    if isinstance(issues, list) and issues:
        current['issues'] = issues
    index[row_no] = current


def _row_verdicts(batch: InboundBatch) -> dict[int, dict]:
    """Index the persisted smoke envelope by 1-based file row.

    ``results`` (the full per-row list) is the primary source; the <=20 sample
    and every reject are merged for older envelopes that predate ``results``.
    A row with no persisted entry stays absent — the viewer shows "not recorded"
    rather than guessing a pass.
    """
    smoke = batch.smoke or {}
    index: dict[int, dict] = {}
    for row in smoke.get('sample') or []:
        _merge_verdict(index, row)
    for row in smoke.get('results') or []:
        _merge_verdict(index, row)
    for row in smoke.get('reject_rows') or []:
        _merge_verdict(index, row)
    return index


def batch_rows(batch: InboundBatch, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    """One read-only page of the batch file's rows.

    Reads from the same ``_all_rows`` re-parse path smoke and commit use, so no
    staging table exists and nothing is written. Per-row verdict/reason/issues
    come from the persisted smoke envelope; a clean insert keeps ``reason == ''``.
    ``smoked`` is false before the first smoke, so the viewer never shows a
    clean pass for an unsmoked batch.
    """
    rows = _all_rows(batch)
    verdicts = _row_verdicts(batch)
    smoked = bool(batch.smoke)
    start = (page - 1) * page_size
    end = start + page_size
    results = []
    for offset, raw in enumerate(rows[start:end], start=start + 1):
        hit = verdicts.get(offset) or {}
        results.append({
            'row': offset,
            'key': hit.get('key', ''),
            'verdict': hit.get('verdict', ''),
            'reason': hit.get('reason', ''),
            'issues': hit.get('issues', []),
            'values': raw,
        })
    return {
        'results': results,
        'headers': list(batch.headers or []),
        'page': page,
        'page_size': page_size,
        'count': len(rows),
        'max_page_size': MAX_PAGE_SIZE,
        'smoked': smoked,
    }


def save_mapping(batch: InboundBatch, mapping: dict) -> InboundBatch:
    if batch.status == InboundBatch.STATUS_COMMITTED:
        raise InboundError('Committed batch cannot be remapped', status=409)
    columns = mapping.get('columns') or {}
    if not isinstance(columns, dict):
        raise InboundError('mapping.columns must be an object', status=400)
    cartridge = _cartridge(batch)
    required = [f['name'] for f in cartridge['fields'] if f.get('required')]
    mapped_targets = {tgt for tgt in columns.values() if tgt}
    missing = [name for name in required if name not in mapped_targets]
    batch.mapping = {
        'columns': columns,
        'crosswalks': mapping.get('crosswalks') or {},
    }
    if missing:
        batch.status = InboundBatch.STATUS_DRAFT
        batch.save(update_fields=['mapping', 'status', 'updated_at'])
        raise InboundError(f'Required fields unmapped: {", ".join(missing)}', status=400)
    batch.status = InboundBatch.STATUS_MAPPED
    batch.smoke = {}
    batch.save(update_fields=['mapping', 'status', 'smoke', 'updated_at'])
    return batch


def project_rows(batch: InboundBatch, rows: list[dict]) -> list[dict]:
    columns = (batch.mapping or {}).get('columns') or {}
    crosswalks = (batch.mapping or {}).get('crosswalks') or {}
    projected = []
    for row in rows:
        out = {}
        for src, tgt in columns.items():
            if not tgt:
                continue
            value = row.get(src, '')
            walk = crosswalks.get(tgt) or {}
            if value in walk:
                value = walk[value]
            out[tgt] = value
        projected.append(out)
    return projected


def run_smoke(batch: InboundBatch, user) -> InboundBatch:
    # Same destination-kind gate as create_batch/run_commit: a product steward
    # must not smoke a typed People batch (and vice versa).
    if not can_use_kind(user, batch.kind):
        raise InboundError('Not allowed for this destination kind', status=403)
    # Hold the batch row lock for the whole smoke so a smoke cannot interleave a
    # commit (and vice versa): the status is re-read under the lock, not from the
    # caller's stale snapshot. A concurrent commit wins and this raises 409.
    with transaction.atomic():
        locked = InboundBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status == InboundBatch.STATUS_COMMITTED:
            raise InboundError('Already committed', status=409)
        if locked.status not in (InboundBatch.STATUS_MAPPED, InboundBatch.STATUS_SMOKED, InboundBatch.STATUS_FAILED):
            raise InboundError('Map required fields before smoke', status=409)
        cartridge = _cartridge(locked)
        rows = project_rows(locked, _all_rows(locked))
        envelope = cartridge['smoke'](rows, batch=locked, user=user)
        locked.smoke = envelope
        locked.status = InboundBatch.STATUS_SMOKED
        locked.save(update_fields=['smoke', 'status', 'updated_at'])
    return locked


# Commit progress is emitted in bounded batches, never per row, so a 50k-row
# batch cannot flood the SSE stream with one frame per row.
COMMIT_PROGRESS_ROWS = 50
COMMIT_PROGRESS_SECONDS = 1.0


class CommitRunError(InboundError):
    """An ``InboundError`` raised inside a commit run, carrying the failed run.

    The view returns the run so a reloaded client can still recover the outcome
    (the durable run record persists regardless of the request outcome).
    """

    def __init__(self, message: str, status: int, run: InboundCommitRun):
        super().__init__(message, status=status)
        self.run = run


def _publish_run(run: InboundCommitRun, status: str, message: str, percent: int | None) -> None:
    """Publish one OUTCOME-shaped frame for this run on the existing transport."""
    from ai.ops_progress import publish_op_progress_sync

    publish_op_progress_sync(
        'import', run.id, status, message,
        percent=percent, host_user_id=run.requested_by_id,
    )


def _append_run_log(run: InboundCommitRun, message: str, percent: int | None, *, save: bool = True) -> None:
    run.log = list(run.log or []) + [{
        't': timezone.now().isoformat(),
        'message': message,
        'percent': percent,
    }]
    if save:
        run.save(update_fields=['log', 'updated_at'])


class _CommitRunReporter:
    """Batched progress reporter for one commit run.

    The cartridge calls ``advance(index, written)`` once per projected row; this
    object only persists + publishes when ~50 rows or ~1 second have passed, so
    the durable log stays bounded and the SSE stream is not flooded.
    """

    def __init__(self, run: InboundCommitRun, total: int):
        self.run = run
        self.total = max(0, int(total or 0))
        self._last_index = 0
        self._last_at = time.monotonic()

    def advance(self, index: int, written: int) -> None:
        now = time.monotonic()
        if (
            self.total
            and (index - self._last_index) < COMMIT_PROGRESS_ROWS
            and (now - self._last_at) < COMMIT_PROGRESS_SECONDS
        ):
            return
        self._emit(index, written, now)

    def _emit(self, index: int, written: int, now: float) -> None:
        percent = 100 if not self.total else min(99, int(round(index * 100 / self.total)))
        message = (
            f'Committing row {index} of {self.total}…'
            if self.total else 'Committing accepted rows…'
        )
        self.run.progress = percent
        _append_run_log(self.run, message, percent)
        _publish_run(self.run, 'running', message, percent)
        self._last_index = index
        self._last_at = now


def _finish_commit_run(run: InboundCommitRun, batch: InboundBatch) -> None:
    result = (batch.smoke or {}).get('commit') or {}
    run.status = InboundCommitRun.STATUS_DONE
    run.progress = 100
    run.written = int(result.get('written') or 0)
    run.reconcile = result.get('reconcile') or {}
    run.error = ''
    run.finished_at = timezone.now()
    _append_run_log(run, f'Committed {run.written} row(s).', 100, save=False)
    run.save()
    _publish_run(run, 'done', f'Committed {run.written} row(s).', 100)


def _fail_commit_run(run: InboundCommitRun, exc: InboundError) -> None:
    run.status = InboundCommitRun.STATUS_FAILED
    run.error = exc.message
    run.finished_at = timezone.now()
    _append_run_log(run, exc.message, run.progress or None, save=False)
    run.save()
    _publish_run(run, 'failed', exc.message, run.progress or None)


def start_commit_run(batch: InboundBatch, user, *, allow_partial=False):
    """Create (or replay) a durable commit run and execute it synchronously.

    Returns ``(batch, run)``. The first commit on a batch records a run and
    performs the one host write. A later commit on the same batch is an
    idempotent replay: the existing run is returned and no host write happens.
    """
    if batch.status == InboundBatch.STATUS_COMMITTED:
        prior = batch.commit_runs.select_related('requested_by').order_by('-id').first()
        if prior is not None:
            return batch, prior
        # Committed before the run ledger existed: record the prior result once.
        prior = InboundCommitRun.objects.create(
            batch=batch, status=InboundCommitRun.STATUS_DONE, progress=100,
            requested_by=user, started_at=timezone.now(), finished_at=timezone.now(),
        )
        _finish_commit_run(prior, batch)
        return batch, prior

    run = InboundCommitRun.objects.create(
        batch=batch, status=InboundCommitRun.STATUS_QUEUED, progress=0,
        requested_by=user, started_at=timezone.now(),
    )
    _append_run_log(run, 'Commit queued.', 0, save=False)
    run.save(update_fields=['log', 'started_at', 'updated_at'])
    _publish_run(run, 'queued', 'Commit queued.', 0)
    run.status = InboundCommitRun.STATUS_RUNNING
    run.save(update_fields=['status', 'updated_at'])
    _publish_run(run, 'running', 'Committing accepted rows…', 0)
    try:
        batch = run_commit(batch, user, allow_partial=allow_partial, run=run)
    except InboundError as exc:
        _fail_commit_run(run, exc)
        raise CommitRunError(exc.message, exc.status, run) from exc
    _finish_commit_run(run, batch)
    return batch, run


def run_commit(batch: InboundBatch, user, *, allow_partial=False, run=None) -> InboundBatch:
    """Commit a smoked batch, exactly once.

    The status guard, the host write and the status flip share ONE
    ``transaction.atomic()`` that begins by locking the batch row
    (``select_for_update``) and re-reads its status INSIDE the lock. A second
    concurrent (or repeated) commit therefore cannot interleave: it waits, sees
    ``committed`` and returns the prior result instead of writing again.

    The smoke-first 409, the SoD preparer≠committer 403 and the
    rejects-without-``allow_partial`` 400 keep the same status codes and
    conditions; they are evaluated against the freshly-locked row.
    """
    if not can_use_kind(user, batch.kind):
        raise InboundError('Not allowed for this destination kind', status=403)
    with transaction.atomic():
        locked = InboundBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status == InboundBatch.STATUS_COMMITTED:
            # Idempotent replay: the prior result is already durable in
            # ``locked.smoke['commit']``. Return it; write nothing.
            return locked
        if locked.status != InboundBatch.STATUS_SMOKED:
            raise InboundError('Smoke the batch before commit', status=409)
        if locked.prepared_by_id and locked.prepared_by_id == user.id and not user.is_superuser:
            raise InboundError('Preparer cannot commit this batch', status=403)
        rejects = int((locked.smoke or {}).get('reject') or 0)
        if rejects and not allow_partial:
            raise InboundError('Rejects remain; set allow_partial to commit the rest', status=400)
        cartridge = _cartridge(locked)
        rows = project_rows(locked, _all_rows(locked))
        progress = _CommitRunReporter(run, len(rows)).advance if run is not None else None
        # A mid-loop failure in the host commit must not leave partial host state,
        # so the host write and the envelope update share this transaction.
        result = cartridge['commit'](
            rows, batch=locked, user=user, smoke=locked.smoke, progress=progress,
        )
        locked.status = InboundBatch.STATUS_COMMITTED
        locked.committed_by = user
        locked.committed_at = timezone.now()
        smoke = dict(locked.smoke or {})
        smoke['commit'] = result or {}
        locked.smoke = smoke
        locked.save()
    return locked
