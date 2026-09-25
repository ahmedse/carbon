// One Pulse status bar for Chat and Tasks. Font / Think / model live here
// so the same controls apply on every Pulse surface.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import TextDecreaseIcon from '@mui/icons-material/TextDecrease';
import TextIncreaseIcon from '@mui/icons-material/TextIncrease';
import { useTranslation } from 'react-i18next';
import AIStatusBar from './AIStatusBar';
import AIModelSelect from './AIModelSelect';
import PulsePresence from './PulsePresence';
import { usePulsePrefs } from './pulsePrefs';

function PulseWorkspaceFooter({
  variant = 'ready',
  label = 'Ready',
  onRetry,
  showModel = true,
  prefs: prefsProp,
  children,
}) {
  const { t } = useTranslation('ai');
  const hooked = usePulsePrefs();
  const {
    contentZoom,
    adjustZoom,
    resetZoom,
    denseThinking,
    setDenseThinking,
    setSelectedModel,
  } = prefsProp || hooked;

  return (
    <Box
      data-testid="pulse-workspace-footer"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        px: 1.25,
        minHeight: 28,
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      <AIStatusBar
        variant={variant}
        label={label}
        onRetry={onRetry}
        denseThinking={denseThinking}
        onDenseThinkingChange={setDenseThinking}
      />
      <PulsePresence />
      <Tooltip title={t('textSize')}>
        <Stack
          direction="row"
          alignItems="center"
          spacing={0.25}
          sx={{ borderLeft: 1, borderColor: 'divider', pl: 0.5 }}
        >
          <IconButton
            size="small"
            aria-label={t('decreaseTextSize')}
            disabled={contentZoom <= 0.8}
            onClick={() => adjustZoom(-0.1)}
            sx={{ p: 0.25 }}
          >
            <TextDecreaseIcon sx={{ fontSize: 13 }} />
          </IconButton>
          <Typography
            variant="caption"
            onClick={resetZoom}
            role="button"
            tabIndex={0}
            aria-label={t('resetTextSize')}
            sx={{
              minWidth: 32,
              textAlign: 'center',
              fontSize: '0.6875rem',
              lineHeight: 1,
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            {Math.round(contentZoom * 100)}%
          </Typography>
          <IconButton
            size="small"
            aria-label={t('increaseTextSize')}
            disabled={contentZoom >= 1.4}
            onClick={() => adjustZoom(0.1)}
            sx={{ p: 0.25 }}
          >
            <TextIncreaseIcon sx={{ fontSize: 13 }} />
          </IconButton>
        </Stack>
      </Tooltip>
      {showModel ? <AIModelSelect onChange={setSelectedModel} /> : null}
      {children}
    </Box>
  );
}

PulseWorkspaceFooter.propTypes = {
  variant: PropTypes.oneOf(['ready', 'working', 'streaming', 'needs-input', 'transient', 'offline']),
  label: PropTypes.string,
  onRetry: PropTypes.func,
  showModel: PropTypes.bool,
  prefs: PropTypes.object,
  children: PropTypes.node,
};

export default PulseWorkspaceFooter;
