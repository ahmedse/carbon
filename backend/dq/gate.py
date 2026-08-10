"""
dq/gate.py — Stateless DQ Gate.

Enforces field-level DQ rules at write time and import.
Pure function — no DB writes, no side effects.
Reads rules from DB, evaluates rows, returns verdicts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.db.models import Prefetch

from dq.rule_schema import GATE_ELIGIBLE_TYPES
from dq.engine import evaluate

logger = logging.getLogger(__name__)

# ── Lightweight row wrapper ──────────────────────────────────────────────────
# engine.evaluate() expects objects with .id and .values attributes.
# Since the gate may run on raw dicts before DataRow creation, we wrap them.


@dataclass
class _RowProxy:
    """Minimal row object for engine.evaluate()."""
    id: Any
    values: Dict[str, Any]


# ── Severity order ───────────────────────────────────────────────────────────

_SEVERITY_RANK = {'info': 0, 'warn': 1, 'error': 2}


def _worst(a: str, b: str) -> str:
    """Return the more severe of two severity levels."""
    return a if _SEVERITY_RANK.get(a, 0) >= _SEVERITY_RANK.get(b, 0) else b


# ── Gate ────────────────────────────────────────────────────────────────────

def check_rows(table, rows: List[Dict[str, Any]], *, mode: str = "write") -> Dict[str, Any]:
    """Evaluate all gate-eligible DQ rules against a list of raw row dicts.

    Args:
        table: DataTable instance (or None).
        rows: list of raw value dicts, e.g. [{'field1': val1}, ...].
        mode: 'write' or 'import'. 'import' mode also respects
              definition.enforcement.on_import.

    Returns:
        {
            "summary": {"blocked": int, "warned": int, "passed": int},
            "row_verdicts": [
                {
                    "row_index": int,
                    "verdict": "pass" | "warn" | "block",
                    "failures": [
                        {"rule_id": int, "rule_name": str, "field": str,
                         "severity": str, "message": str}
                    ]
                }
            ]
        }
    """
    # ── Fast path: no table or no rows ────────────────────────────────
    if table is None or not rows:
        n = len(rows) if rows else 0
        return {
            'summary': {'blocked': 0, 'warned': 0, 'passed': n},
            'row_verdicts': [
                {'row_index': i, 'verdict': 'pass', 'failures': []}
                for i in range(n)
            ],
        }

    # ── Load gate-eligible rules ──────────────────────────────────────
    from dq.models import DQRule, RuleFieldAssignment

    # Find rule IDs bound to this table via M2M
    bound_rule_ids = RuleFieldAssignment.objects.filter(
        data_table=table,
    ).values_list('rule_id', flat=True).distinct()

    if not bound_rule_ids:
        return {
            'summary': {'blocked': 0, 'warned': 0, 'passed': len(rows)},
            'row_verdicts': [
                {'row_index': i, 'verdict': 'pass', 'failures': []}
                for i in range(len(rows))
            ],
        }

    # Fetch rules with their field assignments
    rules = DQRule.objects.filter(
        id__in=bound_rule_ids,
        is_active=True,
        archived=False,
    ).prefetch_related(
        Prefetch('field_assignments', queryset=RuleFieldAssignment.objects.filter(data_table=table)),
    ).select_related('created_by')

    # ── Filter to gate-eligible rules with on_write enforcement ──────
    eligible_rules: List[Dict[str, Any]] = []
    for rule in rules:
        rule_type = rule.rule_type
        definition = rule.definition or {}

        # Only gate-eligible types
        if rule_type not in GATE_ELIGIBLE_TYPES:
            continue

        # Must have on_write enabled
        enforcement = definition.get('enforcement', {})
        if not enforcement.get('on_write', False):
            continue

        # In import mode, check on_import
        if mode == 'import' and enforcement.get('on_import') is False:
            continue

        # Resolve bound field (first field assignment for this rule on this table)
        field_name = None
        field_obj = None
        for fa in rule.field_assignments.all():
            if fa.data_table_id == table.id:
                if fa.data_field:
                    field_name = fa.data_field.name
                    field_obj = fa.data_field
                break

        eligible_rules.append({
            'rule': rule,
            'definition': definition,
            'type': rule_type,
            'severity': definition.get('severity', 'error'),
            'field_name': field_name,
            'field_obj': field_obj,
        })

    if not eligible_rules:
        return {
            'summary': {'blocked': 0, 'warned': 0, 'passed': len(rows)},
            'row_verdicts': [
                {'row_index': i, 'verdict': 'pass', 'failures': []}
                for i in range(len(rows))
            ],
        }

    # ── Evaluate each row against every eligible rule ─────────────────
    row_verdicts: List[Dict[str, Any]] = []
    counts = {'blocked': 0, 'warned': 0, 'passed': 0}

    for i, row_dict in enumerate(rows):
        if not isinstance(row_dict, dict):
            row_verdicts.append({
                'row_index': i, 'verdict': 'pass', 'failures': [],
            })
            counts['passed'] += 1
            continue

        proxy = _RowProxy(id=i, values=row_dict)
        row_verdict_str = 'pass'
        all_failures: List[Dict[str, Any]] = []

        for er in eligible_rules:
            try:
                passed, checked, failed, failures, score = evaluate(
                    er['definition'],
                    [proxy],
                    field=er['field_obj'],
                )
            except Exception:
                logger.exception(
                    "Gate: rule %s failed to evaluate on table %s",
                    er['rule'].id, table.id,
                )
                continue

            if not passed and failed > 0:
                severity = er['severity']
                for f in failures:
                    all_failures.append({
                        'rule_id': er['rule'].id,
                        'rule_name': er['definition'].get('name', er['rule'].name),
                        'field': er['field_name'] or '__row__',
                        'severity': severity,
                        'message': _build_message(er, f),
                    })
                row_verdict_str = _worst(row_verdict_str, severity)

        row_verdicts.append({
            'row_index': i,
            'verdict': 'block' if row_verdict_str == 'error' else row_verdict_str,
            'failures': all_failures,
        })
        final = 'block' if row_verdict_str == 'error' else row_verdict_str
        counts['blocked' if final == 'block' else
                'warned' if row_verdict_str == 'warn' else 'passed'] += 1

    logger.info(
        "Gate check_rows table=%s mode=%s rows=%d %s",
        table.id, mode, len(rows),
        f"blocked={counts['blocked']} warned={counts['warned']} passed={counts['passed']}",
    )

    return {
        'summary': counts,
        'row_verdicts': row_verdicts,
    }


def _build_message(er: Dict[str, Any], failure: Dict[str, Any]) -> str:
    """Build a human-readable message from a rule failure."""
    rule_type = er['type']
    severity = er['severity']
    rule_name = er['definition'].get('name', 'rule')
    value = failure.get('value', 'N/A')
    row = failure.get('row', '?')

    if rule_type == 'not_null':
        return f"'{rule_name}': required value is missing"
    elif rule_type == 'unique':
        return f"'{rule_name}': duplicate value '{value}' found"
    elif rule_type == 'allowed_values':
        return f"'{rule_name}': value '{value}' is not in the allowed set"
    elif rule_type == 'range':
        params = er['definition'].get('params', {})
        lo = params.get('min')
        hi = params.get('max')
        parts = []
        if lo is not None:
            parts.append(f"min {lo}")
        if hi is not None:
            parts.append(f"max {hi}")
        constraint = ', '.join(parts)
        return f"'{rule_name}': value '{value}' is outside range ({constraint})"
    elif rule_type == 'regex':
        return f"'{rule_name}': value '{value}' does not match required pattern"
    elif rule_type == 'reference_integrity':
        return f"'{rule_name}': value '{value}' not found in reference data"
    elif rule_type == 'threshold':
        params = er['definition'].get('params', {})
        op = params.get('operator', 'gte')
        tv = params.get('value', '?')
        return f"'{rule_name}': value '{value}' must be {op} {tv}"
    return f"'{rule_name}': validation failed (severity: {severity})"
