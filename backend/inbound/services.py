from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .exceptions import InboundError
from .models import InboundBatch
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
    parsed = parse_csv(raw, encoding=encoding or None)
    name = getattr(uploaded, 'name', 'upload.csv') or 'upload.csv'
    batch.file.save(name, ContentFile(raw), save=False)
    batch.original_filename = name
    batch.sha256 = sha256_bytes(raw)
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
    if batch.status == InboundBatch.STATUS_COMMITTED:
        raise InboundError('Already committed', status=409)
    if batch.status not in (InboundBatch.STATUS_MAPPED, InboundBatch.STATUS_SMOKED, InboundBatch.STATUS_FAILED):
        raise InboundError('Map required fields before smoke', status=409)
    cartridge = _cartridge(batch)
    rows = project_rows(batch, _all_rows(batch))
    envelope = cartridge['smoke'](rows, batch=batch, user=user)
    batch.smoke = envelope
    batch.status = InboundBatch.STATUS_SMOKED
    batch.save(update_fields=['smoke', 'status', 'updated_at'])
    return batch


def run_commit(batch: InboundBatch, user, *, allow_partial=False) -> InboundBatch:
    if not can_use_kind(user, batch.kind):
        raise InboundError('Not allowed for this destination kind', status=403)
    if batch.status != InboundBatch.STATUS_SMOKED:
        raise InboundError('Smoke the batch before commit', status=409)
    if batch.prepared_by_id and batch.prepared_by_id == user.id and not user.is_superuser:
        raise InboundError('Preparer cannot commit this batch', status=403)
    rejects = int((batch.smoke or {}).get('reject') or 0)
    if rejects and not allow_partial:
        raise InboundError('Rejects remain; set allow_partial to commit the rest', status=400)
    cartridge = _cartridge(batch)
    rows = project_rows(batch, _all_rows(batch))
    # A mid-loop failure in the host commit must not leave partial host state,
    # so the host write and the envelope update share one transaction.
    with transaction.atomic():
        result = cartridge['commit'](rows, batch=batch, user=user, smoke=batch.smoke)
        batch.status = InboundBatch.STATUS_COMMITTED
        batch.committed_by = user
        batch.committed_at = timezone.now()
        smoke = dict(batch.smoke or {})
        smoke['commit'] = result or {}
        batch.smoke = smoke
        batch.save()
    return batch
