"""Tests for ai/knowledge/dq_graph.py — DQ knowledge-graph read projection.

Phase 24 Phase B gate: graph queries return correct lineage and rule/field
relationships for seeded golden tables.
"""
from django.test import TestCase

from catalog.models import AssetProfile, DataDomain
from core.models import Module
from dataschema.models import DataField, DataTable, TableRelation
from dq.models import DQRule, RuleFieldAssignment
from mdm.models import OrgUnit

from ai.knowledge.dq_graph import (
    build_dq_graph,
    field_gaps,
    fields_for_rule,
    rules_for_field,
    similar_fields,
    table_context,
    table_lineage,
)


class DqGraphTests(TestCase):
    def setUp(self):
        self.org_unit = OrgUnit.objects.create(
            name='DG Org', code='DGO', org_type='division')
        self.module = Module.objects.create(name='DG Module', org_unit=self.org_unit)

        self.src_table = DataTable.objects.create(
            name='src_fuel', title='Source Fuel', module=self.module)
        self.dst_table = DataTable.objects.create(
            name='dst_fuel', title='Dest Fuel', module=self.module)
        self.other_table = DataTable.objects.create(
            name='unrelated', title='Unrelated', module=self.module)

        # src fields: f1 has rules, f2/f3 are gaps
        self.f1 = DataField.objects.create(
            data_table=self.src_table, name='amount', label='Amount', type='number')
        self.f2 = DataField.objects.create(
            data_table=self.src_table, name='notes', label='Notes', type='text')
        self.f3 = DataField.objects.create(
            data_table=self.src_table, name='quantity', label='Quantity', type='number')
        self.dst_field = DataField.objects.create(
            data_table=self.dst_table, name='amount', label='Amount', type='number')

        self.domain = DataDomain.objects.create(name='Energy', slug='energy')
        AssetProfile.objects.create(data_table=self.src_table, domain=self.domain)

        # rule bindings: f1 has a range + a disjoint range (conflict), and
        # table-level rule on src_table
        self.r1 = self._rule('amount 0-10', 'range', {'min': 0, 'max': 10})
        self.r2 = self._rule('amount 20-30', 'range', {'min': 20, 'max': 30})
        self.table_rule = self._rule('table-level', 'not_null', {})
        RuleFieldAssignment.objects.create(
            rule=self.r1, data_field=self.f1, data_table=self.src_table)
        RuleFieldAssignment.objects.create(
            rule=self.r2, data_field=self.f1, data_table=self.src_table)
        RuleFieldAssignment.objects.create(
            rule=self.table_rule, data_field=None, data_table=self.src_table)

        # lineage: src_table.amount -> dst_table.amount (one_to_many)
        self.rel = TableRelation.objects.create(
            from_table=self.src_table, from_field=self.f1,
            to_table=self.dst_table, to_field=self.dst_field,
            relation_type='one_to_many', label='fuel flows')

    def _rule(self, name, rule_type, params):
        return DQRule.objects.create(
            name=name, rule_type=rule_type, params=params, is_active=True,
            definition={
                'schema_version': 1, 'name': name, 'level': 'field',
                'dimension': 'validity', 'type': rule_type, 'severity': 'error',
                'active': True, 'params': params,
            },
        )

    # ── rule ↔ field ────────────────────────────────────────────────────────

    def test_rules_for_field(self):
        rules = rules_for_field(self.f1.id)
        self.assertEqual({r['rule_id'] for r in rules}, {self.r1.id, self.r2.id})
        self.assertTrue(all(r['rule_type'] == 'range' for r in rules))

    def test_fields_for_rule(self):
        fields = fields_for_rule(self.r1.id)
        self.assertEqual([f['field_id'] for f in fields], [self.f1.id])

    # ── gap analysis ────────────────────────────────────────────────────────

    def test_field_gaps(self):
        gaps = field_gaps(self.src_table.id)
        self.assertEqual({g['field_id'] for g in gaps}, {self.f2.id, self.f3.id})

    # ── lineage ─────────────────────────────────────────────────────────────

    def test_table_lineage(self):
        lineage = table_lineage(self.src_table.id)
        self.assertEqual(len(lineage['downstream']), 1)
        self.assertEqual(
            lineage['downstream'][0]['to_table_id'], self.dst_table.id)
        self.assertEqual(
            lineage['downstream'][0]['to_field_name'], 'amount')

        reverse = table_lineage(self.dst_table.id)
        self.assertEqual(len(reverse['upstream']), 1)
        self.assertEqual(
            reverse['upstream'][0]['from_table_id'], self.src_table.id)

    # ── context ─────────────────────────────────────────────────────────────

    def test_table_context(self):
        ctx = table_context(self.src_table.id)
        self.assertEqual(ctx['module']['name'], 'DG Module')
        self.assertEqual(ctx['org_unit']['code'], 'DGO')
        self.assertEqual(ctx['domain']['slug'], 'energy')

    # ── similarity ──────────────────────────────────────────────────────────

    def test_similar_fields_same_type_excludes_self(self):
        similar = similar_fields(self.f1.id)
        ids = {f['field_id'] for f in similar}
        self.assertIn(self.f3.id, ids)          # same type, on src_table
        self.assertIn(self.dst_field.id, ids)   # same type, other table
        self.assertNotIn(self.f1.id, ids)       # self excluded
        self.assertNotIn(self.f2.id, ids)       # different type

    # ── graph envelope ──────────────────────────────────────────────────────

    def test_build_dq_graph_scoped_to_table(self):
        graph = build_dq_graph(self.src_table.id)
        node_ids = {n['id'] for n in graph['nodes']}
        # tables: src + lineage neighbor dst
        self.assertIn(f'table:{self.src_table.id}', node_ids)
        self.assertIn(f'table:{self.dst_table.id}', node_ids)
        self.assertNotIn(f'table:{self.other_table.id}', node_ids)
        # fields of src
        self.assertIn(f'field:{self.f1.id}', node_ids)
        # rules bound to src
        self.assertIn(f'rule:{self.r1.id}', node_ids)
        self.assertIn(f'rule:{self.r2.id}', node_ids)
        self.assertIn(f'rule:{self.table_rule.id}', node_ids)

        edges = graph['edges']
        relationships = {(e['source'], e['target'], e['relationship'])
                         for e in edges}
        self.assertIn(
            (f'table:{self.src_table.id}', f'field:{self.f1.id}', 'contains'),
            relationships)
        self.assertIn(
            (f'field:{self.f1.id}', f'rule:{self.r1.id}', 'enforced_by'),
            relationships)
        self.assertIn(
            (f'table:{self.src_table.id}', f'rule:{self.table_rule.id}', 'enforced_by'),
            relationships)
        self.assertIn(
            (f'table:{self.src_table.id}', f'table:{self.dst_table.id}', 'one_to_many'),
            relationships)

    def test_build_dq_graph_unknown_table_empty(self):
        self.assertEqual(build_dq_graph(999999), {'nodes': [], 'edges': []})

    # ── services inventory ──────────────────────────────────────────────────

    def test_table_rule_inventory(self):
        from dq.services import table_rule_inventory
        inv = table_rule_inventory(self.src_table.id)
        # rules: r1, r2 (field) + table-level rule
        self.assertEqual(len(inv['rules']), 3)
        # gap: f2, f3 have no rules
        self.assertEqual(
            {g['field_id'] for g in inv['field_gaps']}, {self.f2.id, self.f3.id})
        # contradiction: disjoint ranges r1 vs r2 on f1
        self.assertEqual(len(inv['contradictions']), 1)
        self.assertEqual(inv['contradictions'][0]['kind'], 'conflict')
        self.assertEqual(inv['contradictions'][0]['data_field_id'], self.f1.id)
