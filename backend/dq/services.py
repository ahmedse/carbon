# dq/services.py
import logging
import time
from statistics import mean
from django.db.models import Q
from django.utils import timezone
from dataschema.models import DataTable, DataRow, DataField
from catalog.models import AssetProfile, GovernanceEvent
from .models import TableProfile, FieldProfile, DQRule, DQResult
from .models import FreshnessCheck, DQProfileConfig, SchemaSnapshot, SchemaChange
from core.utils import retry_on_db_error

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger('dq.performance')

CHUNK_SIZE = 5000


def _rows(table, chunk=False):
    """Return DataRows for a table. If chunk=True yield lists of CHUNK_SIZE."""
    qs = DataRow.objects.filter(data_table=table, is_archived=False)
    if not chunk:
        count = qs.count()
        if count > 10000:
            perf_logger.warning(
                'Loading large dataset without chunking',
                extra={'structured': {
                    'event': 'dq_rows_large_load',
                    'table_id': table.id,
                    'row_count': count,
                    'warning': 'Consider enabling chunking for datasets > 10k rows'
                }}
            )
        return list(qs)
    total = qs.count()
    if total <= CHUNK_SIZE:
        return list(qs)
    # return chunked generator as flat list (synchronous; Celery deferred)
    rows = []
    offset = 0
    while offset < total:
        chunk_batch = list(qs[offset: offset + CHUNK_SIZE])
        rows.extend(chunk_batch)
        offset += CHUNK_SIZE
        # Log progress for very large datasets
        if total > 50000 and offset % (CHUNK_SIZE * 5) == 0:
            progress_pct = round((offset / total) * 100, 1)
            perf_logger.info(
                f'Chunked load progress: {progress_pct}%',
                extra={'structured': {
                    'event': 'dq_rows_chunk_progress',
                    'table_id': table.id,
                    'offset': offset,
                    'total': total,
                    'progress_pct': progress_pct
                }}
            )
    return rows


def _is_empty(v):
    return v is None or v == '' or v == []


@retry_on_db_error(max_retries=3)
def profile_table(table_id):
    """Profile table metrics with retry logic and chunked processing for large tables."""
    start_time = time.time()
    table = DataTable.objects.get(id=table_id)
    
    # Determine if chunked processing is needed
    row_count = DataRow.objects.filter(data_table=table, is_archived=False).count()
    use_chunks = row_count > 10000
    
    if use_chunks:
        logger.info(
            f"Using chunked processing for table {table_id}",
            extra={
                "table_id": table_id,
                "row_count": row_count,
                "use_chunks": True,
            }
        )
    
    rows = _rows(table, chunk=use_chunks)
    n = len(rows)
    
    # Warn on large datasets
    if n > 50000:
        perf_logger.warning(
            'Large dataset profiling initiated',
            extra={'structured': {
                'event': 'dq_profile_large_dataset',
                'table_id': table_id,
                'row_count': n,
                'warning': 'Dataset exceeds 50k rows - consider async processing'
            }}
        )
    
    fields = list(table.fields.filter(is_active=True, is_archived=False))
    completeness_all = []
    field_profile_data = []
    # Collect per-column stats for TableProfile summary JSON fields
    null_counts_dict = {}
    distinct_counts_dict = {}
    min_values_dict = {}
    max_values_dict = {}
    mean_values_dict = {}

    # Clean up old field profiles before creating new ones
    FieldProfile.objects.filter(data_field__data_table=table).delete()
    
    for f in fields:
        field_start = time.time()
        vals = [r.values.get(f.name) for r in rows]
        non_empty = [v for v in vals if not _is_empty(v)]
        null_count = n - len(non_empty)
        distinct = len({str(v) for v in non_empty})
        completeness = (len(non_empty) / n * 100) if n else 0.0
        uniqueness = (distinct / len(non_empty) * 100) if non_empty else 0.0
        completeness_all.append(completeness)
        minv = maxv = ''
        meanv = None
        if f.type == 'number':
            nums = []
            for v in non_empty:
                try:
                    nums.append(float(v))
                except (TypeError, ValueError):
                    pass
            if nums:
                minv, maxv, meanv = str(min(nums)), str(max(nums)), mean(nums)
        # Collect for TableProfile summary JSON
        null_counts_dict[f.name] = null_count
        distinct_counts_dict[f.name] = distinct
        min_values_dict[f.name] = minv if minv != '' else None
        max_values_dict[f.name] = maxv if maxv != '' else None
        mean_values_dict[f.name] = meanv
        counts = {}
        for v in non_empty:
            k = str(v)
            counts[k] = counts.get(k, 0) + 1
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
        fp = FieldProfile.objects.create(
            data_field=f, row_count=n, null_count=null_count, distinct_count=distinct,
            completeness_pct=round(completeness, 2), uniqueness_pct=round(uniqueness, 2),
            min_value=minv, max_value=maxv, mean_value=meanv,
            top_values=[{'value': k, 'count': c} for k, c in top],
        )
        field_profile_data.append({
            'field_id': f.id,
            'field_name': f.name,
            'completeness_pct': fp.completeness_pct,
            'distinct_count': distinct,
            'top_values': fp.top_values,
        })
        
        field_duration_ms = (time.time() - field_start) * 1000
        if field_duration_ms > 1000:  # Warn on slow field profiling
            perf_logger.warning(
                'Slow field profiling',
                extra={'structured': {
                    'event': 'dq_profile_field_slow',
                    'table_id': table_id,
                    'field_id': f.id,
                    'field_name': f.name,
                    'duration_ms': round(field_duration_ms, 2),
                    'row_count': n
                }}
            )
    
    table_completeness = round(mean(completeness_all), 2) if completeness_all else 0.0
    # Deduplicate stale profiles (legacy runs created duplicates), then update
    # or create the single latest row. update_or_create() calls get() internally
    # and raises MultipleObjectsReturned if duplicates exist.
    from django.utils import timezone
    stale_ids = list(
        TableProfile.objects.filter(data_table=table)
        .order_by('-profiled_at').values_list('id', flat=True)[1:]
    )
    if stale_ids:
        TableProfile.objects.filter(id__in=stale_ids).delete()
    tp, _created = TableProfile.objects.update_or_create(
        data_table=table,
        defaults={
            'row_count': n,
            'completeness_pct': table_completeness,
            'null_counts': null_counts_dict,
            'distinct_counts': distinct_counts_dict,
            'min_values': min_values_dict,
            'max_values': max_values_dict,
            'mean_values': mean_values_dict,
            'profiled_at': timezone.now(),
        },
    )
    
    total_duration_ms = (time.time() - start_time) * 1000
    perf_logger.info(
        'Table profiling completed',
        extra={'structured': {
            'event': 'dq_profile_complete',
            'table_id': table.id,
            'rows_profiled': n,
            'fields_profiled': len(fields),
            'duration_ms': round(total_duration_ms, 2),
            'completeness_pct': table_completeness
        }}
    )
    
    return {
        'table_id': table.id,
        'rows_profiled': n,
        'fields_profiled': len(fields),
        'completeness_pct': table_completeness,
        'profiled_at': tp.profiled_at.isoformat(),
        'field_profiles': field_profile_data,
    }


