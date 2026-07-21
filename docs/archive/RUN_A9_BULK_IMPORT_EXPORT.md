# RUN A9: Bulk Import/Export Implementation

**Date:** 2026-07-18  
**Status:** 📋 PLANNING  
**Priority:** HIGH (Critical for data operations efficiency)

---

## Executive Summary

Implement comprehensive bulk data import/export functionality for the Carbon Data Trust Platform. Users can upload CSV/Excel files with automatic column mapping, validation preview, and bulk insert/update operations. Export functionality generates CSV templates and downloads table data with applied filters.

### Current State

**✅ What Works:**
- Client-side CSV export via [`exportRowsToCsv()`](../carbon-frontend/src/api/dataschema.js:155-175)
- Export button in [`TableDataPage`](../carbon-frontend/src/components/TableDataPage.jsx:151-161) (selected rows or all)
- Individual row CRUD via [`DataRowViewSet`](../backend/dataschema/views.py:104-131)
- Field validation in [`DataRowSerializer`](../backend/dataschema/serializers.py:58-105)

**❌ What's Missing:**
- Bulk import wizard UI (file upload, column mapping, validation preview)
- Backend bulk upsert API endpoint
- CSV/Excel parsing on backend (pandas available, but no import logic)
- Template generation endpoint (blank CSV with correct headers)
- Import job tracking/logging
- Error reporting per row during import

---

## User Stories

### Story 1: Data Owner Bulk Imports Data

**As a** Data Owner  
**I want to** upload a CSV/Excel file with multiple data rows  
**So that** I can efficiently add large datasets without manual entry

**Acceptance Criteria:**
- ✅ User clicks "Import" button in toolbar
- ✅ User uploads CSV or Excel file
- ✅ System parses file and shows column mapping interface
- ✅ User maps CSV headers to table fields (auto-mapping attempted first)
- ✅ System validates all rows and shows validation errors
- ✅ User reviews validation preview (pass/fail counts)
- ✅ User clicks "Import" to bulk-create rows (only valid ones)
- ✅ System shows import summary (X created, Y failed with error details)

### Story 2: Data Owner Downloads Template

**As a** Data Owner  
**I want to** download a blank CSV template for a table  
**So that** I can fill it offline and import later

**Acceptance Criteria:**
- ✅ User clicks "Download Template" button
- ✅ System generates CSV with correct headers (field names or labels)
- ✅ Browser downloads template.csv
- ✅ Template includes example row (optional)
- ✅ Template includes field type comments (optional)

### Story 3: Data Owner Exports Filtered Data

**As a** Data Owner  
**I want to** export table data with current filters applied  
**So that** I can analyze subsets in Excel

**Acceptance Criteria:**
- ✅ User applies filters to table (existing functionality)
- ✅ User clicks "Export CSV" button
- ✅ System exports only filtered rows
- ✅ CSV includes all field columns
- ✅ Browser downloads export.csv (existing, ✅ ALREADY WORKS)

### Story 4: Admin Imports Data with Updates

**As an** Admin  
**I want to** upload CSV with row IDs to update existing data  
**So that** I can bulk-edit data from external tools

**Acceptance Criteria:**
- ✅ CSV includes 'id' column for existing rows
- ✅ System detects existing row IDs and performs PATCH (update)
- ✅ System creates new rows for entries without IDs
- ✅ Validation preview shows "X create, Y update"
- ✅ Import executes upsert logic (create + update)

---

## Technical Analysis

### Current Implementation Review

