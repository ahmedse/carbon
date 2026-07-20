// src/pages/catalog/tabs/AssetOverviewTab.jsx
// Asset Overview Tab: Display read-only asset metadata and governance information

import React from 'react';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography, Chip, Grid, Paper } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

export default function AssetOverviewTab({ entityData }) {
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">No data available</Typography>
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
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.title || entityData.name || '—' },
    { label: 'Description', value: entityData.description || '—' },
    { label: 'Asset Type', value: entityData.asset_type || '—' },
  ];

  // Governance attributes (from AssetProfile model)
  const governanceAttributes = [
    { label: 'Domain', value: entityData.domain_name || '—' },
    { label: 'Classification', value: entityData.classification ? (
      <Chip 
        label={entityData.classification} 
        color={getClassificationColor(entityData.classification)}
        size="small"
        variant="outlined"
      />
    ) : '—' },
    { label: 'Quality Status', value: entityData.quality_status ? (
      <Chip 
        label={entityData.quality_status} 
        color={getQualityColor(entityData.quality_status)}
        size="small"
      />
    ) : '—' },
    { label: 'Quality Score', value: entityData.quality_score ? `${entityData.quality_score.toFixed(1)}%` : '—' },
  ];

  // Owner and Steward
  const ownershipAttributes = [
    { label: 'Owner', value: entityData.owner_name || entityData.owner || '—' },
    { label: 'Steward', value: entityData.steward_name || entityData.steward || '—' },
  ];

  // Semantic and classification attributes
  const semanticAttributes = [
    { label: 'Semantic Type', value: entityData.semantic_type || '—' },
    { label: 'Glossary Term', value: entityData.glossary_term_name || entityData.glossary_term || '—' },
    { label: 'Tags', value: entityData.tags && entityData.tags.length > 0 ? (
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
        {entityData.tags.map((tag, idx) => (
          <Chip key={idx} label={tag} size="small" variant="outlined" />
        ))}
      </Box>
    ) : '—' },
  ];

  // Timestamps
  const timestampAttributes = [
    { label: 'Created At', value: entityData.created_at ? new Date(entityData.created_at).toLocaleDateString() : '—' },
    { label: 'Updated At', value: entityData.updated_at ? new Date(entityData.updated_at).toLocaleDateString() : '—' },
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
        {renderTable(governanceAttributes, 'Governance & Quality')}
        {renderTable(ownershipAttributes, 'Ownership')}
        {renderTable(semanticAttributes, 'Semantic & Classification')}
        {renderTable(timestampAttributes, 'Timestamps')}
      </Box>
    </DetailTabContent>
  );
}
