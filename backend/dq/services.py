# dq/services.py
import re
import logging
import time
from statistics import mean
from django.db.models import Q
from dataschema.models import DataTable, DataRow
from catalog.models import AssetProfile, GovernanceEvent
from mdm.models import ReferenceValue
from .models import TableProfile, FieldProfile, DQRule, DQResult
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
    # Deduplicate: update existing TableProfile or create new one.
    # Clean up old field profiles before creating new ones.
    from django.utils import timezone
    tp, _created = TableProfile.objects.update_or_create(
        data_table=table,
        defaults={
            'row_count': n,
            'completeness_pct': table_completeness,
            'profiled_at': timezone.now(),
        },
    )
    # Delete old field profiles for this table (replace with fresh ones)
    FieldProfile.objects.filter(data_field__data_table=table).delete()
    
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


def _evaluate_rule(rule, rows):
    """Evaluate a single DQ rule against a list of DataRow objects.

    Returns (passed, checked_count, failed_count, sample_failures[:20], score).
    """
    field = rule.data_field
    fname = field.name if field else None
    checked = 0
    failures = []

    if rule.rule_type == 'not_null':
        for r in rows:
            checked += 1
            if _is_empty(r.values.get(fname)):
                failures.append({'row': r.id})

    elif rule.rule_type == 'unique':
        seen = {}
        for r in rows:
            checked += 1
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            seen.setdefault(str(v), []).append(r.id)
        for v, ids in seen.items():
            if len(ids) > 1:
                for rid in ids:
                    failures.append({'row': rid, 'value': v})

    elif rule.rule_type == 'allowed_values':
        rs_id = rule.params.get('reference_set')
        if rs_id:
            allowed = {str(c) for c in ReferenceValue.objects.filter(
                reference_set_id=rs_id, is_active=True
            ).values_list('code', flat=True)}
        else:
            allowed = {str(a) for a in rule.params.get('values', [])}
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if str(v) not in allowed:
                failures.append({'row': r.id, 'value': v})

    elif rule.rule_type == 'range':
        lo, hi = rule.params.get('min'), rule.params.get('max')
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            try:
                fv = float(v)
            except (TypeError, ValueError):
                failures.append({'row': r.id, 'value': v})
                continue
            if (lo is not None and fv < lo) or (hi is not None and fv > hi):
                failures.append({'row': r.id, 'value': v})

    elif rule.rule_type == 'regex':
        pat = rule.params.get('pattern', '')
        try:
            rx = re.compile(pat) if pat else None
        except re.error as exc:
            logger.warning("DQ regex compile error rule=%s: %s", rule.id, exc)
            rx = None
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if rx and not rx.search(str(v)):
                failures.append({'row': r.id, 'value': v})

    elif rule.rule_type == 'reference_integrity':
        # params may explicitly name a reference_set_id or fall back to field.reference_set
        rs_id = rule.params.get('reference_set_id')
        if rs_id is None and field and hasattr(field, 'reference_set_id'):
            rs_id = field.reference_set_id
        if rs_id:
            from mdm.models import ReferenceSet
            try:
                ref_set = ReferenceSet.objects.get(id=rs_id)
                allowed = {
                    str(c) for c in ref_set.get_current_values().values_list('code', flat=True)
                }
            except ReferenceSet.DoesNotExist:
                allowed = set()
        else:
            allowed = set()
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if str(v) not in allowed:
                failures.append({'row': r.id, 'value': v})

    elif rule.rule_type == 'threshold':
        from django.db import models as dj_models
        op = rule.params.get('operator', 'gte')
        threshold_val = rule.params.get('value')
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            try:
                fv = float(v)
            except (TypeError, ValueError):
                failures.append({'row': r.id, 'value': v})
                continue
            ok = False
            if threshold_val is not None:
                tv = float(threshold_val)
                if op == 'gte':
                    ok = fv >= tv
                elif op == 'gt':
                    ok = fv > tv
                elif op == 'lte':
                    ok = fv <= tv
                elif op == 'lt':
                    ok = fv < tv
                elif op == 'eq':
                    ok = fv == tv
                elif op == 'neq':
                    ok = fv != tv
                else:
                    ok = True  # unknown operator → pass
            if not ok:
                failures.append({'row': r.id, 'value': v})

    failed = len(failures)
    score = 100 if checked == 0 else round((checked - failed) / checked * 100)
    return (failed == 0), checked, failed, failures[:20], score


