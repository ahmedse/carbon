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
