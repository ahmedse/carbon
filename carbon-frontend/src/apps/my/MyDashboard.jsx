// src/apps/my/MyDashboard.jsx
// My (employee self-service) landing surface.
// Loads the profile, leave balance, and inbox count in PARALLEL with
// independent per-card loading / error / empty states. Semantic <main>.
// All strings via useTranslation('my'); all colors via theme tokens.

import React, { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
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
import DashboardIcon from '@mui/icons-material/Dashboard';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import AssignmentIcon from '@mui/icons-material/Assignment';
import ArticleIcon from '@mui/icons-material/Article';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import ResponsiveList from '../../components/layout/ResponsiveList';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchMyProfile, fetchLeaveBalance, fetchInboxCount, fetchMyPayslips, fetchMyLoans } from '../../api/my';
import { FONT } from '../../theme/themeTokens';
import MyLoansCard from './components/MyLoansCard';

const NewRequestDialog = lazy(() => import('./components/NewRequestDialog'));

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

function Field({ label, value }) {
  const { t } = useTranslation('my');
  return (
    <Stack sx={{ minWidth: 120 }}>
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
      <Typography sx={{ ...FONT.body2 }}>{value || t('profileNotAvailable')}</Typography>
    </Stack>
  );
}

// ── Card: identity strip (GET people/me/) ─────────────────────────────

function ProfileHeader({ profile, loading, error, onRetry }) {
  const { t } = useTranslation('my');

  if (loading) {
    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }} aria-label={t('loading')}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Skeleton variant="circular" width={40} height={40} />
            <Stack spacing={0.5} sx={{ flex: 1 }}>
              <Skeleton width="45%" />
              <Skeleton width="30%" />
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <InlineError message={error} onRetry={onRetry} />
        </CardContent>
      </Card>
    );
  }

  if (!profile) return null;

  const initials = (profile.full_name || '')
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccountCircleIcon} title={t('profileTitle')} />
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Avatar sx={{ bgcolor: 'primary.main', width: 40, height: 40, fontSize: '0.875rem' }}>
            {initials || '?'}
          </Avatar>
          <Stack spacing={0.25} sx={{ minWidth: 0 }}>
            <Typography noWrap sx={{ ...FONT.heading }}>
              {profile.full_name || t('profileNotAvailable')}
            </Typography>
            <Typography noWrap sx={{ ...FONT.body, color: 'text.secondary' }}>
              {profile.job_title || t('profileNotAvailable')}
            </Typography>
          </Stack>
        </Stack>
        <Divider sx={{ my: 1 }} />
        <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" rowGap={1}>
          <Field label={t('profileEmployeeNo')} value={profile.employee_no} />
          <Field label={t('profileJobTitle')} value={profile.job_title} />
          <Field label={t('profileOrgUnit')} value={profile.org_unit?.name} />
          <Field label={t('profileManager')} value={profile.manager?.name} />
        </Stack>
      </CardContent>
    </Card>
  );
}

// ── Card: action-required strip (pending inbox count) ─────────────────

