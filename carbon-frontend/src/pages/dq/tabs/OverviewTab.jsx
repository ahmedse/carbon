// carbon-frontend/src/pages/dq/tabs/OverviewTab.jsx
// Read-only rule summary — shown first when opening a rule detail.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Paper, Stack, Typography } from '@mui/material';
import {
  RULE_TYPE_LABELS,
  RULE_LEVEL_LABELS,
  DIMENSION_LABELS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
} from '../constants';

function Field({ label, children }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Box sx={{ mt: 0.25 }}>{children}</Box>
    </Box>
  );
}

export default function OverviewTab({ rule }) {
  const def = rule?.definition || {};
  const bindings = def.bindings || [];
  const assignments = rule?.field_assignments || [];

  // Prefer field_assignments for real table/field names, fall back to definition bindings
  const boundEntries = assignments.length > 0
    ? assignments.map((a) => `${a.table_name || `#${a.data_table}`}${a.field_name ? `.${a.field_name}` : ''}`)
    : bindings.map((b) => `${b.table}${b.field ? `.${b.field}` : ''}`);

  return (
    <Box sx={{ p: 3 }}>
      <Stack spacing={2}>
        {/* Identity */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            Identity
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label="Name">
              <Typography variant="body2">{rule?.name || '—'}</Typography>
            </Field>
            <Field label="Version">
              <Typography variant="body2">{rule?.version ?? 1}</Typography>
            </Field>
            <Field label="Description">
              <Typography variant="body2" sx={{ color: rule?.description ? 'text.primary' : 'text.disabled' }}>
                {rule?.description || 'No description'}
              </Typography>
            </Field>
            <Field label="Status">
              <Stack direction="row" spacing={0.5}>
                {rule?.archived ? (
                  <Chip size="small" color="default" variant="outlined" label="Archived" />
                ) : (
                  <Chip
                    size="small"
                    color={rule?.is_active ? 'success' : 'default'}
                    label={rule?.is_active ? 'Active' : 'Inactive'}
                  />
                )}
              </Stack>
            </Field>
          </Box>
        </Paper>

        {/* Classification */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            Classification
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label="Type">
              <Typography variant="body2">
                {RULE_TYPE_LABELS[def.type] || def.type || RULE_TYPE_LABELS[rule?.rule_type] || rule?.rule_type || '—'}
              </Typography>
            </Field>
            <Field label="Level">
              <Typography variant="body2">
                {RULE_LEVEL_LABELS[def.level] || def.level || RULE_LEVEL_LABELS[rule?.rule_level] || rule?.rule_level || '—'}
              </Typography>
            </Field>
            <Field label="Dimension">
              <Typography variant="body2">
                {DIMENSION_LABELS[def.dimension] || def.dimension || DIMENSION_LABELS[rule?.dimension] || rule?.dimension || '—'}
              </Typography>
            </Field>
            <Field label="Severity">
              <Chip
                size="small"
                color={SEVERITY_COLORS[def.severity || rule?.severity] || 'default'}
                label={SEVERITY_LABELS[def.severity] || def.severity || SEVERITY_LABELS[rule?.severity] || rule?.severity || '—'}
              />
            </Field>
          </Box>
        </Paper>

        {/* Bindings */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            Bound Tables & Fields
          </Typography>
          {boundEntries.length > 0 ? (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {boundEntries.map((entry) => (
                <Chip key={entry} size="small" variant="outlined" label={entry} />
              ))}
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
              No bindings configured
            </Typography>
          )}
        </Paper>

        {/* Parameters (if any) */}
        {def.params && Object.keys(def.params).length > 0 ? (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
              Parameters
            </Typography>
            <Box
              component="pre"
              sx={{
                fontSize: '0.75rem',
                p: 1.5,
                borderRadius: 1,
                bgcolor: 'action.hover',
                overflow: 'auto',
                maxHeight: 200,
                m: 0,
              }}
            >
              {JSON.stringify(def.params, null, 2)}
            </Box>
          </Paper>
        ) : null}

        {/* Enforcement */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            Enforcement
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label="On Write">
              <Chip
                size="small"
                color={def.enforcement?.on_write ? 'warning' : 'default'}
                label={def.enforcement?.on_write ? 'Enforced' : 'Not enforced'}
              />
            </Field>
          </Box>
        </Paper>

        {/* Metadata */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            Metadata
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label="Results">
              <Typography variant="body2">{rule?.results_count ?? 0}</Typography>
            </Field>
            <Field label="Created">
              <Typography variant="body2">
                {rule?.created_at ? new Date(rule.created_at).toLocaleString() : '—'}
              </Typography>
            </Field>
            <Field label="Created By">
              <Typography variant="body2">{rule?.created_by_name || '—'}</Typography>
            </Field>
            <Field label="Last Modified">
              <Typography variant="body2">
                {rule?.updated_at ? new Date(rule.updated_at).toLocaleString() : '—'}
              </Typography>
            </Field>
          </Box>
        </Paper>
      </Stack>
    </Box>
  );
}

OverviewTab.propTypes = {
  rule: PropTypes.object,
};
