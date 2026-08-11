// src/components/dataproducts/ProductForm.jsx
// Shared Data Product form (create/edit) used by both DataProductsPage and
// DataProductDetailPage. AI-toolkit compliant: theme tokens only, size="small",
// no margin="normal", SystemDialog lives at the call site (CB-14).
import React from 'react';
import { Box, Stack, TextField, MenuItem, FormControlLabel, Switch, Typography } from '@mui/material';
import { SCOPE_LABEL, SCOPE_OPTIONS } from '../../constants/terminology';

/**
 * ProductForm - field set for Data Product (Module) metadata.
 * Props:
 * - form: {name, description, scope, org_unit, is_locked?}
 * - onChange(nextForm): called with a new form object on any field change
 * - orgUnits: [{id, name}] for the Org Unit select
 * - error: optional message to display at top
 * - readOnly: disable all inputs (view mode)
 * - showLock: include the Is Locked toggle (detail page only)
 */
export default function ProductForm({
  form,
  onChange,
  orgUnits = [],
  error = null,
  readOnly = false,
  showLock = false,
}) {
  return (
    <Box px={2} py={1}>
      {error && (
        <Typography variant="body2" color="error.main" sx={{ mb: 1.5 }}>
          {error}
        </Typography>
      )}
      <Stack spacing={2}>
        <TextField
          fullWidth
          label="Name"
          size="small"
          autoFocus={!readOnly}
          required
          disabled={readOnly}
          value={form.name || ''}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
        />
        <TextField
          fullWidth
          label="Description"
          size="small"
          multiline
          rows={2}
          disabled={readOnly}
          value={form.description || ''}
          onChange={(e) => onChange({ ...form, description: e.target.value })}
        />
        <TextField
          select
          fullWidth
          label="Scope"
          size="small"
          disabled={readOnly}
          value={form.scope ?? ''}
          onChange={(e) => onChange({ ...form, scope: e.target.value })}
          helperText="Default GHG scope for this product's activity data"
        >
          {SCOPE_OPTIONS.map((s) => (
            <MenuItem key={s} value={s}>{SCOPE_LABEL[s]}</MenuItem>
          ))}
        </TextField>
        <TextField
          select
          fullWidth
          label="Org Unit"
          size="small"
          disabled={readOnly}
          value={form.org_unit ?? ''}
          onChange={(e) => onChange({ ...form, org_unit: e.target.value })}
          helperText="Owning organizational unit (governs access)"
        >
          <MenuItem value="">— None —</MenuItem>
          {orgUnits.map((ou) => (
            <MenuItem key={ou.id} value={ou.id}>{ou.name}</MenuItem>
          ))}
        </TextField>
        {showLock && (
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={Boolean(form.is_locked)}
                disabled={readOnly}
                onChange={(e) => onChange({ ...form, is_locked: e.target.checked })}
              />
            }
            label="Locked (prevents further edits)"
          />
        )}
      </Stack>
    </Box>
  );
}
