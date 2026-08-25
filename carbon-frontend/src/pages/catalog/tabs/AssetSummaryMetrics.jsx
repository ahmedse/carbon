// src/pages/catalog/tabs/AssetSummaryMetrics.jsx
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, LinearProgress, Typography } from '@mui/material';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import UpdateIcon from '@mui/icons-material/Update';

export default function AssetSummaryMetrics({ entityData }) {
  const { t } = useTranslation('catalog');
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';
  const updatedDate = entityData.updated_at
    ? new Date(entityData.updated_at).toLocaleDateString()
    : '—';

  const getQualityColorBackground = (status) => {
    const colors = { 
      passing: '#c8e6c9', 
      warning: '#fff9c4', 
      failing: '#ffcdd2', 
      unknown: '#f5f5f5' 
    };
    return colors[status] || '#f5f5f5';
  };

  const qualityScore = entityData.quality_score || 0;

  return (
    <DetailMetricsPanel>
      <MetricsSection title={t('assetInformation')}>
        <MetricsGrid>
          <MetricCard
            label={t('id')}
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label={t('type')}
            value={entityData.asset_type || t('unknown')}
            icon={<InfoIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title={t('qualityMetrics')}>
        <Box sx={{ p: 2 }}>
          <Typography variant="caption" sx={{ textTransform: 'uppercase', color: 'text.secondary', display: 'block', mb: 1 }}>
            {t('qualityScore')}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Box sx={{ flex: 1 }}>
              <LinearProgress 
                variant="determinate" 
                value={qualityScore}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: '#e0e0e0',
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: qualityScore >= 80 ? '#4caf50' : qualityScore >= 60 ? '#ff9800' : '#f44336',
                  },
                }}
              />
            </Box>
            <Typography variant="body2" sx={{ fontWeight: 600, minWidth: '60px' }}>
              {qualityScore.toFixed(1)}%
            </Typography>
          </Box>

          <Box 
            sx={{ 
              p: 1.5, 
              borderRadius: 1, 
              bgcolor: getQualityColorBackground(entityData.quality_status),
              border: '1px solid #e0e0e0',
              textAlign: 'center',
            }}
          >
            <Typography variant="caption" sx={{ textTransform: 'uppercase', fontWeight: 600 }}>
              {t('status')}: {entityData.quality_status || t('unknown')}
            </Typography>
          </Box>
        </Box>
      </MetricsSection>

      <MetricsSection title={t('timestamps')}>
        <MetricsGrid>
          <MetricCard
            label={t('created')}
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
          <MetricCard
            label={t('modified')}
            value={updatedDate}
            icon={<UpdateIcon />}
            color="warning"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
