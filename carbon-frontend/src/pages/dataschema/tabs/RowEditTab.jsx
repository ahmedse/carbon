// File: src/pages/dataschema/tabs/RowEditTab.jsx
// Edit form for row data with validation and save

import React, { useState, useEffect } from 'react';
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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
  onClose,
}) {
  const [formData, setFormData] = useState(rowData);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Detect changes
  useEffect(() => {
    const changed = JSON.stringify(formData) !== JSON.stringify(rowData);
    setHasChanges(changed);
    if (changed) {
      setIsDirty(true);
    }
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
      [field]: value,
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      // Build update payload (exclude metadata fields)
      const excludeFields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by'];
      const updateData = Object.entries(formData)
        .filter(([key]) => !excludeFields.includes(key))
        .reduce((acc, [key, value]) => {
          acc[key] = value;
          return acc;
        }, {});

      const response = await fetch(
        `${API_BASE_URL}/api/rows/${rowId}/?data_table=${tableId}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(updateData),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `Save failed: ${response.status}`
        );
      }

      const updated = await response.json();
      setFormData(updated);
      setRowData(updated);
      setIsDirty(false);
      notify('Row saved successfully', 'success');
    } catch (err) {
      console.error('Save error:', err);
      setError(err.message || 'Failed to save row');
      notify(`Error: ${err.message}`, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setFormData(rowData);
    setHasChanges(false);
    setIsDirty(false);
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
          You have unsaved changes. Save or reset before leaving.
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
            placeholder={`Enter ${field.replace(/_/g, ' ')}`}
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
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
        <Button
          startIcon={<CancelIcon />}
          onClick={handleReset}
          disabled={!hasChanges || saving}
          color="warning"
          variant="outlined"
        >
          Reset
        </Button>
      </ButtonGroup>

      {/* Save status */}
      {!isDirty && !hasChanges && (
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: 2,
            color: '#4caf50',
            fontWeight: 500,
          }}
        >
          ✓ All changes saved
        </Typography>
      )}
    </Box>
  );
}
