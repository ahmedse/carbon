"""
dq/typed_gate.py — Stateless DQ gate for typed models (ADR 0025).

The typed-model twin of ``gate.check_rows``: binds DQRules to concrete model
fields via ``ModelRuleAssignment`` and evaluates them against in-memory model
instances, reusing ``engine.evaluate``. Pure function — no DB writes.

``dq`` references models by ``model_label`` string (resolved via
``apps.get_model`` in ``ModelRuleAssignment.clean()``) and never imports a
hosted app (RULE_3).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from dq.engine import evaluate
from dq.gate import _build_message, _worst, _RowProxy
from dq.rule_schema import GATE_ELIGIBLE_TYPES

logger = logging.getLogger(__name__)


@dataclass
class _FieldProxy:
    """Minimal field object for ``engine.evaluate`` — supplies only ``.name``.

    ``engine.evaluate`` derives the target key from ``field.name``; a typed
    binding has no ``DataField``, so we pass this lightweight stand-in.
    """
    name: str


def check_instances(
    model_label: str, instances: List[Any], *, mode: str = "write"
) -> Dict[str, Any]:
    """Evaluate all gate-eligible DQ rules bound to ``model_label`` against instances.

    Args:
        model_label: Django app+model label, e.g. ``'people.Employee'``.
        instances: list of model instances (or any objects exposing the bound
            attributes via ``getattr``).
        mode: ``'write'`` or ``'import'`` — import mode also respects
            ``definition.enforcement.on_import``.

    Returns:
        The same verdict shape as ``gate.check_rows``::

            {
                "summary": {"blocked": int, "warned": int, "passed": int},
                "row_verdicts": [
                    {"row_index": int, "verdict": "pass"|"warn"|"block",
                     "failures": [
                         {"rule_id": int, "rule_name": str, "field": str,
                          "severity": str, "message": str}
                     ]}
                ]
            }

    Stateless — never writes to the DB (no ``DQResult`` rows).
    """
    instances = list(instances)

    # ── Fast path: no rows ───────────────────────────────────────────
    if not instances:
        return {
            'summary': {'blocked': 0, 'warned': 0, 'passed': 0},
            'row_verdicts': [],
        }

    from dq.models import ModelRuleAssignment

    assignments = (
        ModelRuleAssignment.objects
        .filter(model_label=model_label, is_active=True)
        .select_related('rule')
    )

    # ── Filter to gate-eligible rules with on_write enforcement ──────
    eligible_rules: List[Dict[str, Any]] = []
    for mra in assignments:
        rule = mra.rule
        if not rule.is_active or rule.archived:
            continue

        rule_type = rule.rule_type
        if rule_type not in GATE_ELIGIBLE_TYPES:
            continue

        definition = rule.definition or {}
        enforcement = definition.get('enforcement', {})
        if not enforcement.get('on_write', False):
            continue

        if mode == 'import' and enforcement.get('on_import') is False:
            continue

        eligible_rules.append({
            'rule': rule,
            'definition': definition,
            'type': rule_type,
            'severity': definition.get('severity', 'error'),
            'field_name': mra.field_name or None,
        })

    if not eligible_rules:
        return {
            'summary': {'blocked': 0, 'warned': 0, 'passed': len(instances)},
            'row_verdicts': [
                {'row_index': i, 'verdict': 'pass', 'failures': []}
                for i in range(len(instances))
            ],
        }

    # Project only the bound fields we actually need.
    bound_fields = sorted({er['field_name'] for er in eligible_rules if er['field_name']})

    row_verdicts: List[Dict[str, Any]] = []
    counts = {'blocked': 0, 'warned': 0, 'passed': 0}

    for i, instance in enumerate(instances):
        values = {fn: getattr(instance, fn, None) for fn in bound_fields}
        proxy = _RowProxy(id=i, values=values)

        row_verdict_str = 'pass'
        all_failures: List[Dict[str, Any]] = []

        for er in eligible_rules:
            field = _FieldProxy(name=er['field_name']) if er['field_name'] else None
            try:
                passed, checked, failed, failures, score = evaluate(
                    er['definition'], [proxy], field=field,
                )
            except Exception:
                logger.exception(
                    "Typed gate: rule %s failed to evaluate on %s",
                    er['rule'].id, model_label,
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
        "Typed gate check_instances model=%s mode=%s rows=%d %s",
        model_label, mode, len(instances),
        f"blocked={counts['blocked']} warned={counts['warned']} passed={counts['passed']}",
    )

    return {
        'summary': counts,
        'row_verdicts': row_verdicts,
    }