**Frontend Export (✅ Working):**
```javascript
// carbon-frontend/src/api/dataschema.js:155-175
export function exportRowsToCsv(rows, fields, filename = "export.csv") {
  const csvRows = [];
  // Header row
  csvRows.push(fields.map(f => `"${f.label.replace(/"/g, '""')}"`).join(","));
  // Data rows
  for (const row of rows) {
    csvRows.push(fields.map(f => {
      let val = row.values?.[f.name] ?? "";
      // Handle arrays, objects, escaping
      if (Array.isArray(val)) val = val.join("; ");
      if (typeof val === "object" && val !== null) val = JSON.stringify(val);
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(","));
  }
  const csvContent = csvRows.join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
```

**Backend Validation (✅ Working):**
```python
# backend/dataschema/serializers.py:58-105
class DataRowSerializer(serializers.ModelSerializer):
    def validate(self, data):
        data_table = data.get('data_table')
        if data_table:
            # Check required fields
            required_fields = data_table.fields.filter(required=True).values_list('name', flat=True)
            values = data.get('values', {})
            missing = [f for f in required_fields if f not in values or values[f] in (None, '', [])]
            if missing:
                raise serializers.ValidationError({f: "This field is required." for f in missing})
            
            # Validate field types (number, boolean, select, multiselect)
            for f in data_table.fields.all():
                if f.name in values:
                    val = values[f.name]
                    if f.type == 'number':
                        if not isinstance(val, (int, float)):
                            raise serializers.ValidationError({f.name: "Must be a number."})
                        if val < 0:
                            raise serializers.ValidationError({f.name: "Negative values are not allowed."})
                    # ... more validation
        return data
```

**Backend Dependencies (✅ Available):**
```
pandas==2.3.0                         # CSV/Excel parsing
numpy==2.2.6                          # Data manipulation
```

**Design Document Reference:**
[`docs/importexport_app/importexport-design-v1.0.md`](../docs/importexport_app/importexport-design-v1.0.md) proposes:
- Separate `importexport` Django app
- ImportJob/ExportJob models (job tracking, logging)
- Async job support (Celery for large files)
- Audit trail for all operations

**Decision:** For RUN A9, implement **simplified inline import** without separate app. Advanced features (job tracking, async) deferred to future.

---

## Implementation Design

### Architecture Decision: Inline Import (No Separate App)

**Rationale:**
1. **Simplicity:** Avoid creating new Django app for MVP
2. **Speed:** Reuse existing [`DataRowViewSet`](../backend/dataschema/views.py:104-131)
3. **Pattern Reuse:** Leverage A8 evidence upload patterns (file handling, validation)
4. **Future Migration:** Can extract to `importexport` app later if needed

**Approach:**
- Add custom actions to [`DataRowViewSet`](../backend/dataschema/views.py:104-131):
  - `@action` `bulk_import` (POST with CSV/Excel file)
  - `@action` `download_template` (GET returns CSV template)
- Frontend: New component `BulkImportWizard.jsx` (modal, 3 steps)
- Validation: Reuse existing [`DataRowSerializer`](../backend/dataschema/serializers.py:58) validation logic

---

## Component Design

### Backend: Bulk Import API

**New Custom Actions in DataRowViewSet:**

```python
# backend/dataschema/views.py (additions)

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import io

class DataRowViewSet(ScopedViewSet):
    # ... existing code ...
    
    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """
        Bulk import data rows from CSV/Excel file.
        
        Request:
            - file: uploaded CSV/Excel file
            - data_table: table ID
            - column_mapping: JSON dict mapping CSV headers to field names
            - mode: 'create' or 'upsert' (default: create)
        
        Response:
            - created: count of rows created
            - updated: count of rows updated
            - failed: count of rows failed
            - errors: list of {row_number, errors}
        """
        file = request.FILES.get('file')
        data_table_id = request.data.get('data_table')
        column_mapping = request.data.get('column_mapping')  # JSON string
        mode = request.data.get('mode', 'create')  # 'create' or 'upsert'
        
        if not file or not data_table_id:
            return Response(
                {'error': 'file and data_table required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': 'DataTable not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse file (CSV or Excel)
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file.read()))
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file.read()))
            else:
                return Response(
                    {'error': 'File must be CSV or Excel'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to parse file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply column mapping
        if column_mapping:
            import json
            mapping = json.loads(column_mapping)
            df = df.rename(columns=mapping)
        
        # Validate and import rows
        results = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for idx, row in df.iterrows():
            row_data = row.to_dict()
            
            # Check if update (has 'id' column)
            row_id = row_data.pop('id', None)
            
            try:
                if mode == 'upsert' and row_id:
                    # Update existing row
                    instance = DataRow.objects.get(pk=row_id, data_table=data_table)
                    serializer = DataRowSerializer(instance, data={'values': row_data}, partial=True)
                    serializer.is_valid(raise_exception=True)
                    serializer.save(updated_by=request.user)
                    results['updated'] += 1
                else:
                    # Create new row
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
    
    @action(detail=False, methods=['get'], url_path='download-template')
    def download_template(self, request):
        """
        Generate blank CSV template for a table.
        
        Query params:
            - data_table: table ID
            - include_example: 'true' to include example row (optional)
        
        Returns:
            - CSV file with headers (field names or labels)
        """
        data_table_id = request.query_params.get('data_table')
        include_example = request.query_params.get('include_example') == 'true'
        
        if not data_table_id:
            return Response(
                {'error': 'data_table required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': 'DataTable not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate CSV header
        fields = data_table.fields.filter(is_active=True).order_by('order')
        headers = [f.name for f in fields]  # Use field names
        
        csv_rows = [','.join(f'"{h}"' for h in headers)]
        
        if include_example:
            # Add example row with placeholder values
            example_values = []
            for f in fields:
                if f.type == 'string':
                    example_values.append('"example text"')
                elif f.type == 'number':
                    example_values.append('123')
                elif f.type == 'date':
                    example_values.append('"2026-01-01"')
                elif f.type == 'boolean':
                    example_values.append('true')
                elif f.type == 'select':
                    options = f.options or []
                    example_values.append(f'"{options[0]["value"]}"' if options else '""')
                else:
                    example_values.append('""')
            csv_rows.append(','.join(example_values))
        
        csv_content = '\r\n'.join(csv_rows)
        
        # Return as file download
        from django.http import HttpResponse
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{data_table.name}_template.csv"'
        return response
```

**URL Registration:**
```python
# backend/dataschema/urls.py (existing router, no changes needed)
# Custom actions auto-registered:
# POST /carbon-api/datarows/bulk-import/
# GET /carbon-api/datarows/download-template/?data_table=X
```

---

### Frontend: Bulk Import Wizard

**New Component: `BulkImportWizard.jsx`**

**UX Flow (3-Step Modal):**

```
Step 1: File Upload
┌─────────────────────────────────────┐
│  Bulk Import                    [X] │
├─────────────────────────────────────┤
│  Step 1 of 3: Upload File           │
│                                     │
│  ┌───────────────────────────────┐ │
│  │  Drag & Drop CSV/Excel here   │ │
│  │  or click to browse           │ │
│  └───────────────────────────────┘ │
│                                     │
│  Selected: transport_data.csv       │
│  (1,234 rows detected)              │
│                                     │
│           [Cancel]  [Next →]        │
└─────────────────────────────────────┘

Step 2: Column Mapping
┌─────────────────────────────────────┐
│  Bulk Import                    [X] │
├─────────────────────────────────────┤
│  Step 2 of 3: Map Columns           │
│                                     │
│  CSV Column      →  Table Field     │
│  ─────────────────────────────────  │
│  Date            →  [date ▼]        │
│  Bus Line        →  [bus_line ▼]    │
│  Distance (km)   →  [distance ▼]    │
│  Emissions       →  [emissions_kg ▼]│
│                                     │
│  3 matched, 1 unmapped              │
│                                     │
│        [← Back]  [Next →]           │
└─────────────────────────────────────┘

Step 3: Validation Preview
┌─────────────────────────────────────┐
│  Bulk Import                    [X] │
├─────────────────────────────────────┤
│  Step 3 of 3: Validation Results    │
│                                     │
│  ✅ 1,180 rows valid                │
│  ❌ 54 rows have errors             │
│                                     │
│  Errors by type:                    │
│  • Missing required field 'date': 30│
│  • Invalid number 'distance': 24    │
│                                     │
│  [Show Error Details ▼]             │
│  Row 5: Missing required field      │
│  Row 12: Invalid date format        │
│  ...                                │
│                                     │
│  ☐ Import only valid rows (1,180)   │
│                                     │
│        [← Back]  [Import →]         │
└─────────────────────────────────────┘
```

**Component Implementation:**

```jsx
// carbon-frontend/src/components/import/BulkImportWizard.jsx

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Stepper,
  Step,
  StepLabel,
  Box,
  Typography,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel,
  CircularProgress
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import Papa from 'papaparse';  // CSV parsing library

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8009';

export default function BulkImportWizard({ open, onClose, tableId, fields, token, onImportComplete }) {
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [validationResults, setValidationResults] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importOnlyValid, setImportOnlyValid] = useState(true);

  const steps = ['Upload File', 'Map Columns', 'Validation Preview'];

  // Step 1: File Upload
  const onDrop = (acceptedFiles) => {
    const uploadedFile = acceptedFiles[0];
    setFile(uploadedFile);

    // Parse CSV using papaparse
    Papa.parse(uploadedFile, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        setParsedData(results.data);
        
        // Auto-generate column mapping (exact match or fuzzy)
        const autoMapping = {};
        const csvHeaders = results.meta.fields;
        csvHeaders.forEach(csvHeader => {
          const match = fields.find(f => 
            f.name.toLowerCase() === csvHeader.toLowerCase() ||
            f.label.toLowerCase() === csvHeader.toLowerCase()
          );
          if (match) {
            autoMapping[csvHeader] = match.name;
          }
        });
        setColumnMapping(autoMapping);
        setActiveStep(1);  // Move to mapping step
      },
      error: (error) => {
        console.error('CSV parse error:', error);
      }
    });
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    maxFiles: 1
  });

  // Step 2: Column Mapping
  const handleMappingChange = (csvColumn, tableField) => {
    setColumnMapping(prev => ({
      ...prev,
      [csvColumn]: tableField
    }));
  };

  const handleNext = async () => {
    if (activeStep === 1) {
      // Validate before moving to step 3
      await validateData();
    }
    setActiveStep(prev => prev + 1);
  };

  const handleBack = () => {
    setActiveStep(prev => prev - 1);
  };

  // Step 3: Validation
  const validateData = async () => {
    // Client-side validation preview (before actual import)
    const errors = [];
    const validRows = [];

    parsedData.forEach((row, idx) => {
      const mappedRow = {};
      Object.keys(columnMapping).forEach(csvCol => {
        const tableField = columnMapping[csvCol];
        if (tableField) {
          mappedRow[tableField] = row[csvCol];
        }
      });

      // Validate against field requirements
      const rowErrors = [];
      fields.forEach(field => {
        if (field.required && !mappedRow[field.name]) {
          rowErrors.push(`Missing required field '${field.label}'`);
        }
        if (field.type === 'number' && mappedRow[field.name] && isNaN(mappedRow[field.name])) {
          rowErrors.push(`'${field.label}' must be a number`);
        }
      });

      if (rowErrors.length > 0) {
        errors.push({ row: idx + 2, errors: rowErrors, data: row });
      } else {
        validRows.push(mappedRow);
      }
    });

    setValidationResults({
      validCount: validRows.length,
      errorCount: errors.length,
      errors: errors,
      validRows: validRows
    });
  };

  // Step 3: Import
  const handleImport = async () => {
    setImporting(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('data_table', tableId);
    formData.append('column_mapping', JSON.stringify(columnMapping));
    formData.append('mode', 'create');

    try {
      const response = await fetch(`${API_BASE_URL}/carbon-api/datarows/bulk-import/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        throw new Error('Import failed');
      }

      const result = await response.json();
      
      // Show success message
      onImportComplete?.(result);
      onClose();
    } catch (error) {
      console.error('Import error:', error);
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Bulk Import Data</DialogTitle>
      
      <DialogContent>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
          {steps.map(label => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* Step 1: Upload */}
        {activeStep === 0 && (
          <Box>
            <Box
              {...getRootProps()}
              sx={{
                border: '2px dashed',
                borderColor: isDragActive ? 'primary.main' : 'grey.400',
                borderRadius: 2,
                p: 4,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: isDragActive ? 'action.hover' : 'background.paper'
              }}
            >
              <input {...getInputProps()} />
              <Typography variant="body1">
                {isDragActive ? 'Drop file here...' : 'Drag & drop CSV/Excel file or click to browse'}
              </Typography>
            </Box>
            
            {file && (
              <Alert severity="success" sx={{ mt: 2 }}>
                Selected: {file.name} ({parsedData?.length || 0} rows detected)
              </Alert>
            )}
          </Box>
        )}

        {/* Step 2: Column Mapping */}
        {activeStep === 1 && parsedData && (
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Map CSV columns to table fields
            </Typography>
            
            {Object.keys(parsedData[0]).map(csvCol => (
              <Box key={csvCol} sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Typography sx={{ minWidth: 150 }}>{csvCol}</Typography>
                <Typography>→</Typography>
                <FormControl fullWidth>
                  <InputLabel>Table Field</InputLabel>
                  <Select
                    value={columnMapping[csvCol] || ''}
                    onChange={(e) => handleMappingChange(csvCol, e.target.value)}
                    label="Table Field"
                  >
                    <MenuItem value="">-- Skip --</MenuItem>
                    {fields.map(field => (
                      <MenuItem key={field.name} value={field.name}>
                        {field.label} ({field.type})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            ))}
          </Box>
        )}

        {/* Step 3: Validation */}
        {activeStep === 2 && validationResults && (
          <Box>
            <Alert severity={validationResults.errorCount === 0 ? 'success' : 'warning'} sx={{ mb: 2 }}>
              ✅ {validationResults.validCount} rows valid<br />
              {validationResults.errorCount > 0 && `❌ ${validationResults.errorCount} rows have errors`}
            </Alert>

            {validationResults.errorCount > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>Error Details:</Typography>
                {validationResults.errors.slice(0, 10).map((err, idx) => (
                  <Typography key={idx} variant="body2" color="error">
                    Row {err.row}: {err.errors.join(', ')}
                  </Typography>
                ))}
                {validationResults.errors.length > 10 && (
                  <Typography variant="body2" color="text.secondary">
                    ... and {validationResults.errors.length - 10} more errors
                  </Typography>
                )}

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={importOnlyValid}
                      onChange={(e) => setImportOnlyValid(e.target.checked)}
                    />
                  }
                  label={`Import only valid rows (${validationResults.validCount})`}
                  sx={{ mt: 2 }}
                />
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        {activeStep > 0 && <Button onClick={handleBack}>Back</Button>}
        {activeStep < steps.length - 1 && (
          <Button onClick={handleNext} variant="contained" disabled={!file}>
            Next
          </Button>
        )}
        {activeStep === steps.length - 1 && (
          <Button
            onClick={handleImport}
            variant="contained"
            disabled={importing || (validationResults.validCount === 0)}
            startIcon={importing ? <CircularProgress size={18} /> : null}
          >
            Import
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
```

---

### Frontend: Integration with TableDataPage

**Add Import Button:**

```jsx
// carbon-frontend/src/components/TableDataPage.jsx (additions)

import BulkImportWizard from './import/BulkImportWizard';
import UploadIcon from '@mui/icons-material/Upload';
import DownloadIcon from '@mui/icons-material/Download';

export default function TableDataPage({ ... }) {
  const [showImportWizard, setShowImportWizard] = useState(false);

  const handleImportComplete = (result) => {
    notify({
      message: `Import complete: ${result.created} created, ${result.failed} failed`,
      type: result.failed > 0 ? 'warning' : 'success'
    });
    fetchRows();  // Refresh table
  };

  const handleDownloadTemplate = async () => {
    try {
      const url = `${API_BASE_URL}/carbon-api/datarows/download-template/?data_table=${tableId}`;
      const response = await fetch(url, {
        headers: { 'Authorization': `Token ${token}` }
      });
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${table?.name || 'template'}.csv`;
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      notify({ message: 'Template downloaded', type: 'success' });
    } catch (err) {
      notify({ message: 'Failed to download template', type: 'error' });
    }
  };

  return (
    <Box>
      {/* ... existing code ... */}

      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button
          startIcon={<UploadIcon />}
          onClick={() => setShowImportWizard(true)}
          variant="outlined"
          size="small"
        >
          Import
        </Button>

        <Button
          startIcon={<DownloadIcon />}
          onClick={handleDownloadTemplate}
          variant="outlined"
          size="small"
        >
          Template
        </Button>

        <Button
          startIcon={<AttachFileIcon />}
          onClick={() => setShowEvidenceModal(true)}
          disabled={!selectedRowId || selected.length !== 1}
          variant="outlined"
          size="small"
        >
          Evidence
        </Button>
      </Box>

      {/* Existing BulkActionBar, DataTableGrid, Evidence Modal */}

      <BulkImportWizard
        open={showImportWizard}
        onClose={() => setShowImportWizard(false)}
        tableId={tableId}
        fields={fields}
        token={token}
        onImportComplete={handleImportComplete}
      />
    </Box>
  );
}
```

---

## Dependencies

### Frontend

**New Libraries:**
```json
{
  "dependencies": {
    "papaparse": "^5.4.1",  // CSV parsing
    "react-dropzone": "^19.0.2"  // ✅ Already installed (A8)
  }
}
```

Install:
```bash
cd carbon-frontend
npm install papaparse
```

### Backend

**Existing Libraries (✅ Already Available):**
```
pandas==2.3.0      # CSV/Excel parsing
numpy==2.2.6       # Data manipulation
openpyxl           # Excel support (pandas dependency)
```

No additional backend dependencies needed.

---

## Testing Strategy

### Backend API Tests

```python
# backend/dataschema/tests/test_bulk_import.py

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from accounts.models import User
from core.models import Organization, Module
from dataschema.models import DataTable, DataField, DataRow

@pytest.mark.django_db
class TestBulkImport:
    def test_bulk_import_csv(self):
        """Test bulk import with valid CSV file"""
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='pass')
        client.force_authenticate(user=user)
        
        org = Organization.objects.create(name='Test Org')
        module = Module.objects.create(name='Test Module', scope='scope1', org_unit=org)
        table = DataTable.objects.create(title='Test Table', module=module)
        DataField.objects.create(data_table=table, name='name', label='Name', type='string', required=True)
        DataField.objects.create(data_table=table, name='age', label='Age', type='number')
        
        csv_content = b'name,age\nAlice,30\nBob,25'
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': table.id,
            'mode': 'create'
        })
        
        assert response.status_code == 200
        assert response.data['created'] == 2
        assert response.data['failed'] == 0
        assert DataRow.objects.filter(data_table=table).count() == 2
    
    def test_bulk_import_validation_errors(self):
        """Test bulk import with missing required fields"""
        # ... similar setup ...
        csv_content = b'name,age\n,30\nBob,'  # Missing name in row 1, missing age in row 2
        csv_file = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')
        
        response = client.post('/carbon-api/datarows/bulk-import/', {
            'file': csv_file,
            'data_table': table.id,
            'mode': 'create'
        })
        
        assert response.status_code == 200
        assert response.data['created'] == 0
        assert response.data['failed'] == 2
        assert len(response.data['errors']) == 2
    
    def test_download_template(self):
        """Test CSV template generation"""
        # ... similar setup ...
        response = client.get(f'/carbon-api/datarows/download-template/?data_table={table.id}')
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert b'name,age' in response.content
```

### Frontend Component Tests

```javascript
// carbon-frontend/src/components/import/BulkImportWizard.test.jsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BulkImportWizard from './BulkImportWizard';

