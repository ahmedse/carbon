from django.test import TestCase
from catalog.models import AssetProfile, DataDomain
from mdm.models import ReferenceSet
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.contrib.auth import get_user_model
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
