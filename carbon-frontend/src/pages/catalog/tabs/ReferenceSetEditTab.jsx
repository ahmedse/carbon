// src/pages/catalog/tabs/ReferenceSetEditTab.jsx
// Reference Set Edit Tab: Governance form for updating reference set metadata

import React, { useState } from 'react';
import { 
  Box, TextField, Button, CircularProgress, Alert, 
  MenuItem, FormControl, InputLabel, Select,
  FormHelperText, Typography, Switch, FormControlLabel
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { apiFetch } from '../../../api/api';


export default function ReferenceSetEditTab({ entityData, additionalProps = {} }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { selectOptions = {}, onRefSetUpdated = null } = additionalProps;

  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    description: entityData?.description || '',
    domain: entityData?.domain || '',
    steward: entityData?.steward || '',
    is_active: entityData?.is_active !== undefined ? entityData.is_active : true,
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSwitchChange = (e) => {
    setFormData(prev => ({ ...prev, is_active: e.target.checked }));
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Name is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      // Prepare payload with only the fields we're updating
      const payload = {
        name: formData.name,
        description: formData.description,
        domain: formData.domain || null,
        steward: formData.steward || null,
        is_active: formData.is_active,
      };

      const response = await apiFetch(`catalog/reference-sets/${entityData.id}/`, {
        method: 'PATCH',
        token,
        body: payload,
      }); // update reference set

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || errData.message || `Failed to save: ${response.status}`);
      }

      const updatedRefSet = await response.json();
      setFormData({
        name: updatedRefSet.name || '',
        description: updatedRefSet.description || '',
        domain: updatedRefSet.domain || '',
        steward: updatedRefSet.steward || '',
        is_active: updatedRefSet.is_active !== undefined ? updatedRefSet.is_active : true,
      });

      notify({ message: 'Reference set updated successfully', type: 'success' });
      
      // Call parent callback to refresh data
      if (onRefSetUpdated) {
        onRefSetUpdated();
      }
    } catch (err) {
      const message = err.message || 'Failed to save reference set';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: '800px' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>Basic Information</Typography>

        <TextField
          fullWidth
          label="Name"
          name="name"
          value={formData.name}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          required
          helperText="Unique identifier for this reference set"
        />

        <TextField
          fullWidth
          label="Description"
          name="description"
          value={formData.description}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          multiline
          rows={3}
          helperText="Purpose and usage guidance for this reference set"
        />

        <Typography variant="subtitle2" sx={{ mb: 2, mt: 3, fontWeight: 600 }}>Governance</Typography>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Domain</InputLabel>
          <Select
            name="domain"
            value={formData.domain}
            onChange={handleChange}
            label="Domain"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(selectOptions.domains || []).map((domain) => (
              <MenuItem key={domain.id} value={domain.id}>
                {domain.name}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>Data domain for governance and access control</FormHelperText>
        </FormControl>

        <FormControl fullWidth margin="normal" variant="outlined">
          <InputLabel>Steward</InputLabel>
          <Select
            name="steward"
            value={formData.steward}
            onChange={handleChange}
            label="Steward"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(selectOptions.users || []).map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.username || user.email}
              </MenuItem>
            ))}
          </Select>
          <FormHelperText>User responsible for maintaining this reference set</FormHelperText>
        </FormControl>

        <FormControlLabel
          control={
            <Switch
              checked={formData.is_active}
              onChange={handleSwitchChange}
              name="is_active"
              color="primary"
            />
          }
          label="Active"
          sx={{ mt: 2 }}
        />
        <Typography variant="caption" color="text.secondary" display="block" sx={{ ml: 4, mt: -1 }}>
          Inactive reference sets are hidden from selection lists
        </Typography>

        <Box sx={{ mt: 3, display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </DetailTabContent>
  );
}
