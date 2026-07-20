// src/pages/catalog/tabs/ReferenceSetMetricsPanel.jsx
// Reference Set Metrics: Usage statistics and summary

import React from 'react';
import { Box, Typography, Chip, Divider } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

export default function ReferenceSetMetricsPanel({ entityData, additionalProps = {} }) {
  const { values = [] } = additionalProps;

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">
          No metrics available
        </Typography>
      </DetailTabContent>
    );
  }

  const activeValues = values.filter(v => v.is_active);
  const inactiveValues = values.filter(v => !v.is_active);
  const withValidityPeriod = values.filter(v => v.valid_from || v.valid_to);

  const metrics = [
    {
      label: 'Total Values',
      value: values.length,
      color: 'primary',
    },
    {
      label: 'Active',
      value: activeValues.length,
      color: 'success',
      icon: <CheckCircleIcon fontSize="small" />,
    },
    {
      label: 'Inactive',
      value: inactiveValues.length,
      color: 'default',
      icon: <CancelIcon fontSize="small" />,
    },
    {
      label: 'Time-Bound',
      value: withValidityPeriod.length,
      color: 'info',
    },
  ];

  return (
    <DetailTabContent>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Value Statistics
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
        {metrics.map((metric, idx) => (
          <Box key={idx}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {metric.label}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {metric.icon}
              <Chip 
                label={metric.value} 
                size="small" 
                color={metric.color}
                sx={{ fontWeight: 600 }}
              />
            </Box>
          </Box>
        ))}
      </Box>

      <Divider sx={{ my: 3 }} />

      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Governance
      </Typography>

      <Box sx={{ mt: 2 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          Domain
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          {entityData.domain_name || 'Not assigned'}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block">
          Steward
        </Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          {entityData.steward_name || 'Not assigned'}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block">
          Version
        </Typography>
        <Typography variant="body2">
          {entityData.version || '1'}
        </Typography>
      </Box>
    </DetailTabContent>
  );
}