def _evaluate_rule(rule, rows, field=None):
    """Thin delegation wrapper — evaluates a DQRule model instance via engine.evaluate().

    Args:
        rule: DQRule instance
        rows: list of DataRow objects
        field: DataField instance (auto-resolved from first field_assignment if None)

    Returns (passed, checked_count, failed_count, sample_failures[:20], score).
    """
    from dq.engine import evaluate as engine_evaluate

    first_assn = None
    if field is None:
        first_assn = rule.field_assignments.select_related('data_field').first()
        if first_assn:
            field = first_assn.data_field

    # Build definition from rule fields for backwards compatibility
    rule_def = rule.definition or {}
    if not rule_def.get('type'):
        # Legacy rule without definition — construct one from model fields
        if not first_assn:
            first_assn = rule.field_assignments.select_related('data_field').first()
        fname = field.name if field else None
        bindings = [{'table': first_assn.data_table.name if first_assn else '',
                      'field': fname}] if first_assn else []
        rule_def = {
            'schema_version': 1,
            'name': rule.name,
            'level': 'field' if rule.rule_level == 'field_validation' else 'business',
            'dimension': rule.dimension or 'validity',
            'type': rule.rule_type or 'not_null',
            'severity': rule.severity or 'error',
            'active': rule.is_active,
            'bindings': bindings,
            'params': rule.params or {},
        }
        if rule.description:
            rule_def['description'] = rule.description

    return engine_evaluate(rule_def, rows, field=field)


def _evaluate_nl_check(rule, rows, field=None):
    """Thin delegation wrapper — evaluates an NL Check rule via engine._evaluate_nl_check().

    Returns the standard 5-tuple: (passed, checked, failed, failures, score).
    """
    from dq.engine import _evaluate_nl_check as engine_nl_check
    # Build definition from rule fields for backwards compatibility
    rule_def = rule.definition or {}
    if not rule_def.get('type'):
        fname = field.name if field else None
        bindings = [{'table': '', 'field': fname}] if fname else []
        rule_def = {
            'schema_version': 1,
            'name': rule.name,
            'level': 'field' if rule.rule_level == 'field_validation' else 'business',
            'dimension': rule.dimension or 'accuracy',
            'type': 'nl_check',
            'severity': rule.severity or 'error',
            'active': rule.is_active,
            'bindings': bindings,
            'params': rule.params or {},
        }
        if rule.description:
            rule_def['description'] = rule.description
    return engine_nl_check(rule_def, rows, field=field)


