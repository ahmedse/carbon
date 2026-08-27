// src/pages/catalog/tabs/TagSummaryMetrics.jsx
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Typography, useTheme } from '@mui/material';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import ColorLensIcon from '@mui/icons-material/ColorLens';

export default function TagSummaryMetrics({ entityData }) {
  const { t } = useTranslation('catalog');
  const theme = useTheme();
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';

  return (
    <DetailMetricsPanel>
      <MetricsSection title={t('tagInformation')}>
        <MetricsGrid>
          <MetricCard
            label={t('id')}
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label={t('created')}
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title={t('styling')}>
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 6,
              height: 6,
              borderRadius: 1,
              bgcolor: entityData.color || theme.palette.primary.main,
              border: `2px solid ${theme.palette.divider}`,
            }}
          />
          <Box>
            <Typography variant="caption" sx={{ textTransform: 'uppercase', color: 'text.secondary' }}>
              {t('color')}
            </Typography>
            <Typography variant="body2">{entityData.color || t('notSet')}</Typography>
          </Box>
        </Box>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
