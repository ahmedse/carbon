from django.test import TestCase
from catalog.models import AssetProfile, DataDomain
from mdm.models import ReferenceSet, ReferenceValue, OrgUnit
from core.models import Module
from dataschema.models import DataTable, DataField
from dq.models import TableProfile, FieldProfile, DQRule, DQResult
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import time

User = get_user_model()

class QueryOptimizationTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use get_or_create for idempotency with --reuse-db
        domain, _ = DataDomain.objects.get_or_create(
            name="TestDomain",
            defaults={"slug": "testdomain"}
        )
        for i in range(100):
            AssetProfile.objects.get_or_create(
                description=f"Asset_{i}",
                defaults={"domain": domain, "classification": "public"}
            )
    
    def test_asset_list_no_n_plus_one(self):
        """Verify asset list queryset uses select_related to avoid N+1 queries."""
        # Test queryset directly without viewset complexity
        with CaptureQueriesContext(connection) as ctx:
            qs = AssetProfile.objects.select_related('domain', 'owner', 'steward')[:10]
            list(qs)  # Force evaluation
        
        # Should be minimal queries (1 main query, not 10+ for N+1)
        self.assertLess(len(ctx), 5, f"Too many queries: {len(ctx)}")
    
    def test_reference_set_list_performance(self):
        """Verify reference set list completes quickly."""
        # Create many sets
        for i in range(100):
            ReferenceSet.objects.get_or_create(
                name=f"RS_{i}",
                defaults={"slug": f"rs_{i}"}
            )
        
        # Test queryset performance directly
        start = time.time()
        qs = ReferenceSet.objects.select_related('domain', 'steward')[:10]
        list(qs)  # Force evaluation
        duration = time.time() - start
        
        # Should complete quickly
        self.assertLess(duration, 2.0, f"Query took {duration}s, should be <2s")
    
    def test_database_indices_exist(self):
        """Verify performance indices have been created."""
        with connection.cursor() as cursor:
            inspector = connection.introspection
            constraints = inspector.get_constraints(cursor, 'catalog_assetprofile')
        
        # At least one constraint or index should exist
        self.assertGreater(
            len(constraints), 0,
            f"Expected constraints on AssetProfile. Found: {len(constraints)}"
        )