def _get_or_create_table_profile(table_id: int):
    """Ensure a TableProfile exists for the table.

    Returns (table, tp, error_dict). error_dict is None on success.
    Shared by the sync suggest endpoint and the suggest DQJob.
    """
    table = DataTable.objects.get(id=table_id)
    tp = TableProfile.objects.filter(data_table=table).order_by('-profiled_at').first()
    if not tp:
        logger.info(f'No profile for table {table_id} — profiling now')
        profile_table(table_id)
        tp = TableProfile.objects.filter(data_table=table).order_by('-profiled_at').first()
        if not tp:
            return table, None, {
                'code': 'no_profile',
                'message': 'Could not profile table — table may have no rows',
            }
    return table, tp, None


def build_suggest_payload(table_id: int):
    """Build the dq.suggest table-profile payload for a table.

    Returns (table_payload, error_dict). Shared by suggest_rules_for_table()
    (sync endpoint) and the suggest DQJob (async submit via CarbonIntelligence).
    """
    table, tp, err = _get_or_create_table_profile(table_id)
    if err:
        return None, err

    # Build field summaries from FieldProfile records
    field_profiles = FieldProfile.objects.filter(
        data_field__data_table=table,
    ).select_related('data_field')

    fields_payload = []
    for fp in field_profiles:
        field_entry = {
            'name': fp.data_field.name,
            'type': fp.data_field.type,
            'distinct_count': fp.distinct_count,
            'completeness_pct': fp.completeness_pct,
        }
        # Add numeric stats if available
        if fp.min_value:
            field_entry['min'] = fp.min_value
        if fp.max_value:
            field_entry['max'] = fp.max_value
        if fp.mean_value is not None:
            field_entry['mean'] = round(fp.mean_value, 2)
        if fp.top_values:
            field_entry['top_values'] = fp.top_values[:3]

        # Compute approximate stddev from range
        if 'min' in field_entry and 'max' in field_entry:
            try:
                rng = float(field_entry['max']) - float(field_entry['min'])
                field_entry['stddev'] = round(rng / 4, 2)
            except (ValueError, TypeError):
                pass

        fields_payload.append(field_entry)

    table_payload = {
        'table_id': table.id,
        'name': table.name,
        'description': table.title or table.name,
        'row_count': tp.row_count,
        'module_id': table.module_id,
        'org_unit_id': table.module.org_unit_id if table.module_id else None,
        'fields': fields_payload,
    }
    return table_payload, None


def suggest_rules_for_table(table_id: int) -> dict:
    """Build a table profile payload and send it to Pulse for rule suggestions.

    If no current TableProfile exists, run profile_table() first.

    Returns:
        {
            'table_id': int,
            'status': 'completed' | 'pulse_unavailable',
            'suggestions': [ {prompt, rationale, suggested_severity, confidence} ],
            'error': None | {...}
        }
    """
    from ai.intelligence import CarbonIntelligence

    table_payload, err = build_suggest_payload(table_id)
    if err:
        return {
            'table_id': table_id,
            'status': 'pulse_unavailable',
            'suggestions': [],
            'error': err,
        }

    intelligence = CarbonIntelligence()
    response = intelligence.submit_dq_suggest(table_payload)

    if response.get('status') == 'pulse_unavailable':
        return {
            'table_id': table_id,
            'status': 'pulse_unavailable',
            'suggestions': [],
            'error': response.get('error'),
        }

    suggestions = response.get('result', {}).get('suggestions', [])
    return {
        'table_id': table_id,
        'status': 'completed',
        'suggestions': suggestions,
        'error': None,
    }


# ── Phase 4: anomaly detection (TASK-DQ-CORE-P4-PULSE, deliverable 3) ──────

MIN_ANOMALY_PROFILES = 6
"""Fewer profile snapshots than this → anomaly job completes with
result.state = 'insufficient_history' (Carbon-side guard, not a Pulse call)."""


def _prompt_from_rule(rule) -> str:
    """Extract the declarative prompt from an anomaly_detect rule."""
    d = rule.definition or {}
    if isinstance(d, dict):
        params = d.get('params')
        if isinstance(params, dict) and params.get('prompt'):
            return str(params['prompt'])
    if isinstance(rule.params, dict) and rule.params.get('prompt'):
        return str(rule.params['prompt'])
    return rule.description or rule.name or ''


