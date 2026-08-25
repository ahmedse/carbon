// src/pages/catalog/tabs/DataProductDQTab.jsx
// Data Product DQ Tab: aggregate quality summary + per-table breakdown.
// Uses the backend quality_summary endpoint + asset profiles for table status.
import React, { useMemo } from 'react';
import {
  Box, Card, CardContent, Chip, Typography, Table, TableHead, TableRow, TableCell, TableBody, Alert,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

export default function DataProductDQTab({ entityData, additionalProps = {} }) {
  const navigate = useNavigate();
  const { t } = useTranslation('catalog');
  const { qualitySummary = null, tables = [], assets = {} } = additionalProps;

  const tableRows = useMemo(
    () => tables.map((t) => ({ ...t, quality: assets[t.id]?.quality_status || 'unknown', score: assets[t.id]?.quality_score ?? null })),
    [tables, assets]
  );

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  const summary = qualitySummary || { total: 0, passing: 0, warning: 0, failing: 0, unknown: 0, avg_score: null };
  const passRate = summary.total > 0 ? Math.round((summary.passing / summary.total) * 100) : null;

  const statCards = [
    { label: t('tablesChecked'), value: summary.total },
    { label: t('passing'), value: summary.passing, color: 'success' },
    { label: t('warning'), value: summary.warning, color: 'warning' },
    { label: t('failing'), value: summary.failing, color: 'error' },
    { label: t('passRate'), value: passRate != null ? `${passRate}%` : '—' },
    { label: t('avgScore'), value: summary.avg_score != null ? `${Number(summary.avg_score).toFixed(1)}%` : '—' },
  ];

  return (
    <DetailTabContent>
      {summary.total === 0 ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t('noQualityChecksRun')}
        </Alert>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2, mb: 3 }}>
          {statCards.map((stat, idx) => (
            <Card key={idx} variant="outlined" sx={{ height: '100%' }}>
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="caption" color="text.secondary" display="block">
                  {stat.label}
                </Typography>
                <Typography variant="h6" fontWeight={700} color={stat.color ? `${stat.color}.main` : 'text.primary'}>
                  {stat.value}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
        {t('perTableQuality')}
      </Typography>

      {tableRows.length === 0 ? (
        <Alert severity="info">{t('noTablesInProduct')}</Alert>
      ) : (
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'grey.100' }}>
                <TableCell sx={{ fontWeight: 600 }}>{t('table')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('status')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('score')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tableRows.map((row) => (
                <TableRow
                  key={row.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/catalog/tables/${row.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>{row.title}</Typography>
                    <Typography variant="caption" color="text.secondary">{row.description || ''}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={t(row.quality)}
                      size="small"
                      color={QUALITY_COLOR[row.quality] || 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>{row.score != null ? `${Number(row.score).toFixed(1)}%` : '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </DetailTabContent>
  );
}
