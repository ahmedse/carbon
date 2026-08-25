// src/shell/AIStatusBar.jsx
import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { Box, Button, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

const DOT_COLORS = {
  ready: 'success.main',
  working: 'primary.main',
  streaming: 'primary.main',
  'needs-input': 'warning.main',
  transient: 'warning.main',
  offline: 'error.main',
};

function AIStatusBar({ variant = 'ready', label = 'Ready', onRetry }) {
  const { t } = useTranslation('ai');
  const color = DOT_COLORS[variant] || DOT_COLORS.ready;
  const retryable = variant === 'transient' || variant === 'offline';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flex: 1, minWidth: 0 }}>
      <Box
        sx={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          bgcolor: color,
          flexShrink: 0,
        }}
      />
      <Typography
        variant="caption"
        sx={{
          fontSize: '0.7rem',
          color: 'text.secondary',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {label}
      </Typography>
      {retryable && onRetry && (
        <Button
          size="small"
          startIcon={<RefreshIcon sx={{ fontSize: 13 }} />}
          onClick={onRetry}
          aria-label={t('retryAIConnection')}
          sx={{
            minWidth: 0,
            px: 0.75,
            py: 0.25,
            fontSize: '0.65rem',
            textTransform: 'none',
            lineHeight: 1,
          }}
        >
          {t('retry')}
        </Button>
      )}
    </Box>
  );
}

AIStatusBar.propTypes = {
  variant: PropTypes.oneOf(['ready', 'working', 'streaming', 'needs-input', 'transient', 'offline']),
  label: PropTypes.string,
  onRetry: PropTypes.func,
};

export default AIStatusBar;
