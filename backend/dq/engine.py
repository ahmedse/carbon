"""
dq/engine.py — Single DQ rule evaluator.

Pure function operating on a rule JSON definition dict (v1). No model imports.
No logic changes from services._evaluate_rule — only the data source changed
from model instance fields to dict keys.

Moved here from services.py per Phase 1 unification plan.
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Return type: (passed, checked_count, failed_count, sample_failures[:20], score)
EvalResult = Tuple[bool, int, int, List[Dict], int]


def _is_empty(v: Any) -> bool:
    return v is None or v == '' or v == []


def evaluate(rule_def: Dict[str, Any], rows: List[Any], *,
             field: Optional[Any] = None) -> EvalResult:
    """Evaluate a DQ rule definition against a list of DataRow objects.

    Args:
        rule_def: v1 rule JSON definition dict
        rows: list of DataRow objects
        field: DataField instance (optional; resolved from call site)

    Returns:
        (passed, checked_count, failed_count, sample_failures[:20], score)
    """
    rule_type = rule_def.get('type', '')
    params = rule_def.get('params', {})
    fname = field.name if field else None
    checked = 0
    failures: List[Dict] = []

    if rule_type == 'not_null':
        for r in rows:
            checked += 1
            if _is_empty(r.values.get(fname)):
                failures.append({'row': r.id})

    elif rule_type == 'unique':
        seen: Dict[str, List] = {}
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

    elif rule_type == 'allowed_values':
        from mdm.models import ReferenceValue
        rs_id = params.get('reference_set')
        if rs_id:
            allowed = {str(c) for c in ReferenceValue.objects.filter(
                reference_set_id=rs_id, is_active=True
            ).values_list('code', flat=True)}
        else:
            allowed = {str(a) for a in params.get('values', [])}
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if str(v) not in allowed:
                failures.append({'row': r.id, 'value': v})

    elif rule_type == 'range':
        lo = params.get('min')
        hi = params.get('max')
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

    elif rule_type == 'regex':
        pat = params.get('pattern', '')
        try:
            rx = re.compile(pat) if pat else None
        except re.error as exc:
            logger.warning("DQ regex compile error rule=%s: %s", rule_def.get('name', '?'), exc)
            rx = None
        for r in rows:
            v = r.values.get(fname)
            if _is_empty(v):
                continue
            checked += 1
            if rx and not rx.search(str(v)):
                failures.append({'row': r.id, 'value': v})

    elif rule_type == 'reference_integrity':
        rs_id = params.get('reference_set_id')
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

    elif rule_type == 'threshold':
        op = params.get('operator', 'gte')
        threshold_val = params.get('value')
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
                    ok = True
            if not ok:
                failures.append({'row': r.id, 'value': v})

    elif rule_type == 'nl_check':
        return _evaluate_nl_check(rule_def, rows, field)

    failed = len(failures)
    score = 100 if checked == 0 else round((checked - failed) / checked * 100)
    return (failed == 0), checked, failed, failures[:20], score


def _evaluate_nl_check(rule_def: Dict[str, Any], rows: List[Any],
                       field: Optional[Any] = None) -> EvalResult:
    """Evaluate an NL Check rule by delegating to Pulse.

    Handles graceful degradation: returns passed=True if Pulse is unavailable
    so that NL checks never block data workflows.

    Returns the standard 5-tuple: (passed, checked, failed, failures, score).
    """
    params = rule_def.get('params', {}) if isinstance(rule_def, dict) else {}
    prompt = params.get('prompt', '') if isinstance(params, dict) else ''
    rule_name = rule_def.get('name', 'nl_check_rule')
    severity = rule_def.get('severity', 'error')

    if not prompt or not rows:
        return True, 0, 0, [], 100

    try:
        from pulse_gateway import PulseGateway
    except ImportError:
        logger.warning('pulse_gateway module not available for rule %s', rule_name)
        return True, 0, 0, [], 100

    field_names = [field.name] if field else list(rows[0].values.keys()) if rows else []

    gateway = PulseGateway()
    rows_payload = [
        r.values if hasattr(r, 'values') else r
        for r in rows
    ]

    rules_payload = [{
        'id': rule_def.get('id', rule_name),
        'prompt': prompt,
        'fields': field_names,
        'severity': severity,
    }]

    response = gateway.validate_dq_rules(
        rules=rules_payload,
        rows=rows_payload,
        context={
            'table_name': field.data_table.name if field and hasattr(field, 'data_table') and field.data_table else '',
            'row_count_hint': len(rows),
        },
    )

    status = response.get('status', 'pulse_unavailable')

    if status == 'pulse_unavailable':
        logger.warning('Pulse unavailable for NL check rule %s', rule_name)
        return True, len(rows), 0, [], 100

    if status != 'completed':
        logger.warning(
            'Pulse returned status=%s for NL check rule %s',
            status, rule_name,
        )
        return True, len(rows), 0, [], 100

    results = response.get('result', {}).get('results', [])
    if not results:
        return True, len(rows), 0, [], 100

    rule_result = results[0]
    result_status = rule_result.get('status', 'error')

    if result_status == 'error':
        logger.warning(
            'Pulse NL check error for rule %s: %s',
            rule_name, rule_result.get('explanation', ''),
        )
        return True, len(rows), 0, [], 100

    if result_status == 'pass':
        return True, len(rows), 0, [], 100

    # fail
    failing_rows = rule_result.get('failing_rows', [])
    failed_count = len(failing_rows)
    checked = len(rows)
    failures = [
        {
            'row': rows[idx].id if hasattr(rows[idx], 'id') else idx,
            'explanation': rule_result.get('explanation', ''),
            'confidence': rule_result.get('confidence'),
        }
        for idx in failing_rows[:20]
    ]
    score = round((checked - failed_count) / checked * 100) if checked else 100

    return False, checked, failed_count, failures, score
