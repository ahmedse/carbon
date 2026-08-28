// carbon-frontend/src/components/import/BulkImportWizard.jsx

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
import { API_BASE_URL } from '../../config';
import { authFetch } from '../../api/api';

export default function BulkImportWizard({ open, onClose, tableId, fields, token, onImportComplete }) {
  const { t } = useTranslation('importexport');
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState(null);
  const [csvHeaders, setCsvHeaders] = useState([]);
  const [columnMapping, setColumnMapping] = useState({});
  const [validationResults, setValidationResults] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importOnlyValid, setImportOnlyValid] = useState(true);
  const [error, setError] = useState(null);

  const steps = [t('stepUpload'), t('stepMap'), t('stepValidate')];

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
          setError(t('csvParseError', { message: results.errors[0].message }));
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
        setError(t('csvParseFailed', { message: err.message }));
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
          rowErrors.push(t('missingRequired', { label: field.label }));
        }
        
        // Type validation
        if (value !== null && value !== undefined && value !== '') {
          if (field.type === 'number') {
            const numValue = Number(value);
            if (isNaN(numValue)) {
              rowErrors.push(t('mustBeNumber', { label: field.label, value }));
            } else if (numValue < 0) {
              rowErrors.push(t('cannotBeNegative', { label: field.label }));
            }
          }
          
          if (field.type === 'boolean') {
            const boolValue = String(value).toLowerCase();
            if (!['true', 'false', '1', '0', 'yes', 'no'].includes(boolValue)) {
              rowErrors.push(t('mustBeBoolean', { label: field.label, value }));
            }
          }
          
          if (field.type === 'select' && field.options) {
            const allowedValues = field.options.map(opt => opt.value);
            if (!allowedValues.includes(value)) {
              rowErrors.push(t('mustBeOneOf', { label: field.label, values: allowedValues.join(', ') }));
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
      const response = await authFetch('datarows/bulk-import/', {
        method: 'POST',
        body: formData,
        token,
        headers: {
          // authFetch handles Authorization header, FormData body
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || t('importFailed'));
      }

      const result = await response.json();
      
      // Call completion callback with results
      onImportComplete?.(result);
      handleClose();
    } catch (err) {
      setError(err.message || t('importFailed'));
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
      <DialogTitle>{t('title')}</DialogTitle>
      
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
              {t('uploadHint')}
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
                {isDragActive ? t('dropHere') : t('dragDrop')}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                {t('supported')}
              </Typography>
            </Box>
            
            {file && (
              <Alert severity="success" sx={{ mt: 2 }}>
                <strong>{t('selected')}</strong> {file.name} ({t('rowsDetected', { count: parsedData?.length || 0 })})
              </Alert>
            )}
          </Box>
        )}

        {/* Step 2: Column Mapping */}
        {activeStep === 1 && parsedData && (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              {t('mappedCount', { mapped: getMappedCount(), unmapped: getUnmappedCount() })}
            </Alert>
            
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {t('mappingHint')}
            </Typography>
            
            <Table size="small" sx={{ mt: 2 }}>
              <TableHead>
                <TableRow>
                  <TableCell><strong>{t('csvColumn')}</strong></TableCell>
                  <TableCell><strong>{t('arrow')}</strong></TableCell>
                  <TableCell><strong>{t('tableField')}</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {csvHeaders.map(csvCol => (
                  <TableRow key={csvCol}>
                    <TableCell>{csvCol}</TableCell>
                    <TableCell>{t('arrow')}</TableCell>
                    <TableCell>
                      <FormControl fullWidth size="small">
                        <Select
                          value={columnMapping[csvCol] || ''}
                          onChange={(e) => handleMappingChange(csvCol, e.target.value)}
                          displayEmpty
                        >
                          <MenuItem value="">{t('skip')}</MenuItem>
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
              <strong>✅ {t('rowsValid', { count: validationResults.validCount })}</strong><br />
              {validationResults.errorCount > 0 && (
                <span>❌ {t('rowsHaveErrors', { count: validationResults.errorCount })}</span>
              )}
            </Alert>

            {validationResults.errorCount > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                  {t('errorsByType')}
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
                  {t('errorDetails')}
                </Typography>
                
                <Box sx={{ maxHeight: 200, overflow: 'auto', bgcolor: 'grey.50', p: 1, borderRadius: 1 }}>
                  {validationResults.errors.slice(0, 10).map((err, idx) => (
                    <Typography key={idx} variant="body2" color="error" sx={{ mb: 0.5 }}>
                      <strong>{t('rowN', { row: err.row })}</strong> {err.errors.join(', ')}
                    </Typography>
                  ))}
                  {validationResults.errors.length > 10 && (
                    <Typography variant="body2" color="text.secondary">
                      {t('moreErrors', { count: validationResults.errors.length - 10 })}
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
                  label={t('importOnlyValid', { count: validationResults.validCount })}
                  sx={{ mt: 2 }}
                />
              </Box>
            )}

            {validationResults.errorCount === 0 && (
              <Typography variant="body2" color="success.main" sx={{ mt: 2 }}>
                {t('allValid')}
              </Typography>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={importing}>
          {t('cancel')}
        </Button>
        {activeStep > 0 && (
          <Button onClick={handleBack} disabled={importing}>
            {t('back')}
          </Button>
        )}
        {activeStep < steps.length - 1 && (
          <Button 
            onClick={handleNext} 
            variant="contained" 
            disabled={!file || (activeStep === 1 && getMappedCount() === 0)}
          >
            {t('next')}
          </Button>
        )}
        {activeStep === steps.length - 1 && (
          <Button
            onClick={handleImport}
            variant="contained"
            disabled={importing || validationResults.validCount === 0}
            startIcon={importing ? <CircularProgress size={18} /> : null}
          >
            {importing ? t('importing') : t('import')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