describe('BulkImportWizard', () => {
  const mockFields = [
    { name: 'name', label: 'Name', type: 'string', required: true },
    { name: 'age', label: 'Age', type: 'number', required: false }
  ];

  test('renders upload step initially', () => {
    render(<BulkImportWizard open={true} onClose={() => {}} tableId={1} fields={mockFields} token="test" />);
    expect(screen.getByText(/drag & drop csv/i)).toBeInTheDocument();
  });

  test('parses CSV and moves to mapping step', async () => {
    const { getByText } = render(<BulkImportWizard open={true} onClose={() => {}} tableId={1} fields={mockFields} token="test" />);
    
    const file = new File(['name,age\nAlice,30'], 'test.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]');
    
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(getByText(/map columns/i)).toBeInTheDocument();
    });
  });

  test('validates data before import', async () => {
    // ... test validation step ...
  });
});
```

---

## Implementation Phases

### Phase 1: Backend Bulk Import API ✅
**Deliverables:**
- Add `bulk_import()` action to `DataRowViewSet`
- Add `download_template()` action to `DataRowViewSet`
- CSV/Excel parsing with pandas
- Validation using existing `DataRowSerializer`
- Return results (created, updated, failed, errors)

**Files:**
- `backend/dataschema/views.py` - Add custom actions
- `backend/dataschema/tests/test_bulk_import.py` - API tests

**Acceptance:**
- ✅ POST `/carbon-api/datarows/bulk-import/` accepts CSV/Excel
- ✅ Parses file, validates, bulk-creates rows
- ✅ Returns detailed results with error list
- ✅ GET `/carbon-api/datarows/download-template/` returns CSV template
- ✅ Tests pass (5 backend API tests)

---

### Phase 2: Frontend Import Wizard Component ✅
**Deliverables:**
- `BulkImportWizard.jsx` (3-step modal)
- Step 1: File upload (drag-and-drop)
- Step 2: Column mapping interface
- Step 3: Validation preview
- Integration with papaparse for CSV parsing

**Files:**
- `carbon-frontend/src/components/import/BulkImportWizard.jsx` - Main wizard
- `carbon-frontend/package.json` - Add papaparse

**Acceptance:**
- ✅ Modal opens with 3-step stepper
- ✅ Step 1 accepts CSV/Excel upload
- ✅ Step 2 shows column mapping dropdowns
- ✅ Step 3 shows validation results (valid/error counts)
- ✅ Tests pass (4 component tests)

---

### Phase 3: TableDataPage Integration ✅
**Deliverables:**
- Add Import and Template buttons to toolbar
- Integrate `BulkImportWizard` component
- Handle import completion (refresh table, show summary)
- Handle template download

**Files:**
- `carbon-frontend/src/components/TableDataPage.jsx` - Add buttons and handlers

**Acceptance:**
- ✅ Import button opens wizard modal
- ✅ Template button downloads CSV
- ✅ Import completion refreshes table
- ✅ Success/error notifications shown
- ✅ Tests pass (3 integration tests)

---

### Phase 4: Testing & Validation ✅
**Deliverables:**
- Backend API tests (bulk import, template, validation, errors)
- Frontend component tests (wizard steps, mapping, validation)
- Integration tests (end-to-end import flow)
- Browser testing (upload, map, import, verify)

**Files:**
- `backend/dataschema/tests/test_bulk_import.py` - Backend tests
- `carbon-frontend/src/components/import/BulkImportWizard.test.jsx` - Component tests

**Acceptance:**
- ✅ All 12 tests pass (5 backend + 4 component + 3 integration)
- ✅ Browser testing successful
- ✅ Error handling verified
- ✅ No console errors

---

### Phase 5: Documentation ✅
**Deliverables:**
- Update `RUN_LOG.md` with A9 entry
- Create `TASK-RESULT-A9.md`
- User guide for bulk import feature
- API documentation

**Files:**
- `docs/RUN_LOG.md` - Add A9 entry
- `TASK-RESULT-A9.md` - Complete deliverables report

**Acceptance:**
- ✅ RUN_LOG.md updated
- ✅ TASK-RESULT-A9.md created
- ✅ Documentation complete

---

## Acceptance Criteria

### Backend (8 criteria)
- [ ] `bulk_import` action accepts CSV/Excel files
- [ ] Parses file using pandas
- [ ] Applies column mapping from request
- [ ] Validates rows using `DataRowSerializer`
- [ ] Bulk-creates valid rows
- [ ] Returns detailed results (created, failed, errors)
- [ ] `download_template` action returns CSV with table headers
- [ ] RBAC enforced (dataowners_group can import to their modules)

### Frontend (10 criteria)
- [ ] `BulkImportWizard` component renders 3-step modal
- [ ] Step 1: File upload with drag-and-drop
- [ ] Step 2: Column mapping with dropdowns
- [ ] Step 3: Validation preview with error details
- [ ] Auto-mapping attempts exact/fuzzy column name matching
- [ ] Import button disabled until validation passes
- [ ] Import calls backend API with FormData
- [ ] Success notification shows import summary
- [ ] Template button downloads CSV file
- [ ] Import button in `TableDataPage` toolbar

### Integration (5 criteria)
- [ ] Upload CSV → Parse → Map → Validate → Import workflow complete
- [ ] Template download includes correct field names
- [ ] Validation errors displayed per row
- [ ] Import completion refreshes table data
- [ ] No console errors during import flow

### Testing (5 criteria)
- [ ] Backend API tests pass (5 tests)
- [ ] Frontend component tests pass (4 tests)
- [ ] Integration tests pass (3 tests)
- [ ] Browser testing successful
- [ ] Error handling verified

**Total: 28 Acceptance Criteria**

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Large file upload timeout | Medium | High | Add file size limit (10,000 rows for MVP), show progress indicator |
| Excel parsing issues (formats) | Medium | Medium | Support .xlsx and .xls, show clear error if unsupported format |
| Column mapping ambiguity | Medium | Medium | Implement fuzzy matching, allow manual override, show preview |
| Validation errors overwhelming UI | Low | Medium | Limit error display to 10-20 rows, provide download full error log |
| RBAC bypass via bulk import | Low | High | Reuse existing RBAC checks in `DataRowViewSet.get_queryset()` |
| Memory issues with large CSV | Medium | Medium | Use pandas chunking for files >5MB, add server-side limits |

---

## Future Enhancements (Out of Scope for A9)

1. **Async Import Jobs** - Background task processing with Celery for large files (>10,000 rows)
2. **Import Job History** - Track import jobs with status, logs, downloadable error reports
3. **Update Mode (Upsert)** - Support updating existing rows via ID column
4. **Excel Export** - Export to .xlsx format (currently CSV only)
5. **Batch Delete via CSV** - Upload CSV with IDs to bulk-delete rows
6. **Template with Data Types** - Include field type comments in template (e.g., `# name (string, required)`)
7. **Import Wizard Presets** - Save column mappings for reuse
8. **Direct Google Sheets Import** - OAuth integration for Google Sheets connector
9. **Scheduled Imports** - Recurring import jobs from FTP/SFTP/S3
10. **Import Rollback** - Undo import operation