def build_anomaly_payload(table_id: int):
    """Build the anomaly.detect payload for a table (Phase 4).

    Combines TableProfile/FieldProfile history with
    DQProfileConfig.volume_anomaly_pct (wired NOW — it was previously inert)
    and the anomaly_detect rules bound to the table.

    Returns (payload, error_dict). error_dict.code == 'insufficient_history'
    when fewer than MIN_ANOMALY_PROFILES profile snapshots exist — the anomaly
    job then completes with result.state='insufficient_history' (fail-visible:
    nothing is fabricated, Pulse is not even called).
    """
    config = DQProfileConfig.objects.first()
    volume_pct = config.volume_anomaly_pct if config else 25

    table = DataTable.objects.get(id=table_id)
    profiles = list(TableProfile.objects.filter(data_table=table).order_by('profiled_at'))
    if len(profiles) < MIN_ANOMALY_PROFILES:
        return None, {
            'code': 'insufficient_history',
            'message': (
                f'Need at least {MIN_ANOMALY_PROFILES} profile snapshots; '
                f'found {len(profiles)} — run profile jobs over time before '
                'requesting anomaly detection'
            ),
        }

    history = []
    for p in profiles:
        history.append({
            'at': p.profiled_at.isoformat(),
            'row_count': p.row_count,
            'completeness_pct': p.completeness_pct,
            'null_counts': p.null_counts or {},
            'mean_values': p.mean_values or {},
            'min_values': p.min_values or {},
            'max_values': p.max_values or {},
            'distinct_counts': p.distinct_counts or {},
        })

    field_history = {}
    field_names = table.fields.filter(is_archived=False).values_list('name', flat=True)
    for fname in field_names:
        fps = list(FieldProfile.objects.filter(
            data_field__name=fname, data_field__data_table=table
        ).order_by('profiled_at'))
        field_history[fname] = [
            {
                'at': fp.profiled_at.isoformat(),
                'row_count': fp.row_count,
                'null_count': fp.null_count,
                'null_pct': round(fp.null_count / fp.row_count * 100, 2) if fp.row_count else 0.0,
                'distinct_count': fp.distinct_count,
                'mean_value': fp.mean_value,
                'min_value': fp.min_value,
                'max_value': fp.max_value,
            }
            for fp in fps
        ]

    anomaly_rules = list(DQRule.objects.filter(
        rule_type='anomaly_detect', is_active=True,
        field_assignments__data_table=table,
    ).distinct())

    payload = {
        'table': {
            'name': table.name,
            'description': table.title or table.name,
        },
        'sensitivity': volume_pct,
        'volume_anomaly_pct': volume_pct,
        'history': history,
        'fields': field_history,
        'rules': [
            {
                'name': r.name,
                'prompt': _prompt_from_rule(r),
                'severity': r.severity,
            }
            for r in anomaly_rules
        ],
    }
    return payload, None


def _compute_quality(table):
    """Compute quality_status and quality_score from latest DQResult for each active rule.

    Phase 4 (fail-visible): results with passed=None (status=
    skipped_unavailable — Pulse down) are EXCLUDED from the denominator so
    scores honestly show the gap instead of silently auto-passing. If every
    latest result is skipped, quality is 'unknown'.
    """
    field_ids = list(table.fields.values_list('id', flat=True))
    rules = list(DQRule.objects.filter(
        Q(field_assignments__data_table_id=table.id) |
        Q(field_assignments__data_field_id__in=field_ids),
        is_active=True,
    ).distinct())
    if not rules:
        return 'unknown', None
    results = [r.results.order_by('-run_at').first() for r in rules]
    results_with_data = [r for r in results if r is not None]
    if not results_with_data:
        return 'unknown', None
    verdicts = [r for r in results_with_data if r.passed is not None]
    if not verdicts:
        return 'unknown', None  # all skipped — no verdict available
    passed_count = sum(1 for r in verdicts if r.passed)
    total = len(verdicts)
    score = round(passed_count / total * 100)
    if score >= 90:
        status = 'passing'
    elif score >= 70:
        status = 'warning'
    else:
        status = 'failing'
    return status, score


def _rollup_to_catalog(table, rules, results, user=None):
    """Update AssetProfile quality fields and emit GovernanceEvent."""
    # --- Per-field rollup ---
    by_field = {}
    for rule in rules:
        for assn in rule.field_assignments.all():
            if not assn.data_field_id:
                continue
            result = next((r for r in results if r.rule_id == rule.id and r.data_field_id == assn.data_field_id), None)
            if not result:
                result = next((r for r in results if r.rule_id == rule.id), None)
            if result:
                by_field.setdefault(assn.data_field_id, []).append(result)
    for fid, field_results in by_field.items():
        # Phase 4 (fail-visible): skip fields whose results are all
        # skipped_unavailable — no verdict to roll up.
        verdicts = [r for r in field_results if r.passed is not None]
        if not verdicts:
            continue
        passed_count = sum(1 for r in verdicts if r.passed)
        total = len(verdicts)
        field_score = round(passed_count / total * 100)
        field_status = 'passing' if field_score >= 90 else 'warning' if field_score >= 70 else 'failing'
        ap, _ = AssetProfile.objects.get_or_create(data_field_id=fid)
        old_status = ap.quality_status
        old_score = ap.quality_score
        ap.quality_status = field_status
        ap.quality_score = field_score
        if user:
            ap.updated_by = user
        ap.save(update_fields=['quality_status', 'quality_score', 'updated_at'] + (['updated_by'] if user else []))
        _emit_governance_event(ap, old_status, old_score, field_status, field_score, user)

    # --- Table rollup ---
    status, score = _compute_quality(table)
    ap, _ = AssetProfile.objects.get_or_create(data_table=table)
    old_status = ap.quality_status
    old_score = ap.quality_score
    ap.quality_status = status
    ap.quality_score = score
    if user:
        ap.updated_by = user
    ap.save(update_fields=['quality_status', 'quality_score', 'updated_at'] + (['updated_by'] if user else []))
    _emit_governance_event(ap, old_status, old_score, status, score, user)


