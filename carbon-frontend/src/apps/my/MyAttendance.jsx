// src/apps/my/MyAttendance.jsx
// My — daily attendance by month + short-hours permissions (route /my/attendance).
// Records: GET people/me/attendance/ (read-only). Permissions: existing ESS submit.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AddIcon from '@mui/icons-material/Add';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import SearchIcon from '@mui/icons-material/Search';
import TuneIcon from '@mui/icons-material/Tune';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import { SearchSelect } from '../../components/Form';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchMyAttendance, fetchMyAttendancePermissions, fetchMyProfile } from '../../api/my';
import AttendanceHistoryTable from './components/AttendanceHistoryTable';
import RequestAttendanceDialog from './components/RequestAttendanceDialog';

function pad2(n) {
  return String(n).padStart(2, '0');
}

function monthKeyFromDate(value) {
  if (!value) return null;
  const s = String(value).slice(0, 7);
  return /^\d{4}-\d{2}$/.test(s) ? s : null;
}

function monthBounds(key) {
  const [y, m] = key.split('-').map(Number);
  const start = `${y}-${pad2(m)}-01`;
  const last = new Date(y, m, 0).getDate();
  const end = `${y}-${pad2(m)}-${pad2(last)}`;
  return { start, end };
}

function formatMonthLabel(key, locale) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(locale === 'ar' ? 'ar' : 'en', {
    month: 'long',
    year: 'numeric',
  });
}