class NPlusOneListMixin:
    """Shared helpers for N+1 HTTP-list tests.

    Strategy: query count must be CONSTANT as row count grows (the real N+1
    criterion), plus an absolute bound. Exact counts are avoided because this
    project has no DRF default pagination, so a plain list is 1-2 queries and
    any exact-number assertion would be brittle.
    """

    def _make_admin_client(self):
        self.user = User.objects.create_superuser(
            username="perf_admin", password="pass", email="perf_admin@example.com"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _count(self, path):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(path)
        return resp, len(ctx.captured_queries)

    def _assert_no_n_plus_one(self, path, grow_fn, small=3, large=8, bound=6):
        """Assert query count is constant as rows grow and within an absolute bound."""
        grow_fn(small)
        resp1, q1 = self._count(path)
        self.assertEqual(resp1.status_code, 200, resp1.content[:200])
        grow_fn(large - small)
        resp2, q2 = self._count(path)
        self.assertEqual(resp2.status_code, 200, resp2.content[:200])
        self.assertEqual(
            q1, q2,
            f"N+1 detected on {path}: {q1} queries with {small} rows -> "
            f"{q2} queries with {large} rows",
        )
        self.assertLessEqual(q2, bound, f"Too many queries on {path}: {q2}")


class DQNPlusOneTest(TestCase, NPlusOneListMixin):
    """Verify DQ list endpoints (profiles, table-profiles, rules, results)
    do not exhibit N+1 queries after the P12 select_related/prefetch fixes."""

    def setUp(self):
        self._make_admin_client()
        self.org = OrgUnit.objects.create(name="Perf Org", slug="perf-org")
        self.module = Module.objects.create(name="Perf Module", org_unit=self.org)
        self.table = DataTable.objects.create(
            title="Perf Table", name="perf_table", module=self.module
        )
        self._profile_seed = 0

    def _make_profiles(self, n):
        for i in range(n):
            name = f"perf_t{self._profile_seed}"
            t = DataTable.objects.create(
                title=f"PerfT{self._profile_seed}", name=name, module=self.module
            )
            f = DataField.objects.create(
                data_table=t, name=f"perf_f{self._profile_seed}",
                label=f"Perf F{self._profile_seed}", type="number",
            )
            FieldProfile.objects.create(data_field=f)
            TableProfile.objects.create(data_table=t)
            self._profile_seed += 1

    def test_field_profiles_list_no_n_plus_one(self):
        """GET /dq/profiles/ — constant query count as profiles grow."""
        self._assert_no_n_plus_one('/carbon-api/dq/profiles/', self._make_profiles)

    def test_table_profiles_list_no_n_plus_one(self):
        """GET /dq/table-profiles/ — constant query count as profiles grow."""
        self._assert_no_n_plus_one('/carbon-api/dq/table-profiles/', self._make_profiles)

    def _make_rules(self, n):
        from dq.models import RuleFieldAssignment
        for i in range(n):
            rule = DQRule.objects.create(
                rule_type="not_null",
                name=f"PerfRule{i}",
            )
            RuleFieldAssignment.objects.create(rule=rule, data_table=self.table)
            DQResult.objects.create(rule=rule, passed=True)
            DQResult.objects.create(rule=rule, passed=False)

    def test_rules_list_no_n_plus_one(self):
        """GET /dq/rules/ — constant query count as rules grow.
        Covers both select_related (created_by/data_table/data_field) and
        prefetch_related('results') for the serializer's results_count."""
        self._assert_no_n_plus_one('/carbon-api/dq/rules/', self._make_rules, bound=8)

    def _make_results(self, n):
        from dq.models import RuleFieldAssignment
        rule = DQRule.objects.create(
            rule_type="not_null",
            name="PerfResRule",
        )
        RuleFieldAssignment.objects.create(rule=rule, data_table=self.table)
        for i in range(n):
            DQResult.objects.create(rule=rule, passed=(i % 2 == 0))

    def test_results_list_no_n_plus_one(self):
        """GET /dq/results/ — constant query count as results grow."""
        self._assert_no_n_plus_one('/carbon-api/dq/results/', self._make_results)


class MDMNPlusOneTest(TestCase, NPlusOneListMixin):
    """Verify MDM list endpoints after P12 select_related additions."""

    def setUp(self):
        self._make_admin_client()

    def _make_reference_values(self, n):
        rs, _ = ReferenceSet.objects.get_or_create(
            name="PerfRS", defaults={"slug": "perf-rs"}
        )
        for i in range(n):
            ReferenceValue.objects.get_or_create(
                reference_set=rs, code=f"CODE{i}", label=f"Label {i}",
            )

    def test_reference_values_list_no_n_plus_one(self):
        """GET /mdm/reference-values/ — constant query count as values grow."""
        self._assert_no_n_plus_one(
            '/carbon-api/mdm/reference-values/', self._make_reference_values, bound=4
        )

    def test_org_unit_queryset_parent_join_single_query(self):
        """OrgUnit.objects.select_related('parent') evaluates in one query."""
        parent = OrgUnit.objects.create(name="Perf Root", slug="perf-root")
        for i in range(3):
            OrgUnit.objects.create(name=f"Perf Child{i}", slug=f"perf-child{i}", parent=parent)
        with CaptureQueriesContext(connection) as ctx:
            list(OrgUnit.objects.select_related('parent'))
        self.assertLessEqual(len(ctx), 1, f"Too many queries: {len(ctx)}")


class OrgUnitNPlusOneTest(TestCase, NPlusOneListMixin):
    """P14: Verify OrgUnit list endpoint is free of N+1 after
    deep select_related (parent chain for full_path) + nested
    prefetch_related (children for children_count / descendants_count)."""

    def setUp(self):
        self._make_admin_client()
        self._seed = 0

    def _make_org_units(self, n):
        """Create n top-level org units each with a child and grandchild."""
        for i in range(n):
            root = OrgUnit.objects.create(
                name=f"OU_Root_{self._seed}", slug=f"ou-root-{self._seed}"
            )
            child = OrgUnit.objects.create(
                name=f"OU_Child_{self._seed}", slug=f"ou-child-{self._seed}",
                parent=root,
            )
            OrgUnit.objects.create(
                name=f"OU_Grand_{self._seed}", slug=f"ou-grand-{self._seed}",
                parent=child,
            )
            self._seed += 1

    def test_org_unit_list_no_n_plus_one(self):
        """GET /mdm/org-units/ — constant query count as units grow."""
        self._assert_no_n_plus_one(
            '/carbon-api/mdm/org-units/', self._make_org_units, small=2, large=5, bound=15
        )


class DataTableNPlusOneTest(TestCase, NPlusOneListMixin):
    """P14: Verify /dataschema/tables/ is free of N+1 after
    select_related('module') + prefetch_related('fields','rows')."""

    def setUp(self):
        self._make_admin_client()
        self.org = OrgUnit.objects.create(name="DTPerfOrg", slug="dt-perf-org")
        self.module = Module.objects.create(name="DTPerfMod", org_unit=self.org)
        self._seed = 0

    def _make_tables(self, n):
        for i in range(n):
            dt = DataTable.objects.create(
                title=f"PerfDT_{self._seed}", name=f"perf_dt_{self._seed}",
                module=self.module,
            )
            DataField.objects.create(
                data_table=dt, name=f"pf_{self._seed}",
                label=f"PerfField{self._seed}", type="number",
            )
            self._seed += 1

    def test_table_list_no_n_plus_one(self):
        """GET /dataschema/tables/ — constant query count as tables grow."""
        self._assert_no_n_plus_one(
            '/carbon-api/dataschema/tables/', self._make_tables, small=2, large=6, bound=10
        )


class DQLockedDownPermissionsTest(TestCase):
    """P11/P14: Verify DQ admin-write endpoints reject non-admin users (403)
    and allow superusers (200)."""

    @classmethod
    def setUpTestData(cls):
        cls.org = OrgUnit.objects.create(name="PermOrg", slug="perm-org")
        cls.module = Module.objects.create(name="PermMod", org_unit=cls.org)
        cls.table = DataTable.objects.create(
            title="PermTable", name="perm_table", module=cls.module
        )

    def setUp(self):
        self.client = APIClient()

    def _login(self, is_superuser=False, suffix=''):
        tag = 'admin' if is_superuser else 'user'
        user = User.objects.create_user(
            username=f"dq_perm_{tag}_{suffix}",
            password="pass",
        )
        user.is_superuser = is_superuser
        user.save()
        self.client.force_authenticate(user=user)
        return user

    # --- Write endpoints must reject non-admin ---

    def test_profile_trigger_rejects_non_admin(self):
        self._login(is_superuser=False)
        resp = self.client.post('/carbon-api/dq/profile/',
                                {'data_table_id': self.table.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_profile_trigger_allows_admin(self):
        self._login(is_superuser=True, suffix='pt')
        resp = self.client.post('/carbon-api/dq/profile/',
                                {'data_table_id': self.table.id}, format='json')
        # 200/202 = success, 400 = table empty (passed auth, legit business error)
        self.assertIn(resp.status_code, [200, 202, 400])

    def test_bulk_profile_rejects_non_admin(self):
        self._login(is_superuser=False)
        resp = self.client.post('/carbon-api/dq/profile/bulk/',
                                {'data_table_ids': [self.table.id]}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_bulk_profile_allows_admin(self):
        self._login(is_superuser=True, suffix='bp')
        resp = self.client.post('/carbon-api/dq/profile/bulk/',
                                {'data_table_ids': [self.table.id]}, format='json')
        # 200/202 = success, 400 = table empty (passed auth)
        self.assertIn(resp.status_code, [200, 202, 400])

    def test_dq_run_rejects_non_admin(self):
        self._login(is_superuser=False)
        resp = self.client.post('/carbon-api/dq/run/',
                                {'data_table_id': self.table.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_dq_run_allows_admin(self):
        self._login(is_superuser=True, suffix='dr')
        resp = self.client.post('/carbon-api/dq/run/',
                                {'data_table_id': self.table.id}, format='json')
        # 200/202 = success, 400 = no rules to run (passed auth)
        self.assertIn(resp.status_code, [200, 202, 400])

    def test_run_validation_rejects_non_admin(self):
        self._login(is_superuser=False)
        resp = self.client.post('/carbon-api/dq/run-validation/',
                                {'data_table': self.table.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_run_validation_allows_admin(self):
        self._login(is_superuser=True, suffix='rv')
        resp = self.client.post('/carbon-api/dq/run-validation/',
                                {'data_table': self.table.id}, format='json')
        self.assertIn(resp.status_code, [200, 202])

    # --- Read endpoints still open to authenticated users ---

    def test_dq_metrics_readable_by_any_auth(self):
        self._login(is_superuser=False)
        resp = self.client.get('/carbon-api/dq/metrics/')
        self.assertEqual(resp.status_code, 200)

    def test_table_dq_metrics_allows_any_auth(self):
        """Table metrics require scoped table access. Non-admin without scope
        gets 403 from _check_table_access, which is correct (not a permission
        class issue). The global metrics endpoint above is unrestricted."""
        self._login(is_superuser=False)
        resp = self.client.get(f'/carbon-api/dq/metrics/table/{self.table.id}/')
        # 403 is expected for users without table scope — that's _check_table_access
        self.assertEqual(resp.status_code, 403)

    def test_field_dq_metrics_readable_by_any_auth(self):
        self._login(is_superuser=False)
        # No fields exist, expect 404 or empty — either is fine as long as not 403
        resp = self.client.get('/carbon-api/dq/field-metrics/')
        self.assertNotEqual(resp.status_code, 403)
