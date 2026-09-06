// src/apps/my/components/myRequestsCommon.jsx
// Shared presentational primitives for the My Requests screens (SectionTitle
// + InlineError). Mirrors the inline helpers used elsewhere in the my app,
// but shared here so the request list/detail components stay small.

import React from 'react';
import PropTypes from 'prop-types';
import { Alert, Button, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { FONT } from '../../../theme/themeTokens';

export function SectionTitle({ icon: Icon, title }) {
  return (
    <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 1 }}>
      {Icon && <Icon sx={{ fontSize: '1rem', color: 'primary.main' }} />}
      <Typography
        sx={{
          ...FONT.cardTitle,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: 'text.secondary',
        }}
      >
        {title}
      </Typography>
    </Stack>
  );
}

SectionTitle.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.string.isRequired,
};

SectionTitle.defaultProps = {
  icon: null,
};

export function InlineError({ message, onRetry }) {
  const { t } = useTranslation('my');
  return (
    <Alert
      severity="error"
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            {t('retry')}
          </Button>
        ) : null
      }
    >
      {message}
    </Alert>
  );
}

InlineError.propTypes = {
  message: PropTypes.string,
  onRetry: PropTypes.func,
};

InlineError.defaultProps = {
  message: '',
  onRetry: null,
};
