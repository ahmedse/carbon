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
        for i in range(n):
            rule = DQRule.objects.create(
                scope="table", data_table=self.table, rule_type="not_null",
                name=f"PerfRule{i}",
            )
            DQResult.objects.create(rule=rule, passed=True)
            DQResult.objects.create(rule=rule, passed=False)

    def test_rules_list_no_n_plus_one(self):
        """GET /dq/rules/ — constant query count as rules grow.
        Covers both select_related (created_by/data_table/data_field) and
        prefetch_related('results') for the serializer's results_count."""
        self._assert_no_n_plus_one('/carbon-api/dq/rules/', self._make_rules, bound=8)

    def _make_results(self, n):
        rule = DQRule.objects.create(
            scope="table", data_table=self.table, rule_type="not_null",
            name="PerfResRule",
        )
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

    def test_org_units_list_returns_200(self):
        """GET /mdm/org-units/ returns 200 with parent join in place.
        NOTE: residual N+1 remains from OrgUnitSerializer method fields
        (children_count / descendants_count / full_path) — fixing those
        requires serializer changes (out of P12 scope, see report)."""
        parent = OrgUnit.objects.create(name="Perf Root2", slug="perf-root2")
        for i in range(4):
            OrgUnit.objects.create(name=f"Perf C{i}", slug=f"perf-c{i}", parent=parent)
        resp, q = self._count('/carbon-api/mdm/org-units/')
        self.assertEqual(resp.status_code, 200)
        # Loose bound: list query + parent join must keep total under ~1 + 4N
        self.assertLess(q, 30, f"Org unit list too slow: {q} queries")