def _compute_quality(table):
    """Compute quality_status and quality_score from latest DQResult for each active rule."""
    rules = list(DQRule.objects.filter(
        Q(data_table=table) | Q(data_field__data_table=table),
        is_active=True,
    ).distinct())
    if not rules:
        return 'unknown', None
    results = [r.results.order_by('-run_at').first() for r in rules]
    results_with_data = [r for r in results if r is not None]
    if not results_with_data:
        return 'unknown', None
    passed_count = sum(1 for r in results_with_data if r.passed)
    total = len(results_with_data)
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
        if not rule.data_field_id:
            continue
        result = next((r for r in results if r.rule_id == rule.id), None)
        if result:
            by_field.setdefault(rule.data_field_id, []).append(result)
    for fid, field_results in by_field.items():
        passed_count = sum(1 for r in field_results if r.passed)
        total = len(field_results)
        field_score = round(passed_count / total * 100) if total else 100
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
        Q(data_table_id=table_id) | Q(data_field_id__in=field_ids)
    ).select_related('data_field'))
    
    results = []
    for rule in rules:
        rule_start = time.time()
        try:
            passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
            results.append(DQResult.objects.create(
                rule=rule, passed=passed, checked_count=checked,
                failed_count=failed, sample_failures=sample, score=score,
            ))
            rule_duration_ms = (time.time() - rule_start) * 1000
            
            # Log slow rule execution
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
            # Continue with other rules even if one fails
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
        'summary': [{
            'rule_id': r.rule_id,
            'rule_name': r.rule.name,
            'type': r.rule.rule_type,
            'passed': r.passed,
            'failed': r.failed_count,
            'score': r.score,
        } for r in results],
    }


def run_single_rule(rule_id, user=None):
    """Run a single DQ rule by ID. Returns response dict with DQResult data."""
    start_time = time.time()
    rule = DQRule.objects.select_related('data_field', 'data_table').get(id=rule_id)
    table = rule.data_table or (rule.data_field.data_table if rule.data_field else None)
    if table is None:
        raise ValueError("Rule has no associated table or field")
    
    rows = _rows(table, chunk=True)
    passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
    result = DQResult.objects.create(
        rule=rule, passed=passed, checked_count=checked,
        failed_count=failed, sample_failures=sample, score=score,
    )
    
    # Rollup quality for this table
    all_rules = list(DQRule.objects.filter(is_active=True).filter(
        Q(data_table=table) | Q(data_field__data_table=table)
    ).distinct())
    _rollup_to_catalog(table, all_rules, [result], user=user)
    
    duration_ms = (time.time() - start_time) * 1000
    perf_logger.info(
        'Single rule execution completed',
        extra={'structured': {
            'event': 'dq_rule_execute',
            'rule_id': rule.id,
            'rule_type': rule.rule_type,
            'table_id': table.id,
            'passed': passed,
            'checked_count': checked,
            'failed_count': failed,
            'score': score,
            'duration_ms': round(duration_ms, 2)
        }}
    )
    
    return {
        'rule_id': rule.id,
        'rule_name': rule.name,
        'passed': result.passed,
        'checked_count': result.checked_count,
        'failed_count': result.failed_count,
        'score': result.score,
        'sample_failures': result.sample_failures,
        'run_at': result.run_at.isoformat(),
        'result_id': result.id,
    }


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