function ActionRequiredStrip({ count, loading, error, onRetry }) {
  const { t } = useTranslation('my');

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={NotificationsActiveIcon} title={t('actionRequiredTitle')} />
        {loading ? (
          <Skeleton width="40%" aria-label={t('loading')} />
        ) : error ? (
          <InlineError message={error} onRetry={onRetry} />
        ) : count > 0 ? (
          <Stack direction="row" alignItems="center" spacing={1}>
            <Chip size="small" color="warning" label={String(count)} />
            <Typography sx={{ ...FONT.body2 }}>
              {t('actionRequiredPending', { count })}
            </Typography>
          </Stack>
        ) : (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('actionRequiredEmpty')}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

// ── Card: leave balance (GET people/me/leave-balance/) ────────────────

function LeaveBalanceCard({ balances, loading, error, onRetry }) {
  const { t } = useTranslation('my');

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
          <ResponsiveList
            items={balances}
            getKey={(balance) => balance.leave_type || String(balance.id ?? balance.entitled)}
            emptyLabel={t('leaveBalanceEmpty')}
            renderCard={(balance) => ({
              title: balance.leave_type
                ? t(`leaveType.${balance.leave_type}`, { defaultValue: balance.leave_type })
                : t('profileNotAvailable'),
              meta: `${t('leaveBalanceRemaining')}: ${balance.remaining ?? 0}`,
              status: String(balance.remaining ?? 0),
              statusColor: (balance.remaining ?? 0) > 0 ? 'success' : 'default',
            })}
            table={
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('leaveBalanceLeaveType')}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('leaveBalanceEntitled')}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('leaveBalanceUsed')}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('leaveBalancePending')}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('leaveBalanceRemaining')}
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {balances.map((balance, index) => {
                      const pending = balance.pending ?? 0;
                      const remaining = balance.remaining ?? 0;
                      const hasPending = pending > 0;
                      const hasRemaining = remaining > 0;
                      return (
                        <TableRow key={`${balance.leave_type}-${index}`} hover>
                          <TableCell sx={{ ...FONT.body2 }}>
                            {balance.leave_type
                              ? t(`leaveType.${balance.leave_type}`, { defaultValue: balance.leave_type })
                              : t('profileNotAvailable')}
                          </TableCell>
                          <TableCell align="right" sx={{ ...FONT.body2 }}>
                            {balance.entitled ?? 0}
                          </TableCell>
                          <TableCell align="right" sx={{ ...FONT.body2 }}>
                            {balance.used ?? 0}
                          </TableCell>
                          <TableCell align="right" sx={{ ...FONT.body2 }}>
                            {/* Text label (value) + status color — color is NOT the sole indicator */}
                            <Stack
                              direction="row"
                              alignItems="center"
                              justifyContent="flex-end"
                              spacing={0.5}
                            >
                              {hasPending && (
                                <Box
                                  sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: '50%',
                                    bgcolor: 'warning.main',
                                    flexShrink: 0,
                                  }}
                                />
                              )}
                              <Typography
                                sx={{
                                  ...FONT.body2,
                                  color: hasPending ? 'warning.main' : 'text.secondary',
                                }}
                              >
                                {pending}
                              </Typography>
                            </Stack>
                          </TableCell>
                          <TableCell align="right" sx={{ ...FONT.body2 }}>
                            <Stack
                              direction="row"
                              alignItems="center"
                              justifyContent="flex-end"
                              spacing={0.5}
                            >
                              <Typography
                                sx={{
                                  ...FONT.body2,
                                  fontWeight: 600,
                                  color: hasRemaining ? 'success.main' : 'text.primary',
                                }}
                              >
                                {remaining}
                              </Typography>
                            </Stack>
                          </TableCell>
                        </TableRow>
                      );
                    })}
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

// ── Card: payslips (GET people/me/payslips/) ──────────────────────────

const PAYSLIP_LINE_LABEL_KEYS = {
  gross: 'payslipLineGross',
  gosi: 'payslipLineGosi',
  net: 'payslipLineNet',
};

function payslipLineLabel(lineType, t) {
  const key = PAYSLIP_LINE_LABEL_KEYS[String(lineType || '').toLowerCase()];
  if (key) return t(key);
  return String(lineType || '').replace(/_/g, ' ') || '—';
}

