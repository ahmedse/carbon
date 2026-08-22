"""
catalog/dataset_ingest.py — ingest pipeline for the Dataset Hub (trust core; moved from datahub).

Pipeline (design §5.5):
  1. Accept raw rows (ERP snapshot, CSV upload, or API payload).
  2. Materialize them into dataschema (new DataTable + DataFields + DataRows)
     — reuses the existing storage layer; governance rows never duplicated here.
  3. Capture a schema_snapshot from the created DataFields.
  4. Compute health_detail {completeness, validity, freshness} and
     health_score = 0.4·completeness + 0.4·validity + 0.2·freshness.
  5. Run DQ through the existing seam (dq.jobs.create_job + execute) and store
     the DQJob id on the version.
  6. Create the DatasetVersion (status='pending').
  7. Evaluate the dataset's DataContract → DataContractViolation per breach.
  8. If the contract is clean AND auto_approve is on → approve (sets
     dataset.current_version). Otherwise stay 'pending' for manual review.
"""
import csv
import hashlib
import io
import json
import logging
import re

from django.utils import text as text_utils
from django.utils import timezone

from dataschema.models import DataField, DataRow, DataTable
from dq.jobs import create_job, execute as execute_job

from .models import DatasetVersion, DatasetVersionMember
from .dataset_services import approve_version, check_contract, gate_validity, mirror_health_to_catalog

logger = logging.getLogger(__name__)

# Health formula weights (design §5.6)
W_COMPLETENESS = 0.4
W_VALIDITY = 0.4
W_FRESHNESS = 0.2

MAX_TABLE_NAME = 64  # dataschema.DataTable.name SlugField(max_length=64)
FIELD_TYPE_MAP = {
    'text': 'text',
    'string': 'string',
    'number': 'number',
    'date': 'date',
    'boolean': 'boolean',
}


def _infer_field_type(value):
    """Best-effort type inference for a raw column value."""
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 'number'
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?', s):
            return 'date'
        if s.lower() in {'true', 'false', 'yes', 'no', '1', '0'}:
            return 'boolean'
        return 'string'
    return 'string'


def _normalize_name(value):
    """Slugify + shorten to the dataschema name limit."""
    return text_utils.slugify(value)[:MAX_TABLE_NAME]


def row_hash_of(values) -> str:
    """Stable content hash for dedup — canonical JSON of normalized values.

    Normalization must match DataRow.save(): keys lowercased. Used by
    write_rows (inserts) and the ingest watermark (skip already-ingested rows).
    """
    normalized = {str(k).lower(): v for k, v in (values or {}).items()}
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(',', ':'),
                   default=str).encode('utf-8')
    ).hexdigest()


def create_data_table(dataset, columns, version_number, user=None) -> DataTable:
    """Create the dataschema.DataTable + DataFields backing a dataset version."""
    table_name = _normalize_name(f"{dataset.slug}_v{version_number}")
    table = DataTable.objects.create(
        name=table_name,
        title=f"{dataset.name} — Version {version_number}",
        module=dataset.module,
    )
    for order, col in enumerate(columns, start=1):
        field_name = text_utils.slugify(str(col['name'])).replace('-', '_')
        field_name = (field_name or f'field_{order}')[:50]
        DataField.objects.create(
            data_table=table,
            name=field_name,
            label=str(col.get('label') or col['name'])[:100],
            type=col.get('type') or _infer_field_type(col.get('sample')),
            order=order,
            required=bool(col.get('required', False)),
        )
    return table


def write_rows(table, rows, user=None, *, skip_hashes=None) -> int:
    """Bulk-create DataRows (keyed by lowercased normalized field name).

    Returns the number of rows actually inserted. When ``skip_hashes`` is a
    set of content hashes already materialized, rows matching a stored hash
    are skipped — the incremental (watermark) re-run dedup path. Duplicates
    within the incoming batch are also skipped.
    """
    fields = list(table.fields.order_by('order'))
    field_names = [f.name for f in fields]
    now = timezone.now()
    skip_hashes = skip_hashes or set()
    seen = set()
    payloads = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = {}
        for name in field_names:
            values[name] = row.get(name, row.get(name.title(), ''))
        row_hash = row_hash_of(values)
        if row_hash in skip_hashes or row_hash in seen:
            continue
        seen.add(row_hash)
        payloads.append(DataRow(
            data_table=table,
            values=values,
            row_hash=row_hash,
            is_archived=False,
            version=1,
        ))
    DataRow.objects.bulk_create(payloads, batch_size=500)
    return len(payloads)