function formatDay(value, locale) {
  if (!value) return '—';
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return '—';
  return new Date(y, m - 1, d).toLocaleDateString(locale === 'ar' ? 'ar' : 'en', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

function formatHours(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function statusColor(status) {
  switch (status) {
    case 'present':
      return 'success';
    case 'absent':
      return 'error';
    case 'leave':
      return 'info';
    case 'permission':
      return 'warning';
    default:
      return 'default';
  }
}

/** Collect YYYY-MM keys from records + permissions (newest first). */
export function collectAttendanceMonths(records, permissions, fallbackKey) {
  const keys = new Set();
  for (const row of records || []) {
    const k = monthKeyFromDate(row.date);
    if (k) keys.add(k);
  }
  for (const row of permissions || []) {
    const k = monthKeyFromDate(row.date);
    if (k) keys.add(k);
  }
  if (keys.size === 0 && fallbackKey) keys.add(fallbackKey);
  return [...keys].sort((a, b) => b.localeCompare(a));
}

export default function MyAttendance() {
  const { t, i18n } = useTranslation('my');
  const { token } = useAuth();
  const { notify } = useNotification();
  useDocumentTitle(t('attendanceTitle'));

  const locale = i18n.language?.startsWith('ar') ? 'ar' : 'en';
  const nowKey = `${new Date().getFullYear()}-${pad2(new Date().getMonth() + 1)}`;

  const [profile, setProfile] = useState(null);
  const [records, setRecords] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [monthKey, setMonthKey] = useState(nowKey);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [daySearch, setDaySearch] = useState('');
  const [dayStatus, setDayStatus] = useState('');
  const [dayOvertime, setDayOvertime] = useState(''); // '' | 'yes' | 'no'
  const [showDayFilters, setShowDayFilters] = useState(false);
  const [permSearch, setPermSearch] = useState('');
  const [permStatus, setPermStatus] = useState('');
  const [showPermFilters, setShowPermFilters] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [att, perms] = await Promise.all([
        fetchMyAttendance(token),
        fetchMyAttendancePermissions(token),
      ]);
      const nextRecords = Array.isArray(att) ? att : [];
      const nextPerms = Array.isArray(perms) ? perms : [];
      setRecords(nextRecords);
      setPermissions(nextPerms);
      const months = collectAttendanceMonths(nextRecords, nextPerms, nowKey);
      setMonthKey((prev) => (months.includes(prev) ? prev : months[0]));
    } catch (err) {
      setError(err?.message || t('error'));
      setRecords([]);
      setPermissions([]);
    } finally {
      setLoading(false);
    }
  }, [token, t, nowKey]);

  const loadProfile = useCallback(async () => {
    try {
      setProfile(await fetchMyProfile(token));
    } catch {
      setProfile(null);
    }
  }, [token]);

  useEffect(() => {
    load();
    loadProfile();
  }, [load, loadProfile]);

  // Month change resets day/permission filters (scoped to the visible period).
  useEffect(() => {
    setDaySearch('');
    setDayStatus('');
    setDayOvertime('');
    setShowDayFilters(false);
    setPermSearch('');
    setPermStatus('');
    setShowPermFilters(false);
  }, [monthKey]);

  const months = useMemo(
    () => collectAttendanceMonths(records, permissions, nowKey),
    [records, permissions, nowKey],
  );

  const monthIndex = Math.max(0, months.indexOf(monthKey));
  const { start: monthStart, end: monthEnd } = useMemo(() => monthBounds(monthKey), [monthKey]);

  const monthRecords = useMemo(
    () => records
      .filter((r) => {
        const d = String(r.date || '').slice(0, 10);
        return d >= monthStart && d <= monthEnd;
      })
      .sort((a, b) => String(b.date).localeCompare(String(a.date))),
    [records, monthStart, monthEnd],
  );

  const filteredMonthRecords = useMemo(() => {
    const q = daySearch.trim().toLowerCase();
    return monthRecords.filter((row) => {
      if (dayStatus && row.status !== dayStatus) return false;
      const ot = Number(row.overtime_hours) || 0;
      if (dayOvertime === 'yes' && ot <= 0) return false;
      if (dayOvertime === 'no' && ot > 0) return false;
      if (!q) return true;
      const statusLabel = t(`attendanceStatus.${row.status}`, { defaultValue: row.status || '' });
      const hay = [
        row.date,
        formatDay(row.date, locale),
        row.status,
        statusLabel,
        row.hours_worked,
        row.overtime_hours,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  }, [monthRecords, daySearch, dayStatus, dayOvertime, t, locale]);

  const monthPermissions = useMemo(
    () => permissions.filter((r) => {
      const d = String(r.date || '').slice(0, 10);
      return d >= monthStart && d <= monthEnd;
    }),
    [permissions, monthStart, monthEnd],
  );

  const filteredMonthPermissions = useMemo(() => {
    const q = permSearch.trim().toLowerCase();
    return monthPermissions.filter((row) => {
      const st = row.status || (row.approved ? 'approved' : 'pending');
      if (permStatus && st !== permStatus) return false;
      if (!q) return true;
      const type = row.permission_type;
      const typeText = typeof type === 'object'
        ? `${type.label || ''} ${type.code || ''}`
        : String(type || '');
      const hay = [row.date, formatDay(row.date, locale), typeText, st, row.hours, row.notes]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  }, [monthPermissions, permSearch, permStatus, locale]);

  const dayFilterActive = Boolean(daySearch || dayStatus || dayOvertime);
  const permFilterActive = Boolean(permSearch || permStatus);

  const statusOptions = useMemo(
    () => ['present', 'absent', 'leave', 'permission'].map((code) => ({
      value: code,
      label: t(`attendanceStatus.${code}`, { defaultValue: code }),
    })),
    [t],
  );

  const overtimeOptions = useMemo(
    () => [
      { value: 'yes', label: t('attendanceFilterOvertimeYes') },
      { value: 'no', label: t('attendanceFilterOvertimeNo') },
    ],
    [t],
  );

  const permStatusOptions = useMemo(
    () => [
      { value: 'pending', label: t('statusPending') },
      { value: 'approved', label: t('statusApproved') },
      { value: 'rejected', label: t('statusRejected') },
      { value: 'cancelled', label: t('statusCancelled') },
    ],
    [t],
  );

  const summary = useMemo(() => {
    const counts = { present: 0, absent: 0, leave: 0, permission: 0 };
    let hours = 0;
    let overtime = 0;
    for (const row of monthRecords) {
      const st = row.status || 'present';
      if (counts[st] != null) counts[st] += 1;
      hours += Number(row.hours_worked) || 0;
      overtime += Number(row.overtime_hours) || 0;
    }
    const pendingPerms = monthPermissions.filter(
      (p) => (p.status || (p.approved ? 'approved' : 'pending')) === 'pending',
    ).length;
    return { ...counts, hours, overtime, pendingPerms, days: monthRecords.length };
  }, [monthRecords, monthPermissions]);

  const handleSubmitted = useCallback(async () => {
    setDialogOpen(false);
    notify({ message: t('successSubmitted'), type: 'success' });
    await load();
  }, [load, notify, t]);

  const canOlder = monthIndex < months.length - 1;
  const canNewer = monthIndex > 0;

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
      data-testid="my-attendance"
    >
      <PageContainer>
        <PageHeader
          icon={AccessTimeIcon}
          title={t('attendanceTitle')}
          subtitle={t('attendanceSubtitleFull')}
          actions={
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setDialogOpen(true)}
            >
              {t('requestAttendanceButton')}
            </Button>
          }
        />

        {loading ? (
          <Stack spacing={1.5}>
            <Skeleton variant="rounded" height={48} />
            <Skeleton variant="rounded" height={88} />
            <Skeleton variant="rounded" height={220} />
          </Stack>
        ) : error ? (
          <Alert
            severity="error"
            action={(
              <Button color="inherit" size="small" onClick={load}>{t('retry')}</Button>
            )}
          >
            {error}
          </Alert>
        ) : (
          <Stack spacing={1.5}>
            <Paper
              variant="outlined"
              sx={{ px: 1, py: 0.75, display: 'flex', alignItems: 'center', gap: 1, borderRadius: 2 }}
              data-testid="attendance-month-nav"
            >
              <IconButton
                size="small"
                aria-label={t('attendancePrevMonth')}
                disabled={!canOlder}
                onClick={() => {
                  if (!canOlder) return;
                  setMonthKey(months[monthIndex + 1]);
                }}
                data-testid="attendance-month-prev"
              >
                <ChevronLeftIcon />
              </IconButton>
              <Box sx={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }} data-testid="attendance-month-label">
                  {formatMonthLabel(monthKey, locale)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('payslipMonthOf', { current: monthIndex + 1, total: Math.max(months.length, 1) })}
                  {` · ${monthStart} → ${monthEnd}`}
                </Typography>
              </Box>
              <IconButton
                size="small"
                aria-label={t('attendanceNextMonth')}
                disabled={!canNewer}
                onClick={() => {
                  if (!canNewer) return;
                  setMonthKey(months[monthIndex - 1]);
                }}
                data-testid="attendance-month-next"
              >
                <ChevronRightIcon />
              </IconButton>
            </Paper>

            <Typography variant="caption" color="text.secondary" sx={{ px: 0.25 }}>
              {t('attendanceHonesty')}
            </Typography>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              {[
                { label: t('attendanceStatPresent'), value: summary.present },
                { label: t('attendanceStatAbsent'), value: summary.absent },
                { label: t('attendanceStatHours'), value: formatHours(summary.hours) },
                { label: t('attendanceStatPendingPerms'), value: summary.pendingPerms },
              ].map((card) => (
                <Card key={card.label} variant="outlined" sx={{ flex: 1 }}>
                  <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {card.label}
                    </Typography>
                    <Typography variant="h6" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                      {card.value}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Stack>

            <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }} data-testid="attendance-records-table">
              <Box sx={{ px: 1.5, pt: 1.25, pb: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'text.secondary' }}>
                  {t('attendanceDaysTitle')}
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                  <TextField
                    size="small"
                    placeholder={t('attendanceSearchDays')}
                    value={daySearch}
                    onChange={(e) => setDaySearch(e.target.value)}
                    sx={{ flex: '1 1 200px', minWidth: 160 }}
                    inputProps={{ 'data-testid': 'attendance-day-search' }}
                    InputProps={{
                      startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary', fontSize: '1.125rem' }} />,
                    }}
                  />
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<TuneIcon />}
                    color={dayStatus || dayOvertime ? 'primary' : 'inherit'}
                    onClick={() => setShowDayFilters((v) => !v)}
                    data-testid="attendance-day-filters-toggle"
                  >
                    {t('filters', { ns: 'common', defaultValue: 'Filters' })}
                    {(dayStatus || dayOvertime) ? ` (${[dayStatus, dayOvertime].filter(Boolean).length})` : ''}
                  </Button>
                  {dayStatus ? (
                    <Chip
                      size="small"
                      color="primary"
                      variant="outlined"
                      label={t(`attendanceStatus.${dayStatus}`, { defaultValue: dayStatus })}
                      onDelete={() => setDayStatus('')}
                    />
                  ) : null}
                  {dayOvertime ? (
                    <Chip
                      size="small"
                      color="primary"
                      variant="outlined"
                      label={dayOvertime === 'yes' ? t('attendanceFilterOvertimeYes') : t('attendanceFilterOvertimeNo')}
                      onDelete={() => setDayOvertime('')}
                    />
                  ) : null}
                  {dayFilterActive ? (
                    <Button
                      size="small"
                      onClick={() => {
                        setDaySearch('');
                        setDayStatus('');
                        setDayOvertime('');
                      }}
                    >
                      {t('clearFilters', { defaultValue: 'Clear' })}
                    </Button>
                  ) : null}
                </Stack>
                {showDayFilters ? (
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 1.5 }}>
                    <Box sx={{ flex: 1, minWidth: 160 }}>
                      <SearchSelect
                        options={[
                          { value: '', label: t('filterAll') },
                          ...statusOptions,
                        ]}
                        valueKey="value"
                        labelKey="label"
                        label={t('filterStatus')}
                        value={dayStatus}
                        onChange={(v) => setDayStatus(v?.value ?? '')}
                        clearable={false}
                        size="small"
                      />
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 160 }}>
                      <SearchSelect
                        options={[
                          { value: '', label: t('filterAll') },
                          ...overtimeOptions,
                        ]}
                        valueKey="value"
                        labelKey="label"
                        label={t('attendanceFilterOvertime')}
                        value={dayOvertime}
                        onChange={(v) => setDayOvertime(v?.value ?? '')}
                        clearable={false}
                        size="small"
                      />
                    </Box>
                  </Stack>
                ) : null}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  {t('attendanceDaysCount', {
                    shown: filteredMonthRecords.length,
                    total: monthRecords.length,
                  })}
                </Typography>
              </Box>
              {monthRecords.length === 0 ? (
                <Box sx={{ px: 1.5, pb: 1.5 }}>
                  <EmptyState title={t('attendanceDaysEmpty')} description={t('attendanceDaysEmptyDesc')} />
                </Box>
              ) : filteredMonthRecords.length === 0 ? (
                <Box sx={{ px: 1.5, pb: 1.5 }}>
                  <EmptyState title={t('attendanceDaysNoMatch')} description={t('attendanceDaysNoMatchDesc')} />
                </Box>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>{t('historyDate')}</TableCell>
                        <TableCell>{t('historyStatus')}</TableCell>
                        <TableCell align="right">{t('attendanceHoursWorked')}</TableCell>
                        <TableCell align="right">{t('attendanceOvertime')}</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredMonthRecords.map((row) => (
                        <TableRow key={row.id} hover>
                          <TableCell>{formatDay(row.date, locale)}</TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              color={statusColor(row.status)}
                              label={t(`attendanceStatus.${row.status}`, { defaultValue: row.status })}
                            />
                          </TableCell>
                          <TableCell align="right" dir="ltr" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                            {formatHours(row.hours_worked)}
                          </TableCell>
                          <TableCell align="right" dir="ltr" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                            {formatHours(row.overtime_hours)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>

            <Box>
              <Paper variant="outlined" sx={{ borderRadius: 2, p: 1.5, mb: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <TextField
                    size="small"
                    placeholder={t('attendanceSearchPerms')}
                    value={permSearch}
                    onChange={(e) => setPermSearch(e.target.value)}
                    sx={{ flex: '1 1 200px', minWidth: 160 }}
                    inputProps={{ 'data-testid': 'attendance-perm-search' }}
                    InputProps={{
                      startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary', fontSize: '1.125rem' }} />,
                    }}
                  />
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<TuneIcon />}
                    color={permStatus ? 'primary' : 'inherit'}
                    onClick={() => setShowPermFilters((v) => !v)}
                  >
                    {t('filters', { ns: 'common', defaultValue: 'Filters' })}
                    {permStatus ? ' (1)' : ''}
                  </Button>
                  {permStatus ? (
                    <Chip
                      size="small"
                      color="primary"
                      variant="outlined"
                      label={permStatus}
                      onDelete={() => setPermStatus('')}
                      sx={{ textTransform: 'capitalize' }}
                    />
                  ) : null}
                  {permFilterActive ? (
                    <Button size="small" onClick={() => { setPermSearch(''); setPermStatus(''); }}>
                      {t('clearFilters', { defaultValue: 'Clear' })}
                    </Button>
                  ) : null}
                </Stack>
                {showPermFilters ? (
                  <Box sx={{ mt: 1.5, maxWidth: 280 }}>
                    <SearchSelect
                      options={[
                        { value: '', label: t('filterAll') },
                        ...permStatusOptions,
                      ]}
                      valueKey="value"
                      labelKey="label"
                      label={t('filterStatus')}
                      value={permStatus}
                      onChange={(v) => setPermStatus(v?.value ?? '')}
                      clearable={false}
                      size="small"
                    />
                  </Box>
                ) : null}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  {t('attendancePermsCount', {
                    shown: filteredMonthPermissions.length,
                    total: monthPermissions.length,
                  })}
                </Typography>
              </Paper>
              <AttendanceHistoryTable
                records={filteredMonthPermissions}
                loading={false}
                error={null}
                onRetry={load}
              />
            </Box>
          </Stack>
        )}
      </PageContainer>

      <RequestAttendanceDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        profile={profile}
        onSubmitted={handleSubmitted}
      />
    </Box>
  );
}
