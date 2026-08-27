// src/inspector/tabs/ruleTabs.jsx
// Contextual Inspector tabs for a DQ Rule (entityType: 'rule').
//
// Lifts the inline RuleSummaryMetrics out of RuleDetailPage so the rule summary
// surfaces in the global drawer. Page supplies payload { entityData: { rule } }.
/* eslint-disable react-refresh/only-export-components */

import React from 'react';
import { Box, Chip, Paper, Typography } from '@mui/material';
import RuleIcon from '@mui/icons-material/Rule';
import { registerEntityInspectorTab } from './helpers';
import {
  RULE_TYPE_LABELS,
  RULE_LEVEL_LABELS,
  DIMENSION_LABELS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
} from '../../pages/dq/constants';

function RuleSummaryMetrics({ entityData }) {
  const { rule } = entityData || {};
  if (!rule) return null;

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'grid', gap: 1.5 }}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Version</Typography>
          <Typography variant="h6">{rule.version ?? 1}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Results</Typography>
          <Typography variant="h6">{rule.results_count ?? 0}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Dimension</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {DIMENSION_LABELS[rule.dimension] || rule.dimension || '—'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Severity</Typography>
          <Box sx={{ mt: 0.5 }}>
            <Chip
              size="small"
              color={SEVERITY_COLORS[rule.severity] || 'default'}
              label={SEVERITY_LABELS[rule.severity] || rule.severity}
            />
          </Box>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Type</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Level</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {RULE_LEVEL_LABELS[rule.rule_level] || rule.rule_level}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">Created</Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            {rule.created_at ? new Date(rule.created_at).toLocaleDateString() : '—'}
            {rule.created_by_name ? ` by ${rule.created_by_name}` : ''}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
}

export function registerRuleInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'rule-summary',
    entityType: 'rule',
    label: 'Summary',
    icon: RuleIcon,
    order: 10,
    Component: RuleSummaryMetrics,
  });
}
