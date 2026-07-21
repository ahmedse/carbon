# File: backend/catalog/tests/test_scoped_access.py
# Test org-unit scoped access for AssetProfileViewSet

from decimal import Decimal
from django.contrib.auth.models import Group
from django.test import TestCase, Client

from accounts.models import User, ScopedRole
from mdm.models import OrgUnit
from core.models import Module
from dataschema.models import DataTable
from catalog.models import AssetProfile
from emissions.models import Calculation, EmissionFactor, ReportingPeriod


class AssetProfileScopedAccessTest(TestCase):
    """Test that AssetProfileViewSet enforces org-unit scoping."""
    
    def setUp(self):
        """Set up test data with two org units and users."""
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True, is_superuser=True
        )
        self.owner1 = User.objects.create_user(username='owner1', password='pass123')
        self.owner2 = User.objects.create_user(username='owner2', password='pass123')
        self.outsider = User.objects.create_user(username='outsider', password='pass123')
        
        # Create org units
        self.org_unit1 = OrgUnit.objects.create(name='Unit 1', slug='unit-1')
        self.org_unit2 = OrgUnit.objects.create(name='Unit 2', slug='unit-2')
        
        # Create modules
        self.module1 = Module.objects.create(org_unit=self.org_unit1, name='Module 1', scope=1)
        self.module2 = Module.objects.create(org_unit=self.org_unit2, name='Module 2', scope=1)
        
        # Create data tables
        self.table1 = DataTable.objects.create(module=self.module1, name='Table 1')
        self.table2 = DataTable.objects.create(module=self.module2, name='Table 2')
        
        # Create asset profiles
        self.asset1 = AssetProfile.objects.create(data_table=self.table1, description='Asset 1')
        self.asset2 = AssetProfile.objects.create(data_table=self.table2, description='Asset 2')
        
        # Assign scoped roles
        self.dataowner_group = Group.objects.get_or_create(name='dataowners_group')[0]
        ScopedRole.objects.create(user=self.owner1, org_unit=self.org_unit1, group=self.dataowner_group, is_active=True)
        ScopedRole.objects.create(user=self.owner2, org_unit=self.org_unit2, group=self.dataowner_group, is_active=True)
        
        self.client = Client()
    
    def test_superuser_sees_all_assets(self):
        """Superuser should see all assets regardless of org unit."""
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/v1/catalog/assets/')
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json().get('results', [])), 2)
        
        asset_ids = [a['id'] for a in response.json()['results']]
        self.assertIn(self.asset1.id, asset_ids)
        self.assertIn(self.asset2.id, asset_ids)
    
    def test_owner1_sees_only_their_assets(self):
        """Owner1 should only see assets from their org unit."""
        self.client.force_login(self.owner1)
        response = self.client.get('/api/v1/catalog/assets/')
        
        self.assertEqual(response.status_code, 200)
        asset_ids = [a['id'] for a in response.json().get('results', [])]
        
        self.assertIn(self.asset1.id, asset_ids)
        self.assertNotIn(self.asset2.id, asset_ids)
    
    def test_owner2_sees_only_their_assets(self):
        """Owner2 should only see assets from their org unit."""
        self.client.force_login(self.owner2)
        response = self.client.get('/api/v1/catalog/assets/')
        
        self.assertEqual(response.status_code, 200)
        asset_ids = [a['id'] for a in response.json().get('results', [])]
        
        self.assertIn(self.asset2.id, asset_ids)
        self.assertNotIn(self.asset1.id, asset_ids)
    
    def test_outsider_sees_no_assets(self):
        """User without scoped role should see no assets."""
        self.client.force_login(self.outsider)
        response = self.client.get('/api/v1/catalog/assets/')
        
        self.assertEqual(response.status_code, 200)
        assets = response.json().get('results', [])
        self.assertEqual(len(assets), 0)


class OwnerDashboardAccessTest(TestCase):
    """Test org-unit scoped access for owner dashboard."""
    
    def setUp(self):
        """Set up test data with emissions calculations."""
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin', password='admin123', is_staff=True, is_superuser=True
        )
        self.owner1 = User.objects.create_user(username='owner1', password='pass123')
        self.outsider = User.objects.create_user(username='outsider', password='pass123')
        
        # Create org units and modules
        self.org_unit1 = OrgUnit.objects.create(name='Unit 1', slug='unit-1')
        self.org_unit2 = OrgUnit.objects.create(name='Unit 2', slug='unit-2')
        self.module1 = Module.objects.create(org_unit=self.org_unit1, name='Module 1', scope=1)
        self.module2 = Module.objects.create(org_unit=self.org_unit2, name='Module 2', scope=1)
        
        # Create reporting period
        self.period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            status='open'
        )
        
        # Create emission factor
        self.factor = EmissionFactor.objects.create(
            code='TEST-EF',
            name='Test Factor',
            scope=1,
            category='electricity',
            co2e_kg=Decimal('0.5'),
        )
        
        # Create calculations for both modules
        self.calc1 = Calculation.objects.create(
            module=self.module1,
            reporting_period=self.period,
            reporting_month=1,
            scope=1,
            category='electricity',
            activity_data=100,
            activity_unit='kWh',
            co2e_kg=50000,
            emission_factor=self.factor,
        )
        
        self.calc2 = Calculation.objects.create(
            module=self.module2,
            reporting_period=self.period,
            reporting_month=1,
            scope=1,
            category='electricity',
            activity_data=100,
            activity_unit='kWh',
            co2e_kg=50000,
            emission_factor=self.factor,
        )
        
        # Assign scoped roles
        self.dataowner_group = Group.objects.get_or_create(name='dataowners_group')[0]
        ScopedRole.objects.create(user=self.owner1, org_unit=self.org_unit1, group=self.dataowner_group, is_active=True)
        
        self.client = Client()
    
    def test_owner_sees_only_their_calculations(self):
        """Owner should only see emissions from their org unit."""
        self.client.force_login(self.owner1)
        response = self.client.get('/api/v1/emissions/owner-dashboard/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should show only their calculation (50000 kg = 50 tonnes)
        self.assertEqual(data['total_co2e_tonnes'], 50.0)
        self.assertEqual(data['calculation_count'], 1)
    
    def test_outsider_cannot_access_dashboard(self):
        """User without scoped role should get 403."""
        self.client.force_login(self.outsider)
        response = self.client.get('/api/v1/emissions/owner-dashboard/')
        
        self.assertEqual(response.status_code, 403)
    
    def test_admin_sees_all_calculations(self):
        """Admin should see all calculations."""
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/v1/emissions/owner-dashboard/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should show both calculations (100 tonnes total)
        self.assertEqual(data['total_co2e_tonnes'], 100.0)
        self.assertEqual(data['calculation_count'], 2)
