// src/pages/catalog/tabs/ReferenceSetOverviewTab.jsx
// Reference Set Overview Tab: Display read-only metadata

import React from 'react';
import { Box, Table, TableBody, TableRow, TableCell, Typography, Chip } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  LIFECYCLE_COLORS,
  LIFECYCLE_LABELS,
} from '../../../constants/referenceSetLifecycle';

export default function ReferenceSetOverviewTab({ entityData }) {
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  // Primary attributes
  const primaryAttributes = [
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.name || '—' },
    { label: 'Slug', value: entityData.slug || '—' },
    { label: 'Description', value: entityData.description || '—' },
  ];

  // Governance attributes
  const lifecycleState = entityData.lifecycle_state || 'draft';
  const governanceAttributes = [
    { label: 'Domain', value: entityData.domain_name || '—' },
    { label: 'Steward', value: entityData.steward_name || '—' },
    {
      label: 'Lifecycle',
      value: (
        <Chip
          label={LIFECYCLE_LABELS[lifecycleState] || lifecycleState}
          size="small"
          color={LIFECYCLE_COLORS[lifecycleState] || 'default'}
          variant={lifecycleState === 'active' ? 'filled' : 'outlined'}
        />
      ),
    },
    {
      label: 'Status',
      value: entityData.is_active ? (
        <Chip label="Active" color="success" size="small" />
      ) : (
        <Chip label="Inactive" color="default" size="small" variant="outlined" />
      ),
    },
    { label: 'Version', value: entityData.version || '1' },
  ];

  // Statistics
  const statisticsAttributes = [
    { 
      label: 'Value Count', 
      value: <Chip label={entityData.value_count || 0} size="small" color="primary" />
    },
  ];

  // Timestamps
  const timestampAttributes = [
    { label: 'Created At', value: entityData.created_at ? new Date(entityData.created_at).toLocaleString() : '—' },
    { label: 'Updated At', value: entityData.updated_at ? new Date(entityData.updated_at).toLocaleString() : '—' },
  ];

  const renderTable = (attributes, title) => (
    <Box sx={{ mb: 3 }}>
      {title && <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>{title}</Typography>}
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
        {renderTable(primaryAttributes, 'Basic Information')}
        {renderTable(governanceAttributes, 'Governance')}
        {renderTable(statisticsAttributes, 'Statistics')}
        {renderTable(timestampAttributes, 'Timestamps')}
      </Box>
    </DetailTabContent>
  );
}