---

## Definition of Done

- [ ] All 5 phases completed
- [ ] All 28 acceptance criteria met
- [ ] All 12 tests passing (100%)
- [ ] Frontend builds without errors
- [ ] Backend migrations applied
- [ ] No console errors in browser
- [ ] Documentation complete (`RUN_LOG.md`, `TASK-RESULT-A9.md`)
- [ ] Code reviewed and approved by architect
- [ ] RBAC enforcement verified
- [ ] User testing successful

---

## Next Steps After A9

**RUN A10: Data Lineage Panel** - Resizable right drawer showing data provenance, edit history, comments

Reference: [`plans/PLATFORM_COMPLETION_AUDIT.md:422-446`](../plans/PLATFORM_COMPLETION_AUDIT.md:422-446)

---

## References

- **A8 Evidence Upload Pattern:** [`backend/evidence/views.py`](../backend/evidence/views.py:69-130) (bulk_upload action reference)
- **Existing Export:** [`carbon-frontend/src/api/dataschema.js:155-175`](../carbon-frontend/src/api/dataschema.js:155-175)
- **DataRow Validation:** [`backend/dataschema/serializers.py:58-105`](../backend/dataschema/serializers.py:58-105)
- **ImportExport Design:** [`docs/importexport_app/importexport-design-v1.0.md`](../docs/importexport_app/importexport-design-v1.0.md)
- **Platform Audit:** [`plans/PLATFORM_COMPLETION_AUDIT.md:397-420`](../plans/PLATFORM_COMPLETION_AUDIT.md:397-420)
