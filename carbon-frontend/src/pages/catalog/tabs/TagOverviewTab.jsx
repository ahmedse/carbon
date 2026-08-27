// src/pages/catalog/tabs/TagOverviewTab.jsx
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

export default function TagOverviewTab({ entityData }) {
  const { t } = useTranslation('catalog');
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  const attributes = [
    { label: t('id'), value: entityData.id },
    { label: t('name'), value: entityData.name },
    { label: t('description'), value: entityData.description || '—' },
    { label: t('color'), value: entityData.color || '—' },
    { label: t('createdAt'), value: entityData.created_at ? new Date(entityData.created_at).toLocaleDateString() : '—' },
  ];

  return (
    <DetailTabContent>
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell sx={{ fontWeight: 600 }}>{t('property')}</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>{t('value')}</TableCell>
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
