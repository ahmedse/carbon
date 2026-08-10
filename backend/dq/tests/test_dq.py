"""Tests for DQ (Data Quality) rules and results — M2M decoupled model."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import ScopedRole
from dq.models import DQRule, DQResult, RuleTag, RuleFieldAssignment
from dataschema.models import DataTable, DataField, DataRow
from core.models import Module
from mdm.models import OrgUnit


User = get_user_model()

BASE = '/carbon-api/dq'


def _create_field_assignment(rule, data_field=None, data_table=None):
    """Helper: create a RuleFieldAssignment for a rule."""
    return RuleFieldAssignment.objects.create(
        rule=rule,
        data_field=data_field,
        data_table=data_table or (data_field.data_table if data_field else None),
    )


class DQRuleCRUDTestCase(TestCase):
    """Test CRUD operations on DQ rules with M2M field assignments."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='user_dq', password='user'
        )
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division'
        )
        self.data_module, _ = Module.objects.get_or_create(
            name='Sales', defaults={'scope': 1, 'org_unit': self.org_unit}
        )
        self.data_table = DataTable.objects.create(
            name='Transactions', module=self.data_module
        )
        self.data_field = DataField.objects.create(
            name='amount', type='number', label='Amount',
            data_table=self.data_table, required=True
        )
        self.tag = RuleTag.objects.create(name='Critical', color='#ff0000')

    def _make_payload(self, **overrides):
        return {
            'name': 'Test Rule',
            'rule_level': 'field_validation',
            'rule_type': 'not_null',
            'severity': 'error',
            'is_active': True,
            'tag_ids': [self.tag.id],
            **overrides,
        }

    def test_list_rules_authenticated(self):
        rule = DQRule.objects.create(
            name='Not Null Check', rule_level='field_validation',
            rule_type='not_null', severity='error', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_list_rules_unauthenticated(self):
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_rule_admin(self):
        self.client.force_authenticate(self.admin_user)
        payload = self._make_payload(name='Amount Range Check', rule_type='range',
            params={'min': 0, 'max': 1000000}, severity='warn')
        r = self.client.post(f'{BASE}/rules/', payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['name'], 'Amount Range Check')

    def test_create_rule_includes_tags(self):
        self.client.force_authenticate(self.admin_user)
        payload = self._make_payload(name='Tagged Rule')
        r = self.client.post(f'{BASE}/rules/', payload, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn('tags', r.data)
        tag_names = [t['name'] for t in r.data['tags']]
        self.assertIn('Critical', tag_names)

    def test_retrieve_rule(self):
        rule = DQRule.objects.create(
            name='Retrieve Test', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        rule.tags.add(self.tag)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['rule_level'], 'field_validation')
        self.assertFalse(r.data['is_locked'])

    def test_update_rule(self):
        rule = DQRule.objects.create(
            name='Update Test', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.patch(f'{BASE}/rules/{rule.id}/', {'severity': 'error'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertEqual(rule.severity, 'error')

    def test_update_rule_tags(self):
        rule = DQRule.objects.create(
            name='Tag Update Test', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        new_tag = RuleTag.objects.create(name='PII', color='#00ff00')
        self.client.force_authenticate(self.admin_user)
        r = self.client.patch(f'{BASE}/rules/{rule.id}/', {'tag_ids': [new_tag.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertEqual(rule.tags.count(), 1)

    def test_delete_unused_rule(self):
        rule = DQRule.objects.create(
            name='Deletable Rule', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.delete(f'{BASE}/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_rule_with_results_archives_instead(self):
        """DELETE on rule with results now archives (200) instead of rejecting (409)."""
        rule = DQRule.objects.create(
            name='Locked Rule', rule_level='field_validation',
            rule_type='not_null', is_active=True,
            definition={'schema_version': 1, 'name': 'test', 'level': 'field',
                        'dimension': 'validity', 'type': 'not_null', 'severity': 'error',
                        'active': True, 'bindings': [{'table': 'test', 'field': 'test'}]},
        )
        _create_field_assignment(rule, data_field=self.data_field)
        DQResult.objects.create(rule=rule, passed=True, checked_count=10, failed_count=0, score=100)
        self.client.force_authenticate(self.admin_user)
        r = self.client.delete(f'{BASE}/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['archived'])
        rule.refresh_from_db()
        self.assertTrue(rule.archived)
        self.assertFalse(rule.is_active)

    def test_hard_delete_rule_without_results(self):
        """DELETE on rule with zero results still hard-deletes."""
        rule = DQRule.objects.create(
            name='Clean Rule', rule_level='field_validation',
            rule_type='not_null', is_active=True,
            definition={'schema_version': 1, 'name': 'test', 'level': 'field',
                        'dimension': 'validity', 'type': 'not_null', 'severity': 'error',
                        'active': True, 'bindings': [{'table': 'test', 'field': 'test'}]},
        )
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.delete(f'{BASE}/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DQRule.objects.filter(id=rule.id).exists())

    def test_deactivate_locked_rule(self):
        rule = DQRule.objects.create(
            name='Locked Deactivate', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        DQResult.objects.create(rule=rule, passed=True, checked_count=10, failed_count=0, score=100)
        self.client.force_authenticate(self.admin_user)
        r = self.client.patch(f'{BASE}/rules/{rule.id}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)


class DQRuleValidationTestCase(TestCase):
    """Test DQ rule validation on the new model."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division'
        )
        self.data_module, _ = Module.objects.get_or_create(
            name='Sales', defaults={'scope': 1, 'org_unit': self.org_unit}
        )
        self.data_table = DataTable.objects.create(name='Transactions', module=self.data_module)
        self.data_field = DataField.objects.create(
            name='amount', type='number', label='Amount', data_table=self.data_table, required=True)

    def test_invalid_rule_type(self):
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/', {
            'name': 'Bad Rule', 'rule_level': 'field_validation',
            'rule_type': 'invalid_type', 'severity': 'error'
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_rule_level(self):
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/', {
            'name': 'Bad Level', 'rule_level': 'invalid_level',
            'rule_type': 'not_null', 'severity': 'error'
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_name(self):
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/', {
            'rule_level': 'field_validation', 'rule_type': 'not_null', 'severity': 'error'
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class DQRuleRBACTestCase(TestCase):
    """Test RBAC filtering on DQ rules."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True)
        self.regular_user = User.objects.create_user(username='user_dq', password='user')
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division')
        self.data_module, _ = Module.objects.get_or_create(
            name='Sales', defaults={'scope': 1, 'org_unit': self.org_unit})
        self.data_table = DataTable.objects.create(name='Transactions', module=self.data_module)
        self.data_field = DataField.objects.create(
            name='amount', type='number', label='Amount', data_table=self.data_table, required=True)

    def test_admin_sees_all_rules(self):
        rule = DQRule.objects.create(
            name='Admin Visible', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        count = r.data.get('count') if isinstance(r.data, dict) else len(r.data)
        self.assertGreaterEqual(count, 1)

    def test_user_without_scopedrole_sees_nothing(self):
        self.client.force_authenticate(self.regular_user)
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        count = r.data.get('count') if isinstance(r.data, dict) else len(r.data)
        self.assertEqual(count, 0)

    def test_user_with_scopedrole_sees_assigned_rules(self):
        from django.contrib.auth.models import Group
        viewer_group, _ = Group.objects.get_or_create(name='viewer_group')
        ScopedRole.objects.create(user=self.regular_user, group=viewer_group,
            org_unit=self.org_unit, is_active=True)
        rule = DQRule.objects.create(
            name='Scoped Visible', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.regular_user)
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        count = r.data.get('count') if isinstance(r.data, dict) else len(r.data)
        self.assertGreaterEqual(count, 1)


class DQResultsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True)
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division')
        self.data_module, _ = Module.objects.get_or_create(
            name='Sales', defaults={'scope': 1, 'org_unit': self.org_unit})
        self.data_table = DataTable.objects.create(name='Transactions', module=self.data_module)
        self.data_field = DataField.objects.create(
            name='amount', type='number', label='Amount', data_table=self.data_table, required=True)

    def test_list_results_authenticated(self):
        rule = DQRule.objects.create(
            name='Rule for Results', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule, data_field=self.data_field)
        DQResult.objects.create(rule=rule, data_field=self.data_field,
            passed=True, checked_count=100, failed_count=0, score=100)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/results/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class DQBulkExecuteTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_bulk', password='admin', is_staff=True, is_superuser=True)
        self.org_unit = OrgUnit.objects.create(
            name='Bulk Org', slug='bulk-org', code='BLK', org_type='division')
        self.data_module, _ = Module.objects.get_or_create(
            name='BulkSales', defaults={'scope': 1, 'org_unit': self.org_unit})
        self.data_table = DataTable.objects.create(name='BulkTransactions', module=self.data_module)
        self.data_field = DataField.objects.create(
            name='amount', type='number', label='Amount', data_table=self.data_table, required=True)

    def test_bulk_execute_by_rule_ids(self):
        rule = DQRule.objects.create(
            name='Bulk Rule 1', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/bulk-execute/', {'rule_ids': [rule.id]}, format='json')
        self.assertIn(r.status_code, [200, 400])

    def test_bulk_execute_no_params_400(self):
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/bulk-execute/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_execute_unauthenticated(self):
        r = self.client.post(f'{BASE}/rules/bulk-execute/', {'rule_ids': [1]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bulk_execute_two_passing_rules(self):
        """2 passing rules → summary shows 2 passed, 0 failed, len(results)==2."""
        # Create data so rules have rows to evaluate
        DataRow.objects.create(data_table=self.data_table, values={'amount': '100'})
        DataRow.objects.create(data_table=self.data_table, values={'amount': '200'})

        rule1 = DQRule.objects.create(
            name='Bulk Pass 1', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule1, data_field=self.data_field)

        rule2 = DQRule.objects.create(
            name='Bulk Pass 2', rule_level='field_validation',
            rule_type='range', is_active=True,
            params={'min': 0, 'max': 1000})
        _create_field_assignment(rule2, data_field=self.data_field)

        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/rules/bulk-execute/',
                             {'rule_ids': [rule1.id, rule2.id]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['total'], 2)
        self.assertEqual(r.data['passed'], 2)
        self.assertEqual(r.data['failed'], 0)
        self.assertEqual(len(r.data['results']), 2)


class RuleTagTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='tag_admin', password='admin', is_staff=True, is_superuser=True)

    def test_list_tags(self):
        RuleTag.objects.create(name='PII', color='#ff0000')
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/tags/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_create_tag(self):
        self.client.force_authenticate(self.admin_user)
        r = self.client.post(f'{BASE}/tags/', {'name': 'Critical', 'color': '#ff0000'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_delete_tag(self):
        tag = RuleTag.objects.create(name='Temp', color='#cccccc')
        self.client.force_authenticate(self.admin_user)
        r = self.client.delete(f'{BASE}/tags/{tag.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)


class DQMetricsRegressionTestCase(TestCase):
    """P0 regression: metrics endpoints must return 200 and correct rule counts."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='metrics_admin', password='admin', is_staff=True, is_superuser=True)
        self.org_unit = OrgUnit.objects.create(
            name='Metrics Org', slug='metrics-org', code='MTO', org_type='division')
        self.data_module, _ = Module.objects.get_or_create(
            name='MetricsModule', defaults={'scope': 1, 'org_unit': self.org_unit})
        self.data_table = DataTable.objects.create(name='MetricsTable', module=self.data_module)
        self.data_field = DataField.objects.create(
            name='score', type='number', label='Score', data_table=self.data_table, required=True)

    def test_table_metrics_200_with_rule_count(self):
        """GET /dq/metrics/table/<id>/ returns 200 and correct active_rules count."""
        rule = DQRule.objects.create(
            name='Table Metric Rule', rule_level='field_validation',
            rule_type='not_null', is_active=True)
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/metrics/table/{self.data_table.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['table_id'], self.data_table.id)
        self.assertEqual(len(r.data['active_rules']), 1)
        self.assertEqual(r.data['active_rules'][0]['name'], 'Table Metric Rule')

    def test_table_metrics_rule_assigned_to_table_not_field(self):
        """Rule assigned to table (data_field=null) is still returned."""
        rule = DQRule.objects.create(
            name='Table Level Rule', rule_level='business_rule',
            rule_type='threshold', is_active=True,
            params={'operator': 'gte', 'value': 1})
        RuleFieldAssignment.objects.create(
            rule=rule, data_table=self.data_table, data_field=None)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/metrics/table/{self.data_table.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['active_rules']), 1)

    def test_field_metrics_200_with_rule_count(self):
        """GET /dq/metrics/field/<id>/ returns 200 and correct active_rules count."""
        rule = DQRule.objects.create(
            name='Field Metric Rule', rule_level='field_validation',
            rule_type='range', is_active=True,
            params={'min': 0, 'max': 100})
        _create_field_assignment(rule, data_field=self.data_field)
        self.client.force_authenticate(self.admin_user)
        r = self.client.get(f'{BASE}/metrics/field/{self.data_field.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['field_id'], self.data_field.id)
        self.assertEqual(len(r.data['active_rules']), 1)
        self.assertEqual(r.data['active_rules'][0]['name'], 'Field Metric Rule')
