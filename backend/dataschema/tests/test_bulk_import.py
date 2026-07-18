# backend/dataschema/tests/test_bulk_import.py
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from accounts.models import User
from core.models import Module
from mdm.models import OrgUnit
from dataschema.models import DataTable, DataField, DataRow
import json


class TestBulkImport(TestCase):
    
    def setUp(self):
        """Create test data before each test"""
        self.user = User.objects.create_user(username='testuser', password='testpass', email='test@example.com')
        self.org = OrgUnit.objects.create(name='Test Org', code='TEST', org_type='organization')
        self.module = Module.objects.create(name='Test Module', scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(title='Transport Data', name='transport_data', module=self.module)
        DataField.objects.create(data_table=self.table, name='date', label='Date', type='string', required=True, order=1)
        DataField.objects.create(data_table=self.table, name='distance', label='Distance (km)', type='number', required=False, order=2)
        DataField.objects.create(data_table=self.table, name='fuel_type', label='Fuel Type', type='select', required=False, order=3, options=[
            {'value': 'diesel', 'label': 'Diesel'},
            {'value': 'gasoline', 'label': 'Gasoline'}
        ])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_bulk_import_csv_success(self):
        """Test successful CSV import"""
        csv_content = b'date,distance,fuel_type\n2026-01-01,100,diesel\n2026-01-02,150,gasoline'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': self.table.id,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 2)
        self.assertEqual(response.data['failed'], 0)
        self.assertEqual(DataRow.objects.filter(data_table=self.table).count(), 2)
    
    def test_bulk_import_with_column_mapping(self):
        """Test CSV import with column mapping"""
        # CSV has different column names
        csv_content = b'Date,Dist,Fuel\n2026-01-01,100,diesel'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        # Map CSV headers to field names
        column_mapping = json.dumps({
            'Date': 'date',
            'Dist': 'distance',
            'Fuel': 'fuel_type'
        })
        
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': self.table.id,
            'column_mapping': column_mapping,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['failed'], 0)
    
    def test_bulk_import_validation_errors(self):
        """Test import with missing required fields"""
        # Missing 'date' field (required)
        csv_content = b'distance,fuel_type\n100,diesel\n150,gasoline'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': self.table.id,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 0)
        self.assertEqual(response.data['failed'], 2)
        self.assertEqual(len(response.data['errors']), 2)
        self.assertIn('required', response.data['errors'][0]['error'].lower())
    
    def test_bulk_import_invalid_file_type(self):
        """Test import with unsupported file type"""
        txt_file = SimpleUploadedFile('test.txt', b'not a csv', content_type='text/plain')
        
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'file': txt_file,
            'data_table': self.table.id,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 400)
        self.assertTrue('CSV' in response.data['error'] or 'Excel' in response.data['error'])
    
    def test_download_template(self):
        """Test CSV template generation"""
        response = self.client.get(f'/carbon-api/datarows/download-template/?data_table={self.table.id}')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'date', response.content)
        self.assertIn(b'distance', response.content)
        self.assertIn(b'fuel_type', response.content)
    
    def test_download_template_with_example(self):
        """Test template generation with example row"""
        response = self.client.get(f'/carbon-api/datarows/download-template/?data_table={self.table.id}&include_example=true')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'date', response.content)
        # Check for example data (should have 2 lines: header + example)
        lines = response.content.decode('utf-8').split('\r\n')
        self.assertGreaterEqual(len(lines), 2)
    
    def test_bulk_import_missing_file(self):
        """Test import without file parameter"""
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'data_table': self.table.id,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('file', response.data['error'].lower())
    
    def test_bulk_import_missing_table_id(self):
        """Test import without data_table parameter"""
        csv_content = b'date,distance\n2026-01-01,100'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = self.client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'mode': 'create'
        }, format='multipart')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('data_table', response.data['error'].lower())
