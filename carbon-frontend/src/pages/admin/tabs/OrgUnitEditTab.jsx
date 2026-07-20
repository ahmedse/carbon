// src/pages/admin/tabs/OrgUnitEditTab.jsx
import React, { useState } from 'react';
import { Box, TextField, MenuItem, Button, CircularProgress, Alert } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { updateOrgUnit } from '../../../api/orgUnits';

const ORG_TYPES = [
  'university', 'campus', 'college', 'department', 'division', 'team', 'facility', 'other',
];

export default function OrgUnitEditTab({ entityData }) {
  const { user } = useAuth();
  const { notify } = useNotification();
  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    org_type: entityData?.org_type || 'department',
    code: entityData?.code || '',
    parent: entityData?.parent || '',
    description: entityData?.description || '',
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
      const payload = {
        name: formData.name.trim(),
        org_type: formData.org_type,
        code: formData.code.trim(),
        parent: formData.parent === '' ? null : parseInt(formData.parent, 10),
        description: formData.description.trim(),
      };

      await updateOrgUnit(user.token, entityData.id, payload);
      notify({ message: 'Organization unit updated successfully', type: 'success' });
    } catch (err) {
      const message = err.message || 'Failed to save organization unit';
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
          label="Organization Type"
          name="org_type"
          value={formData.org_type}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          select
        >
          {ORG_TYPES.map(type => (
            <MenuItem key={type} value={type}>
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          fullWidth
          label="Code"
          name="code"
          value={formData.code}
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
