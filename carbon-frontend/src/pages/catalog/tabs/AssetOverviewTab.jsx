// src/pages/catalog/tabs/AssetOverviewTab.jsx
// Asset Overview Tab: Display read-only asset metadata and governance information

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography, Chip, Grid, Paper } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

export default function AssetOverviewTab({ entityData }) {
  const { t } = useTranslation('catalog');
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  const getQualityColor = (status) => {
    const colors = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };
    return colors[status] || 'default';
  };

  const getClassificationColor = (classification) => {
    const colors = {
      public: 'default',
      internal: 'info',
      confidential: 'warning',
      pii: 'error',
      sensitive: 'error',
    };
    return colors[classification] || 'default';
  };

  // Primary attributes (always displayed)
  const primaryAttributes = [
    { label: t('id'), value: entityData.id },
    { label: t('name'), value: entityData.title || entityData.name || '—' },
    { label: t('description'), value: entityData.description || '—' },
    { label: t('assetType'), value: entityData.asset_type || '—' },
  ];

  // Governance attributes (from AssetProfile model)
  const governanceAttributes = [
    { label: t('domain'), value: entityData.domain_name || '—' },
    { label: t('classification'), value: entityData.classification ? (
      <Chip 
        label={entityData.classification} 
        color={getClassificationColor(entityData.classification)}
        size="small"
        variant="outlined"
      />
    ) : '—' },
    { label: t('qualityStatus'), value: entityData.quality_status ? (
      <Chip 
        label={entityData.quality_status} 
        color={getQualityColor(entityData.quality_status)}
        size="small"
      />
    ) : '—' },
    { label: t('qualityScore'), value: entityData.quality_score ? `${entityData.quality_score.toFixed(1)}%` : '—' },
  ];

  // Owner and Steward
  const ownershipAttributes = [
    { label: t('owner'), value: entityData.owner_name || entityData.owner || '—' },
    { label: t('steward'), value: entityData.steward_name || entityData.steward || '—' },
  ];

  // Semantic and classification attributes
  const semanticAttributes = [
    { label: t('semanticType'), value: entityData.semantic_type || '—' },
    { label: t('glossaryTerm'), value: entityData.glossary_term_name || entityData.glossary_term || '—' },
    { label: t('tags'), value: entityData.tags && entityData.tags.length > 0 ? (
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
        {entityData.tags.map((tag, idx) => (
          <Chip key={idx} label={tag} size="small" variant="outlined" />
        ))}
      </Box>
    ) : '—' },
  ];

  // Timestamps
  const timestampAttributes = [
    { label: t('createdAt'), value: entityData.created_at ? new Date(entityData.created_at).toLocaleDateString() : '—' },
    { label: t('updatedAt'), value: entityData.updated_at ? new Date(entityData.updated_at).toLocaleDateString() : '—' },
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
        {renderTable(governanceAttributes, t('governanceQuality'))}
        {renderTable(ownershipAttributes, t('ownership'))}
        {renderTable(semanticAttributes, t('semanticClassification'))}
        {renderTable(timestampAttributes, t('timestamps'))}
      </Box>
    </DetailTabContent>
  );
}
