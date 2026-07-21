# TASK A9 - PHASE 2: Frontend Import Wizard Component

**Phase:** 2 of 5  
**Focus:** React Frontend - Bulk Import Wizard (3-Step Modal)  
**Duration:** Step-by-step execution

---

## Objective

Create a `BulkImportWizard` React component with a 3-step wizard interface: (1) File Upload, (2) Column Mapping, (3) Validation Preview. Use Material-UI for consistent styling and react-dropzone for file upload.

---

## Scope - IN

✅ Create `BulkImportWizard.jsx` component (modal dialog)  
✅ Step 1: File upload with drag-and-drop (react-dropzone)  
✅ Step 2: Column mapping interface (CSV headers → table fields)  
✅ Step 3: Validation preview (show valid/error counts)  
✅ CSV parsing using papaparse library  
✅ Auto-mapping logic (match CSV headers to field names)  
✅ Client-side validation preview  
✅ Import API call to backend  
✅ Success/error feedback

---

## Scope - OUT

❌ Backend API (Phase 1 complete)  
❌ TableDataPage integration (Phase 3)  
❌ Excel parsing (backend handles this, frontend just uploads file)  
❌ Import job history UI  
❌ Advanced mapping (fuzzy matching with confidence scores)

---

## Preconditions

1. Phase 1 complete (backend API working)
2. Frontend dev server running (`npm run dev`)
3. `react-dropzone` installed (from A8: `react-dropzone@^19.0.2`)
4. Material-UI installed (`@mui/material@^7.1.0`)

---

## Implementation Steps

### Step 1: Install papaparse Library

**Task:** Add CSV parsing library

**Command:**

```bash
cd carbon-frontend
npm install papaparse
```

**Verify:**

```bash
npm list papaparse
# Should show: papaparse@5.x.x
```

**Update `package.json`:**

```json
{
  "dependencies": {
    // ... existing ...
    "papaparse": "^5.4.1",
    "react-dropzone": "^19.0.2"
  }
}
```

---

### Step 2: Create BulkImportWizard Component

**File:** `carbon-frontend/src/components/import/BulkImportWizard.jsx` (NEW)

**Task:** Create 3-step wizard component

**Full Code:**

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
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Chip
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import Papa from 'papaparse';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8009';

