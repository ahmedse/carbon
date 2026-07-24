# File: emissions/tests/test_report_config.py
# Tests for ReportConfig API

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta

from accounts.models import User
from mdm.models import OrgUnit
from emissions.models import ReportingPeriod, Calculation, ReportConfig
from core.models import Module


class ReportConfigAPITest(TestCase):
    """Test ReportConfig ViewSet and generate_report functionality."""
    
    def setUp(self):
        """Create test fixtures."""
        # Users
        self.user1 = User.objects.create_user(
            username='owner1', password='testpass', email='owner1@test.com'
        )
        self.user2 = User.objects.create_user(
            username='owner2', password='testpass', email='owner2@test.com'
        )
        self.staff_user = User.objects.create_user(
            username='admin', password='testpass', email='admin@test.com',
            is_staff=True
        )
        
        # OrgUnit
        self.org_unit = OrgUnit.objects.create(
            name='Test OrgUnit', code='TEST'
        )
        
        # Reporting Period
        today = timezone.now().date()
        self.reporting_period = ReportingPeriod.objects.create(
            name='FY 2026',
            start_date=today - timedelta(days=365),
            end_date=today,
            period_type='fiscal',
            status='open'
        )
        
        # Module
        self.module = Module.objects.create(
            name='Test Module',
            org_unit=self.org_unit,
            scope=1
        )
        
        # Test calculation
        self.calc = Calculation.objects.create(
            module=self.module,
            activity_value=100.0,
            activity_unit='kWh',
            scope=1,
            category='Energy',
            co2e_kg=50000.0,
            reporting_period=self.reporting_period,
            reporting_year=today.year,
            activity_date=today
        )
        
        # Client
        self.client = APIClient()
    
    def test_create_report_config(self):
        """Test creating a report config."""
        self.client.force_authenticate(user=self.user1)
        data = {
            'name': 'My First Report',
            'reporting_period': self.reporting_period.id,
            'org_unit': self.org_unit.id,
            'ghg_scopes': [1],
            'output_format': 'json',
            'grouping': 'scope'
        }
        response = self.client.post('/api/v1/emissions/report-configs/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by_username'], 'owner1')
        self.assertEqual(response.data['name'], 'My First Report')
    
    def test_list_own_configs_only(self):
        """Test that users see only their own configs."""
        # User1 creates config
        config1 = ReportConfig.objects.create(
            name='Config 1',
            created_by=self.user1,
            reporting_period=self.reporting_period
        )
        # User2 creates config
        config2 = ReportConfig.objects.create(
            name='Config 2',
            created_by=self.user2,
            reporting_period=self.reporting_period
        )
        
        # User1 lists configs
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/emissions/report-configs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Config 1')
    
    def test_staff_sees_all_configs(self):
        """Test that staff users see all configs."""
        # Create configs from two users
        ReportConfig.objects.create(
            name='Config 1',
            created_by=self.user1,
            reporting_period=self.reporting_period
        )
        ReportConfig.objects.create(
            name='Config 2',
            created_by=self.user2,
            reporting_period=self.reporting_period
        )
        
        # Staff lists all configs
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get('/api/v1/emissions/report-configs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_run_config_returns_data(self):
        """Test running a config returns report data."""
        config = ReportConfig.objects.create(
            name='Test Config',
            created_by=self.user1,
            reporting_period=self.reporting_period,
            ghg_scopes=[1]
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/v1/emissions/report-configs/{config.id}/run/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_co2e_tonnes', response.data)
        self.assertIn('scope_breakdown', response.data)
        self.assertGreater(response.data['total_co2e_tonnes'], 0)
    
    def test_run_config_updates_last_run_at(self):
        """Test that running a config updates last_run_at."""
        config = ReportConfig.objects.create(
            name='Test Config',
            created_by=self.user1,
            reporting_period=self.reporting_period
        )
        self.assertIsNone(config.last_run_at)
        
        self.client.force_authenticate(user=self.user1)
        self.client.post(f'/api/v1/emissions/report-configs/{config.id}/run/')
        
        config.refresh_from_db()
        self.assertIsNotNone(config.last_run_at)
    
    def test_org_unit_filter(self):
        """Test that org_unit filter scopes results."""
        # Create second org unit
        ou2 = OrgUnit.objects.create(name='Second OrgUnit', code='OU2')
        module2 = Module.objects.create(name='Module 2', org_unit=ou2, scope=1)
        calc2 = Calculation.objects.create(
            module=module2,
            activity_value=50.0,
            scope=1,
            category='Energy',
            co2e_kg=25000.0,
            reporting_period=self.reporting_period,
            reporting_year=timezone.now().year,
            activity_date=timezone.now().date()
        )
        
        config = ReportConfig.objects.create(
            name='Test Config',
            created_by=self.user1,
            reporting_period=self.reporting_period,
            org_unit=self.org_unit  # Only org_unit 1
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/v1/emissions/report-configs/{config.id}/run/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see calc1 (50 tonnes), not calc2 (25 tonnes)
        self.assertAlmostEqual(response.data['total_co2e_tonnes'], 50.0, places=1)
    
    def test_ghg_scope_filter(self):
        """Test that ghg_scopes filter works."""
        config = ReportConfig.objects.create(
            name='Test Config',
            created_by=self.user1,
            reporting_period=self.reporting_period,
            ghg_scopes=[2, 3]  # Exclude Scope 1
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/v1/emissions/report-configs/{config.id}/run/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No Scope 2/3 calculations exist, so should be 0
        self.assertEqual(response.data['total_co2e_tonnes'], 0.0)
    
    def test_csv_export(self):
        """Test CSV export format."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/emissions/report/?format=csv')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('emissions_report.csv', response['Content-Disposition'])
    
    def test_unauthenticated_403(self):
        """Test unauthenticated users get 403."""
        response = self.client.get('/api/v1/emissions/report-configs/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_delete_own_config(self):
        """Test users can delete their own configs."""
        config = ReportConfig.objects.create(
            name='Config to Delete',
            created_by=self.user1,
            reporting_period=self.reporting_period
        )
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(f'/api/v1/emissions/report-configs/{config.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ReportConfig.objects.filter(id=config.id).exists())
