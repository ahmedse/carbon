// src/pages/catalog/tabs/DataProductOverviewTab.jsx
// Data Product Overview Tab: read-only metadata + governance info.
// Follows AssetOverviewTab pattern (theme tokens, size="small", Chip values).
import React from 'react';
import { Box, Table, TableRow, TableCell, TableBody, Typography, Chip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import LockIcon from '@mui/icons-material/Lock';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

function formatDate(value, locale) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString(locale);
}

export default function DataProductOverviewTab({ entityData, additionalProps = {} }) {
  const { t, i18n } = useTranslation('catalog');
  const { qualitySummary = null } = additionalProps;

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  const basicAttributes = [
    { label: t('id'), value: entityData.id },
    { label: t('name'), value: entityData.name || '—' },
    { label: t('description'), value: entityData.description || '—' },
  ];

  const governanceAttributes = [
    { label: t('orgUnit'), value: entityData.org_unit_name || '—' },
    {
      label: t('status'),
      value: entityData.is_locked ? (
        <Chip
          icon={<LockIcon sx={{ fontSize: '0.9rem' }} />}
          label={t('locked')}
          size="small"
          color="warning"
          variant="outlined"
        />
      ) : (
        <Chip label={t('unlocked')} size="small" color="success" variant="outlined" />
      ),
    },
    {
      label: t('quality'),
      value: qualitySummary ? (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {qualitySummary.failing > 0 && (
            <Chip label={`${qualitySummary.failing} ${t('failing')}`} size="small" color={QUALITY_COLOR.failing} variant="outlined" />
          )}
          {qualitySummary.warning > 0 && (
            <Chip label={`${qualitySummary.warning} ${t('warning')}`} size="small" color={QUALITY_COLOR.warning} variant="outlined" />
          )}
          {qualitySummary.passing > 0 && (
            <Chip label={`${qualitySummary.passing} ${t('passing')}`} size="small" color={QUALITY_COLOR.passing} variant="outlined" />
          )}
          {qualitySummary.total === 0 && (
            <Chip label={t('noChecks')} size="small" color="default" variant="outlined" />
          )}
        </Box>
      ) : '—',
    },
  ];

  const statisticsAttributes = [
    { label: t('tables'), value: entityData.table_count ?? '—' },
    {
      label: t('qualityScore'),
      value: qualitySummary?.avg_score != null
        ? `${Number(qualitySummary.avg_score).toFixed(1)}%`
        : '—',
    },
  ];

  const timestampAttributes = [
    { label: t('createdAt'), value: formatDate(entityData.created_at, i18n.language) },
    { label: t('updatedAt'), value: formatDate(entityData.updated_at, i18n.language) },
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
        {renderTable(basicAttributes, t('basicInformation'))}
        {renderTable(governanceAttributes, t('governance'))}
        {renderTable(statisticsAttributes, t('statistics'))}
        {renderTable(timestampAttributes, t('timestamps'))}
      </Box>
    </DetailTabContent>
  );
}
