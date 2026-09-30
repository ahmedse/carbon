from django.test import TestCase
from catalog.models import GovernancePolicy
from catalog.policy_engine import check_policy


class PolicyEngineTests(TestCase):
    def setUp(self):
        self.policy = GovernancePolicy.objects.create(
            name='Block All Deletes', policy_type='module_delete',
            enabled=True, scope_type='global'
        )

    def test_global_policy_blocks(self):
        allowed, blocked_by = check_policy('module_delete', org_unit_id=1)
        self.assertFalse(allowed)
        self.assertIn('Block All Deletes', blocked_by)

    def test_disabled_policy_allows(self):
        self.policy.enabled = False
        self.policy.save()
        allowed, blocked_by = check_policy('module_delete', org_unit_id=1)
        self.assertTrue(allowed)

    def test_no_matching_policy_allows(self):
        allowed, blocked_by = check_policy('table_delete', org_unit_id=1)
        self.assertTrue(allowed)
        self.assertEqual(blocked_by, [])

    def test_scope_row_count_allows_an_empty_module(self):
        self.policy.enabled = False
        self.policy.save()
        GovernancePolicy.objects.create(
            name='Protect Scope 1 Carbon Modules',
            policy_type='module_delete',
            enabled=True,
            scope_type='scope',
            emission_scope=1,
            config={'check_row_count': True},
        )
        from core.models import Module
        module = Module.objects.create(name='Empty Scope 1 Shell', scope=1)
        allowed, blocked_by = check_policy('module_delete', module=module)
        self.assertTrue(allowed)
        self.assertEqual(blocked_by, [])

    def test_scope_row_count_blocks_a_module_with_rows(self):
        self.policy.enabled = False
        self.policy.save()
        GovernancePolicy.objects.create(
            name='Protect Scope 1 Carbon Modules',
            policy_type='module_delete',
            enabled=True,
            scope_type='scope',
            emission_scope=1,
            config={'check_row_count': True},
        )
        from core.models import Module
        from dataschema.models import DataRow, DataTable
        module = Module.objects.create(name='Scope 1 With Rows', scope=1)
        table = DataTable.objects.create(title='Fuel', name='fuel_rows', module=module)
        DataRow.objects.create(data_table=table, values={'liters': 10})
        allowed, blocked_by = check_policy('module_delete', module=module)
        self.assertFalse(allowed)
        self.assertIn('Protect Scope 1 Carbon Modules', blocked_by)
