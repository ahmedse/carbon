# TASK A9 - PHASE 1: Backend Bulk Import API

**Phase:** 1 of 5  
**Focus:** Django Backend - Bulk Import & Template Generation  
**Duration:** Step-by-step execution

---

## Objective

Implement backend API endpoints for bulk data import (CSV/Excel) and CSV template generation. Add custom actions to the existing [`DataRowViewSet`](backend/dataschema/views.py:104-131) to enable file upload, parsing, validation, and bulk row creation.

---

## Scope - IN

✅ Add `bulk_import()` custom action to `DataRowViewSet`  
✅ Add `download_template()` custom action to `DataRowViewSet`  
✅ CSV/Excel parsing using pandas (already installed)  
✅ Column mapping support (rename CSV columns to field names)  
✅ Row validation using existing [`DataRowSerializer`](backend/dataschema/serializers.py:58-105)  
✅ Bulk row creation with created_by tracking  
✅ Detailed result reporting (created, failed, errors per row)  
✅ Template generation with field names as headers  
✅ Backend tests for bulk import API

---

## Scope - OUT

❌ Frontend components (Phase 2)  
❌ Async/background jobs (Celery)  
❌ Import job history/logging models  
❌ Update mode (upsert) - only CREATE for Phase 1  
❌ Excel export (only CSV template)  
❌ File size limits (Django settings handle this)

---

## Preconditions

1. Django backend running (`python manage.py runserver 0.0.0.0:8009`)
2. Pandas installed (`pandas==2.3.0` in requirements.txt)
3. Existing `DataRowViewSet` in `backend/dataschema/views.py`
4. Existing `DataRowSerializer` with validation logic

---

## Implementation Steps

### Step 1: Add Bulk Import Action

**File:** `backend/dataschema/views.py`

**Task:** Add `bulk_import()` custom action to `DataRowViewSet`

**Code to Add:**

```python
# Add these imports at the top (after existing imports)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import io
import json

# Inside DataRowViewSet class (after existing methods, before SchemaChangeLogViewSet)
class DataRowViewSet(ScopedViewSet):
    # ... existing code ...
    
    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """
        Bulk import data rows from CSV/Excel file.
        
        Request (multipart/form-data):
            - file: uploaded CSV/Excel file
            - data_table: table ID (required)
            - column_mapping: JSON string mapping CSV headers to field names (optional)
            - mode: 'create' (default, only mode supported in Phase 1)
        
        Response:
            {
                "created": int,
                "failed": int,
                "errors": [{"row": int, "data": dict, "error": str}, ...]
            }
        """
        # Extract request parameters
        file = request.FILES.get('file')
        data_table_id = request.data.get('data_table')
        column_mapping_str = request.data.get('column_mapping')
        mode = request.data.get('mode', 'create')
        
        # Validate required parameters
        if not file:
            return Response(
                {'error': 'file parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not data_table_id:
            return Response(
                {'error': 'data_table parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get DataTable instance
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'DataTable with id={data_table_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse file (CSV or Excel)
        try:
            file_content = file.read()
            if file.name.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_content))
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return Response(
                    {'error': 'File must be CSV (.csv) or Excel (.xlsx, .xls)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to parse file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply column mapping if provided
        if column_mapping_str:
            try:
                column_mapping = json.loads(column_mapping_str)
                df = df.rename(columns=column_mapping)
            except json.JSONDecodeError:
                return Response(
                    {'error': 'column_mapping must be valid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Initialize results
        results = {
            'created': 0,
            'failed': 0,
            'errors': []
        }
        
        # Process each row
        for idx, row in df.iterrows():
            row_data = row.to_dict()
            
            # Remove NaN values (pandas represents empty cells as NaN)
            row_data = {k: v for k, v in row_data.items() if pd.notna(v)}
            
            # Remove 'id' column if present (Phase 1: create only)
            row_data.pop('id', None)
            
            try:
                # Validate and create row
                serializer = DataRowSerializer(data={
                    'data_table': data_table.id,
                    'values': row_data
                })
                serializer.is_valid(raise_exception=True)
                serializer.save(created_by=request.user)
                results['created'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': idx + 2,  # +2 because: 0-indexed + header row
                    'data': row_data,
                    'error': str(e)
                })
        
        return Response(results, status=status.HTTP_200_OK)
```

**Expected Result:**
- New endpoint: `POST /carbon-api/datarows/bulk-import/`
- Accepts CSV/Excel files
- Parses and validates rows
- Returns detailed results

---

### Step 2: Add Template Generation Action

**File:** `backend/dataschema/views.py`

**Task:** Add `download_template()` custom action to `DataRowViewSet`

**Code to Add:**

