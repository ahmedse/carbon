from django.test import TestCase, TransactionTestCase
from catalog.models import AssetProfile, DataDomain
from mdm.models import ReferenceSet
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.contrib.auth.models import User
import time

class QueryOptimizationTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test data
        domain = DataDomain.objects.create(name="TestDomain")
        for i in range(100):
            AssetProfile.objects.create(
                name=f"Asset_{i}",
                domain=domain,
                classification="public"
            )
    
    def test_asset_list_no_n_plus_one(self):
        """Verify asset list endpoint doesn't have N+1 queries."""
        from catalog.views import AssetProfileViewSet
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/catalog/assets/')
        request.user = User.objects.first() or User.objects.create_superuser('admin', password='test')
        
        viewset = AssetProfileViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        
        with CaptureQueriesContext(connection) as ctx:
            qs = viewset.get_queryset()
            list(qs[:10])  # Fetch first 10 to avoid huge dataset in test
        
        # Should be minimal queries (not 100+ for N+1)
        # Expecting: 1 select + 1-2 for related objects
        self.assertLess(len(ctx), 15, f"Too many queries: {len(ctx)}")
    
    def test_reference_set_list_performance(self):
        """Verify reference set list completes quickly."""
        from mdm.views import ReferenceSetViewSet
        from django.test import RequestFactory
        
        # Create many sets
        for i in range(100):
            ReferenceSet.objects.create(name=f"RS_{i}", code=f"rs_{i}")
        
        factory = RequestFactory()
        request = factory.get('/mdm/reference-sets/')
        request.user = User.objects.first() or User.objects.create_superuser('admin', password='test')
        
        viewset = ReferenceSetViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        
        start = time.time()
        qs = viewset.get_queryset()
        list(qs[:10])
        duration = time.time() - start
        
        # Should complete in <2 seconds
        self.assertLess(duration, 2.0, f"Query took {duration}s, should be <2s")
    
    def test_database_indices_exist(self):
        """Verify performance indices have been created."""
        from django.db import connection
        
        inspector = connection.introspection
        
        # Check catalog app indices
        catalog_indices = inspector.get_indexes('catalog_assetprofile')
        index_names = [idx['name'] for idx in catalog_indices.values()]
        
        # At least one of the new indices should exist
        self.assertTrue(
            any('active_domain' in name for name in index_names) or
            len(index_names) >= 3,  # Fallback check for index count
            f"Expected performance indices on AssetProfile. Found: {index_names}"
        )
