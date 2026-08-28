// File: src/pages/dataschema/tabs/RowEditTab.jsx
// Edit form for row data with validation and save

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Stack,
  Paper,
  Typography,
  ButtonGroup,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { apiFetch } from '../../../api/api';

function notify(message, type = 'info') {
  const event = new CustomEvent('notify', { detail: { message, type } });
  window.dispatchEvent(event);
}

export default function RowEditTab({
  rowData,
  setRowData,
  tableId,
  rowId,
  token,
  onClose: _onClose,
}) {
  const { t } = useTranslation('dataschema');
  // Extract editable field data from the 'values' object
  const extractEditableFields = (data) => {
    const metadataFields = ['created_at', 'updated_at', 'created_by', 'updated_by'];
    const nonDataFields = ['id', 'data_table', 'is_archived', 'version', 'values', ...metadataFields];
    const fieldData = {};

    // Primary: extract from nested 'values' object
    if (data.values && typeof data.values === 'object') {
      Object.entries(data.values).forEach(([key, value]) => {
        fieldData[key] = value;
      });
    }

    // Fallback: extract from data directly if values is empty
    if (Object.keys(fieldData).length === 0) {
      Object.entries(data).forEach(([key, value]) => {
        if (!nonDataFields.includes(key)) {
          fieldData[key] = value;
        }
      });
    }

    return fieldData;
  };

  const [formData, setFormData] = useState(() => extractEditableFields(rowData));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const parseFormValue = (value) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    if (trimmed === '') return '';
    if (/^-?\d+$/.test(trimmed)) {
      return Number.parseInt(trimmed, 10);
    }
    if (/^-?\d*\.\d+$/.test(trimmed)) {
      return Number.parseFloat(trimmed);
    }
    if (/^(true|false)$/i.test(trimmed)) {
      return trimmed.toLowerCase() === 'true';
    }
    return value;
  };

  useEffect(() => {
    const extracted = extractEditableFields(rowData);
    setFormData(extracted);
    setHasChanges(false);
    setIsDirty(false);
    console.log('🟦 RowEditTab: Form data loaded', {
      fieldsCount: Object.keys(extracted).length,
      fieldNames: Object.keys(extracted),
      sampleValue: Object.values(extracted)[0],
    });
  }, [rowData]);

  // Detect changes - compare formData with properly extracted original
  useEffect(() => {
    const originalExtracted = extractEditableFields(rowData);
    const changed = JSON.stringify(formData) !== JSON.stringify(originalExtracted);
    setHasChanges(changed);
    setIsDirty(changed);
  }, [formData, rowData]);

  // Prevent accidental page exit if there are unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: parseFormValue(value),
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      // Build update payload (exclude metadata fields)
      const excludeFields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by'];
      const fieldData = Object.entries(formData)
        .filter(([key]) => !excludeFields.includes(key))
        .reduce((acc, [key, value]) => {
          acc[key] = value;
          return acc;
        }, {});

      // Backend expects data_table on the request body for validation and will merge values into the row.
      const updatePayload = {
        data_table: Number(tableId),
        values: fieldData,
      };

      console.log('🟦 RowEditTab: Saving with apiFetch', {
        rowId,
        tableId,
        payloadKeys: Object.keys(updatePayload),
        valuesKeys: Object.keys(fieldData),
        fieldDataSample: fieldData,
        updatePayload,
      });

      const updated = await apiFetch(`dataschema/rows/${rowId}/?data_table=${tableId}`, {
        method: 'PATCH',
        body: updatePayload,
        token,
      });

      console.log('✅ RowEditTab: Response received', {
        updatedKeys: Object.keys(updated),
        updated
      });

      // Extract field data from the updated response (handles nested 'values' object)
      const editableFields = extractEditableFields(updated);
      setFormData(editableFields);
      setRowData(updated);
      setIsDirty(false);
      setHasChanges(false);
      notify(t('edit.rowSaved'), 'success');
      console.log('✅ RowEditTab: Row saved successfully');
    } catch (err) {
      console.error('🔴 RowEditTab: Save error - full details:', {
        errorMessage: err.message,
        errorResponse: err.response,
        errorData: err.data,
        formDataSent: formData,
        error: err,
      });
      setError(err.message || t('edit.saveError'));
      notify(t('errors.prefix', { message: err.message }), 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const extracted = extractEditableFields(rowData);
    setFormData(extracted);
    setHasChanges(false);
    setIsDirty(false);
    console.log('✅ RowEditTab: Form reset to saved values');
  };

  // Filter out metadata fields for editing
  const editableFields = Object.entries(formData).filter(
    ([key]) => !['id', 'created_at', 'updated_at', 'created_by', 'updated_by'].includes(key)
  );

  return (
    <Box sx={{ maxWidth: '800px' }}>
      {/* Warning if unsaved changes */}
      {isDirty && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t('edit.unsavedChanges')}
        </Alert>
      )}

      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Form fields */}
      <Stack spacing={2} sx={{ mb: 3 }}>
        {editableFields.map(([field, value]) => (
          <TextField
            key={field}
            fullWidth
            label={field.replace(/_/g, ' ').toUpperCase()}
            value={value !== null && value !== undefined ? value : ''}
            onChange={(e) => handleInputChange(field, e.target.value)}
            multiline={typeof value === 'string' && value.length > 100}
            rows={typeof value === 'string' && value.length > 100 ? 4 : 1}
            variant="outlined"
            disabled={saving}
            placeholder={t('edit.enterField', { field: field.replace(/_/g, ' ') })}
          />
        ))}
      </Stack>

      {/* Action buttons */}
      <ButtonGroup variant="contained" fullWidth>
        <Button
          startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
          onClick={handleSave}
          disabled={!hasChanges || saving}
          color="success"
        >
          {saving ? t('edit.saving') : t('edit.saveChanges')}
        </Button>
        <Button
          startIcon={<CancelIcon />}
          onClick={handleReset}
          disabled={!hasChanges || saving}
          color="warning"
          variant="outlined"
        >
          {t('edit.reset')}
        </Button>
      </ButtonGroup>

      {/* Save status */}
      {!isDirty && !hasChanges && (
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: 2,
            color: 'success.main',
            fontWeight: 500,
          }}
        >
          ✓ {t('edit.allSaved')}
        </Typography>
      )}
    </Box>
  );
}