```python
# Add this method to DataRowViewSet class (after bulk_import)

    @action(detail=False, methods=['get'], url_path='download-template')
    def download_template(self, request):
        """
        Generate blank CSV template for a table.
        
        Query parameters:
            - data_table: table ID (required)
            - include_example: 'true' to include example row (optional)
        
        Returns:
            CSV file with field names as headers
        """
        data_table_id = request.query_params.get('data_table')
        include_example = request.query_params.get('include_example') == 'true'
        
        if not data_table_id:
            return Response(
                {'error': 'data_table query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'DataTable with id={data_table_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get active fields ordered by position
        fields = data_table.fields.filter(is_active=True, is_archived=False).order_by('order')
        
        # Generate CSV header (use field names, not labels)
        headers = [f.name for f in fields]
        csv_rows = [','.join(f'"{h}"' for h in headers)]
        
        # Optionally add example row
        if include_example:
            example_values = []
            for f in fields:
                if f.type == 'string':
                    example_values.append('"example text"')
                elif f.type == 'text':
                    example_values.append('"example multiline text"')
                elif f.type == 'number':
                    example_values.append('123')
                elif f.type == 'date':
                    example_values.append('"2026-01-01"')
                elif f.type == 'boolean':
                    example_values.append('true')
                elif f.type == 'select':
                    options = f.options or []
                    if options:
                        example_values.append(f'"{options[0].get("value", "")}"')
                    else:
                        example_values.append('""')
                elif f.type == 'multiselect':
                    example_values.append('""')  # Empty for simplicity
                elif f.type == 'file':
                    example_values.append('""')  # Not supported in CSV import
                else:
                    example_values.append('""')
            csv_rows.append(','.join(example_values))
        
        csv_content = '\r\n'.join(csv_rows)
        
        # Return as file download
        from django.http import HttpResponse
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{data_table.name}_template.csv"'
        return response
```

**Expected Result:**
- New endpoint: `GET /carbon-api/datarows/download-template/?data_table={id}`
- Returns CSV file with field names as headers
- Optional example row if `include_example=true`

---

### Step 3: Verify Import Registration

**File:** `backend/dataschema/urls.py`

**Task:** Confirm router auto-registers custom actions (no changes needed)

**Existing Code:**

```python
# backend/dataschema/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DataTableViewSet, DataFieldViewSet, DataRowViewSet, SchemaChangeLogViewSet

router = DefaultRouter()
router.register(r'data-tables', DataTableViewSet, basename='data-table')
router.register(r'data-fields', DataFieldViewSet, basename='data-field')
router.register(r'datarows', DataRowViewSet, basename='datarow')
router.register(r'schema-change-logs', SchemaChangeLogViewSet, basename='schema-change-log')

urlpatterns = [
    path('', include(router.urls)),
]
```

**Expected Result:**
- Custom actions automatically registered at:
  - `POST /carbon-api/datarows/bulk-import/`
  - `GET /carbon-api/datarows/download-template/`

---

### Step 4: Test Bulk Import API

**File:** `backend/dataschema/tests/test_bulk_import.py` (NEW)

**Task:** Create backend API tests for bulk import

**Code:**

```python
# backend/dataschema/tests/test_bulk_import.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from accounts.models import User
from core.models import Organization, Module
from dataschema.models import DataTable, DataField, DataRow
import json

@pytest.mark.django_db
class TestBulkImport:
    
    @pytest.fixture
    def setup_data(self):
        """Create test data"""
        user = User.objects.create_user(username='testuser', password='testpass', email='test@example.com')
        org = Organization.objects.create(name='Test Org', code='TEST')
        module = Module.objects.create(name='Test Module', scope='scope1', org_unit=org)
        table = DataTable.objects.create(title='Transport Data', name='transport_data', module=module)
        DataField.objects.create(data_table=table, name='date', label='Date', type='string', required=True, order=1)
        DataField.objects.create(data_table=table, name='distance', label='Distance (km)', type='number', required=False, order=2)
        DataField.objects.create(data_table=table, name='fuel_type', label='Fuel Type', type='select', required=False, order=3, options=[
            {'value': 'diesel', 'label': 'Diesel'},
            {'value': 'gasoline', 'label': 'Gasoline'}
        ])
        
        return {
            'user': user,
            'table': table,
            'module': module
        }
    
    def test_bulk_import_csv_success(self, setup_data):
        """Test successful CSV import"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        csv_content = b'date,distance,fuel_type\n2026-01-01,100,diesel\n2026-01-02,150,gasoline'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': setup_data['table'].id,
            'mode': 'create'
        }, format='multipart')
        
        assert response.status_code == 200
        assert response.data['created'] == 2
        assert response.data['failed'] == 0
        assert DataRow.objects.filter(data_table=setup_data['table']).count() == 2
    
    def test_bulk_import_with_column_mapping(self, setup_data):
        """Test CSV import with column mapping"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        # CSV has different column names
        csv_content = b'Date,Dist,Fuel\n2026-01-01,100,diesel'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        # Map CSV headers to field names
        column_mapping = json.dumps({
            'Date': 'date',
            'Dist': 'distance',
            'Fuel': 'fuel_type'
        })
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': setup_data['table'].id,
            'column_mapping': column_mapping,
            'mode': 'create'
        }, format='multipart')
        
        assert response.status_code == 200
        assert response.data['created'] == 1
        assert response.data['failed'] == 0
    
    def test_bulk_import_validation_errors(self, setup_data):
        """Test import with missing required fields"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        # Missing 'date' field (required)
        csv_content = b'distance,fuel_type\n100,diesel\n150,gasoline'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': setup_data['table'].id,
            'mode': 'create'
        }, format='multipart')
        
        assert response.status_code == 200
        assert response.data['created'] == 0
        assert response.data['failed'] == 2
        assert len(response.data['errors']) == 2
        assert 'required' in response.data['errors'][0]['error'].lower()
    
    def test_bulk_import_invalid_file_type(self, setup_data):
        """Test import with unsupported file type"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        txt_file = SimpleUploadedFile('test.txt', b'not a csv', content_type='text/plain')
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': txt_file,
            'data_table': setup_data['table'].id,
            'mode': 'create'
        }, format='multipart')
        
        assert response.status_code == 400
        assert 'CSV' in response.data['error'] or 'Excel' in response.data['error']
    
    def test_download_template(self, setup_data):
        """Test CSV template generation"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        response = client.get(f'/carbon-api/datarows/download-template/?data_table={setup_data["table"].id}')
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv; charset=utf-8'
        assert b'date' in response.content
        assert b'distance' in response.content
        assert b'fuel_type' in response.content
    
    def test_download_template_with_example(self, setup_data):
        """Test template generation with example row"""
        client = APIClient()
        client.force_authenticate(user=setup_data['user'])
        
        response = client.get(f'/carbon-api/datarows/download-template/?data_table={setup_data["table"].id}&include_example=true')
        
        assert response.status_code == 200
        assert b'date' in response.content
        # Check for example data (should have 2 lines: header + example)
        lines = response.content.decode('utf-8').split('\r\n')
        assert len(lines) >= 2
```

