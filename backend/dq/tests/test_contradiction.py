"""Tests for dq/contradiction.py — semantic rule-contradiction detection.

Covers the pure analyzer (no DB) and the service/API integration.
"""
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Module
from dataschema.models import DataTable, DataField
from mdm.models import OrgUnit
from dq.models import DQRule, RuleFieldAssignment
from dq.contradiction import analyze_rules, CONFLICT, REDUNDANT, UNDECIDABLE

User = get_user_model()
BASE = '/carbon-api/dq'


def _spec(rule_id, rule_type, params, name=None):
    return {
        'rule_id': rule_id,
        'name': name or f'{rule_type}-{rule_id}',
        'rule_type': rule_type,
        'params': params,
    }


class AnalyzeRulesUnitTests(SimpleTestCase):
    """Pure-function tests — no database."""

    def test_disjoint_ranges_are_conflict(self):
        rules = [
            _spec(1, 'range', {'min': 0, 'max': 10}),
            _spec(2, 'range', {'min': 20, 'max': 30}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], CONFLICT)
        self.assertEqual(findings[0]['rule_ids'], [1, 2])

    def test_overlapping_ranges_are_not_conflict(self):
        rules = [
            _spec(1, 'range', {'min': 0, 'max': 10}),
            _spec(2, 'range', {'min': 5, 'max': 15}),
        ]
        self.assertEqual(analyze_rules(rules), [])

    def test_open_bounded_ranges_disjoint(self):
        rules = [
            _spec(1, 'range', {'min': None, 'max': 10}),
            _spec(2, 'range', {'min': 20, 'max': None}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], CONFLICT)

    def test_disjoint_allowed_values_are_conflict(self):
        rules = [
            _spec(1, 'allowed_values', {'values': ['a', 'b']}),
            _spec(2, 'allowed_values', {'values': ['c', 'd']}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], CONFLICT)

    def test_overlapping_allowed_values_are_not_conflict(self):
        rules = [
            _spec(1, 'allowed_values', {'values': ['a', 'b']}),
            _spec(2, 'allowed_values', {'values': ['b', 'c']}),
        ]
        self.assertEqual(analyze_rules(rules), [])

    def test_allowed_values_via_reference_set_is_undecidable(self):
        rules = [
            _spec(1, 'allowed_values', {'reference_set': 3}),
            _spec(2, 'range', {'min': 0, 'max': 10}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], UNDECIDABLE)

    def test_range_excluding_all_values_is_conflict(self):
        rules = [
            _spec(1, 'range', {'min': 0, 'max': 10}),
            _spec(2, 'allowed_values', {'values': [100, 200]}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], CONFLICT)

    def test_range_containing_some_value_is_not_conflict(self):
        rules = [
            _spec(1, 'range', {'min': 0, 'max': 10}),
            _spec(2, 'allowed_values', {'values': [5, 200]}),
        ]
        self.assertEqual(analyze_rules(rules), [])

    def test_duplicate_not_null_is_redundant(self):
        rules = [
            _spec(1, 'not_null', {}),
            _spec(2, 'not_null', {}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], REDUNDANT)

    def test_duplicate_unique_is_redundant(self):
        rules = [
            _spec(1, 'unique', {}),
            _spec(2, 'unique', {}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], REDUNDANT)

    def test_unique_plus_not_null_is_redundant(self):
        rules = [
            _spec(1, 'unique', {}),
            _spec(2, 'not_null', {}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], REDUNDANT)

    def test_nl_check_vs_regex_is_undecidable(self):
        rules = [
            _spec(1, 'nl_check', {'prompt': 'is this a valid code?'}),
            _spec(2, 'regex', {'pattern': '^\\d+$'}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], UNDECIDABLE)

    def test_two_regex_rules_are_undecidable(self):
        rules = [
            _spec(1, 'regex', {'pattern': '^\\d+$'}),
            _spec(2, 'regex', {'pattern': '^[a-z]+$'}),
        ]
        findings = analyze_rules(rules)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], UNDECIDABLE)

    def test_independent_rules_have_no_findings(self):
        rules = [
            _spec(1, 'not_null', {}),
            _spec(2, 'range', {'min': 0, 'max': 10}),
        ]
        self.assertEqual(analyze_rules(rules), [])

    def test_empty_input(self):
        self.assertEqual(analyze_rules([]), [])


class ContradictionIntegrationTests(TestCase):
    """Service + API tests against a real field binding."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='contradict_admin', password='pass',
            is_staff=True, is_superuser=True)
        self.org_unit = OrgUnit.objects.create(
            name='Contra Org', code='CTRO', org_type='division')
        self.module = Module.objects.create(name='Contra Module', org_unit=self.org_unit)
        self.table = DataTable.objects.create(name='contra_table', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='amount', label='Amount', type='number')
        self.client.force_authenticate(self.admin)

    def _rule(self, name, rule_type, params):
        return DQRule.objects.create(
            name=name, rule_type=rule_type, params=params, is_active=True,
            definition={
                'schema_version': 1, 'name': name, 'level': 'field',
                'dimension': 'validity', 'type': rule_type, 'severity': 'error',
                'active': True, 'params': params,
            },
        )

    def test_service_detects_disjoint_ranges_on_field(self):
        r1 = self._rule('low', 'range', {'min': 0, 'max': 10})
        r2 = self._rule('high', 'range', {'min': 20, 'max': 30})
        for r in (r1, r2):
            RuleFieldAssignment.objects.create(
                rule=r, data_field=self.field, data_table=self.table)
        from dq.services import detect_rule_contradictions
        findings = detect_rule_contradictions(data_field_id=self.field.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], CONFLICT)
        self.assertEqual(findings[0]['data_field_id'], self.field.id)
        self.assertEqual(findings[0]['data_field_name'], 'amount')

    def test_api_returns_conflict_findings(self):
        r1 = self._rule('low', 'range', {'min': 0, 'max': 10})
        r2 = self._rule('high', 'range', {'min': 20, 'max': 30})
        for r in (r1, r2):
            RuleFieldAssignment.objects.create(
                rule=r, data_field=self.field, data_table=self.table)
        resp = self.client.get(f'{BASE}/rules/contradictions/', {'data_field': self.field.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['findings'][0]['kind'], CONFLICT)

    def test_api_requires_field_or_table(self):
        resp = self.client.get(f'{BASE}/rules/contradictions/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
