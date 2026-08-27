// src/shell/DevelopmentBanner.jsx
// Slim "early access" strip rendered directly under the header.
//
// Enterprise pattern (see AIOfflineBanner for the in-repo precedent):
//   - Non-blocking, single-row, no interstitials.
//   - One primary CTA ("Share feedback") funneling into the existing /feedback
//     loop (which already feeds the AI Feedback Review panel).
//   - Fully i18n (shell.devBanner.*) and theme-token driven (no hardcoded hex).

import React from 'react';
import { Alert, Button, Chip, Typography, useTheme } from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

function DevelopmentBanner() {
  const { t } = useTranslation('shell');
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  // Don't surface the "share feedback" prompt on the feedback/help pages
  // themselves — the CTA would be redundant there.
  const isFeedbackSurface =
    location.pathname.startsWith('/feedback') || location.pathname.startsWith('/help');

  if (isFeedbackSurface) return null;

  return (
    <Alert
      severity="info"
      icon={<RocketLaunchIcon fontSize="small" />}
      role="status"
      action={
        <Button
          size="small"
          variant="contained"
          color="info"
          onClick={() => navigate('/feedback')}
          sx={{
            textTransform: 'none',
            fontWeight: 600,
            fontSize: '0.72rem',
            whiteSpace: 'nowrap',
            py: 0.25,
          }}
        >
          {t('devBanner.cta')}
        </Button>
      }
      sx={{
        position: 'sticky',
        top: 56,
        zIndex: theme.zIndex.appBar - 1,
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        py: 0,
        minHeight: 30,
        '& .MuiAlert-icon': { py: 0, alignItems: 'center' },
        '& .MuiAlert-message': {
          flex: 1,
          minWidth: 0,
          py: 0,
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1,
        },
        '& .MuiAlert-action': { alignItems: 'center', mr: 0, pl: 0, py: 0 },
      }}
    >
      <Chip
        label={t('devBanner.label')}
        size="small"
        variant="outlined"
        color="info"
        sx={{
          height: 18,
          fontSize: '0.6rem',
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          '& .MuiChip-label': { px: 0.75 },
        }}
      />
      <Typography component="span" variant="caption" sx={{ color: 'inherit', lineHeight: 1.3 }}>
        {t('devBanner.message')}
      </Typography>
    </Alert>
  );
}

export default React.memo(DevelopmentBanner);
