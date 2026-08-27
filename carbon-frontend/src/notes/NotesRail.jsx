// src/notes/NotesRail.jsx
// Collapsed rail (default state): a slim arrow toggle on the edge of the
// content area — mirrors the left-menu pattern (arrow button + tooltip that
// opens the drawer; the tabs live inside the expanded panel, Notes first).

import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../i18n/useLanguage';

export function NotesRail({ onOpen }) {
  const { t } = useTranslation('notes');
  const { isRtl } = useLanguage();

  const label = t('tabs.notes');
  const Arrow = isRtl ? ChevronRightIcon : ChevronLeftIcon;

  return (
    <Box
      role="navigation"
      aria-label={t('rail.label')}
      sx={{
        width: 32,
        flexShrink: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.paper',
        borderRight: isRtl ? 'none' : '1px solid',
        borderLeft: isRtl ? '1px solid' : 'none',
        borderColor: 'divider',
        overflow: 'hidden',
      }}
    >
      <Tooltip title={label} placement={isRtl ? 'left' : 'right'}>
        <IconButton
          size="small"
          onClick={onOpen}
          aria-label={label}
          sx={{
            p: 0.4,
            borderRadius: 1,
            color: 'text.secondary',
            transition: 'all 150ms ease',
            '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
            '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' },
          }}
        >
          <Arrow sx={{ fontSize: 15 }} />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
