// src/pages/admin/tabs/OrgUnitEditTab.jsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, TextField, MenuItem, Button, CircularProgress, Alert, Stack,
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { SearchSelect } from '../../../components/Form';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { updateOrgUnit } from '../../../api/orgUnits';
import { fetchEmployees } from '../../../api/people';
import { ORG_TYPE_KEYS as ORG_TYPES } from '../../../constants/orgTypes';

export default function OrgUnitEditTab({ entityData }) {
  const { user } = useAuth();
  const { notify } = useNotification();
  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    org_type: entityData?.org_type || 'department',
    code: entityData?.code || '',
    parent: entityData?.parent || '',
    description: entityData?.description || '',
    manager_employee_id: entityData?.manager_employee_id != null
      ? String(entityData.manager_employee_id)
      : '',
  });
  const [employees, setEmployees] = useState(() => (
    Array.isArray(entityData?.employees) ? entityData.employees : []
  ));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user?.token) return;
      if (Array.isArray(entityData?.employees) && entityData.employees.length) {
        setEmployees(entityData.employees);
        return;
      }
      try {
        const list = await fetchEmployees(user.token);
        if (!cancelled) setEmployees(Array.isArray(list) ? list : []);
      } catch {
        if (!cancelled) setEmployees([]);
      }
    })();
    return () => { cancelled = true; };
  }, [user?.token, entityData?.employees]);

  const managerOptions = useMemo(
    () => [
      { value: '', label: '— Unassigned —' },
      ...employees
        .filter((e) => e.is_active !== false)
        .map((e) => ({
          value: String(e.id),
          label: `${e.employee_no} — ${e.full_name}`,
        })),
    ],
    [employees],
  );

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
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
        manager_employee_id: formData.manager_employee_id
          ? parseInt(formData.manager_employee_id, 10)
          : null,
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
          {ORG_TYPES.map((type) => (
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

        <Stack sx={{ mt: 2 }}>
          <SearchSelect
            options={managerOptions}
            valueKey="value"
            labelKey="label"
            label="Unit manager (employee)"
            value={formData.manager_employee_id}
            onChange={(v) => setFormData((prev) => ({
              ...prev,
              manager_employee_id: v?.value ?? '',
            }))}
            clearable
            size="small"
            placeholder="— Unassigned —"
          />
        </Stack>

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
