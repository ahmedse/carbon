// Presentational table of the caller's attendance permissions (ESS history).

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
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { useTranslation } from 'react-i18next';
import ResponsiveList from '../../../components/layout/ResponsiveList';
import { FONT } from '../../../theme/themeTokens';

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

/** GovernedValueField reads as {id, code, label}; writes may be a bare code string. */
function permissionTypeLabel(t, value) {
  if (value == null || value === '') return '—';
  const code =
    typeof value === 'object' ? value.code || value.id : value;
  if (code == null || code === '') {
    return typeof value === 'object' && value.label ? value.label : '—';
  }
  const fallback =
    typeof value === 'object' && value.label ? value.label : String(code);
  return t(`permissionType.${code}`, { defaultValue: fallback });
}

export default function AttendanceHistoryTable({ records, loading, error, onRetry }) {
  const { t, i18n } = useTranslation('my');
  const sorted = useMemo(() => {
    const list = Array.isArray(records) ? records : [];
    return [...list].sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
  }, [records]);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccessTimeIcon} title={t('attendanceHistoryTitle')} />
        {loading ? (
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
          </Stack>
        ) : error ? (
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
            {error}
          </Alert>
        ) : sorted.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('attendanceHistoryEmpty')}
          </Typography>
        ) : (
          <ResponsiveList
            items={sorted}
            getKey={(row) => row.id}
            emptyLabel={t('attendanceHistoryEmpty')}
            renderCard={(row) => ({
              title: permissionTypeLabel(t, row.permission_type),
              meta: `${formatDate(row.date, i18n.language)} · ${row.hours}h`,
              status: row.approved ? t('statusApproved') : t('statusSubmitted'),
              statusColor: row.approved ? 'success' : 'info',
            })}
            table={
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('historyDate')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('historyType')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('fieldHours')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('historyStatus')}
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sorted.map((row) => (
                      <TableRow key={row.id} hover>
                        <TableCell>{formatDate(row.date, i18n.language)}</TableCell>
                        <TableCell>{permissionTypeLabel(t, row.permission_type)}</TableCell>
                        <TableCell>{row.hours}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={row.approved ? t('statusApproved') : t('statusSubmitted')}
                            color={row.approved ? 'success' : 'info'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}

AttendanceHistoryTable.propTypes = {
  records: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.string,
  onRetry: PropTypes.func,
};

AttendanceHistoryTable.defaultProps = {
  records: [],
  loading: false,
  error: null,
  onRetry: undefined,
};
