// src/pages/catalog/tabs/TagEditTab.jsx
import React, { useState } from 'react';
import { Box, TextField, Button, CircularProgress, Alert } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { apiFetch } from '../../../api/api';

export default function TagEditTab({ entityData }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    description: entityData?.description || '',
    color: entityData?.color || '#000000',
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
      await apiFetch(`catalog/tags/${entityData.id}/`, {
        method: 'PUT',
        token,
        body: formData,
      }); // update tag

      notify({ message: 'Tag updated successfully', type: 'success' });
    } catch (err) {
      const message = err.message || 'Failed to save tag';
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
          rows={3}
        />

        <TextField
          fullWidth
          label="Color"
          name="color"
          type="color"
          value={formData.color}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
        />

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
