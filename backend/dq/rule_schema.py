"""
dq/rule_schema.py — Pure Python validators for DQ rule JSON definition (v1).

No external dependencies. No jsonschema package. No raises — returns error list
mirroring the validate_row convention.

DAMA DMBOK2 dimensions: completeness, validity, accuracy, consistency,
timeliness, uniqueness, integrity, reasonability.
"""
import re
from typing import Any, Dict, List

# ── Constants ───────────────────────────────────────────────────────────────
# Phase 24 (Phase A): the vocabulary is externalized to dq/catalog.py (data,
# not code). Re-exported here for backward compatibility — existing call sites
# do `from dq.rule_schema import RULE_TYPES`, `GATE_ELIGIBLE_TYPES`, etc.
from .catalog import (  # noqa: E402
    RULE_TYPE_CODES as RULE_TYPES,
    RULE_LEVEL_CODES as RULE_LEVELS,
    DIMENSIONS,
    DIMENSION_CODES,
    SEVERITY_VALUES,
    THRESHOLD_OPERATORS,
    GATE_ELIGIBLE_TYPES,
    RULE_FIELD_TYPE_COMPAT,
    rule_field_type_compatible,
)


def validate_definition(d: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate a DQ rule JSON definition (v1).

    Returns:
        list of error dicts: [{'field': str, 'code': str, 'message': str}, ...]
        Empty list = valid. Never raises.
    """
    errors: List[Dict[str, str]] = []

    if not isinstance(d, dict):
        errors.append({'field': '_root', 'code': 'invalid_type',
                        'message': 'definition must be a JSON object'})
        return errors

    # ── schema_version ────────────────────────────────────────────────
    sv = d.get('schema_version')
    if sv != 1:
        errors.append({'field': 'schema_version', 'code': 'invalid_value',
                        'message': 'schema_version must be 1'})

    # ── name ──────────────────────────────────────────────────────────
    name = d.get('name')
    if not name or not isinstance(name, str) or not name.strip():
        errors.append({'field': 'name', 'code': 'required',
                        'message': 'name is required and must be a non-empty string'})

    # ── level ─────────────────────────────────────────────────────────
    level = d.get('level')
    if level not in RULE_LEVELS:
        errors.append({'field': 'level', 'code': 'invalid_value',
                        'message': f'level must be one of {sorted(RULE_LEVELS)}, got {level!r}'})

    # ── dimension ─────────────────────────────────────────────────────
    dimension = d.get('dimension')
    if dimension not in DIMENSION_CODES:
        errors.append({'field': 'dimension', 'code': 'invalid_value',
                        'message': f'dimension must be one of {sorted(DIMENSION_CODES)}, got {dimension!r}'})

    # ── type ──────────────────────────────────────────────────────────
    rule_type = d.get('type')
    if rule_type not in RULE_TYPES:
        errors.append({'field': 'type', 'code': 'invalid_value',
                        'message': f'type must be one of {RULE_TYPES}, got {rule_type!r}'})

    # ── severity ──────────────────────────────────────────────────────
    severity = d.get('severity')
    if severity not in SEVERITY_VALUES:
        errors.append({'field': 'severity', 'code': 'invalid_value',
                        'message': f'severity must be one of {sorted(SEVERITY_VALUES)}, got {severity!r}'})

    # ── active ────────────────────────────────────────────────────────
    active = d.get('active')
    if not isinstance(active, bool):
        errors.append({'field': 'active', 'code': 'invalid_type',
                        'message': 'active must be a boolean'})

    # ── bindings (optional — ADR-0006: rules are standalone; bindings applied separately) ──
    bindings = d.get('bindings')
    if bindings is not None:
        if not isinstance(bindings, list):
            errors.append({'field': 'bindings', 'code': 'invalid_type',
                            'message': 'bindings must be a list of {table, field} objects'})
        else:
            for i, b in enumerate(bindings):
                if not isinstance(b, dict):
                    errors.append({'field': f'bindings[{i}]', 'code': 'invalid_type',
                                    'message': 'each binding must be an object with table and optional field'})
                    continue
                if not b.get('table') or not isinstance(b['table'], str):
                    errors.append({'field': f'bindings[{i}].table', 'code': 'required',
                                    'message': 'binding table is required and must be a string'})

    # ── params (per-type validation) ──────────────────────────────────
    params = d.get('params', {})
    if rule_type in RULE_TYPES:
        errors.extend(_validate_params(rule_type, params))

    # ── enforcement ───────────────────────────────────────────────────
    enforcement = d.get('enforcement', {})
    if isinstance(enforcement, dict):
        on_write = enforcement.get('on_write')
        if on_write is True and rule_type in ('nl_check', 'anomaly_detect'):
            errors.append({'field': 'enforcement.on_write', 'code': 'invalid_value',
                            'message': f'enforcement.on_write cannot be true for {rule_type} rules'})
    # enforcement is optional; missing or non-dict is silently accepted.

    return errors


def _validate_params(rule_type: str, params: Any) -> List[Dict[str, str]]:
    """Validate params dict for a specific rule type."""
    errors: List[Dict[str, str]] = []

    if not isinstance(params, dict):
        errors.append({'field': 'params', 'code': 'invalid_type',
                        'message': 'params must be a JSON object'})
        return errors

    if rule_type == 'not_null':
        # no params needed — silently accept anything
        pass

    elif rule_type == 'unique':
        # no params needed — silently accept anything
        pass

    elif rule_type == 'allowed_values':
        if 'values' in params:
            vals = params['values']
            if not isinstance(vals, list) or len(vals) == 0:
                errors.append({'field': 'params.values', 'code': 'invalid_value',
                                'message': 'values must be a non-empty list'})
        if 'reference_set' in params:
            rs = params['reference_set']
            if not isinstance(rs, int) or rs <= 0:
                errors.append({'field': 'params.reference_set', 'code': 'invalid_type',
                                'message': 'reference_set must be a positive integer'})
        if 'values' not in params and 'reference_set' not in params:
            errors.append({'field': 'params', 'code': 'required',
                            'message': 'allowed_values requires either "values" (list) or "reference_set" (int)'})

    elif rule_type == 'range':
        has_min = 'min' in params
        has_max = 'max' in params
        if not has_min and not has_max:
            errors.append({'field': 'params', 'code': 'required',
                            'message': 'range requires at least one of min or max'})
        # range is an inclusive [min, max] bound with no comparison operator.
        # A stray ``operator`` key (a common LLM mistake for "positive number")
        # is rejected here rather than silently ignored — comparisons belong to
        # the ``threshold`` type.
        if 'operator' in params:
            errors.append({'field': 'params.operator', 'code': 'invalid_value',
                            'message': "range does not support operator; use type 'threshold' with operator gt/gte/lt/lte for inequality comparisons"})
        for key in ('min', 'max'):
            if key in params:
                try:
                    float(params[key])
                except (TypeError, ValueError):
                    errors.append({'field': f'params.{key}', 'code': 'invalid_type',
                                    'message': f'{key} must be numeric'})

    elif rule_type == 'regex':
        pattern = params.get('pattern', '')
        if not pattern or not isinstance(pattern, str):
            errors.append({'field': 'params.pattern', 'code': 'required',
                            'message': 'regex requires a non-empty pattern string'})
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append({'field': 'params.pattern', 'code': 'invalid_value',
                                'message': f'regex pattern does not compile: {exc}'})

    elif rule_type == 'reference_integrity':
        rs_id = params.get('reference_set_id')
        if rs_id is None:
            errors.append({'field': 'params.reference_set_id', 'code': 'required',
                            'message': 'reference_integrity requires reference_set_id (int)'})
        elif not isinstance(rs_id, int) or rs_id <= 0:
            errors.append({'field': 'params.reference_set_id', 'code': 'invalid_type',
                            'message': 'reference_set_id must be a positive integer'})

    elif rule_type == 'threshold':
        operator = params.get('operator', 'gte')
        if operator not in THRESHOLD_OPERATORS:
            errors.append({'field': 'params.operator', 'code': 'invalid_value',
                            'message': f'operator must be one of {sorted(THRESHOLD_OPERATORS)}, got {operator!r}'})
        if 'value' not in params:
            errors.append({'field': 'params.value', 'code': 'required',
                            'message': 'threshold requires a numeric value'})
        else:
            try:
                float(params['value'])
            except (TypeError, ValueError):
                errors.append({'field': 'params.value', 'code': 'invalid_type',
                                'message': 'value must be numeric'})

    elif rule_type == 'nl_check':
        prompt = params.get('prompt', '')
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            errors.append({'field': 'params.prompt', 'code': 'required',
                            'message': 'nl_check requires a non-empty prompt string'})

    elif rule_type == 'anomaly_detect':
        # Business-level (Phase 4): the prompt is declarative context for the
        # anomaly.detect payload; stats-first detection means no field params
        # to validate. Silently accept anything (like not_null/unique).
        pass

    return errors
