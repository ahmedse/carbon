"""Tests for ai/knowledge/dq_retriever.py — Phase C retrieval + context assembly.

Phase 24 Phase C gate: retrieval-augmented suggest/nl_check context is a strict
superset of the pre-Phase-C baseline (table metadata only).  These tests prove
the retriever assembles field profiles, canonical per-type examples, and
similar existing rules — partitioned by org unit — and that the prompt builders
render that context (while still degrading cleanly without it).
"""
from django.test import TestCase

from core.models import Module
from dataschema.models import DataField, DataTable
from dq.models import DQRule, FieldProfile, RuleFieldAssignment
from mdm.models import OrgUnit

from ai.knowledge.dq_retriever import (
    retrieve_nl_check_context,
    retrieve_suggest_context,
)
from ai.engine_runtime import (
    _dq_suggest_prompt,
    _nl_rule_test_prompt,
    _suggest_columns,
)


class DqRetrieverTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(
            name='Retriever Org', slug='retriever-org', code='RET', org_type='division')
        self.other_org = OrgUnit.objects.create(
            name='Other Org', slug='other-org', code='OTH', org_type='division')
        self.module = Module.objects.create(name='Retriever Module', org_unit=self.org)
        self.other_module = Module.objects.create(
            name='Other Module', org_unit=self.other_org)

        self.table = DataTable.objects.create(
            name='fuel_consumption', title='Fuel Consumption', module=self.module)
        self.other_table = DataTable.objects.create(
            name='other_fuel', title='Other Fuel', module=self.other_module)

        self.amount = DataField.objects.create(
            data_table=self.table, name='amount', label='Amount', type='number')
        self.units = DataField.objects.create(
            data_table=self.table, name='units', label='Units', type='string')
        self.other_amount = DataField.objects.create(
            data_table=self.other_table, name='amount', label='Amount', type='number')

        FieldProfile.objects.create(
            data_field=self.amount, row_count=10, null_count=1, distinct_count=9,
            completeness_pct=90.0, uniqueness_pct=100.0, min_value='0',
            max_value='100', mean_value=50.0, top_values=['0', '1', '2'],
        )
        FieldProfile.objects.create(
            data_field=self.units, row_count=10, null_count=0, distinct_count=2,
            completeness_pct=100.0, uniqueness_pct=20.0, top_values=['L', 'kg'],
        )

        # In-scope rules bound to the target table (reuse candidates).
        self.r_not_null = self._rule(
            'amount required', 'not_null', {}, self.amount, self.table)
        self.r_range = self._rule(
            'amount 0-100', 'range', {'min': 0, 'max': 100},
            self.amount, self.table)

        # Out-of-scope rule (other org) — must NOT leak into scoped retrieval.
        self.r_other = self._rule(
            'other amount required', 'not_null', {},
            self.other_amount, self.other_table)

    def _rule(self, name, rule_type, params, field, table):
        rule = DQRule.objects.create(
            name=name, rule_type=rule_type, params=params, is_active=True,
            definition={
                'schema_version': 1, 'name': name, 'level': 'field',
                'dimension': 'validity', 'type': rule_type, 'severity': 'error',
                'active': True, 'params': params,
            },
        )
        RuleFieldAssignment.objects.create(
            rule=rule, data_field=field, data_table=table)
        return rule

    # ── suggest context ─────────────────────────────────────────────────────

    def test_retrieve_suggest_context_shape(self):
        ctx = retrieve_suggest_context(self.table.id)
        self.assertEqual(ctx['table']['table_id'], self.table.id)
        self.assertEqual(ctx['scope']['org_unit_id'], self.org.id)
        # Field profiles for both fields (latest-wins).
        self.assertEqual({p['field'] for p in ctx['field_profiles']},
                         {'amount', 'units'})
        # Canonical examples grouped by type, only in-scope rules.
        self.assertIn('not_null', ctx['canonical_examples'])
        self.assertIn('range', ctx['canonical_examples'])
        self.assertEqual(
            {r['rule_id'] for r in ctx['similar_rules']},
            {self.r_not_null.id, self.r_range.id},
        )

    def test_retrieve_suggest_context_partitions_by_org_unit(self):
        ctx = retrieve_suggest_context(self.table.id)
        # The out-of-scope rule must not appear anywhere in the context.
        collected = []
        for rules in ctx['canonical_examples'].values():
            collected.extend(r['rule_id'] for r in rules)
        collected.extend(r['rule_id'] for r in ctx['similar_rules'])
        self.assertNotIn(self.r_other.id, collected)

    def test_canonical_examples_dedup_identical_params(self):
        # A second identical in-scope not_null rule should not double the list.
        duplicate = self._rule(
            'amount required dup', 'not_null', {}, self.amount, self.table)
        ctx = retrieve_suggest_context(self.table.id)
        not_null_examples = ctx['canonical_examples']['not_null']
        self.assertEqual(len(not_null_examples), 1)
        self.assertIn(
            not_null_examples[0]['rule_id'], {self.r_not_null.id, duplicate.id})

    def test_retrieve_suggest_context_unknown_table(self):
        with self.assertRaises(DataTable.DoesNotExist):
            retrieve_suggest_context(999999)

    # ── nl_check context ────────────────────────────────────────────────────

    def test_retrieve_nl_check_context_resolves_field_profile(self):
        ctx = retrieve_nl_check_context(self.table.id, field_name='amount')
        self.assertEqual(ctx['field_profile']['field'], 'amount')
        self.assertEqual(ctx['field_profile']['min'], '0')
        self.assertIn(
            self.r_range.id, {r['rule_id'] for r in ctx['similar_rules']})

    def test_retrieve_nl_check_context_missing_field_profile_is_none(self):
        ctx = retrieve_nl_check_context(self.table.id, field_name='no_such')
        self.assertIsNone(ctx['field_profile'])
        # Similar rules still resolved from the table's fields.
        self.assertTrue(ctx['similar_rules'])

    # ── prompt builders ─────────────────────────────────────────────────────

    def test_suggest_columns_normalises_fields_columns_and_strings(self):
        fields = [{'name': 'a', 'type': 'number'}, {'name': 'b', 'type': 'string'}]
        self.assertEqual(len(_suggest_columns({'fields': fields})), 2)
        self.assertEqual(_suggest_columns({'columns': ['a', 'b']}),
                         [{'name': 'a'}, {'name': 'b'}])
        self.assertEqual(_suggest_columns({'fields': []}), [])

    def test_suggest_prompt_baseline_has_no_retrieval(self):
        prompt = _dq_suggest_prompt({'name': 't', 'description': 'd',
                                     'row_count': 3, 'fields': []})
        self.assertIn('Table name: t', prompt)
        self.assertNotIn('Column profiles', prompt)

    def test_suggest_prompt_includes_retrieval(self):
        retrieval = {
            'field_profiles': [{'field': 'amount', 'type': 'number'}],
            'canonical_examples': {'range': [{'rule_id': 1, 'rule_type': 'range'}]},
            'similar_rules': [{'rule_id': 2, 'rule_type': 'not_null'}],
        }
        prompt = _dq_suggest_prompt(
            {'name': 't', 'fields': [{'name': 'amount', 'type': 'number'}]},
            retrieval,
        )
        self.assertIn('Column profiles', prompt)
        self.assertIn('Canonical v1 rule definitions', prompt)
        self.assertIn('Existing rules on similar fields', prompt)

    def test_nl_rule_test_prompt_includes_retrieval(self):
        retrieval = {
            'field_profile': {'field': 'amount', 'min': '0', 'max': '100'},
            'similar_rules': [{'rule_id': 1, 'rule_type': 'range'}],
        }
        prompt = _nl_rule_test_prompt(
            'amount must be positive',
            [{'name': 'amount', 'type': 'number'}],
            'fuel_consumption',
            retrieval,
        )
        self.assertIn('Field profile (observed stats)', prompt)
        self.assertIn('Existing rules on similar fields', prompt)
        # Baseline (no retrieval) still works.
        baseline = _nl_rule_test_prompt(
            'amount must be positive',
            [{'name': 'amount', 'type': 'number'}],
            'fuel_consumption',
        )
        self.assertNotIn('Field profile (observed stats)', baseline)
