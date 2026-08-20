"""Phase 24 (Phase A) — deterministic eval harness + catalog invariants.

A fixed golden corpus of rule definitions → expected EvalResult, run as pure
unit tests (no DB). This is the regression gate every later learning phase must
keep green: if a phase changes suggestion/retrieval/learning behavior, the
deterministic interpreter must still produce these exact verdicts.
"""
from django.test import SimpleTestCase

from dq.engine import evaluate
from dq.catalog import (
    RULE_TYPE_CATALOG, RULE_TYPE_CHOICES, RULE_TYPE_CODES,
    RULE_FIELD_TYPE_COMPAT, GATE_ELIGIBLE_TYPES,
)


class _Field:
    def __init__(self, name):
        self.name = name


class _Row:
    def __init__(self, rid, values):
        self.id = rid
        self.values = values


def _rule(rule_type, params=None, name='golden'):
    return {
        'schema_version': 1,
        'name': name,
        'level': 'field',
        'dimension': 'validity',
        'type': rule_type,
        'severity': 'error',
        'active': True,
        'params': params or {},
    }


# Each case: expected = (passed, checked_count, failed_count, score).
# sample_failures content is intentionally not asserted — only the verdict shape.
GOLDEN_SET = [
    {'id': 'not_null_all_present', 'rule': _rule('not_null'), 'field': 'x',
     'rows': [{'x': 1}, {'x': 2}], 'expected': (True, 2, 0, 100)},
    {'id': 'not_null_one_missing', 'rule': _rule('not_null'), 'field': 'x',
     'rows': [{'x': 1}, {'x': None}], 'expected': (False, 2, 1, 50)},
    {'id': 'unique_no_dupes', 'rule': _rule('unique'), 'field': 'x',
     'rows': [{'x': 'a'}, {'x': 'b'}], 'expected': (True, 2, 0, 100)},
    {'id': 'unique_dupes', 'rule': _rule('unique'), 'field': 'x',
     'rows': [{'x': 'a'}, {'x': 'a'}, {'x': 'b'}], 'expected': (False, 3, 2, 33)},
    {'id': 'allowed_values_ok', 'rule': _rule('allowed_values', {'values': ['a', 'b']}),
     'field': 'x', 'rows': [{'x': 'a'}, {'x': 'b'}], 'expected': (True, 2, 0, 100)},
    {'id': 'allowed_values_bad', 'rule': _rule('allowed_values', {'values': ['a', 'b']}),
     'field': 'x', 'rows': [{'x': 'a'}, {'x': 'c'}], 'expected': (False, 2, 1, 50)},
    {'id': 'range_in_bounds', 'rule': _rule('range', {'min': 0, 'max': 10}),
     'field': 'x', 'rows': [{'x': 5}, {'x': 10}], 'expected': (True, 2, 0, 100)},
    {'id': 'range_out_of_bounds', 'rule': _rule('range', {'min': 0, 'max': 10}),
     'field': 'x', 'rows': [{'x': 5}, {'x': 15}], 'expected': (False, 2, 1, 50)},
    {'id': 'regex_match', 'rule': _rule('regex', {'pattern': r'^\d+$'}),
     'field': 'x', 'rows': [{'x': '123'}], 'expected': (True, 1, 0, 100)},
    {'id': 'regex_no_match', 'rule': _rule('regex', {'pattern': r'^\d+$'}),
     'field': 'x', 'rows': [{'x': 'abc'}], 'expected': (False, 1, 1, 0)},
    {'id': 'threshold_gte', 'rule': _rule('threshold', {'operator': 'gte', 'value': 5}),
     'field': 'x', 'rows': [{'x': 5}, {'x': 4}], 'expected': (False, 2, 1, 50)},
    {'id': 'threshold_eq', 'rule': _rule('threshold', {'operator': 'eq', 'value': 5}),
     'field': 'x', 'rows': [{'x': 5}, {'x': 6}], 'expected': (False, 2, 1, 50)},
    {'id': 'nl_check_empty_prompt_noop', 'rule': _rule('nl_check', {}),
     'field': 'x', 'rows': [{'x': 'anything'}], 'expected': (True, 0, 0, 100)},
    {'id': 'anomaly_detect_skipped', 'rule': _rule('anomaly_detect', {}),
     'field': 'x', 'rows': [{'x': 1}], 'expected': (None, 0, 0, 0)},
]


class GoldenEvalHarnessTests(SimpleTestCase):
    """The golden-set gate: deterministic interpreter verdicts never regress."""

    def test_golden_set_verdicts(self):
        for case in GOLDEN_SET:
            with self.subTest(case=case['id']):
                field = _Field(case['field'])
                rows = [_Row(i, vals) for i, vals in enumerate(case['rows'], start=1)]
                result = evaluate(case['rule'], rows, field=field)
                passed, checked, failed, _sample, score = result
                exp_passed, exp_checked, exp_failed, exp_score = case['expected']
                self.assertEqual(passed, exp_passed, f"{case['id']}: passed")
                self.assertEqual(checked, exp_checked, f"{case['id']}: checked")
                self.assertEqual(failed, exp_failed, f"{case['id']}: failed")
                self.assertEqual(score, exp_score, f"{case['id']}: score")


class CatalogInvariantTests(SimpleTestCase):
    """The catalog must be internally consistent — derived structures cannot drift."""

    def test_derived_structures_are_in_sync(self):
        codes = [r['code'] for r in RULE_TYPE_CATALOG]
        self.assertEqual(codes, RULE_TYPE_CODES)
        self.assertEqual([c[0] for c in RULE_TYPE_CHOICES], codes)
        self.assertEqual(set(RULE_FIELD_TYPE_COMPAT.keys()), set(codes))
        self.assertTrue(GATE_ELIGIBLE_TYPES <= set(codes), 'gate-eligible must be a subset')

    def test_models_and_schema_reexport_match_catalog(self):
        from dq.models import RULE_TYPES as model_choices
        from dq.rule_schema import RULE_TYPES as schema_codes
        self.assertEqual([c[0] for c in model_choices], RULE_TYPE_CODES)
        self.assertEqual(schema_codes, RULE_TYPE_CODES)

    def test_no_duplicate_codes(self):
        codes = [r['code'] for r in RULE_TYPE_CATALOG]
        self.assertEqual(len(codes), len(set(codes)), 'catalog codes must be unique')