function formatPayslipAmount(amount) {
  const value = Number(amount);
  if (Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function PayslipsCard({ payslips, loading, error, onRetry }) {
  const { t } = useTranslation('my');

  if (loading) {
    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={ReceiptLongIcon} title={t('payslipsTitle')} />
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
            <Skeleton width="85%" />
          </Stack>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={ReceiptLongIcon} title={t('payslipsTitle')} />
          <InlineError message={error} onRetry={onRetry} />
        </CardContent>
      </Card>
    );
  }

  if (payslips.length === 0) {
    return (
      <Card variant="outlined">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={ReceiptLongIcon} title={t('payslipsTitle')} />
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('payslipsEmpty')}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Group lines by payroll_run id (newest run first).
  const runs = [];
  const runsById = new Map();
  for (const line of payslips) {
    const runId = line.payroll_run ?? '—';
    let group = runsById.get(runId);
    if (!group) {
      group = { id: runId, lines: [] };
      runsById.set(runId, group);
      runs.push(group);
    }
    group.lines.push(line);
  }
  runs.sort((a, b) => Number(b.id) - Number(a.id));

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={ReceiptLongIcon} title={t('payslipsTitle')} />
        <Stack spacing={1.5}>
          {runs.map((run) => (
            <Stack key={String(run.id)} spacing={0.5}>
              <Typography sx={{ ...FONT.body, fontWeight: 600 }}>
                {t('payslipRunLabel', { id: run.id })}
              </Typography>
              <ResponsiveList
                items={run.lines}
                getKey={(line) => line.id}
                renderCard={(line) => ({
                  title: payslipLineLabel(line.line_type, t),
                  meta: formatPayslipAmount(line.amount),
                })}
                table={
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                            {t('payslipLineType')}
                          </TableCell>
                          <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                            {t('payslipAmount')}
                          </TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {run.lines.map((line) => (
                          <TableRow key={line.id} hover>
                            <TableCell sx={{ ...FONT.body2 }}>
                              {payslipLineLabel(line.line_type, t)}
                            </TableCell>
                            <TableCell
                              align="right"
                              sx={{ ...FONT.body2, fontVariantNumeric: 'tabular-nums' }}
                              dir="ltr"
                            >
                              {formatPayslipAmount(line.amount)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                }
              />
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

// ── Card: quick actions ───────────────────────────────────────────────

function QuickActions({ onNewRequest }) {
  const { t } = useTranslation('my');
  const navigate = useNavigate();

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={DashboardIcon} title={t('quickActionsTitle')} />
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          <Button
            size="small"
            variant="contained"
            startIcon={<AddIcon />}
            onClick={onNewRequest}
          >
            {t('quickActionsNewRequest')}
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<AssignmentIcon />}
            onClick={() => navigate('/my/leave')}
          >
            {t('quickActionsRequestLeave')}
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<ArticleIcon />}
            onClick={() => navigate('/my/requests')}
          >
            {t('quickActionsMyRequests')}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

export default function MyDashboard() {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const navigate = useNavigate();
  const { notify } = useNotification();
  useDocumentTitle(t('dashboardTitle'));

  const [dialogOpen, setDialogOpen] = useState(false);

  // Independent state per card → independent loading / error / empty states.
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState(null);

  const [balances, setBalances] = useState([]);
  const [balancesLoading, setBalancesLoading] = useState(true);
  const [balancesError, setBalancesError] = useState(null);

  const [inboxCount, setInboxCount] = useState(0);
  const [inboxLoading, setInboxLoading] = useState(true);
  const [inboxError, setInboxError] = useState(null);

  const [payslips, setPayslips] = useState([]);
  const [payslipsLoading, setPayslipsLoading] = useState(true);
  const [payslipsError, setPayslipsError] = useState(null);

  const [loans, setLoans] = useState([]);
  const [loansLoading, setLoansLoading] = useState(true);
  const [loansError, setLoansError] = useState(null);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      setProfile(await fetchMyProfile(token));
    } catch (err) {
      setProfileError(err?.message || t('error'));
    } finally {
      setProfileLoading(false);
    }
  }, [token, t]);

  const loadBalances = useCallback(async () => {
    setBalancesLoading(true);
    setBalancesError(null);
    try {
      const data = await fetchLeaveBalance(token);
      setBalances(Array.isArray(data) ? data : []);
    } catch (err) {
      setBalancesError(err?.message || t('error'));
    } finally {
      setBalancesLoading(false);
    }
  }, [token, t]);

  const loadInbox = useCallback(async () => {
    setInboxLoading(true);
    setInboxError(null);
    try {
      setInboxCount(await fetchInboxCount(token));
    } catch (err) {
      setInboxError(err?.message || t('error'));
    } finally {
      setInboxLoading(false);
    }
  }, [token, t]);

  const loadPayslips = useCallback(async () => {
    setPayslipsLoading(true);
    setPayslipsError(null);
    try {
      const data = await fetchMyPayslips(token);
      setPayslips(Array.isArray(data) ? data : []);
    } catch (err) {
      setPayslipsError(err?.message || t('error'));
    } finally {
      setPayslipsLoading(false);
    }
  }, [token, t]);

  const loadLoans = useCallback(async () => {
    setLoansLoading(true);
    setLoansError(null);
    try {
      setLoans(await fetchMyLoans(token));
    } catch (err) {
      setLoansError(err?.message || t('error'));
    } finally {
      setLoansLoading(false);
    }
  }, [token, t]);

  // Fire the fetches in parallel.
  useEffect(() => {
    loadProfile();
    loadBalances();
    loadInbox();
    loadPayslips();
    loadLoans();
  }, [loadProfile, loadBalances, loadInbox, loadPayslips, loadLoans]);

  const handleNewRequestSubmitted = useCallback(() => {
    setDialogOpen(false);
    notify({ message: t('successRequestSubmitted'), type: 'success' });
    navigate('/my/requests');
  }, [notify, navigate, t]);

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader
          icon={DashboardIcon}
          title={t('dashboardTitle')}
          subtitle={t('dashboardSubtitle')}
        />
        <Stack spacing={1}>
          <ProfileHeader
            profile={profile}
            loading={profileLoading}
            error={profileError}
            onRetry={loadProfile}
          />
          <ActionRequiredStrip
            count={inboxCount}
            loading={inboxLoading}
            error={inboxError}
            onRetry={loadInbox}
          />
          <LeaveBalanceCard
            balances={balances}
            loading={balancesLoading}
            error={balancesError}
            onRetry={loadBalances}
          />
          <PayslipsCard
            payslips={payslips}
            loading={payslipsLoading}
            error={payslipsError}
            onRetry={loadPayslips}
          />
          <MyLoansCard
            loans={loans}
            loading={loansLoading}
            error={loansError}
            onRetry={loadLoans}
          />
          <QuickActions onNewRequest={() => setDialogOpen(true)} />
        </Stack>
      </PageContainer>

      <Suspense fallback={null}>
        <NewRequestDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          profile={profile}
          balances={balances}
          onSubmitted={handleNewRequestSubmitted}
        />
      </Suspense>
    </Box>
  );
}
