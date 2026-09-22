// src/apps/people/components/CertExpiryChip.jsx
// Shared expiry urgency chip + legend for Certifications list and Employee Certs tab.

import React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useTranslation } from 'react-i18next';
import { daysUntilExpiry, expiryUrgency } from '../utils';

export default function CertExpiryChip({ expiryDate }) {
  const { t } = useTranslation('people');
  const u = expiryUrgency(expiryDate);
  if (!u) {
    return (
      <Chip size="small" label={t('certsTabValid')} color="success" variant="outlined" />
    );
  }
  const days = daysUntilExpiry(expiryDate);
  if (u === 'expired') {
    return (
      <Chip size="small" icon={<WarningAmberIcon />} label={t('certsTabExpired')} color="error" />
    );
  }
  if (u === 'critical') {
    return (
      <Chip
        size="small"
        icon={<WarningAmberIcon />}
        label={t('certsTabDaysLeft', { days })}
        color="error"
      />
    );
  }
  if (u === 'warning') {
    return (
      <Chip
        size="small"
        icon={<WarningAmberIcon />}
        label={t('certsTabDaysLeft', { days })}
        color="warning"
      />
    );
  }
  return (
    <Chip
      size="small"
      label={t('certsTabDaysLeft', { days })}
      color="info"
      variant="outlined"
    />
  );
}

export function CertExpiryLegend() {
  const { t } = useTranslation('people');
  const items = [
    { color: 'error.main', label: t('certsLegendCritical') },
    { color: 'warning.main', label: t('certsLegendWarning') },
    { color: 'info.main', label: t('certsLegendNotice') },
    { color: 'success.main', label: t('certsLegendValid') },
  ];
  return (
    <Box sx={{ mt: 1, display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
      {items.map(({ color, label }) => (
        <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 0.375 }}>
          <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
          <Typography variant="caption" color="text.disabled">{label}</Typography>
        </Box>
      ))}
    </Box>
  );
}