def _emit_governance_event(ap, old_status, old_score, new_status, new_score, user):
    """Create a GovernanceEvent capturing quality status transition."""
    try:
        GovernanceEvent.objects.create(
            asset=ap,
            entity_type='AssetProfile',
            entity_id=ap.id,
            action='update',
            before={'quality_status': old_status, 'quality_score': old_score},
            after={'quality_status': new_status, 'quality_score': new_score},
            user=user,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("GovernanceEvent create failed: %s", exc)


def _run_conflict_verdicts(table_id, results):
    """Composite conflict verdicts for a completed DQ run.

    Combines the static ``conflict``/``redundant`` findings with runtime-resolved
    ``undecidable`` overlaps. Each finding is scoped to one field, so rule
    outcomes are keyed by ``(rule_id, data_field_id)`` and resolved per field.

    Returns a list of verdict dicts (empty list = no findings).
    """
    from .contradiction import composite_runtime_verdicts

    findings = detect_rule_contradictions(data_table_id=table_id)
    if not findings:
        return []

    outcomes = {}
    for res in results:
        outcomes[(res.rule_id, res.data_field_id)] = res.passed

    verdicts = []
    for finding in findings:
        field_id = finding.get('data_field_id')
        rule_outcomes = {
            rid: outcomes.get((rid, field_id)) for rid in finding['rule_ids']
        }
        verdicts.extend(composite_runtime_verdicts([finding], rule_outcomes))
    return verdicts


def run_dq(table_id, user=None):
    """Run all active DQ rules for a table. Returns summary dict."""
    start_time = time.time()
    table = DataTable.objects.get(id=table_id)
    rows = _rows(table, chunk=True)
    row_count = len(rows)

    # Warn on very large datasets
    if row_count > 100000:
        perf_logger.warning(
            'Large dataset DQ execution initiated',
            extra={'structured': {
                'event': 'dq_run_large_dataset',
                'table_id': table_id,
                'row_count': row_count,
                'warning': 'Dataset exceeds 100k rows - execution may be slow'
            }}
        )

    field_ids = list(table.fields.values_list('id', flat=True))
    rules = list(DQRule.objects.filter(is_active=True).filter(
        Q(field_assignments__data_table_id=table_id) |
        Q(field_assignments__data_field_id__in=field_ids)
    ).prefetch_related('field_assignments__data_field').distinct())

    results = []
    for rule in rules:
        # Phase 3 (TASK-DQ-CORE-P3-JOBS, deliverable 5): nl_check rules are
        # job-only — nothing AI runs synchronously in a request. They execute
        # via the `nl_check` DQJob type only.
        # Phase 4 (TASK-DQ-CORE-P4-PULSE): anomaly_detect rules are also not
        # row-evaluated — they feed the anomaly.detect job payload only.
        if rule.rule_type in ('nl_check', 'anomaly_detect'):
            logger.info(
                'Skipping %s rule %s (id=%s) in run_dq — job-only',
                rule.rule_type, rule.name, rule.id,
            )
            continue
        assignments = rule.field_assignments.all()
        for assn in assignments:
            rule_start = time.time()
            field = assn.data_field  # may be None for table-level
            try:
                passed, checked, failed, sample, score = _evaluate_rule(rule, rows, field=field)
                # Phase 4 (fail-visible): passed=None → Pulse could not evaluate.
                status = 'skipped_unavailable' if passed is None else ('passed' if passed else 'failed')
                results.append(DQResult.objects.create(
                    rule=rule,
                    data_field=field,
                    status=status,
                    passed=passed, checked_count=checked,
                    failed_count=failed, sample_failures=sample, score=score,
                ))
                # EPH-6A: count DQ runs for Prometheus telemetry.
                try:
                    from core.telemetry import dq_runs_total
                    dq_runs_total.labels(status=status).inc()
                except Exception:
                    pass  # Never let telemetry break DQ execution
                rule_duration_ms = (time.time() - rule_start) * 1000

                if rule_duration_ms > 2000:
                    perf_logger.warning(
                        'Slow DQ rule execution',
                        extra={'structured': {
                            'event': 'dq_rule_slow',
                            'table_id': table_id,
                            'rule_id': rule.id,
                            'rule_type': rule.rule_type,
                            'duration_ms': round(rule_duration_ms, 2),
                            'row_count': row_count
                        }}
                    )
            except Exception as exc:
                logger.error(
                    f'DQ rule execution failed: {exc}',
                    extra={'structured': {
                        'event': 'dq_rule_error',
                        'table_id': table_id,
                        'rule_id': rule.id,
                        'rule_type': rule.rule_type,
                        'error': str(exc)
                    }},
                    exc_info=True
                )
                continue
    
    _rollup_to_catalog(table, rules, results, user=user)
    
    total_duration_ms = (time.time() - start_time) * 1000
    perf_logger.info(
        'DQ execution completed',
        extra={'structured': {
            'event': 'dq_run_complete',
            'table_id': table_id,
            'row_count': row_count,
            'rules_run': len(results),
            'duration_ms': round(total_duration_ms, 2)
        }}
    )
    
    return {
        'table': table_id,
        'rules_run': len(results),
        'conflicts': _run_conflict_verdicts(table_id, results),
        'summary': [{
            'rule_id': r.rule_id,
            'rule_name': r.rule.name,
            'type': r.rule.rule_type,
            'passed': r.passed,
            'status': r.status,
            'failed': r.failed_count,
            'score': r.score,
        } for r in results],
    }


def run_single_rule(rule_id, user=None):
    """Run a single DQ rule by ID across all its field assignments. Returns list of result dicts."""
    start_time = time.time()
    rule = DQRule.objects.prefetch_related('field_assignments__data_field',
        'field_assignments__data_table').get(id=rule_id)

    all_results = []
    assignments = rule.field_assignments.all()

    if not assignments:
        raise ValueError("Rule has no field assignments. Assign at least one field or table first.")

    for assn in assignments:
        field = assn.data_field
        table = assn.data_table
        if table is None:
            continue
        rows = _rows(table, chunk=True)
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows, field=field)
        # Phase 4 (fail-visible): passed=None → Pulse could not evaluate.
        status = 'skipped_unavailable' if passed is None else ('passed' if passed else 'failed')
        result = DQResult.objects.create(
            rule=rule, data_field=field, status=status, passed=passed,
            checked_count=checked, failed_count=failed,
            sample_failures=sample, score=score,
        )
        all_results.append({
            'rule_id': rule.id,
            'rule_name': rule.name,
            'data_field_id': field.id if field else None,
            'data_field_name': field.name if field else None,
            'table_id': table.id,
            'passed': result.passed,
            'status': result.status,
            'checked_count': result.checked_count,
            'failed_count': result.failed_count,
            'score': result.score,
            'sample_failures': result.sample_failures,
            'run_at': result.run_at.isoformat(),
            'result_id': result.id,
        })

    # Rollup quality for all affected tables
    tables = {a.data_table for a in assignments if a.data_table}
    all_rules = list(DQRule.objects.filter(is_active=True).filter(
        field_assignments__data_table__in=[t.id for t in tables]
    ).distinct())
    for table in tables:
        _rollup_to_catalog(table, all_rules, [result], user=user)

    return all_results


