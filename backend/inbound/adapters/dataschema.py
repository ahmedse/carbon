"""Data Product cartridge resolver (ADR-0060 · DMS-2).

Keys: dataschema.<table_id>
inbound is core; dataschema and importexport are core. No hosted-app imports.
"""
from __future__ import annotations

from django.utils import timezone

PREFIX = 'dataschema.'


def parse_table_id(key: str) -> int | None:
    if not key or not key.startswith(PREFIX):
        return None
    rest = key[len(PREFIX):]
    return int(rest) if rest.isdigit() else None


def _table(key: str):
    from dataschema.models import DataTable

    table_id = parse_table_id(key)
    if table_id is None:
        raise KeyError(key)
    table = DataTable.objects.filter(pk=table_id, is_archived=False).first()
    if table is None:
        raise KeyError(key)
    return table


def _field_rows(table) -> list[dict]:
    rows = []
    for field in table.fields.filter(is_active=True, is_archived=False):
        rows.append({
            'name': field.name,
            'label': field.label or field.name,
            'required': bool(field.required),
            'ref_set': getattr(field.reference_set, 'slug', None) if field.reference_set_id else None,
        })
    return rows


def _active_fields(table):
    return list(table.fields.filter(is_active=True, is_archived=False))


def _coerce_value(field, value):
    if value is None or value == '':
        return value
    if field.type == 'number':
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        text = str(value).strip()
        try:
            return int(text) if text.lstrip('-').isdigit() else float(text)
        except (TypeError, ValueError):
            return value
    if field.type == 'boolean':
        if isinstance(value, bool):
            return value
        low = str(value).strip().lower()
        if low in ('true', '1', 'yes'):
            return True
        if low in ('false', '0', 'no'):
            return False
    return value


def _coerce_rows(rows, fields) -> list[dict]:
    coerced = []
    for row in rows:
        out = dict(row)
        for field in fields:
            if field.name in out:
                out[field.name] = _coerce_value(field, out[field.name])
        coerced.append(out)
    return coerced


def smoke_table(table, rows, **_kwargs) -> dict:
    from dataschema.validators import validate_row

    fields = _active_fields(table)
    rows = _coerce_rows(rows, fields)
    insert = reject = 0
    sample = []
    reject_rows = []
    for i, row in enumerate(rows, start=1):
        errors = validate_row(row, fields)
        if errors:
            reject += 1
            reason = '; '.join(f"{e['field']}: {e['message']}" for e in errors)
            verdict = 'reject'
            reject_rows.append({'row': i, 'key': str(i), 'verdict': verdict, 'reason': reason})
        else:
            insert += 1
            verdict = 'insert'
            reason = ''
        if len(sample) < 20:
            sample.append({'row': i, 'key': str(i), 'verdict': verdict, 'reason': reason})
    return {
        'insert': insert, 'update': 0, 'skip': 0, 'reject': reject,
        'sample': sample, 'reject_rows': reject_rows,
        'reconcile_preview': {'data_rows': insert},
    }


def commit_table(table, rows, *, batch, user, smoke, **_kwargs) -> dict:
    from dataschema.models import DataRow
    from importexport.models import ImportJob

    fields = _active_fields(table)
    rows = _coerce_rows(rows, fields)
    reject_idx = {int(item['row']) for item in (smoke or {}).get('reject_rows') or []}
    written = 0
    for i, row in enumerate(rows, start=1):
        if i in reject_idx:
            continue
        DataRow.objects.create(data_table=table, values=row, created_by=user)
        written += 1
    job = ImportJob.objects.create(
        data_table=table,
        file=batch.file,
        format='csv',
        user=user,
        status='done',
        row_count=written,
        error_count=len(reject_idx),
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    return {
        'written': written,
        'import_job_id': job.id,
        'reconcile': {'data_rows': written},
    }


def resolve(key: str) -> dict:
    table = _table(key)
    return {
        'kind': 'data_product',
        'key': key,
        'label': table.title,
        'label_ar': '',
        'fields': _field_rows(table),
        'smoke': lambda rows, **kw: smoke_table(table, rows, **kw),
        'commit': lambda rows, **kw: commit_table(table, rows, **kw),
    }


def list_product_targets() -> list[dict]:
    from dataschema.models import DataTable

    rows = []
    for table in DataTable.objects.filter(is_archived=False).order_by('title', 'id'):
        key = f'{PREFIX}{table.id}'
        rows.append({
            'key': key,
            'kind': 'data_product',
            'label': table.title,
            'label_ar': '',
            'fields': _field_rows(table),
        })
    return rows
