"""
dq/templates.py — Reusable, parameterizable rule template catalog (Phase 24-E).

The "emp-no case" from the design doc — a hardcoded
``{"employee_no": {"type": "regex", "params": {"pattern": "^\\d{4,5}$"}}}``
— becomes a catalog template, instantiated with a confirmation gate.

Templates are *definitions*, not rules: :func:`instantiate_rule_template`
returns a validated v1 definition (+ ``confirmation_required`` flag) and
never writes to the DB — the caller must confirm before creating a rule
(RULE_21: AI proposes, Carbon executes).

No model imports (mirrors ``dq/catalog.py``): importable at module load
time without a database.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from .rule_schema import validate_definition

__all__ = [
    'RULE_TEMPLATES',
    'list_rule_templates',
    'get_rule_template',
    'instantiate_rule_template',
    'validate_template_catalog',
]

# ── Template catalog ───────────────────────────────────────────────────────
# key → template. ``definition`` must pass rule_schema.validate_definition.
# ``confirmation_required`` is the RULE_21 gate every instantiation carries.
RULE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    'employee_no': {
        'label': 'Employee Number',
        'description': 'Employee numbers are exactly 4-5 digits.',
        'confirmation_required': True,
        'definition': {
            'schema_version': 1,
            'name': 'Employee Number Format',
            'level': 'field',
            'dimension': 'validity',
            'type': 'regex',
            'severity': 'warn',
            'active': True,
            'params': {'pattern': r'^\d{4,5}$'},
        },
    },
    'email': {
        'label': 'Email Address',
        'description': 'Basic email format check (regex).',
        'confirmation_required': True,
        'definition': {
            'schema_version': 1,
            'name': 'Email Format',
            'level': 'field',
            'dimension': 'validity',
            'type': 'regex',
            'severity': 'warn',
            'active': True,
            'params': {'pattern': r'^[^@\s]+@[^@\s]+\.[^@\s]+$'},
        },
    },
    'non_negative': {
        'label': 'Non-Negative',
        'description': 'Numeric values must be >= 0.',
        'confirmation_required': True,
        'definition': {
            'schema_version': 1,
            'name': 'Non-Negative Value',
            'level': 'field',
            'dimension': 'validity',
            'type': 'range',
            'severity': 'warn',
            'active': True,
            'params': {'min': 0},
        },
    },
    'required': {
        'label': 'Required Field',
        'description': 'Field must not be null.',
        'confirmation_required': True,
        'definition': {
            'schema_version': 1,
            'name': 'Required Field',
            'level': 'field',
            'dimension': 'completeness',
            'type': 'not_null',
            'severity': 'error',
            'active': True,
            'params': {},
        },
    },
}


def list_rule_templates() -> List[Dict[str, Any]]:
    """Return catalog metadata (key, label, description, gate flag)."""
    return [
        {
            'key': key,
            'label': t['label'],
            'description': t.get('description', ''),
            'confirmation_required': t.get('confirmation_required', True),
        }
        for key, t in sorted(RULE_TEMPLATES.items())
    ]


def get_rule_template(key: str) -> Dict[str, Any]:
    """Return the template dict for ``key`` (raises KeyError)."""
    if key not in RULE_TEMPLATES:
        raise KeyError(
            f'Unknown rule template: {key!r}. '
            f'Available: {sorted(RULE_TEMPLATES)}'
        )
    return RULE_TEMPLATES[key]


def instantiate_rule_template(
    key: str,
    *,
    table_name: str | None = None,
    field_name: str | None = None,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Instantiate a template into a validated v1 rule definition.

    Never writes to the database — returns the definition plus the RULE_21
    ``confirmation_required`` gate; the caller must confirm before creating
    the rule. ``overrides`` may replace any top-level definition key or
    merge into ``params`` (e.g. ``{'params': {'pattern': '^\\d{6}$'}}``).

    Returns::

        {
          'key': ...,
          'label': ...,
          'definition': {...},           # validated v1 definition
          'confirmation_required': True, # RULE_21 gate
          'errors': [...],               # [] when valid
        }
    """
    template = get_rule_template(key)
    definition = copy.deepcopy(template['definition'])

    if table_name:
        bindings = definition.setdefault('bindings', [])
        binding = {'table': table_name}
        if field_name:
            binding['field'] = field_name
        bindings.append(binding)

    if overrides:
        params = dict(definition.get('params') or {})
        for k, v in overrides.items():
            if k == 'params' and isinstance(v, dict):
                params.update(v)
            else:
                definition[k] = v
        definition['params'] = params

    errors = validate_definition(definition)
    return {
        'key': key,
        'label': template['label'],
        'definition': definition,
        'confirmation_required': template.get('confirmation_required', True),
        'errors': errors,
    }


def validate_template_catalog() -> List[Tuple[str, List[Dict[str, str]]]]:
    """Validate every template definition; return [(key, errors)] failures.

    Catalog integrity gate — a template that fails its own validation would
    poison every instantiation.
    """
    failures: List[Tuple[str, List[Dict[str, str]]]] = []
    for key, t in RULE_TEMPLATES.items():
        errors = validate_definition(t['definition'])
        if errors:
            failures.append((key, errors))
    return failures
