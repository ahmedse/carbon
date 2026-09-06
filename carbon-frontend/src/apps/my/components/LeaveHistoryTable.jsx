// src/apps/my/components/LeaveHistoryTable.jsx
// Presentational — a compact table of leave request records. The display
// status is DERIVED from `reference_no` presence (submitted vs draft) because
// the raw leave `status` is always "draft" in this thin slice (the governed
// Correspondence carries the real approval status). Color never stands alone
// — a text label always accompanies the chip.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
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

/** Localized label for a leave-type code, falling back to the raw code. */
function leaveTypeLabel(i18n, t, code) {
  if (!code) return t('profileNotAvailable');
  const key = `leaveType.${code}`;
  return i18n.exists(key) ? t(key) : code;
}

/** Localized date formatting, robust to ISO datetimes and timezone shift. */
function formatDate(value, lang) {
  if (!value) return '—';
  const str = String(value).slice(0, 10);
  const [y, m, d] = str.split('-').map(Number);
  if (!y || !m || !d) return '—';
  const date = new Date(y, m - 1, d);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(lang === 'ar' ? 'ar' : 'en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// ── Component ─────────────────────────────────────────────────────────

export default function LeaveHistoryTable({ records, loading, error, onRetry }) {
  const { t, i18n } = useTranslation('my');

  const sorted = useMemo(() => {
    const list = Array.isArray(records) ? records : [];
    return [...list].sort((a, b) => {
      const aKey = String(a.created_at || a.start_date || '');
      const bKey = String(b.created_at || b.start_date || '');
      return bKey.localeCompare(aKey);
    });
  }, [records]);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AssignmentIcon} title={t('historyTitle')} />
        {loading ? (
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
            <Skeleton width="85%" />
          </Stack>
        ) : error ? (
          <InlineError message={error} onRetry={onRetry} />
        ) : sorted.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('historyEmpty')}
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyReferenceNo')}
                  </TableCell>
                  <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyType')}
                  </TableCell>
                  <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyStart')}
                  </TableCell>
                  <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyEnd')}
                  </TableCell>
                  <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyDays')}
                  </TableCell>
                  <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                    {t('historyStatus')}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.map((record) => {
                  const submitted = Boolean(record.reference_no);
                  return (
                    <TableRow key={record.id} hover>
                      <TableCell sx={{ ...FONT.body2 }}>
                        {record.reference_no || '—'}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body2 }}>
                        {leaveTypeLabel(i18n, t, record.leave_type)}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body2 }}>
                        {formatDate(record.start_date, i18n.language)}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body2 }}>
                        {formatDate(record.end_date, i18n.language)}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body2 }}>
                        {record.days ?? '—'}
                      </TableCell>
                      <TableCell align="right">
                        <Chip
                          size="small"
                          variant="outlined"
                          color={submitted ? 'success' : 'default'}
                          label={submitted ? t('statusSubmitted') : t('statusDraft')}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}

LeaveHistoryTable.propTypes = {
  records: PropTypes.array.isRequired,
  loading: PropTypes.bool.isRequired,
  error: PropTypes.string,
  onRetry: PropTypes.func,
};

LeaveHistoryTable.defaultProps = {
  error: null,
  onRetry: null,
};
