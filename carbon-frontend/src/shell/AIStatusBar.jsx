import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { Box, Button, Switch, Tooltip, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

const DOT_COLORS = {
  ready: 'success.main',
  working: 'primary.main',
  streaming: 'primary.main',
  'needs-input': 'warning.main',
  transient: 'warning.main',
  offline: 'error.main',
};

function AIStatusBar({
  variant = 'ready',
  label = 'Ready',
  onRetry,
  denseThinking = false,
  onDenseThinkingChange,
}) {
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
          }}
        >
          {t('retry')}
        </Button>
      )}
      {typeof onDenseThinkingChange === 'function' && (
        <Tooltip title={t('denseThinking.hint')}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.25,
              ml: 0.5,
              pl: 0.75,
              borderLeft: 1,
              borderColor: 'divider',
              flexShrink: 0,
            }}
          >
            <Typography
              component="label"
              htmlFor="pulse-dense-thinking"
              variant="caption"
              sx={{ fontSize: '0.65rem', color: 'text.secondary', cursor: 'pointer', userSelect: 'none' }}
            >
              {t('denseThinking.label')}
            </Typography>
            <Switch
              id="pulse-dense-thinking"
              size="small"
              checked={Boolean(denseThinking)}
              onChange={(event) => onDenseThinkingChange(event.target.checked)}
              inputProps={{ 'aria-label': t('denseThinking.label') }}
              sx={{
                m: 0,
                '& .MuiSwitch-switchBase': { p: 0.4 },
                '& .MuiSwitch-thumb': { width: 12, height: 12 },
                '& .MuiSwitch-track': { borderRadius: 8 },
                width: 28,
                height: 16,
              }}
            />
          </Box>
        </Tooltip>
      )}
    </Box>
  );
}

AIStatusBar.propTypes = {
  variant: PropTypes.oneOf(['ready', 'working', 'streaming', 'needs-input', 'transient', 'offline']),
  label: PropTypes.string,
  onRetry: PropTypes.func,
  denseThinking: PropTypes.bool,
  onDenseThinkingChange: PropTypes.func,
};

export default AIStatusBar;