export default function BulkImportWizard({ open, onClose, tableId, fields, token, onImportComplete }) {
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [csvHeaders, setCsvHeaders] = useState([]);
  const [columnMapping, setColumnMapping] = useState({});
  const [validationResults, setValidationResults] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importOnlyValid, setImportOnlyValid] = useState(true);
  const [error, setError] = useState(null);

  const steps = ['Upload File', 'Map Columns', 'Validation Preview'];

  // Reset state when dialog closes
  const handleClose = () => {
    setActiveStep(0);
    setFile(null);
    setParsedData(null);
    setCsvHeaders([]);
    setColumnMapping({});
    setValidationResults(null);
    setImporting(false);
    setError(null);
    onClose();
  };

  // Step 1: File Upload
  const onDrop = (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    const uploadedFile = acceptedFiles[0];
    setFile(uploadedFile);
    setError(null);

    // Parse CSV using papaparse
    Papa.parse(uploadedFile, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.errors.length > 0) {
          setError(`CSV parse error: ${results.errors[0].message}`);
          return;
        }

        setParsedData(results.data);
        setCsvHeaders(results.meta.fields || []);

        // Auto-generate column mapping (exact match or fuzzy)
        const autoMapping = {};
        const headers = results.meta.fields || [];
        
        headers.forEach(csvHeader => {
          // Try exact match (case-insensitive)
          const exactMatch = fields.find(f => 
            f.name.toLowerCase() === csvHeader.toLowerCase() ||
            f.label.toLowerCase() === csvHeader.toLowerCase()
          );
          
          if (exactMatch) {
            autoMapping[csvHeader] = exactMatch.name;
          } else {
            // Try fuzzy match (remove spaces, underscores)
            const normalizedCsvHeader = csvHeader.toLowerCase().replace(/[\s_-]/g, '');
            const fuzzyMatch = fields.find(f => {
              const normalizedFieldName = f.name.toLowerCase().replace(/[\s_-]/g, '');
              const normalizedFieldLabel = f.label.toLowerCase().replace(/[\s_-]/g, '');
              return normalizedFieldName === normalizedCsvHeader || normalizedFieldLabel === normalizedCsvHeader;
            });
            
            if (fuzzyMatch) {
              autoMapping[csvHeader] = fuzzyMatch.name;
            }
          }
        });

        setColumnMapping(autoMapping);
        setActiveStep(1); // Move to mapping step
      },
      error: (err) => {
        setError(`Failed to parse CSV: ${err.message}`);
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
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024 // 10MB limit
  });

  // Step 2: Column Mapping
  const handleMappingChange = (csvColumn, tableField) => {
    setColumnMapping(prev => ({
      ...prev,
      [csvColumn]: tableField
    }));
  };

  const getMappedCount = () => {
    return Object.values(columnMapping).filter(v => v && v !== '').length;
  };

  const getUnmappedCount = () => {
    return csvHeaders.length - getMappedCount();
  };

  // Step 3: Client-side Validation
  const validateData = () => {
    const errors = [];
    const validRows = [];

    parsedData.forEach((row, idx) => {
      const mappedRow = {};
      
      // Apply column mapping
      Object.keys(columnMapping).forEach(csvCol => {
        const tableField = columnMapping[csvCol];
        if (tableField) {
          let value = row[csvCol];
          // Convert empty strings to null
          if (value === '') value = null;
          mappedRow[tableField] = value;
        }
      });

      // Validate against field requirements
      const rowErrors = [];
      
      fields.forEach(field => {
        const value = mappedRow[field.name];
        
        // Required field validation
        if (field.required && (value === null || value === undefined || value === '')) {
          rowErrors.push(`Missing required field '${field.label}'`);
        }
        
        // Type validation
        if (value !== null && value !== undefined && value !== '') {
          if (field.type === 'number') {
            const numValue = Number(value);
            if (isNaN(numValue)) {
              rowErrors.push(`'${field.label}' must be a number (got: ${value})`);
            } else if (numValue < 0) {
              rowErrors.push(`'${field.label}' cannot be negative`);
            }
          }
          
          if (field.type === 'boolean') {
            const boolValue = String(value).toLowerCase();
            if (!['true', 'false', '1', '0', 'yes', 'no'].includes(boolValue)) {
              rowErrors.push(`'${field.label}' must be true/false (got: ${value})`);
            }
          }
          
          if (field.type === 'select' && field.options) {
            const allowedValues = field.options.map(opt => opt.value);
            if (!allowedValues.includes(value)) {
              rowErrors.push(`'${field.label}' must be one of: ${allowedValues.join(', ')}`);
            }
          }
        }
      });

      if (rowErrors.length > 0) {
        errors.push({ 
          row: idx + 2,  // +2 because: 0-indexed + header row
          errors: rowErrors,
          data: row
        });
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

  // Navigation
  const handleNext = () => {
    if (activeStep === 1) {
      // Validate before moving to step 3
      validateData();
    }
    setActiveStep(prev => prev + 1);
  };

  const handleBack = () => {
    setActiveStep(prev => prev - 1);
  };

  // Step 3: Import
  const handleImport = async () => {
    setImporting(true);
    setError(null);

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
        const errorData = await response.json();
        throw new Error(errorData.error || 'Import failed');
      }

      const result = await response.json();
      
      // Call completion callback with results
      onImportComplete?.(result);
      handleClose();
    } catch (err) {
      setError(err.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  // Helper: Group errors by type
  const getErrorSummary = () => {
    if (!validationResults || validationResults.errorCount === 0) return [];
    
    const errorTypes = {};
    validationResults.errors.forEach(err => {
      err.errors.forEach(errMsg => {
        if (!errorTypes[errMsg]) {
          errorTypes[errMsg] = 0;
        }
        errorTypes[errMsg]++;
      });
    });
    
    return Object.entries(errorTypes).map(([msg, count]) => ({ msg, count }));
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: '60vh', maxHeight: '90vh' }
      }}
    >
      <DialogTitle>Bulk Import Data</DialogTitle>
      
      <DialogContent>
        <Stepper activeStep={activeStep} sx={{ mb: 3, mt: 1 }}>
          {steps.map(label => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Step 1: Upload */}
        {activeStep === 0 && (
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Upload a CSV or Excel file containing data rows. The first row should contain column headers.
            </Typography>
            
            <Box
              {...getRootProps()}
              sx={{
                border: '2px dashed',
                borderColor: isDragActive ? 'primary.main' : 'grey.400',
                borderRadius: 2,
                p: 4,
                mt: 2,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: isDragActive ? 'action.hover' : 'background.paper',
                transition: 'all 0.2s'
              }}
            >
              <input {...getInputProps()} />
              <Typography variant="body1" color={isDragActive ? 'primary' : 'text.primary'}>
                {isDragActive ? 'Drop file here...' : 'Drag & drop CSV/Excel file or click to browse'}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Supported: .csv, .xlsx, .xls (max 10MB)
              </Typography>
            </Box>
            
            {file && (
              <Alert severity="success" sx={{ mt: 2 }}>
                <strong>Selected:</strong> {file.name} ({parsedData?.length || 0} rows detected)
              </Alert>
            )}
          </Box>
        )}

        {/* Step 2: Column Mapping */}
        {activeStep === 1 && parsedData && (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              {getMappedCount()} columns mapped, {getUnmappedCount()} unmapped
            </Alert>
            
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Map CSV columns to table fields. Unmapped columns will be ignored.
            </Typography>
            
            <Table size="small" sx={{ mt: 2 }}>
              <TableHead>
                <TableRow>
                  <TableCell><strong>CSV Column</strong></TableCell>
                  <TableCell><strong>→</strong></TableCell>
                  <TableCell><strong>Table Field</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {csvHeaders.map(csvCol => (
                  <TableRow key={csvCol}>
                    <TableCell>{csvCol}</TableCell>
                    <TableCell>→</TableCell>
                    <TableCell>
                      <FormControl fullWidth size="small">
                        <Select
                          value={columnMapping[csvCol] || ''}
                          onChange={(e) => handleMappingChange(csvCol, e.target.value)}
                          displayEmpty
                        >
                          <MenuItem value="">-- Skip --</MenuItem>
                          {fields.map(field => (
                            <MenuItem key={field.name} value={field.name}>
                              {field.label} ({field.type}){field.required && ' *'}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}

        {/* Step 3: Validation */}
        {activeStep === 2 && validationResults && (
          <Box>
            <Alert 
              severity={validationResults.errorCount === 0 ? 'success' : 'warning'} 
              sx={{ mb: 2 }}
            >
              <strong>✅ {validationResults.validCount} rows valid</strong><br />
              {validationResults.errorCount > 0 && (
                <span>❌ {validationResults.errorCount} rows have errors</span>
              )}
            </Alert>

            {validationResults.errorCount > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                  Errors by type:
                </Typography>
                
                {getErrorSummary().map((errType, idx) => (
                  <Chip
                    key={idx}
                    label={`${errType.msg} (${errType.count})`}
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                    color="error"
                    variant="outlined"
                  />
                ))}

                <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                  Error details (showing first 10):
                </Typography>
                
                <Box sx={{ maxHeight: 200, overflow: 'auto', bgcolor: 'grey.50', p: 1, borderRadius: 1 }}>
                  {validationResults.errors.slice(0, 10).map((err, idx) => (
                    <Typography key={idx} variant="body2" color="error" sx={{ mb: 0.5 }}>
                      <strong>Row {err.row}:</strong> {err.errors.join(', ')}
                    </Typography>
                  ))}
                  {validationResults.errors.length > 10 && (
                    <Typography variant="body2" color="text.secondary">
                      ... and {validationResults.errors.length - 10} more errors
                    </Typography>
                  )}
                </Box>

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

            {validationResults.errorCount === 0 && (
              <Typography variant="body2" color="success.main" sx={{ mt: 2 }}>
                All rows passed validation. Ready to import!
              </Typography>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={importing}>
          Cancel
        </Button>
        {activeStep > 0 && (
          <Button onClick={handleBack} disabled={importing}>
            Back
          </Button>
        )}
        {activeStep < steps.length - 1 && (
          <Button 
            onClick={handleNext} 
            variant="contained" 
            disabled={!file || (activeStep === 1 && getMappedCount() === 0)}
          >
            Next
          </Button>
        )}
        {activeStep === steps.length - 1 && (
          <Button
            onClick={handleImport}
            variant="contained"
            disabled={importing || validationResults.validCount === 0}
            startIcon={importing ? <CircularProgress size={18} /> : null}
          >
            {importing ? 'Importing...' : 'Import'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
```

---

### Step 3: Create Component Index

**File:** `carbon-frontend/src/components/import/index.js` (NEW)

**Code:**

```javascript
// carbon-frontend/src/components/import/index.js
export { default as BulkImportWizard } from './BulkImportWizard';
```

---

### Step 4: Test Component Rendering

**Task:** Create basic component test

**File:** `carbon-frontend/src/components/import/BulkImportWizard.test.jsx` (NEW)

**Code:**

```javascript
// carbon-frontend/src/components/import/BulkImportWizard.test.jsx
import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BulkImportWizard from './BulkImportWizard';

describe('BulkImportWizard', () => {
  const mockFields = [
    { name: 'name', label: 'Name', type: 'string', required: true },
    { name: 'age', label: 'Age', type: 'number', required: false }
  ];

  test('renders upload step initially', () => {
    render(
      <BulkImportWizard 
        open={true} 
        onClose={() => {}} 
        tableId={1} 
        fields={mockFields} 
        token="test-token"
      />
    );
    
    expect(screen.getByText(/upload file/i)).toBeInTheDocument();
    expect(screen.getByText(/drag & drop/i)).toBeInTheDocument();
  });

  test('shows stepper with 3 steps', () => {
    render(
      <BulkImportWizard 
        open={true} 
        onClose={() => {}} 
        tableId={1} 
        fields={mockFields} 
        token="test-token"
      />
    );
    
    expect(screen.getByText('Upload File')).toBeInTheDocument();
    expect(screen.getByText('Map Columns')).toBeInTheDocument();
    expect(screen.getByText('Validation Preview')).toBeInTheDocument();
  });

  test('cancel button closes dialog', () => {
    const onClose = vi.fn();
    render(
      <BulkImportWizard 
        open={true} 
        onClose={onClose} 
        tableId={1} 
        fields={mockFields} 
        token="test-token"
      />
    );
    
    const cancelButton = screen.getByText('Cancel');
    cancelButton.click();
    expect(onClose).toHaveBeenCalled();
  });
});
```

---

## Acceptance Criteria

- [ ] `papaparse` library installed
- [ ] `BulkImportWizard.jsx` component created
- [ ] Step 1: File upload with drag-and-drop renders
- [ ] Step 1: File upload accepts CSV/Excel files
- [ ] Step 1: CSV parsing works (papaparse)
- [ ] Step 2: Column mapping interface renders
- [ ] Step 2: Auto-mapping logic works (exact + fuzzy matching)
- [ ] Step 2: Manual mapping dropdowns work
- [ ] Step 3: Validation preview renders
- [ ] Step 3: Client-side validation works (required, types)
- [ ] Step 3: Error summary displays
- [ ] Import button calls backend API
- [ ] Success callback triggers on completion
- [ ] Component tests pass (3 tests)

**Total: 14 Acceptance Criteria**

---

## Verification Checklist

Before proceeding to Phase 3:

- [ ] `papaparse` installed and in `package.json`
- [ ] Component file created: `carbon-frontend/src/components/import/BulkImportWizard.jsx`
- [ ] Index file created: `carbon-frontend/src/components/import/index.js`
- [ ] Test file created: `carbon-frontend/src/components/import/BulkImportWizard.test.jsx`
- [ ] Run tests: `npm run test`
- [ ] Frontend builds without errors: `npm run build`
- [ ] No console errors in browser DevTools
- [ ] Component renders in isolation (test with mock data)

---

## Next Phase

✅ Phase 2 Complete → Proceed to **Phase 3: TableDataPage Integration**

Phase 3 will integrate the `BulkImportWizard` into `TableDataPage` with Import and Template buttons.
