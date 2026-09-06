// src/apps/my/components/LeaveBalanceCards.jsx
// Presentational — renders one compact card per leave-balance row (Entitled /
// Used / Pending / Remaining) with a localized leave-type label. Handles its
// own loading / error / empty states. All strings via useTranslation('my');
// all colors via theme tokens.

import React from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Button,
  Card,
  CardContent,
  Grid,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import { useTranslation } from 'react-i18next';
import { FONT } from '../../../theme/themeTokens';

// ── Small presentational helpers ──────────────────────────────────────

function SectionTitle({ icon: Icon, title }) {
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

function InlineError({ message, onRetry }) {
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

function Metric({ label, value, tone }) {
  return (
    <Stack sx={{ minWidth: 0 }}>
      <Typography
        sx={{
          ...FONT.bodySmall,
          color: 'text.secondary',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
        }}
      >
        {label}
      </Typography>
      <Typography sx={{ ...FONT.cardTitle, color: tone || 'text.primary' }}>
        {value ?? 0}
      </Typography>
    </Stack>
  );
}

/** Localized label for a leave-type code, falling back to the raw code. */
function leaveTypeLabel(i18n, t, code) {
  if (!code) return t('profileNotAvailable');
  const key = `leaveType.${code}`;
  return i18n.exists(key) ? t(key) : code;
}

// ── Component ─────────────────────────────────────────────────────────

export default function LeaveBalanceCards({ balances, loading, error, onRetry }) {
  const { t, i18n } = useTranslation('my');

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={EventAvailableIcon} title={t('leaveBalanceTitle')} />
        {loading ? (
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
            <Skeleton width="85%" />
          </Stack>
        ) : error ? (
          <InlineError message={error} onRetry={onRetry} />
        ) : balances.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('leaveBalanceEmpty')}
          </Typography>
        ) : (
          <Grid container spacing={1}>
            {balances.map((balance, index) => {
              const pending = Number(balance.pending ?? 0);
              const remaining = Number(balance.remaining ?? 0);
              return (
                <Grid key={`${balance.leave_type}-${index}`} size={{ xs: 12, sm: 6, md: 4 }}>
                  <Card variant="outlined">
                    <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                      <Typography
                        noWrap
                        sx={{ ...FONT.cardTitle, mb: 0.75 }}
                      >
                        {leaveTypeLabel(i18n, t, balance.leave_type)}
                      </Typography>
                      <Stack direction="row" spacing={1.5} useFlexGap flexWrap="wrap" rowGap={1}>
                        {Number(balance.carried_forward ?? 0) > 0 && (
                          <Metric
                            label={t('leaveCarriedForward')}
                            value={balance.carried_forward}
                            tone="info.main"
                          />
                        )}
                        <Metric label={t('leaveBalanceEntitled')} value={balance.entitled} />
                        <Metric label={t('leaveBalanceUsed')} value={balance.used} />
                        <Metric
                          label={t('leaveBalancePending')}
                          value={balance.pending}
                          tone={pending > 0 ? 'warning.main' : null}
                        />
                        <Metric
                          label={t('leaveBalanceRemaining')}
                          value={balance.remaining}
                          tone={remaining > 0 ? 'success.main' : null}
                        />
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        )}
      </CardContent>
    </Card>
  );
}

LeaveBalanceCards.propTypes = {
  balances: PropTypes.array.isRequired,
  loading: PropTypes.bool.isRequired,
  error: PropTypes.string,
  onRetry: PropTypes.func,
};

LeaveBalanceCards.defaultProps = {
  error: null,
  onRetry: null,
};
