# dq/services.py
import re
from statistics import mean
from django.db.models import Q
from dataschema.models import DataTable, DataRow
from catalog.models import AssetProfile
from mdm.models import ReferenceValue
from .models import TableProfile, FieldProfile, DQRule, DQResult


def _rows(table):
    return list(DataRow.objects.filter(data_table=table, is_archived=False))


def _is_empty(v):
    return v is None or v == '' or v == []


def profile_table(table_id):
    table = DataTable.objects.get(id=table_id)
    rows = _rows(table)
    n = len(rows)
    fields = list(table.fields.filter(is_active=True, is_archived=False))
    completeness_all = []
    for f in fields:
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
        FieldProfile.objects.create(
            data_field=f, row_count=n, null_count=null_count, distinct_count=distinct,
            completeness_pct=round(completeness, 2), uniqueness_pct=round(uniqueness, 2),
            min_value=minv, max_value=maxv, mean_value=meanv,
            top_values=[{'value': k, 'count': c} for k, c in top],
        )
    table_completeness = round(mean(completeness_all), 2) if completeness_all else 0.0
    TableProfile.objects.create(data_table=table, row_count=n, completeness_pct=table_completeness)
    return {'table': table.id, 'rows': n, 'fields_profiled': len(fields), 'completeness_pct': table_completeness}


def _evaluate_rule(rule, rows):
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
            allowed = {str(c) for c in ReferenceValue.objects.filter(reference_set_id=rs_id, is_active=True).values_list('code', flat=True)}
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
        rx = re.compile(pat) if pat else None
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if rx and not rx.search(str(v)):
                failures.append({'row': r.id, 'value': v})
    failed = len(failures)
    score = 100 if checked == 0 else round((checked - failed) / checked * 100)
    return (failed == 0), checked, failed, failures[:20], score


def _status_for(entries):
    # entries: list of (severity, passed, score)
    if not entries:
        return 'unknown', None
    worst_score = min(s for (_sev, _p, s) in entries)
    if any((not p) and sev == 'error' for (sev, p, s) in entries):
        return 'failing', worst_score
    if any((not p) and sev in ('warn', 'info') for (sev, p, s) in entries):
        return 'warning', worst_score
    return 'passing', worst_score


def _rollup_to_catalog(table, rules, results):
    result_by_rule = {r.rule_id: r for r in results}
    by_field = {}
    table_level = []
    for rule in rules:
        r = result_by_rule.get(rule.id)
        if not r:
            continue
        entry = (rule.severity, r.passed, r.score)
        if rule.data_field_id:
            by_field.setdefault(rule.data_field_id, []).append(entry)
        else:
            table_level.append(entry)
    for fid, entries in by_field.items():
        status, score = _status_for(entries)
        ap, _ = AssetProfile.objects.get_or_create(data_field_id=fid)
        ap.quality_status = status
        ap.quality_score = score
        ap.save(update_fields=['quality_status', 'quality_score', 'updated_at'])
    all_entries = table_level + [e for entries in by_field.values() for e in entries]
    status, score = _status_for(all_entries)
    ap, _ = AssetProfile.objects.get_or_create(data_table=table)
    ap.quality_status = status
    ap.quality_score = score
    ap.save(update_fields=['quality_status', 'quality_score', 'updated_at'])


def run_dq(table_id):
    table = DataTable.objects.get(id=table_id)
    rows = _rows(table)
    field_ids = list(table.fields.values_list('id', flat=True))
    rules = list(DQRule.objects.filter(is_active=True).filter(
        Q(data_table_id=table_id) | Q(data_field_id__in=field_ids)
    ))
    results = []
    for rule in rules:
        passed, checked, failed, sample, score = _evaluate_rule(rule, rows)
        results.append(DQResult.objects.create(
            rule=rule, passed=passed, checked_count=checked,
            failed_count=failed, sample_failures=sample, score=score,
        ))
    _rollup_to_catalog(table, rules, results)
    return {
        'table': table_id, 'rules_run': len(results),
        'summary': [{'rule': r.rule_id, 'type': r.rule.rule_type, 'passed': r.passed,
                     'failed': r.failed_count, 'score': r.score} for r in results],
    }
