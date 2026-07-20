// src/pages/catalog/tabs/TagSummaryMetrics.jsx
import React from 'react';
import { Box, Typography } from '@mui/material';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import ColorLensIcon from '@mui/icons-material/ColorLens';

export default function TagSummaryMetrics({ entityData }) {
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';

  return (
    <DetailMetricsPanel>
      <MetricsSection title="Tag Information">
        <MetricsGrid>
          <MetricCard
            label="ID"
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label="Created"
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title="Styling">
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 1,
              bgcolor: entityData.color || '#000000',
              border: '2px solid #e0e0e0',
            }}
          />
          <Box>
            <Typography variant="caption" sx={{ textTransform: 'uppercase', color: 'text.secondary' }}>
              Color
            </Typography>
            <Typography variant="body2">{entityData.color || 'Not set'}</Typography>
          </Box>
        </Box>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
