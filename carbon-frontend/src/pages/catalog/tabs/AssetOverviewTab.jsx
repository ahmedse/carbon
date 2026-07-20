// src/pages/catalog/tabs/AssetOverviewTab.jsx
import React from 'react';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography, Chip } from '@mui/material';
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

  const attributes = [
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.name },
    { label: 'Description', value: entityData.description || '—' },
    { label: 'Asset Type', value: entityData.asset_type || '—' },
    { label: 'Quality Status', value: <Chip label={entityData.quality_status || 'Unknown'} color={getQualityColor(entityData.quality_status)} size="small" /> },
    { label: 'Quality Score', value: entityData.quality_score ? `${entityData.quality_score.toFixed(1)}%` : '—' },
  ];

  return (
    <DetailTabContent>
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell sx={{ fontWeight: 600 }}>Property</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {attributes.map((attr, idx) => (
              <TableRow key={idx} sx={{ '&:hover': { bgcolor: 'grey.50' } }}>
                <TableCell sx={{ fontWeight: 500, width: '30%' }}>{attr.label}</TableCell>
                <TableCell>{attr.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </DetailTabContent>
  );
}
