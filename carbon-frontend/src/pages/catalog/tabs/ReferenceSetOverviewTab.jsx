// src/pages/catalog/tabs/ReferenceSetOverviewTab.jsx
// Reference Set Overview Tab: Display read-only metadata

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Table, TableBody, TableRow, TableCell, Typography, Chip } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  LIFECYCLE_COLORS,
  LIFECYCLE_LABELS,
} from '../../../constants/referenceSetLifecycle';

export default function ReferenceSetOverviewTab({ entityData }) {
  const { t } = useTranslation('catalog');
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  // Primary attributes
  const primaryAttributes = [
    { label: t('id'), value: entityData.id },
    { label: t('name'), value: entityData.name || '—' },
    { label: t('slug'), value: entityData.slug || '—' },
    { label: t('description'), value: entityData.description || '—' },
  ];

  // Governance attributes
  const lifecycleState = entityData.lifecycle_state || 'draft';
  const governanceAttributes = [
    { label: t('domain'), value: entityData.domain_name || '—' },
    { label: t('steward'), value: entityData.steward_name || '—' },
    {
      label: t('lifecycle'),
      value: (
        <Chip
          label={LIFECYCLE_LABELS[lifecycleState] || lifecycleState}
          size="small"
          color={LIFECYCLE_COLORS[lifecycleState] || 'default'}
          variant="filled"
        />
      ),
    },
    {
      label: t('listVisibility'),
      value: entityData.is_active ? (
        <Chip label={t('enabled')} color="success" size="small" variant="filled" />
      ) : (
        <Chip label={t('disabled')} color="default" size="small" variant="outlined" />
      ),
    },
    { label: t('version'), value: entityData.version || '1' },
  ];

  // Statistics
  const statisticsAttributes = [
    { 
      label: t('valueCount'), 
      value: <Chip label={entityData.value_count || 0} size="small" color="primary" />
    },
  ];

  // Timestamps
  const timestampAttributes = [
    { label: t('createdAt'), value: entityData.created_at ? new Date(entityData.created_at).toLocaleString() : '—' },
    { label: t('updatedAt'), value: entityData.updated_at ? new Date(entityData.updated_at).toLocaleString() : '—' },
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
        {renderTable(primaryAttributes, t('basicInformation'))}
        {renderTable(governanceAttributes, t('governance'))}
        {renderTable(statisticsAttributes, t('statistics'))}
        {renderTable(timestampAttributes, t('timestamps'))}
      </Box>
    </DetailTabContent>
  );
}
