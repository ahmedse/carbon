// carbon-frontend/src/pages/dq/tabs/OverviewTab.jsx
// Read-only rule summary — shown first when opening a rule detail.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Paper, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import {
  ruleTypeLabel,
  ruleLevelLabel,
  dimensionLabel,
  severityLabel,
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
  const { t } = useTranslation('dq');
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
            {t('overview.identity')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label={t('overview.name')}>
              <Typography variant="body2">{rule?.name || '—'}</Typography>
            </Field>
            <Field label={t('overview.version')}>
              <Typography variant="body2">{rule?.version ?? 1}</Typography>
            </Field>
            <Field label={t('overview.description')}>
              <Typography variant="body2" sx={{ color: rule?.description ? 'text.primary' : 'text.disabled' }}>
                {rule?.description || t('overview.noDescription')}
              </Typography>
            </Field>
            <Field label={t('overview.status')}>
              <Stack direction="row" spacing={0.5}>
                {rule?.archived ? (
                  <Chip size="small" color="default" variant="outlined" label={t('status.archived')} />
                ) : (
                  <Chip
                    size="small"
                    color={rule?.is_active ? 'success' : 'default'}
                    label={rule?.is_active ? t('status.active') : t('status.inactive')}
                  />
                )}
              </Stack>
            </Field>
          </Box>
        </Paper>

        {/* Classification */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            {t('overview.classification')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label={t('overview.type')}>
              <Typography variant="body2">
                {ruleTypeLabel(t, def.type) || def.type || ruleTypeLabel(t, rule?.rule_type) || rule?.rule_type || '—'}
              </Typography>
            </Field>
            <Field label={t('overview.level')}>
              <Typography variant="body2">
                {ruleLevelLabel(t, def.level) || def.level || ruleLevelLabel(t, rule?.rule_level) || rule?.rule_level || '—'}
              </Typography>
            </Field>
            <Field label={t('overview.dimension')}>
              <Typography variant="body2">
                {dimensionLabel(t, def.dimension) || def.dimension || dimensionLabel(t, rule?.dimension) || rule?.dimension || '—'}
              </Typography>
            </Field>
            <Field label={t('overview.severity')}>
              <Chip
                size="small"
                color={SEVERITY_COLORS[def.severity || rule?.severity] || 'default'}
                label={severityLabel(t, def.severity) || def.severity || severityLabel(t, rule?.severity) || rule?.severity || '—'}
              />
            </Field>
          </Box>
        </Paper>

        {/* Bindings */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            {t('overview.boundTablesFields')}
          </Typography>
          {boundEntries.length > 0 ? (
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {boundEntries.map((entry) => (
                <Chip key={entry} size="small" variant="outlined" label={entry} />
              ))}
            </Stack>
          ) : (
            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
              {t('overview.noBindings')}
            </Typography>
          )}
        </Paper>

        {/* Parameters (if any) */}
        {def.params && Object.keys(def.params).length > 0 ? (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
              {t('overview.parameters')}
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
            {t('overview.enforcement')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label={t('overview.onWrite')}>
              <Chip
                size="small"
                color={def.enforcement?.on_write ? 'warning' : 'default'}
                label={def.enforcement?.on_write ? t('overview.enforced') : t('overview.notEnforced')}
              />
            </Field>
          </Box>
        </Paper>

        {/* Metadata */}
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1.5 }}>
            {t('overview.metadata')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
            <Field label={t('overview.results')}>
              <Typography variant="body2">{rule?.results_count ?? 0}</Typography>
            </Field>
            <Field label={t('overview.created')}>
              <Typography variant="body2">
                {rule?.created_at ? new Date(rule.created_at).toLocaleString() : '—'}
              </Typography>
            </Field>
            <Field label={t('overview.createdBy')}>
              <Typography variant="body2">{rule?.created_by_name || '—'}</Typography>
            </Field>
            <Field label={t('overview.lastModified')}>
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
