import React from 'react';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { PulseMark } from './PulseLogo';

/**
 * Attribution tick for Pulse-authored copy. Never labeled "AI".
 */
export default function AIGeneratedBadge({ label, size = 'small', sx }) {
  const { t } = useTranslation('ai');
  const mark = size === 'small' ? 12 : 14;
  return (
    <Box
      data-testid="ai-generated-badge"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.5,
        ...sx,
      }}
    >
      <PulseMark size={mark} />
      <Typography
        component="span"
        variant="caption"
        color="text.secondary"
        sx={{ fontSize: '0.625rem', letterSpacing: '0.04em', lineHeight: 1 }}
      >
        {label || t('pulseBrand')}
      </Typography>
    </Box>
  );
}
