"""Tests for DQ (Data Quality) rules and results."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import ScopedRole
from dq.models import DQRule, DQResult
from dataschema.models import DataTable, DataField, DataModule
from mdm.models import OrgUnit


User = get_user_model()


class DQRuleCRUDTestCase(TestCase):
    """Test CRUD operations on DQ rules."""

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
        self.data_module = DataModule.objects.create(
            name='Sales', slug='sales', org_unit=self.org_unit
        )
        self.data_table = DataTable.objects.create(
            name='Transactions', slug='transactions', module=self.data_module
        )
        self.data_field = DataField.objects.create(
            name='amount', data_type='decimal',
            data_table=self.data_table, is_required=True
        )

    def test_list_rules_authenticated(self):
        """Authenticated user can list rules."""
        DQRule.objects.create(
            name='Not Null Check',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            severity='error',
            is_active=True
        )
        
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/dq/rules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_rules_unauthenticated(self):
        """Unauthenticated user gets 401."""
        response = self.client.get('/dq/rules/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_rule_admin(self):
        """Admin can create DQ rule."""
        self.client.force_authenticate(self.admin_user)
        payload = {
            'name': 'Amount Range Check',
            'scope': 'field',
            'data_field': self.data_field.id,
            'rule_type': 'range',
            'params': {'min': 0, 'max': 1000000},
            'severity': 'warn',
            'is_active': True
        }
        response = self.client.post('/dq/rules/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Amount Range Check')
        self.assertTrue(DQRule.objects.filter(name='Amount Range Check').exists())

    def test_retrieve_rule(self):
        """Can retrieve single rule."""
        rule = DQRule.objects.create(
            name='Retrieve Test',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            is_active=True
        )
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(f'/dq/rules/{rule.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Retrieve Test')

    def test_update_rule(self):
        """Admin can update rule."""
        rule = DQRule.objects.create(
            name='Update Test',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            is_active=True
        )
        self.client.force_authenticate(self.admin_user)
        payload = {'severity': 'error'}
        response = self.client.patch(f'/dq/rules/{rule.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rule.refresh_from_db()
        self.assertEqual(rule.severity, 'error')


class DQRuleValidationTestCase(TestCase):
    """Test DQ rule validation."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division'
        )
        self.data_module = DataModule.objects.create(
            name='Sales', slug='sales', org_unit=self.org_unit
        )
        self.data_table = DataTable.objects.create(
            name='Transactions', slug='transactions', module=self.data_module
        )
        self.data_field = DataField.objects.create(
            name='amount', data_type='decimal',
            data_table=self.data_table, is_required=True
        )

    def test_invalid_rule_type(self):
        """Invalid rule_type is rejected."""
        self.client.force_authenticate(self.admin_user)
        payload = {
            'name': 'Bad Rule',
            'scope': 'field',
            'data_field': self.data_field.id,
            'rule_type': 'invalid_type',
            'severity': 'error'
        }
        response = self.client.post('/dq/rules/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_field_rule_without_data_field(self):
        """Field-scope rule requires data_field."""
        self.client.force_authenticate(self.admin_user)
        payload = {
            'name': 'No Field',
            'scope': 'field',
            'rule_type': 'not_null',
            'severity': 'error'
        }
        response = self.client.post('/dq/rules/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DQRuleRBACTestCase(TestCase):
    """Test RBAC filtering on DQ rules (Rule 1: RBAC is ABSOLUTE)."""

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
        self.data_module = DataModule.objects.create(
            name='Sales', slug='sales', org_unit=self.org_unit
        )
        self.data_table = DataTable.objects.create(
            name='Transactions', slug='transactions', module=self.data_module
        )
        self.data_field = DataField.objects.create(
            name='amount', data_type='decimal',
            data_table=self.data_table, is_required=True
        )

    def test_admin_sees_all_rules(self):
        """Admin can see all rules."""
        DQRule.objects.create(
            name='Admin Visible',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            is_active=True
        )
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/dq/rules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_user_without_scopedrole_sees_nothing(self):
        """User without ScopedRole sees no rules (Rule 1: RBAC ABSOLUTE)."""
        self.client.force_authenticate(self.regular_user)
        response = self.client.get('/dq/rules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return empty list (no rules accessible)
        self.assertEqual(len(response.data), 0)

    def test_user_with_scopedrole_sees_assigned_rules(self):
        """User with ScopedRole sees rules from their org_unit."""
        # Assign user to org_unit
        ScopedRole.objects.create(
            user=self.regular_user,
            role='viewer',
            org_unit=self.org_unit,
            is_active=True
        )
        
        # Create rule in user's org_unit
        DQRule.objects.create(
            name='Scoped Visible',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            is_active=True
        )
        
        self.client.force_authenticate(self.regular_user)
        response = self.client.get('/dq/rules/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see at least the rule we created
        self.assertGreaterEqual(len(response.data), 1)


class DQResultsTestCase(TestCase):
    """Test DQ results."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username='admin_dq', password='admin', is_staff=True, is_superuser=True
        )
        self.org_unit = OrgUnit.objects.create(
            name='Data Org', slug='data-org', code='DAO', org_type='division'
        )
        self.data_module = DataModule.objects.create(
            name='Sales', slug='sales', org_unit=self.org_unit
        )
        self.data_table = DataTable.objects.create(
            name='Transactions', slug='transactions', module=self.data_module
        )
        self.data_field = DataField.objects.create(
            name='amount', data_type='decimal',
            data_table=self.data_table, is_required=True
        )

    def test_list_results_authenticated(self):
        """Authenticated user can list results."""
        rule = DQRule.objects.create(
            name='Rule for Results',
            scope='field',
            data_field=self.data_field,
            rule_type='not_null',
            is_active=True
        )
        DQResult.objects.create(
            rule=rule,
            passed=True,
            checked_count=100,
            failed_count=0,
            score=100
        )
        
        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/dq/results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