def bulk_profile(table_ids, user=None):
    """Profile multiple tables. Returns per-table status."""
    start_time = time.time()
    results = []
    success = 0
    failed = 0
    
    for tid in table_ids:
        try:
            data = profile_table(tid)
            results.append({'table_id': tid, 'status': 'success', 'rows_profiled': data['rows_profiled']})
            success += 1
        except Exception as exc:
            logger.warning("bulk_profile table=%s error: %s", tid, exc)
            results.append({'table_id': tid, 'status': 'error', 'error': str(exc)})
            failed += 1
    
    total_duration_ms = (time.time() - start_time) * 1000
    perf_logger.info(
        'Bulk profiling completed',
        extra={'structured': {
            'event': 'dq_bulk_profile_complete',
            'table_count': len(table_ids),
            'success': success,
            'failed': failed,
            'duration_ms': round(total_duration_ms, 2)
        }}
    )
    
    return {'total': len(table_ids), 'success': success, 'failed': failed, 'results': results}


# ── Phase 3: shared callables for freshness / schema jobs ──────────────────
# Extracted from the management commands (check_freshness, schema_snapshot) so
# the DQJob runner and the commands call the SAME code path.

def check_freshness(table_id=None, notify=False) -> dict:
    """Check data freshness for tables and create FreshnessCheck records.

    Args:
        table_id: optional — check a single table; None checks all active tables.
        notify: fire notifications for stale tables.

    Returns summary dict: {total, stale, results: [{table_id, table_name,
    is_fresh, age_hours}]}.
    """
    config = DQProfileConfig.objects.first()
    default_threshold = config.freshness_threshold_hours if config else 24

    qs = DataTable.objects.filter(is_archived=False)
    if table_id:
        qs = qs.filter(id=table_id)

    total = qs.count()
    stale_count = 0
    results = []
    for table in qs.iterator():
        # Find newest DataRow
        newest = DataRow.objects.filter(
            data_table=table, is_archived=False
        ).order_by('-created_at').first()

        last_ts = newest.created_at if newest else None
        now = timezone.now()

        if last_ts:
            age_hours = (now - last_ts).total_seconds() / 3600
            is_fresh = age_hours <= default_threshold
        else:
            age_hours = None
            is_fresh = True  # Empty table is not "stale"

        FreshnessCheck.objects.create(
            data_table=table,
            expected_max_age_hours=default_threshold,
            last_data_timestamp=last_ts,
            is_fresh=is_fresh,
        )

        if not is_fresh:
            stale_count += 1
        results.append({
            'table_id': table.id,
            'table_name': table.name,
            'is_fresh': is_fresh,
            'age_hours': age_hours,
        })

        if notify and not is_fresh:
            try:
                from accounts.models import notify_event
                notify_event(
                    event_type='freshness_violation',
                    title=f'Stale data: {table.name}',
                    body=f'Table "{table.name}" has not been updated in {age_hours:.1f} hours '
                         f'(threshold: {default_threshold}h).',
                    severity='warning',
                    link=f'/dataschema/tables/{table.id}/',
                )
            except Exception:
                logger.exception('Failed to send freshness notification')

    return {'total': total, 'stale': stale_count, 'results': results}