def schema_snapshot_from_table(table) -> dict:
    return {
        f.name: {'type': f.type, 'required': f.required, 'label': f.label}
        for f in table.fields.order_by('order')
    }


def compute_health(table, rows, validity, contract=None) -> dict:
    """Health dimensions per design §5.5/§5.6.

    ``rows`` is the list of RAW row dicts (already normalized, lowercased keys).

    completeness = 1 - (null cells / total cells)
    validity     = DQ gate pass rate (passed / total verdicts)
    freshness    = 1.0 if data age <= freshness_hours (or no SLA), else 0.0
    health_score = 0.4·completeness + 0.4·validity + 0.2·freshness
    """
    total_cells = len(rows) * table.fields.count()
    null_cells = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in table.fields.all():
            if row.get(field.name) in (None, ''):
                null_cells += 1
    completeness = 1.0 if total_cells == 0 else round(1 - (null_cells / total_cells), 4)

    # Freshness: 1.0 unless the dataset's contract imposes a data-age SLA that
    # the ingested payload already violates (rows are new at ingest → 1.0).
    freshness = 1.0
    if contract and contract.freshness_hours:
        latest = table.rows.order_by('-created_at').values_list('created_at', flat=True).first()
        if latest:
            age_hours = (timezone.now() - latest).total_seconds() / 3600.0
            if age_hours > contract.freshness_hours:
                freshness = 0.0

    health_score = round(
        W_COMPLETENESS * completeness
        + W_VALIDITY * validity
        + W_FRESHNESS * freshness,
        4,
    )
    return {
        'completeness': completeness,
        'validity': validity,
        'freshness': freshness,
        'health_score': health_score,
    }


