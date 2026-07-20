// src/pages/catalog/tabs/DQRuleDialog.jsx
// Create/edit a DQ rule. Fields/enums match backend dq.DQRule.
import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
  FormControl, InputLabel, Select, MenuItem, Box, Alert, FormControlLabel, Switch,
} from '@mui/material';

// Matches backend RULE_TYPES / SEVERITY_CHOICES / SCOPE_CHOICES exactly.
const RULE_TYPES = [
  { value: 'not_null', label: 'Not Null' },
  { value: 'unique', label: 'Unique' },
  { value: 'allowed_values', label: 'Allowed Values' },
  { value: 'range', label: 'Range' },
  { value: 'regex', label: 'Regex' },
];
const SEVERITIES = ['info', 'warn', 'error'];
const SCOPES = ['field', 'table'];

const emptyForm = {
  name: '',
  scope: 'field',
  rule_type: 'not_null',
  data_field: '',
  severity: 'error',
  is_active: true,
  // param helpers (flattened for the form)
  values: '',
  min: '',
  max: '',
  pattern: '',
};

export default function DQRuleDialog({ open, onClose, onSave, rule, tableId, fields = [] }) {
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    if (rule) {
      const p = rule.params || {};
      setForm({
        name: rule.name || '',
        scope: rule.scope || 'field',
        rule_type: rule.rule_type || 'not_null',
        data_field: rule.data_field || '',
        severity: rule.severity || 'error',
        is_active: rule.is_active !== false,
        values: Array.isArray(p.values) ? p.values.join(', ') : '',
        min: p.min ?? '',
        max: p.max ?? '',
        pattern: p.pattern ?? '',
      });
    } else {
      setForm(emptyForm);
    }
    setError(null);
  }, [rule, open]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const buildParams = () => {
    switch (form.rule_type) {
      case 'allowed_values':
        return {
          values: form.values
            .split(',')
            .map((v) => v.trim())
            .filter(Boolean),
        };
      case 'range': {
        const params = {};
        if (form.min !== '') params.min = Number(form.min);
        if (form.max !== '') params.max = Number(form.max);
        return params;
      }
      case 'regex':
        return { pattern: form.pattern };
      default:
        return {};
    }
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) { setError('Rule name is required'); return; }
    if (form.scope === 'field' && !form.data_field) {
      setError('Select a field for a field-scoped rule'); return;
    }

    const payload = {
      name: form.name.trim(),
      scope: form.scope,
      rule_type: form.rule_type,
      severity: form.severity,
      is_active: form.is_active,
      params: buildParams(),
      // Always set data_table so the rule lists under this table; set data_field for field scope.
      data_table: tableId,
      data_field: form.scope === 'field' ? form.data_field : null,
    };

    setSaving(true);
    setError(null);
    try {
      await onSave(payload);
    } catch (err) {
      setError(err.message || 'Failed to save rule');
      setSaving(false);
    }
  };

  const renderParams = () => {
    switch (form.rule_type) {
      case 'allowed_values':
        return (
          <TextField
            label="Allowed values (comma-separated)"
            value={form.values}
            onChange={(e) => set('values', e.target.value)}
            fullWidth margin="normal"
            helperText="e.g. active, inactive, pending"
          />
        );
      case 'range':
        return (
          <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
            <TextField label="Min" type="number" value={form.min}
              onChange={(e) => set('min', e.target.value)} fullWidth />
            <TextField label="Max" type="number" value={form.max}
              onChange={(e) => set('max', e.target.value)} fullWidth />
          </Box>
        );
      case 'regex':
        return (
          <TextField
            label="Regex pattern" value={form.pattern}
            onChange={(e) => set('pattern', e.target.value)}
            fullWidth margin="normal" helperText="e.g. ^[A-Z]{2}[0-9]{4}$"
          />
        );
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{rule ? 'Edit DQ Rule' : 'New DQ Rule'}</DialogTitle>
      <DialogContent sx={{ pt: 2 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <TextField
          label="Rule Name" value={form.name}
          onChange={(e) => set('name', e.target.value)}
          fullWidth margin="normal" required
        />

        <FormControl fullWidth margin="normal">
          <InputLabel>Scope</InputLabel>
          <Select value={form.scope} label="Scope" onChange={(e) => set('scope', e.target.value)}>
            {SCOPES.map((s) => (
              <MenuItem key={s} value={s}>{s === 'field' ? 'Field' : 'Table'}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {form.scope === 'field' && (
          <FormControl fullWidth margin="normal" required>
            <InputLabel>Field</InputLabel>
            <Select value={form.data_field} label="Field" onChange={(e) => set('data_field', e.target.value)}>
              {fields.map((f) => (
                <MenuItem key={f.id} value={f.id}>{f.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        <FormControl fullWidth margin="normal">
          <InputLabel>Rule Type</InputLabel>
          <Select value={form.rule_type} label="Rule Type" onChange={(e) => set('rule_type', e.target.value)}>
            {RULE_TYPES.map((t) => (
              <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {renderParams()}

        <FormControl fullWidth margin="normal">
          <InputLabel>Severity</InputLabel>
          <Select value={form.severity} label="Severity" onChange={(e) => set('severity', e.target.value)}>
            {SEVERITIES.map((s) => (
              <MenuItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControlLabel
          control={<Switch checked={form.is_active} onChange={(e) => set('is_active', e.target.checked)} />}
          label="Active"
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