def snapshot_schema(table_id=None, notify=False) -> dict:
    """Snapshot current table schemas and detect changes from previous snapshot.

    Args:
        table_id: optional — snapshot a single table; None snapshots all active.
        notify: fire notifications for schema changes.

    Returns summary dict: {total, changes_detected, results: [{table_id,
    table_name, columns, initial, added, dropped, modified, changes}]}.
    """
    qs = DataTable.objects.filter(is_archived=False)
    if table_id:
        qs = qs.filter(id=table_id)

    total = qs.count()
    changes_detected = 0
    results = []
    for table in qs.iterator():
        fields = DataField.objects.filter(data_table=table, is_active=True, is_archived=False)
        current_schema = {}
        for f in fields:
            current_schema[f.name] = {
                'type': f.type,
                'is_nullable': True,  # DataField has no is_nullable; default to True
                'position': f.id,  # proxy for order
            }

        row_count = table.rows.filter(is_archived=False).count()

        new_snapshot = SchemaSnapshot.objects.create(
            data_table=table,
            column_schema=current_schema,
            row_count=row_count,
        )

        # Compare with previous snapshot
        prev = SchemaSnapshot.objects.filter(
            data_table=table
        ).exclude(id=new_snapshot.id).order_by('-snapshot_at').first()

        added = dropped = modified = 0
        changes = []
        if prev and prev.column_schema:
            prev_cols = set(prev.column_schema.keys()) if isinstance(prev.column_schema, dict) else set()
            curr_cols = set(current_schema.keys())

            for col in sorted(curr_cols - prev_cols):
                SchemaChange.objects.create(
                    data_table=table,
                    snapshot_from=prev,
                    snapshot_to=new_snapshot,
                    change_type='added',
                    field_name=col,
                    old_definition=None,
                    new_definition=current_schema.get(col),
                )
                added += 1
                changes_detected += 1
                changes.append({'change_type': 'added', 'field_name': col})

            for col in sorted(prev_cols - curr_cols):
                SchemaChange.objects.create(
                    data_table=table,
                    snapshot_from=prev,
                    snapshot_to=new_snapshot,
                    change_type='dropped',
                    field_name=col,
                    old_definition=prev.column_schema.get(col),
                    new_definition=None,
                )
                dropped += 1
                changes_detected += 1
                changes.append({'change_type': 'dropped', 'field_name': col})

            for col in sorted(curr_cols & prev_cols):
                if prev.column_schema.get(col) != current_schema.get(col):
                    SchemaChange.objects.create(
                        data_table=table,
                        snapshot_from=prev,
                        snapshot_to=new_snapshot,
                        change_type='modified',
                        field_name=col,
                        old_definition=prev.column_schema.get(col),
                        new_definition=current_schema.get(col),
                    )
                    modified += 1
                    changes_detected += 1
                    changes.append({'change_type': 'modified', 'field_name': col})

            if notify and (added or dropped or modified):
                try:
                    from accounts.models import notify_event
                    notify_event(
                        event_type='schema_change',
                        title=f'Schema change: {table.name}',
                        body=f'Table "{table.name}" schema changed: '
                             f'{added} added, {dropped} dropped, {modified} modified columns.',
                        severity='info',
                        link=f'/dataschema/tables/{table.id}/',
                    )
                except Exception:
                    logger.exception('Failed to send schema change notification')
        else:
            logger.info('Initial schema snapshot for table %s (%d columns)',
                        table.name, len(current_schema))

        results.append({
            'table_id': table.id,
            'table_name': table.name,
            'columns': len(current_schema),
            'initial': not (prev and prev.column_schema),
            'added': added,
            'dropped': dropped,
            'modified': modified,
            'changes': changes,
        })

    return {'total': total, 'changes_detected': changes_detected, 'results': results}


