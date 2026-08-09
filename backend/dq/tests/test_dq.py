"""Tests for DQ (Data Quality) rules and results — M2M decoupled model."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import ScopedRole
from dq.models import DQRule, DQResult, RuleTag, RuleFieldAssignment
from dataschema.models import DataTable, DataField
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

    def test_cannot_delete_locked_rule(self):
        rule = DQRule.objects.create(
            name='Locked Rule', rule_level='field_validation',
            rule_type='not_null', is_active=True
        )
        _create_field_assignment(rule, data_field=self.data_field)
        DQResult.objects.create(rule=rule, passed=True, checked_count=10, failed_count=0, score=100)
        self.client.force_authenticate(self.admin_user)
        r = self.client.delete(f'{BASE}/rules/{rule.id}/')
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(r.data['is_locked'])

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
