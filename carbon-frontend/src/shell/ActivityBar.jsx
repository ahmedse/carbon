// File: src/shell/ActivityBar.jsx
// 48px left activity bar for studio switching (VSCode-inspired)

import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../i18n/useLanguage';
import { STUDIO_LABEL_KEYS } from '../i18n/shellLabels';

export function ActivityBar({ studios, activeStudio, onStudioChange }) {
  const { t } = useTranslation('shell');
  const { isRtl } = useLanguage();

  // Split: main studios vs bottom studios (Settings, Help)
  const mainStudios = studios.filter(s => !s.bottom);
  const bottomStudios = studios.filter(s => s.bottom);

  const renderStudioButton = (studio) => {
    const Icon = studio.icon;
    const isActive = activeStudio === studio.id;
    const label = STUDIO_LABEL_KEYS[studio.id]
      ? t(STUDIO_LABEL_KEYS[studio.id])
      : studio.label;

    return (
      <Tooltip title={label} placement="right" key={studio.id}>
        <IconButton
          size="small"
          onClick={() => onStudioChange(studio.id)}
          aria-label={label}
          aria-current={isActive ? 'page' : undefined}
          sx={{
            width: 40,
            height: 40,
            borderRadius: 1,
            color: isActive ? 'primary.main' : 'text.secondary',
            bgcolor: isActive ? 'action.selected' : 'transparent',
            mb: 0.5,
            transition: 'all 150ms ease',
            '&:hover': {
              bgcolor: isActive ? 'action.selected' : 'action.hover',
              color: isActive ? 'primary.main' : 'text.primary',
            },
            '&:focus-visible': {
              outline: '2px solid',
              outlineColor: 'primary.main',
              outlineOffset: '2px',
            },
          }}
        >
          <Icon sx={{ fontSize: 20 }} />
        </IconButton>
      </Tooltip>
    );
  };

  return (
    <Box
      component="nav"
      aria-label={t('ui.studioNavigation')}
      sx={{
        width: 48,
        bgcolor: 'background.dark',
        ...(isRtl ? { borderLeft: '1px solid' } : { borderRight: '1px solid' }),
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 1,
        flexShrink: 0,
      }}
    >
      {/* Main studios */}
      {mainStudios.map(renderStudioButton)}

      {/* Spacer */}
      <Box sx={{ flex: 1 }} />

      {/* Bottom studios */}
      {bottomStudios.map(renderStudioButton)}
    </Box>
  );
}