def _rule_spec(rule):
    """Build an analysis-ready rule spec from a DQRule instance.

    Prefers `definition` (source of truth, ADR-0006); falls back to flat columns
    for legacy rules that predate `definition`.
    """
    d = rule.definition or {}
    params = d.get('params') or rule.params or {}
    return {
        'rule_id': rule.id,
        'name': rule.name or d.get('name') or f'rule-{rule.id}',
        'rule_type': rule.rule_type or d.get('type') or '',
        'params': params,
    }


def detect_rule_contradictions(data_field_id=None, data_table_id=None):
    """Return contradiction findings for active rules on a field or table.

    Semantic analysis lives in ``dq/contradiction.py`` (pure). This function
    only gathers the active, non-archived rules and groups them by field (table
    level business rules — ``data_field`` NULL — form their own group).

    Args:
        data_field_id: optional int — analyze rules bound to this field only.
        data_table_id: optional int — analyze all rules bound to this table.

    Returns:
        list of finding dicts, each annotated with ``data_field_id`` and
        ``data_field_name`` (the latter is None for table-level groups).
    """
    from .contradiction import analyze_rules
    from .models import RuleFieldAssignment

    if data_field_id is None and data_table_id is None:
        return []

    assignments = (
        RuleFieldAssignment.objects
        .filter(rule__archived=False, rule__is_active=True)
        .select_related('rule', 'data_field')
    )
    if data_field_id is not None:
        assignments = assignments.filter(data_field_id=data_field_id)
    else:
        assignments = assignments.filter(data_table_id=data_table_id)

    # Group by field (None = table-level business rules).
    groups: dict = {}
    field_names: dict = {}
    for assn in assignments:
        key = assn.data_field_id
        groups.setdefault(key, []).append(assn.rule)
        if key is not None:
            field_names.setdefault(key, assn.data_field.name if assn.data_field else None)

    findings = []
    for field_id, rules in groups.items():
        specs = [_rule_spec(r) for r in rules]
        for f in analyze_rules(specs):
            f = dict(f)
            f['data_field_id'] = field_id
            f['data_field_name'] = field_names.get(field_id)
            findings.append(f)
    return findings


def table_rule_inventory(table_id):
    """Domain-level inventory of a table's active rules (Phase 24 Phase B).

    Returns ``{rules, field_gaps, contradictions}``:
      - ``rules``: flat list of active rule specs, each annotated with
        ``data_field_id`` / ``data_field_name`` (table-level rules have None).
      - ``field_gaps``: active fields with no active rules (gap analysis).
      - ``contradictions``: findings from ``detect_rule_contradictions``.

    Pure domain logic (no AI); consumed by ``ai/knowledge/dq_graph.py``.
    """
    from .models import RuleFieldAssignment
    from dataschema.models import DataField

    fields = {
        f.id: f for f in DataField.objects.filter(
            data_table_id=table_id, is_active=True, is_archived=False)
    }
    assignments = (
        RuleFieldAssignment.objects
        .filter(data_table_id=table_id, rule__archived=False, rule__is_active=True)
        .select_related('rule', 'data_field')
    )

    rules = []
    covered = set()
    for a in assignments:
        d = a.rule.definition or {}
        rules.append({
            'rule_id': a.rule.id,
            'name': a.rule.name or d.get('name'),
            'rule_type': a.rule.rule_type or d.get('type'),
            'dimension': a.rule.dimension,
            'severity': a.rule.severity,
            'is_active': a.rule.is_active,
            'params': d.get('params') or a.rule.params or {},
            'data_field_id': a.data_field_id,
            'data_field_name': a.data_field.name if a.data_field_id else None,
        })
        if a.data_field_id:
            covered.add(a.data_field_id)

    gaps = [
        {'field_id': f.id, 'name': f.name, 'label': f.label, 'type': f.type}
        for f in fields.values() if f.id not in covered
    ]

    return {
        'rules': rules,
        'field_gaps': gaps,
        'contradictions': detect_rule_contradictions(data_table_id=table_id),
    }
