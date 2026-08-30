"""
Typed gate tests — ModelRuleAssignment binding + check_instances regression
(DQ-CORE-TYPED-BIND / RULE_11).

``dq`` binds rules to typed models by label (ADR 0025) and never imports a
hosted app. These tests use the core ``mdm.ReferenceValue`` model label (and
``dq.DQRule`` for the non-concrete-field case) so the ``dq`` app stays decoupled
(RULE_3).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from dq.models import DQRule, DQResult, ModelRuleAssignment
from dq.typed_gate import check_instances

MODEL_LABEL = 'mdm.ReferenceValue'


def _rule_definition(name, rule_type, dimension, params, severity='error'):
    return {
        'schema_version': 1,
        'name': name,
        'level': 'field',
        'dimension': dimension,
        'type': rule_type,
        'severity': severity,
        'params': params,
        'enforcement': {'on_write': True},
        'active': True,
    }


def _bind_rule(name, rule_type, dimension, params, field_name,
               model_label=MODEL_LABEL, severity='error'):
    rule = DQRule.objects.create(
        name=name,
        rule_type=rule_type,
        rule_level='field_validation',
        is_active=True,
        definition=_rule_definition(name, rule_type, dimension, params, severity),
    )
    mra = ModelRuleAssignment.objects.create(
        rule=rule, model_label=model_label, field_name=field_name, is_active=True,
    )
    return rule, mra


class ModelRuleAssignmentCleanTests(TestCase):
    """clean() validates model_label and field_name via apps.get_model."""

    @classmethod
    def setUpTestData(cls):
        cls.rule = DQRule.objects.create(
            name='clean-rule', rule_type='not_null', rule_level='field_validation',
            is_active=True,
            definition=_rule_definition('clean-rule', 'not_null', 'completeness', {}),
        )

    def test_valid_assignment_cleans(self):
        mra = ModelRuleAssignment(rule=self.rule, model_label=MODEL_LABEL, field_name='code')
        mra.full_clean()  # should not raise

    def test_blank_field_cleans(self):
        mra = ModelRuleAssignment(rule=self.rule, model_label=MODEL_LABEL, field_name='')
        mra.full_clean()

    def test_unknown_model_label_rejected(self):
        mra = ModelRuleAssignment(
            rule=self.rule, model_label='doesnotexist.Nope', field_name='code'
        )
        with self.assertRaises(ValidationError):
            mra.full_clean()

    def test_malformed_model_label_rejected(self):
        mra = ModelRuleAssignment(rule=self.rule, model_label='no_dot_here', field_name='code')
        with self.assertRaises(ValidationError):
            mra.full_clean()

    def test_unknown_field_name_rejected(self):
        mra = ModelRuleAssignment(
            rule=self.rule, model_label=MODEL_LABEL, field_name='not_a_field'
        )
        with self.assertRaises(ValidationError):
            mra.full_clean()

    def test_non_concrete_field_rejected(self):
        # 'tags' is a ManyToManyField on DQRule → not a concrete field.
        mra = ModelRuleAssignment(rule=self.rule, model_label='dq.DQRule', field_name='tags')
        with self.assertRaises(ValidationError):
            mra.full_clean()

    def test_str_format(self):
        mra = ModelRuleAssignment(rule=self.rule, model_label=MODEL_LABEL, field_name='code')
        self.assertEqual(str(mra), f'{self.rule.name} → {MODEL_LABEL}.code')
        mra_blank = ModelRuleAssignment(rule=self.rule, model_label=MODEL_LABEL, field_name='')
        self.assertEqual(str(mra_blank), f'{self.rule.name} → {MODEL_LABEL}.*')


class CheckInstancesRuleTests(TestCase):
    """not_null / range / allowed_values evaluate pass/fail against instances."""

    def test_not_null_pass_and_fail(self):
        _bind_rule('code-required', 'not_null', 'completeness', {}, 'code')
        instances = [SimpleNamespace(code='A'), SimpleNamespace(code=None)]
        result = check_instances(MODEL_LABEL, instances)
        self.assertEqual(result['summary']['blocked'], 1)
        self.assertEqual(result['summary']['passed'], 1)
        self.assertEqual(result['row_verdicts'][0]['verdict'], 'pass')
        self.assertEqual(result['row_verdicts'][1]['verdict'], 'block')

    def test_range_pass_and_fail(self):
        _bind_rule('sort-order-range', 'range', 'validity', {'min': 0, 'max': 100}, 'sort_order')
        instances = [SimpleNamespace(sort_order=5), SimpleNamespace(sort_order=150)]
        result = check_instances(MODEL_LABEL, instances)
        self.assertEqual(result['summary']['blocked'], 1)
        self.assertEqual(result['summary']['passed'], 1)
        self.assertEqual(result['row_verdicts'][0]['verdict'], 'pass')
        self.assertEqual(result['row_verdicts'][1]['verdict'], 'block')

    def test_allowed_values_pass_and_fail(self):
        _bind_rule('code-allowed', 'allowed_values', 'validity', {'values': ['A', 'B']}, 'code')
        instances = [SimpleNamespace(code='A'), SimpleNamespace(code='Z')]
        result = check_instances(MODEL_LABEL, instances)
        self.assertEqual(result['summary']['blocked'], 1)
        self.assertEqual(result['summary']['passed'], 1)

    def test_inactive_assignment_skipped(self):
        _rule, mra = _bind_rule('inactive-rule', 'not_null', 'completeness', {}, 'code')
        mra.is_active = False
        mra.save()
        result = check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
        self.assertEqual(result['summary']['passed'], 1)

    def test_archived_rule_skipped(self):
        rule, _mra = _bind_rule('archived-rule', 'not_null', 'completeness', {}, 'code')
        rule.archived = True
        rule.save()
        result = check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
        self.assertEqual(result['summary']['passed'], 1)

    def test_no_assignments_all_pass(self):
        result = check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
        self.assertEqual(result['summary']['passed'], 1)
        self.assertEqual(result['row_verdicts'][0]['verdict'], 'pass')

    def test_empty_instances(self):
        _bind_rule('empty-rule', 'not_null', 'completeness', {}, 'code')
        result = check_instances(MODEL_LABEL, [])
        self.assertEqual(result['summary']['passed'], 0)
        self.assertEqual(result['row_verdicts'], [])


class CheckInstancesShapeTests(TestCase):
    """Verdict shape matches gate.check_rows."""

    def test_verdict_shape_matches_gate(self):
        _bind_rule('shape-rule', 'not_null', 'completeness', {}, 'code')
        result = check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
        self.assertEqual(set(result.keys()), {'summary', 'row_verdicts'})
        self.assertEqual(set(result['summary'].keys()), {'blocked', 'warned', 'passed'})
        row_verdict = result['row_verdicts'][0]
        self.assertEqual(set(row_verdict.keys()), {'row_index', 'verdict', 'failures'})
        self.assertEqual(row_verdict['verdict'], 'block')
        failure = row_verdict['failures'][0]
        self.assertEqual(
            set(failure.keys()), {'rule_id', 'rule_name', 'field', 'severity', 'message'}
        )
        self.assertEqual(failure['field'], 'code')

    def test_no_dqresult_created(self):
        _bind_rule('purity-rule', 'not_null', 'completeness', {}, 'code')
        check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
        self.assertEqual(DQResult.objects.count(), 0)


class CheckInstancesPurityTests(TestCase):
    """check_instances is pure — no DB writes."""

    @classmethod
    def setUpTestData(cls):
        cls.rule, cls.mra = _bind_rule('pure-rule', 'not_null', 'completeness', {}, 'code')

    def test_check_instances_no_db_writes(self):
        with patch.object(DQRule, 'save') as mock_rule_save, \
             patch.object(ModelRuleAssignment, 'save') as mock_mra_save, \
             patch.object(DQResult, 'save') as mock_result_save, \
             patch.object(DQResult.objects, 'create') as mock_result_create:
            result = check_instances(MODEL_LABEL, [SimpleNamespace(code=None)])
            self.assertIn('summary', result)
            mock_rule_save.assert_not_called()
            mock_mra_save.assert_not_called()
            mock_result_save.assert_not_called()
            mock_result_create.assert_not_called()