def create_version(dataset, tables, *, source_type, source_ref, user=None,
                   auto_approve=False, contract=None, labels=None) -> DatasetVersion:
    """Core pipeline: table(s) → DQ → health → DatasetVersion → contract → (approve).

    ``tables`` may be a single ``DataTable`` (back-compat) or a list of
    ``DataTable`` instances (multi-table composition). Each table gets its own
    ``DatasetVersionMember`` with per-table health/schema/DQ; the version-level
    aggregates are the union/mean across members.
    """
    if isinstance(tables, DataTable):
        tables = [tables]
    if not tables:
        raise ValueError('create_version requires at least one table.')
    labels = labels or {}

    # Per-table: DQ job + gate validity + compute health → one member each.
    member_data = []
    total_rows = 0
    merged_schema = {}
    merged_health = {'completeness': [], 'validity': [], 'freshness': []}
    member_health_scores = []
    last_dq_job_id = ''

    for order, table in enumerate(tables):
        rows = list(table.rows.filter(is_archived=False))
        # The gate + health math operate on raw dicts, not DataRow instances.
        raw_rows = [row.values for row in rows]
        validity = gate_validity(table, raw_rows)
        health = compute_health(table, raw_rows, validity, contract=contract)

        # DQ via the existing seam: create a profile job and execute it inline.
        dq_job_id = ''
        try:
            dq_job = create_job('profile', table=table, user=user)
            executed = execute_job(dq_job)
            dq_job_id = str(getattr(executed, 'pk', '') or '')
        except Exception:  # pragma: no cover — DQ must never break ingest
            logger.exception('DQ job failed during ingest for table %s', table.pk)
        last_dq_job_id = dq_job_id

        member_data.append({
            'table': table,
            'order': order,
            'row_count': len(rows),
            'schema_snapshot': schema_snapshot_from_table(table),
            'health_score': health['health_score'],
            'health_detail': {
                'completeness': health['completeness'],
                'validity': health['validity'],
                'freshness': health['freshness'],
            },
            'dq_job_id': dq_job_id,
            'label': labels.get(table.pk, ''),
        })

        total_rows += len(rows)
        for name, spec in (member_data[-1]['schema_snapshot'] or {}).items():
            merged_schema.setdefault(name, spec)
        merged_health['completeness'].append(health['completeness'])
        merged_health['validity'].append(health['validity'])
        merged_health['freshness'].append(health['freshness'])
        if health['health_score'] is not None:
            member_health_scores.append(health['health_score'])

    # Version-level aggregates across members (plain mean — deliberate simplification).
    def _mean(values, default=None):
        return round(sum(values) / len(values), 4) if values else default
    version_health_score = _mean(member_health_scores)
    version_health_detail = {
        'completeness': _mean(merged_health['completeness']),
        'validity': _mean(merged_health['validity']),
        'freshness': _mean(merged_health['freshness']),
    }

    next_number = (
        DatasetVersion.objects.filter(dataset=dataset)
        .order_by('-version_number').values_list('version_number', flat=True).first()
        or 0
    ) + 1

    version = DatasetVersion.objects.create(
        dataset=dataset,
        version_number=next_number,
        data_table=tables[0],
        row_count=total_rows,
        schema_snapshot=merged_schema,
        health_score=version_health_score,
        health_detail=version_health_detail,
        dq_job_id=last_dq_job_id,
        lineage={
            'source': {'type': source_type, 'ref': source_ref or ''},
            'upstream_version_ids': [],
            'transforms': [],
        },
        status='pending',
        created_by=user if user and user.is_authenticated else None,
    )

    for md in member_data:
        DatasetVersionMember.objects.create(
            version=version,
            data_table=md['table'],
            order=md['order'],
            label=md['label'],
            row_count=md['row_count'],
            schema_snapshot=md['schema_snapshot'],
            health_score=md['health_score'],
            health_detail=md['health_detail'],
            dq_job_id=md['dq_job_id'],
        )

    # Mirror health into the catalog.
    if user and user.is_authenticated:
        mirror_health_to_catalog(version, user=user)
    else:
        mirror_health_to_catalog(version)

    # Contract evaluation.
    if contract is None:
        from .models import DataContract
        contract = DataContract.objects.filter(
            dataset=dataset, is_active=True,
        ).first()
    violations = check_contract(version, contract=contract)

    # Auto-approve only when the contract (if any) is fully satisfied.
    if auto_approve and not violations and user and user.is_authenticated:
        approve_version(version, user)

    return version


def create_version_from_tables(dataset, table_specs, *, source_type, source_ref,
                               user=None, auto_approve=False, contract=None) -> DatasetVersion:
    """Convenience multi-table compose: each spec is either
    {'table': DataTable} or {'columns': [...], 'rows': [...], 'label': '...'}.
    Column/row specs are materialized via the existing create_data_table +
    write_rows helpers, then all tables flow through create_version.
    """
    tables = []
    labels = {}
    next_number = (
        DatasetVersion.objects.filter(dataset=dataset)
        .order_by('-version_number').values_list('version_number', flat=True).first()
        or 0
    ) + 1
    for spec in table_specs:
        if 'table' in spec:
            tables.append(spec['table'])
        else:
            table = create_data_table(dataset, spec['columns'], next_number, user=user)
            write_rows(table, spec['rows'], user=user)
            tables.append(table)
            if spec.get('label'):
                labels[table.pk] = spec['label']
    return create_version(
        dataset, tables, source_type=source_type, source_ref=source_ref,
        user=user, auto_approve=auto_approve, contract=contract, labels=labels,
    )


