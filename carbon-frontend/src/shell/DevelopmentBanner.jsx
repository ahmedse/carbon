// src/shell/DevelopmentBanner.jsx
// Slim, dismissible "early access" strip rendered directly under the header.
//
// Enterprise pattern (see AIOfflineBanner for the in-repo precedent):
//   - Non-blocking, single-row, no interstitials.
//   - One primary CTA ("Share feedback") funneling into the existing /feedback
//     loop (which already feeds the AI Feedback Review panel).
//   - Dismissal is persisted (localStorage) so the notice never nags; the
//     persistent "Early access" badge in the header remains as the always-on
//     status indicator.
//   - Fully i18n (shell.devBanner.*) and theme-token driven (no hardcoded hex).

import React, { useState } from 'react';
import { Alert, Button, Chip, IconButton, Typography, useTheme } from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import CloseIcon from '@mui/icons-material/Close';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const DISMISS_KEY = 'carbon-dev-banner-dismissed';

function DevelopmentBanner() {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) === '1';
    } catch {
      return false;
    }
  });

  // Don't surface the "share feedback" prompt on the feedback/help pages
  // themselves — the CTA would be redundant there.
  const isFeedbackSurface =
    location.pathname.startsWith('/feedback') || location.pathname.startsWith('/help');

  if (dismissed || isFeedbackSurface) return null;

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, '1');
    } catch {
      // localStorage unavailable — banner will simply re-appear next load.
    }
    setDismissed(true);
  };

  return (
    <Alert
      severity="info"
      icon={<RocketLaunchIcon fontSize="small" />}
      role="status"
      action={
        <>
          <Button
            size="small"
            variant="contained"
            color="info"
            onClick={() => navigate('/feedback')}
            sx={{
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
            }}
          >
            {t('devBanner.cta')}
          </Button>
          <IconButton
            size="small"
            color="inherit"
            aria-label={t('devBanner.dismiss')}
            title={t('devBanner.dismiss')}
            onClick={handleDismiss}
            sx={{ color: 'text.secondary' }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </>
      }
      sx={{
        position: 'sticky',
        top: 56,
        zIndex: theme.zIndex.appBar - 1,
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        '& .MuiAlert-message': {
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1,
        },
        '& .MuiAlert-action': {
          alignItems: 'center',
          mr: 0,
          pl: 0,
          gap: 1,
        },
      }}
    >
      <Chip
        label={t('devBanner.label')}
        size="small"
        variant="outlined"
        color="info"
        sx={{
          height: 20,
          fontSize: '0.625rem',
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          flexShrink: 0,
          '& .MuiChip-label': { px: 0.75 },
        }}
      />
      <Typography variant="body2" sx={{ color: 'inherit', lineHeight: 1.4 }}>
        {t('devBanner.message')}
      </Typography>
    </Alert>
  );
}

export default React.memo(DevelopmentBanner);
