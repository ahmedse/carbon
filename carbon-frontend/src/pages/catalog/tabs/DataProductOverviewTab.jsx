// src/pages/catalog/tabs/DataProductOverviewTab.jsx
// Data Product Overview Tab: read-only metadata + governance info.
// Follows AssetOverviewTab pattern (theme tokens, size="small", Chip values).
import React from 'react';
import { Box, Table, TableRow, TableCell, TableBody, Typography, Chip } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

export default function DataProductOverviewTab({ entityData, additionalProps = {} }) {
  const { qualitySummary = null } = additionalProps;

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  const basicAttributes = [
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.name || '—' },
    { label: 'Description', value: entityData.description || '—' },
  ];

  const governanceAttributes = [
    { label: 'Org Unit', value: entityData.org_unit_name || '—' },
    {
      label: 'Status',
      value: entityData.is_locked ? (
        <Chip
          icon={<LockIcon sx={{ fontSize: '0.9rem' }} />}
          label="Locked"
          size="small"
          color="warning"
          variant="outlined"
        />
      ) : (
        <Chip label="Unlocked" size="small" color="success" variant="outlined" />
      ),
    },
    {
      label: 'Quality',
      value: qualitySummary ? (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {qualitySummary.failing > 0 && (
            <Chip label={`${qualitySummary.failing} failing`} size="small" color={QUALITY_COLOR.failing} variant="outlined" />
          )}
          {qualitySummary.warning > 0 && (
            <Chip label={`${qualitySummary.warning} warning`} size="small" color={QUALITY_COLOR.warning} variant="outlined" />
          )}
          {qualitySummary.passing > 0 && (
            <Chip label={`${qualitySummary.passing} passing`} size="small" color={QUALITY_COLOR.passing} variant="outlined" />
          )}
          {qualitySummary.total === 0 && (
            <Chip label="No checks" size="small" color="default" variant="outlined" />
          )}
        </Box>
      ) : '—',
    },
  ];

  const statisticsAttributes = [
    { label: 'Tables', value: entityData.table_count ?? '—' },
    {
      label: 'Quality Score',
      value: qualitySummary?.avg_score != null
        ? `${Number(qualitySummary.avg_score).toFixed(1)}%`
        : '—',
    },
  ];

  const timestampAttributes = [
    { label: 'Created At', value: formatDate(entityData.created_at) },
    { label: 'Updated At', value: formatDate(entityData.updated_at) },
  ];

  const renderTable = (attributes, title) => (
    <Box sx={{ mb: 3 }}>
      {title && (
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>
          {title}
        </Typography>
      )}
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableBody>
            {attributes.map((attr, idx) => (
              <TableRow key={idx} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                <TableCell sx={{ fontWeight: 500, width: '25%', bgcolor: 'grey.50' }}>{attr.label}</TableCell>
                <TableCell>{attr.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Box>
  );

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: '100%' }}>
        {renderTable(basicAttributes, 'Basic Information')}
        {renderTable(governanceAttributes, 'Governance')}
        {renderTable(statisticsAttributes, 'Statistics')}
        {renderTable(timestampAttributes, 'Timestamps')}
      </Box>
    </DetailTabContent>
  );
}
