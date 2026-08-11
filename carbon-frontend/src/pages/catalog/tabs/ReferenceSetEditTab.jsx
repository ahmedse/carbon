// src/pages/catalog/tabs/ReferenceSetEditTab.jsx
// Reference Set Edit Tab: Governance form for updating reference set metadata
// plus lifecycle transition controls.

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Box, TextField, Button, CircularProgress, Alert, 
  MenuItem, FormControl, InputLabel, Select,
  FormHelperText, Typography, Switch, FormControlLabel, Chip,
  Stack
} from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { apiFetch } from '../../../api/api';
import {
  LIFECYCLE_COLORS,
  LIFECYCLE_LABELS,
  getValidTransitions,
} from '../../../constants/referenceSetLifecycle';


export default function ReferenceSetEditTab({ entityData, additionalProps = {} }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const navigate = useNavigate();
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
  const [transitioning, setTransitioning] = useState(null);
  const [transitionError, setTransitionError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSwitchChange = (e) => {
    setFormData(prev => ({ ...prev, is_active: e.target.checked }));
  };

  // Transition a reference set to a new lifecycle state.
  const handleTransition = async (targetState) => {
    setTransitioning(targetState);
    setTransitionError(null);
    try {
      await apiFetch(`mdm/reference-sets/${entityData.id}/transition/`, {
        method: 'POST',
        token,
        body: { state: targetState },
      });
      notify({ message: `Lifecycle state changed to ${LIFECYCLE_LABELS[targetState] || targetState}`, type: 'success' });
      if (targetState === 'archived') {
        // Archived sets are hidden from all endpoints; return to the MDM list.
        navigate('/catalog/mdm');
        return;
      }
      if (onRefSetUpdated) {
        onRefSetUpdated();
      }
    } catch (err) {
      const errData = err.data;
      const message = errData?.state?.[0] || errData?.detail || err.message || 'Failed to change lifecycle state';
      setTransitionError(message);
      notify({ message, type: 'error' });
    } finally {
      setTransitioning(null);
    }
  };

  const lifecycleState = entityData?.lifecycle_state || 'draft';
  const validTransitions = getValidTransitions(lifecycleState);

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

      const updatedRefSet = await apiFetch(`mdm/reference-sets/${entityData.id}/`, {
        method: 'PATCH',
        token,
        body: payload,
      }); // update reference set

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

        {/* Lifecycle */}
        <Typography variant="subtitle2" sx={{ mb: 1, mt: 2, fontWeight: 600 }}>Lifecycle</Typography>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Chip
            label={LIFECYCLE_LABELS[lifecycleState] || lifecycleState}
            size="small"
            color={LIFECYCLE_COLORS[lifecycleState] || 'default'}
            variant="filled"
          />
          {validTransitions.length === 0 ? (
            <Typography variant="caption" color="text.secondary">
              Archived — no further transitions allowed
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Move to:
            </Typography>
          )}
        </Stack>

        {validTransitions.length > 0 && (
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            {validTransitions.map((state) => (
              <Button
                key={state}
                size="small"
                variant="outlined"
                color={LIFECYCLE_COLORS[state] === 'success' ? 'success' : 'primary'}
                disabled={transitioning !== null}
                startIcon={transitioning === state ? <CircularProgress size={14} /> : null}
                onClick={() => handleTransition(state)}
              >
                {LIFECYCLE_LABELS[state] || state}
              </Button>
            ))}
          </Stack>
        )}
        {transitionError && (
          <Alert severity="error" sx={{ mb: 1, mt: 1 }}>{transitionError}</Alert>
        )}
        <FormControlLabel
          control={
            <Switch
              checked={formData.is_active}
              onChange={handleSwitchChange}
              name="is_active"
              color="primary"
              size="small"
            />
          }
          label="Enabled in lists"
          sx={{ mt: 2 }}
        />
        <Typography variant="caption" color="text.secondary" display="block" sx={{ ml: 4, mt: -0.5 }}>
          When disabled, this reference set is hidden from selection lists
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
          Lifecycle: Draft → Active → Deprecated → Archived (deprecated may return to active)
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
