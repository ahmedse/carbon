from __future__ import annotations

from django.core.files.base import ContentFile
from django.utils import timezone

from .exceptions import InboundError
from .models import InboundBatch
from .parse import parse_csv, sha256_bytes
from .permissions import can_use_kind
from . import registry


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
    raw = uploaded.read()
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
    batch.file.open('rb')
    try:
        raw = batch.file.read()
    finally:
        batch.file.close()
    parsed = parse_csv(raw, encoding=batch.encoding or None, delimiter=batch.delimiter or None)
    return parsed['rows']


# Full-row viewer bounds. The endpoint re-parses the file; it never stages rows.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _row_verdicts(batch: InboundBatch) -> dict[int, dict]:
    """Index the persisted smoke envelope by 1-based file row.

    The smoke envelope keeps a <=20 sample plus every reject, so a reject is
    always known and a clean row that fell outside the sample carries an empty
    verdict/reason. This mirrors the sample grid exactly — no second source.
    """
    smoke = batch.smoke or {}
    index: dict[int, dict] = {}
    for row in smoke.get('sample') or []:
        if isinstance(row, dict) and row.get('row') is not None:
            index[int(row['row'])] = {
                'key': row.get('key') or '',
                'verdict': row.get('verdict') or '',
                'reason': row.get('reason') or '',
            }
    for row in smoke.get('reject_rows') or []:
        if isinstance(row, dict) and row.get('row') is not None:
            index[int(row['row'])] = {
                'key': row.get('key') or '',
                'verdict': row.get('verdict') or 'reject',
                'reason': row.get('reason') or '',
            }
    return index


def batch_rows(batch: InboundBatch, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    """One read-only page of the batch file's rows.

    Reads from the same ``_all_rows`` re-parse path smoke and commit use, so no
    staging table exists and nothing is written. Per-row verdict/reason come
    from the persisted smoke envelope; a clean insert keeps ``reason == ''``.
    """
    rows = _all_rows(batch)
    verdicts = _row_verdicts(batch)
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
            'values': raw,
        })
    return {
        'results': results,
        'headers': list(batch.headers or []),
        'page': page,
        'page_size': page_size,
        'count': len(rows),
        'max_page_size': MAX_PAGE_SIZE,
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
    result = cartridge['commit'](rows, batch=batch, user=user, smoke=batch.smoke)
    batch.status = InboundBatch.STATUS_COMMITTED
    batch.committed_by = user
    batch.committed_at = timezone.now()
    smoke = dict(batch.smoke or {})
    smoke['commit'] = result or {}
    batch.smoke = smoke
    batch.save()
    return batch
