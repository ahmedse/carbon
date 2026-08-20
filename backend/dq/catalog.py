"""
dq/catalog.py — Seedable catalog for the DQ rule vocabulary (data, not code).

Phase 24 (Adaptive Learning DQ Core) Phase A: the DQ interpreter's vocabulary
was previously hardcoded as tuples/lists split across `dq/models.py` and
`dq/rule_schema.py`. This module is now the single source of truth.

Adding a new rule type = adding one row to `RULE_TYPE_CATALOG`. The choices
tuples, the code list, the field-type applicability map, and the gate-eligibility
set are all *derived* from that row list, so they can never drift out of sync.

No model imports (mirrors `rule_schema.py` / `engine.py` / `contradiction.py`):
this module is importable at module load time without a database.
"""
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

__all__ = [
    'RULE_TYPE_CATALOG',
    'RULE_TYPE_CHOICES',
    'RULE_TYPE_CODES',
    'RULE_LEVEL_CHOICES',
    'RULE_LEVEL_CODES',
    'DIMENSIONS',
    'DIMENSION_CODES',
    'SEVERITY_CHOICES',
    'SEVERITY_VALUES',
    'THRESHOLD_OPERATORS',
    'GATE_ELIGIBLE_TYPES',
    'RULE_FIELD_TYPE_COMPAT',
    'rule_field_type_compatible',
]

# ── Rule types ──────────────────────────────────────────────────────────────
# Each row is the catalog entry. ``field_types`` is the set of DataField.type
# values a rule can apply to (``None`` = any). ``gate_eligible`` marks rules the
# write-time CBAC gate enforces (vs. job/business-level rules).
RULE_TYPE_CATALOG: List[Dict[str, Any]] = [
    {'code': 'not_null', 'label': 'Not Null',
     'dimension': 'completeness', 'field_types': None, 'gate_eligible': True},
    {'code': 'unique', 'label': 'Unique',
     'dimension': 'uniqueness', 'field_types': None, 'gate_eligible': True},
    {'code': 'allowed_values', 'label': 'Allowed Values',
     'dimension': 'validity',
     'field_types': {'string', 'text', 'select', 'number', 'date', 'boolean'},
     'gate_eligible': True},
    {'code': 'range', 'label': 'Range',
     'dimension': 'validity', 'field_types': {'number'}, 'gate_eligible': True},
    {'code': 'regex', 'label': 'Regex',
     'dimension': 'validity', 'field_types': {'string', 'text'}, 'gate_eligible': True},
    {'code': 'reference_integrity', 'label': 'Reference Integrity',
     'dimension': 'integrity', 'field_types': {'reference', 'select'},
     'gate_eligible': True},
    {'code': 'threshold', 'label': 'Threshold',
     'dimension': 'reasonability', 'field_types': {'number'}, 'gate_eligible': True},
    {'code': 'nl_check', 'label': 'NL Check',
     'dimension': 'validity', 'field_types': None, 'gate_eligible': False},
    # Phase 4 — feeds the anomaly.detect job payload; not row-evaluated.
    {'code': 'anomaly_detect', 'label': 'Anomaly Detect',
     'dimension': 'reasonability', 'field_types': None, 'gate_eligible': False},
]

# Derived — never edit by hand; derived from RULE_TYPE_CATALOG.
RULE_TYPE_CHOICES: List[Tuple[str, str]] = [
    (r['code'], r['label']) for r in RULE_TYPE_CATALOG
]
RULE_TYPE_CODES: List[str] = [r['code'] for r in RULE_TYPE_CATALOG]
RULE_FIELD_TYPE_COMPAT: Dict[str, Optional[Set[str]]] = {
    r['code']: r['field_types'] for r in RULE_TYPE_CATALOG
}
GATE_ELIGIBLE_TYPES: FrozenSet[str] = frozenset(
    r['code'] for r in RULE_TYPE_CATALOG if r['gate_eligible']
)

# ── Rule levels ──────────────────────────────────────────────────────────────
# Choices (code, label) for the DQRule.rule_level column; codes for the v1
# definition `level` key ('field' / 'business').
RULE_LEVEL_CHOICES: List[Tuple[str, str]] = [
    ('field_validation', 'Field Validation'),
    ('business_rule', 'Business Rule'),
]
RULE_LEVEL_CODES: Set[str] = {'field', 'business'}

# ── DAMA DMBOK2 quality dimensions ───────────────────────────────────────────
DIMENSIONS: List[Tuple[str, str]] = [
    ('completeness', 'Completeness'),
    ('validity', 'Validity'),
    ('accuracy', 'Accuracy'),
    ('consistency', 'Consistency'),
    ('timeliness', 'Timeliness'),
    ('uniqueness', 'Uniqueness'),
    ('integrity', 'Integrity'),
    ('reasonability', 'Reasonability'),
]
DIMENSION_CODES: Set[str] = {d[0] for d in DIMENSIONS}

# ── Severity ─────────────────────────────────────────────────────────────────
SEVERITY_CHOICES: List[Tuple[str, str]] = [
    ('info', 'Info'), ('warn', 'Warn'), ('error', 'Error'),
]
SEVERITY_VALUES: Set[str] = {s[0] for s in SEVERITY_CHOICES}

# ── Threshold operators ──────────────────────────────────────────────────────
THRESHOLD_OPERATORS: FrozenSet[str] = frozenset(
    {'gte', 'gt', 'lte', 'lt', 'eq', 'neq'}
)


def rule_field_type_compatible(rule_type: str, field_type: str) -> bool:
    """Return True if ``rule_type`` can apply to a DataField of ``field_type``."""
    allowed = RULE_FIELD_TYPE_COMPAT.get(rule_type)
    if allowed is None:
        return True
    return field_type in allowed
