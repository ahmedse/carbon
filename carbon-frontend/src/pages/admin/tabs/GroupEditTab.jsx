// src/pages/admin/tabs/GroupEditTab.jsx
import React, { useState, useEffect } from 'react';
import { Box, Typography, TextField, Button, Alert } from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { updateGroup } from '../../../api/groups';

export default function GroupEditTab({ entityData: group }) {
  const { user } = useAuth();
  const [form, setForm] = useState({ name: '', description: '' });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (group) {
      setForm({
        name: group.name || '',
        description: group.description || '',
      });
    }
  }, [group]);

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError('Name is required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateGroup(user?.token, group.id, { name: form.name.trim(), description: form.description });
    } catch (err) {
      setError(err.message || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  if (!group) return null;

  return (
    <Box sx={{ p: 3 }}>
      {error && <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert>}
      <TextField
        fullWidth
        label='Group Name'
        margin='normal'
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <TextField
        fullWidth
        label='Description'
        margin='normal'
        multiline
        rows={4}
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
      />
      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
        <Button variant='contained' onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </Box>
    </Box>
  );
}
