// src/pages/catalog/tabs/AssetEditTab.jsx
import React, { useState } from 'react';
import { Box, TextField, MenuItem, Button, CircularProgress, Alert } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { API_BASE_URL, API_ROUTES } from '../../../config';

const ASSET_TYPES = ['Table', 'Schema', 'Field', 'Report', 'API', 'Database', 'Other'];

export default function AssetEditTab({ entityData }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    description: entityData?.description || '',
    asset_type: entityData?.asset_type || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Name is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const baseUrl = API_BASE_URL.replace(/\/$/, '');
      const url = `${baseUrl}${API_ROUTES.assets}${entityData.id}/`;
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`Failed to save: ${response.status}`);
      }

      notify({ message: 'Asset updated successfully', type: 'success' });
    } catch (err) {
      const message = err.message || 'Failed to save asset';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: '600px' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <TextField
          fullWidth
          label="Name"
          name="name"
          value={formData.name}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
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
          rows={4}
        />

        <TextField
          fullWidth
          label="Asset Type"
          name="asset_type"
          value={formData.asset_type}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          select
        >
          {ASSET_TYPES.map(type => (
            <MenuItem key={type} value={type}>{type}</MenuItem>
          ))}
        </TextField>

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
