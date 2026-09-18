// NotesDrawer — desktop docked panel; mobileFullscreen → Dialog overlay (ADR-0035)

import React from 'react';
import { Box, Dialog, AppBar, Toolbar, IconButton, Typography, Fab } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import StickyNote2OutlinedIcon from '@mui/icons-material/StickyNote2Outlined';
import { useNotes } from './NotesContext';
import { NotesRail } from './NotesRail';
import { NotesPanel } from './NotesPanel';
import { useLanguage } from '../i18n/useLanguage';
import { useTranslation } from 'react-i18next';

const WIDTH_MIN = () => Math.min(240, Math.floor(window.innerWidth * 0.35));
const WIDTH_MAX = () => Math.max(WIDTH_MIN(), Math.floor(window.innerWidth * 0.5));

export function NotesDrawer({ mobileFullscreen = false }) {
  const { open, width, setWidth, setOpen } = useNotes();
  const { isRtl } = useLanguage();
  const { t } = useTranslation('shell');

  if (mobileFullscreen) {
    return (
      <>
        {!open && (
          <Fab
            color="primary"
            size="medium"
            aria-label={t('ui.notes', { defaultValue: 'Notes' })}
            onClick={() => setOpen(true)}
            sx={{
              position: 'fixed',
              bottom: 48,
              zIndex: (theme) => theme.zIndex.speedDial,
              minWidth: 40,
              minHeight: 40,
              ...(isRtl ? { left: 16 } : { right: 16 }),
            }}
          >
            <StickyNote2OutlinedIcon />
          </Fab>
        )}
        <Dialog
          fullScreen
          open={open}
          onClose={() => setOpen(false)}
          PaperProps={{ sx: { bgcolor: 'background.paper' } }}
        >
          <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Toolbar sx={{ minHeight: 48, gap: 1 }}>
              <Typography variant="subtitle2" sx={{ flex: 1 }}>
                {t('ui.notes', { defaultValue: 'Notes' })}
              </Typography>
              <IconButton
                edge="end"
                onClick={() => setOpen(false)}
                aria-label={t('ui.close', { defaultValue: 'Close' })}
                sx={{ minWidth: 40, minHeight: 40 }}
              >
                <CloseIcon />
              </IconButton>
            </Toolbar>
          </AppBar>
          <Box sx={{ flex: 1, minHeight: 0, height: '100%' }}>
            <NotesPanel />
          </Box>
        </Dialog>
      </>
    );
  }

  if (!open) {
    return <NotesRail onOpen={() => setOpen(true)} />;
  }

  return (
    <Box
      sx={{
        position: 'relative',
        width,
        maxWidth: WIDTH_MAX(),
        minWidth: WIDTH_MIN(),
        flexShrink: 0,
        height: '100%',
        display: 'flex',
      }}
    >
      <Box
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize notes panel"
        sx={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          zIndex: 2,
          bgcolor: 'transparent',
          '&:hover': { bgcolor: 'action.hover' },
          ...(isRtl ? { right: 0 } : { left: 0 }),
        }}
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const startX = e.clientX;
          const startWidth = width;
          const onMove = (moveEvent) => {
            const delta = isRtl ? moveEvent.clientX - startX : startX - moveEvent.clientX;
            setWidth(startWidth + delta);
          };
          const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
          };
          window.addEventListener('mousemove', onMove);
          window.addEventListener('mouseup', onUp);
        }}
      />
      <Box sx={{ flex: 1, minWidth: 0, height: '100%' }}>
        <NotesPanel />
      </Box>
    </Box>
  );
}
