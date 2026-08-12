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
# Phase 4 (fail-visible, TASK-DQ-CORE-P4-PULSE design decision #1): `passed` is
# Optional — None means the rule could NOT be evaluated (Pulse unavailable/error)
# and callers must record DQResult(status='skipped_unavailable', passed=None) and
# exclude the rule from score denominators. Reverses the old silent auto-pass.
EvalResult = Tuple[Optional[bool], int, int, List[Dict], int]

# Sentinel returned by _evaluate_nl_check when Pulse cannot produce a verdict.
SKIPPED_UNAVAILABLE: EvalResult = (None, 0, 0, [], 0)


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

    elif rule_type == 'anomaly_detect':
        # Phase 4 (TASK-DQ-CORE-P4-PULSE): anomaly_detect rules are
        # payload-fed — their definitions go into the anomaly.detect job
        # payload, they are NOT row-evaluated. Never fabricate a verdict:
        # fail-visible returns the skipped sentinel instead of a silent pass.
        return SKIPPED_UNAVAILABLE

    failed = len(failures)
    score = 100 if checked == 0 else round((checked - failed) / checked * 100)
    return (failed == 0), checked, failed, failures[:20], score


def _evaluate_nl_check(rule_def: Dict[str, Any], rows: List[Any],
                       field: Optional[Any] = None) -> EvalResult:
    """Evaluate an NL Check rule by delegating to Pulse.

    Phase 4 fail-visible behavior (design decision #1): when Pulse is
    unreachable, errors, or returns a non-completed/verdict-less response,
    this returns `SKIPPED_UNAVAILABLE` (passed=None) instead of silently
    auto-passing. Callers map passed is None to
    DQResult(status='skipped_unavailable') and exclude the rule from score
    denominators — scores honestly show the gap.

    Only a missing prompt / empty row set is still a local no-op pass (that is
    a rule-config state, not a Pulse outage).

    Returns the standard 5-tuple: (passed, checked, failed, failures, score).
    """
    params = rule_def.get('params', {}) if isinstance(rule_def, dict) else {}
    prompt = params.get('prompt', '') if isinstance(params, dict) else ''
    rule_name = rule_def.get('name', 'nl_check_rule')
    severity = rule_def.get('severity', 'error')

    if not prompt or not rows:
        return True, 0, 0, [], 100

    from ai.providers.pulse import PulseProvider
    from ai.protocol import DqRuleInput, DqValidateRequest

    field_names = [field.name] if field else list(rows[0].values.keys()) if rows else []

    rows_payload = [
        r.values if hasattr(r, 'values') else r
        for r in rows
    ]

    request = DqValidateRequest(
        rules=[
            DqRuleInput(
                id=str(rule_def.get('id', rule_name)),
                prompt=prompt,
                fields=field_names,
                severity=severity,
            )
        ],
        rows=rows_payload,
        context={
            'table_name': field.data_table.name if field and hasattr(field, 'data_table') and field.data_table else '',
            'row_count_hint': len(rows),
        },
    )

    response = PulseProvider().validate_dq(request)

    if response.status == 'provider_unavailable':
        logger.warning('Pulse unavailable for NL check rule %s', rule_name)
        return SKIPPED_UNAVAILABLE

    if response.status != 'completed':
        logger.warning(
            'Pulse returned status=%s for NL check rule %s',
            response.status, rule_name,
        )
        return SKIPPED_UNAVAILABLE

    if not response.results:
        logger.warning('Pulse NL check returned no results for rule %s', rule_name)
        return SKIPPED_UNAVAILABLE

    rule_result = response.results[0]
    result_status = rule_result.status

    # Pulse may return "error" when it can't evaluate (insufficient data, etc).
    # Treat as skipped — not a pass, not a fail, just unavailable.
    if result_status not in ('pass', 'fail'):
        logger.warning(
            'Pulse NL check status=%s for rule %s: %s',
            result_status, rule_name, rule_result.explanation or '',
        )
        return SKIPPED_UNAVAILABLE

    if result_status == 'pass':
        return True, len(rows), 0, [], 100

    # fail
    failing_rows = rule_result.failing_rows or []
    failed_count = len(failing_rows)
    checked = len(rows)
    failures = [
        {
            'row': rows[idx].id if hasattr(rows[idx], 'id') else idx,
            'explanation': rule_result.explanation or '',
            'confidence': rule_result.confidence,
        }
        for idx in failing_rows[:20]
    ]
    score = round((checked - failed_count) / checked * 100) if checked else 100

    return False, checked, failed_count, failures, score