def ingest_rows(dataset, columns, rows, *, source_type, source_ref,
                user=None, auto_approve=False, since_id=0) -> DatasetVersion:
    """Ingest from an already-normalized payload of rows.

    ``columns`` is a list of {name, label?, type?, required?, sample?}.
    ``rows`` is a list of dicts keyed by column name.

    ``since_id`` is the MaterializationCheckpoint watermark. 0 / falsy = full
    re-materialization into a fresh per-version table. > 0 = incremental:
    reuse the dataset's latest materialized table and append only rows whose
    content hash is not already stored there; if nothing is new, the current
    version is returned unchanged (no duplicate version / duplicate rows).
    """
    from .models import DataContract
    contract = DataContract.objects.filter(dataset=dataset, is_active=True).first()
    next_number = (
        DatasetVersion.objects.filter(dataset=dataset)
        .order_by('-version_number').values_list('version_number', flat=True).first()
        or 0
    ) + 1
    table, skip_hashes = _resolve_ingest_table(dataset, columns, next_number, since_id)
    inserted = write_rows(table, rows, user=user, skip_hashes=skip_hashes)
    if inserted == 0 and since_id > 0:
        # Re-run of an unchanged extract — nothing new to materialize.
        # Return the current version instead of creating a duplicate.
        latest = (
            DatasetVersion.objects.filter(dataset=dataset)
            .order_by('-version_number').first()
        )
        if latest is not None:
            return latest
    return create_version(
        dataset, table, source_type=source_type, source_ref=source_ref,
        user=user, auto_approve=auto_approve, contract=contract,
    )


def _resolve_ingest_table(dataset, columns, next_number, since_id):
    """Return (table, skip_hashes) for this ingest run.

    - since_id == 0 (full): fresh per-version table, no dedup.
    - since_id > 0 (incremental): reuse the dataset's latest materialized
      table (when the incoming schema still fits) and skip rows whose content
      hash is already stored there.
    """
    if since_id <= 0:
        return create_data_table(dataset, columns, next_number), None
    latest_id = (
        DatasetVersion.objects.filter(dataset=dataset)
        .exclude(data_table__isnull=True)
        .order_by('-version_number')
        .values_list('data_table_id', flat=True)
        .first()
    )
    if latest_id is None:
        return create_data_table(dataset, columns, next_number), None
    table = DataTable.objects.get(pk=latest_id)
    existing_fields = {f.name for f in table.fields.all()}
    incoming_fields = {
        (text_utils.slugify(str(c['name'])).replace('-', '_') or f'field_{i}')[:50]
        for i, c in enumerate(columns, start=1)
    }
    if not incoming_fields.issubset(existing_fields):
        # Schema drift since the last run — fall back to a fresh table.
        return create_data_table(dataset, columns, next_number), None
    existing_hashes = set(
        DataRow.objects.filter(data_table=table)
        .exclude(row_hash='')
        .values_list('row_hash', flat=True)
    )
    return table, existing_hashes


def ingest_erp(dataset, rows, *, source_ref='', user=None, auto_approve=False,
               since_id=0) -> DatasetVersion:
    """ERP snapshot ingest. ``rows`` = list of dicts from the ERP view."""
    if not rows:
        raise ValueError('ERP snapshot contains no rows.')
    columns = _columns_from_rows(rows)
    return ingest_rows(
        dataset, columns, rows,
        source_type='erp_snapshot', source_ref=source_ref or 'erp',
        user=user, auto_approve=auto_approve, since_id=since_id,
    )


def ingest_csv(dataset, file, *, user=None, auto_approve=False) -> DatasetVersion:
    """CSV upload ingest. ``file`` is a file-like object or bytes."""
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError('CSV contains no data rows.')
    columns = _columns_from_rows(rows)
    return ingest_rows(
        dataset, columns, rows,
        source_type='csv_upload', source_ref=getattr(file, 'name', '') or 'upload.csv',
        user=user, auto_approve=auto_approve,
    )


def _columns_from_rows(rows) -> list:
    """Derive column descriptors from the first data row (best-effort)."""
    first = rows[0]
    columns = []
    for name, value in first.items():
        columns.append({
            'name': name,
            'label': name,
            'type': _infer_field_type(value),
            'required': False,
            'sample': value,
        })
    return columns