**Expected Result:**
- 7 backend tests created
- Run tests: `python manage.py test dataschema.tests.test_bulk_import`
- All tests should PASS

---

### Step 5: Manual Testing with cURL

**Task:** Test endpoints manually to verify functionality

**Test 1: Download Template**

```bash
# Get authentication token first
curl -X POST http://localhost:8009/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Download template (replace {table_id} and {token})
curl -X GET "http://localhost:8009/carbon-api/datarows/download-template/?data_table={table_id}" \
  -H "Authorization: Token {token}" \
  -o template.csv

# Verify template.csv downloaded
cat template.csv
```

**Test 2: Bulk Import CSV**

```bash
# Create test CSV file
echo "date,distance,fuel_type" > test_import.csv
echo "2026-01-01,100,diesel" >> test_import.csv
echo "2026-01-02,150,gasoline" >> test_import.csv

# Upload CSV (replace {table_id} and {token})
curl -X POST http://localhost:8009/carbon-api/datarows/bulk-import/ \
  -H "Authorization: Token {token}" \
  -F "file=@test_import.csv" \
  -F "data_table={table_id}" \
  -F "mode=create"

# Expected response:
# {"created": 2, "failed": 0, "errors": []}
```

---

## Acceptance Criteria

- [ ] `bulk_import()` action added to `DataRowViewSet`
- [ ] `download_template()` action added to `DataRowViewSet`
- [ ] CSV parsing works (pandas)
- [ ] Excel parsing works (.xlsx, .xls)
- [ ] Column mapping applies correctly
- [ ] Row validation uses `DataRowSerializer`
- [ ] Bulk row creation works
- [ ] Created rows have `created_by` set to request user
- [ ] Detailed error reporting (row number, data, error message)
- [ ] Template generation returns CSV with field names
- [ ] Template includes example row when `include_example=true`
- [ ] Backend tests pass (7 tests)
- [ ] Manual cURL tests successful

**Total: 13 Acceptance Criteria**

---

## Verification Checklist

Before proceeding to Phase 2:

- [ ] Code added to `backend/dataschema/views.py` (2 actions)
- [ ] Test file created: `backend/dataschema/tests/test_bulk_import.py`
- [ ] Run tests: `python manage.py test dataschema.tests.test_bulk_import`
- [ ] All 7 tests PASS
- [ ] Manual cURL test: Download template successful
- [ ] Manual cURL test: Bulk import successful
- [ ] No errors in Django logs
- [ ] Endpoints accessible:
  - `POST /carbon-api/datarows/bulk-import/`
  - `GET /carbon-api/datarows/download-template/`

---

## Next Phase

✅ Phase 1 Complete → Proceed to **Phase 2: Frontend Import Wizard Component**

Phase 2 will implement the `BulkImportWizard.jsx` React component with 3-step modal (upload, mapping, validation).

---

## Notes

- Phase 1 supports CREATE only (no UPDATE/UPSERT)
- File size limits handled by Django `FILE_UPLOAD_MAX_MEMORY_SIZE` setting
- RBAC enforced via existing `DataRowViewSet.get_permissions()` and `ScopedViewSet`
- Pandas is already installed (`pandas==2.3.0` in requirements.txt)
- Custom actions automatically registered by DRF router (no URL changes needed)
