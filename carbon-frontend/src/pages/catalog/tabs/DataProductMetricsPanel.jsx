// src/pages/catalog/tabs/DataProductMetricsPanel.jsx
// Data Product Metrics: table count, total rows, quality pass rate, last modified,
// plus governance summary. Follows ReferenceSetMetricsPanel pattern.
import React from 'react';
import { Box, Typography, Chip, Divider } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import TableChartIcon from '@mui/icons-material/TableChart';
import StorageIcon from '@mui/icons-material/Storage';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ScheduleIcon from '@mui/icons-material/Schedule';

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

export default function DataProductMetricsPanel({ entityData, additionalProps = {} }) {
  const {
    tables = [],
    qualitySummary = null,
    auditEvents = [],
  } = additionalProps;

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">No metrics available</Typography>
      </DetailTabContent>
    );
  }

  const totalRows = tables.reduce((sum, t) => sum + (Number(t.row_count) || 0), 0);
  const summary = qualitySummary || { total: 0, passing: 0, warning: 0, failing: 0, unknown: 0, avg_score: null };
  const passRate = summary.total > 0 ? Math.round((summary.passing / summary.total) * 100) : null;

  let lastModified = entityData.updated_at || null;
  tables.forEach((t) => {
    const ts = t.updated_at ? Date.parse(t.updated_at) : NaN;
    if (!Number.isNaN(ts) && (!lastModified || ts > Date.parse(lastModified))) lastModified = t.updated_at;
  });

  const metrics = [
    { label: 'Tables', value: entityData.table_count ?? tables.length, color: 'primary', icon: <TableChartIcon fontSize="small" /> },
    { label: 'Total Rows', value: totalRows, color: 'info', icon: <StorageIcon fontSize="small" /> },
    {
      label: 'Quality Pass Rate',
      value: passRate != null ? `${passRate}%` : '—',
      color: passRate != null && passRate >= 80 ? 'success' : passRate != null ? 'warning' : 'default',
      icon: <CheckCircleIcon fontSize="small" />,
    },
    { label: 'Avg Score', value: summary.avg_score != null ? `${Number(summary.avg_score).toFixed(1)}%` : '—', color: 'default' },
    { label: 'Last Modified', value: formatDate(lastModified), color: 'default', icon: <ScheduleIcon fontSize="small" /> },
  ];

  return (
    <DetailTabContent>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Product Statistics
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
        {metrics.map((metric, idx) => (
          <Box key={idx}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {metric.label}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {metric.icon}
              <Chip label={metric.value} size="small" color={metric.color} sx={{ fontWeight: 600 }} />
            </Box>
          </Box>
        ))}
      </Box>

      <Divider sx={{ my: 3 }} />

      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Governance
      </Typography>

      <Box sx={{ mt: 2 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          Org Unit
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          {entityData.org_unit_name || 'Not assigned'}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block">
          Lock Status
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          {entityData.is_locked ? 'Locked' : 'Unlocked'}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block">
          Audit Events
        </Typography>
        <Typography variant="body2">
          {auditEvents.length} recorded
        </Typography>
      </Box>
    </DetailTabContent>
  );
}
