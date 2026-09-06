// src/apps/my/MyLeave.jsx
// My (employee self-service) — My Leave page (route /my/leave).
// Loads leave balance, profile (manager preview), and leave history in
// PARALLEL with independent per-section loading / error / empty states.
// The "Request Leave" dialog (SystemDialog) lives here; a successful submit
// closes it, shows a success snackbar, and refetches balance + history.

import React, { useCallback, useEffect, useState } from 'react';
import { Box, Button, Stack } from '@mui/material';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchMyProfile, fetchLeaveBalance, fetchMyLeave } from '../../api/my';
import LeaveBalanceCards from './components/LeaveBalanceCards';
import LeaveHistoryTable from './components/LeaveHistoryTable';
import RequestLeaveDialog from './components/RequestLeaveDialog';

export default function MyLeave() {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const { notify } = useNotification();
  useDocumentTitle(t('leaveTitle'));

  const [balances, setBalances] = useState([]);
  const [balancesLoading, setBalancesLoading] = useState(true);
  const [balancesError, setBalancesError] = useState(null);

  const [profile, setProfile] = useState(null);

  const [leave, setLeave] = useState([]);
  const [leaveLoading, setLeaveLoading] = useState(true);
  const [leaveError, setLeaveError] = useState(null);

  const [dialogOpen, setDialogOpen] = useState(false);

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

  const loadProfile = useCallback(async () => {
    try {
      setProfile(await fetchMyProfile(token));
    } catch {
      // Profile only powers the approver preview; the dialog falls back to a
      // generic "line manager" message when it is unavailable.
      setProfile(null);
    }
  }, [token]);

  const loadLeave = useCallback(async () => {
    setLeaveLoading(true);
    setLeaveError(null);
    try {
      const data = await fetchMyLeave(token);
      setLeave(Array.isArray(data) ? data : []);
    } catch (err) {
      setLeaveError(err?.message || t('error'));
    } finally {
      setLeaveLoading(false);
    }
  }, [token, t]);

  // Fire the three fetches in parallel.
  useEffect(() => {
    loadBalances();
    loadProfile();
    loadLeave();
  }, [loadBalances, loadProfile, loadLeave]);

  // On a successful submit: close, toast, and refetch balance + history.
  const handleSubmitted = useCallback(async () => {
    setDialogOpen(false);
    notify({ message: t('successSubmitted'), type: 'success' });
    await loadBalances();
    await loadLeave();
  }, [loadBalances, loadLeave, notify, t]);

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader
          icon={EventAvailableIcon}
          title={t('leaveTitle')}
          subtitle={t('leaveSubtitle')}
          actions={
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setDialogOpen(true)}
            >
              {t('requestLeaveButton')}
            </Button>
          }
        />
        <Stack spacing={1}>
          <LeaveBalanceCards
            balances={balances}
            loading={balancesLoading}
            error={balancesError}
            onRetry={loadBalances}
          />
          <LeaveHistoryTable
            records={leave}
            loading={leaveLoading}
            error={leaveError}
            onRetry={loadLeave}
          />
        </Stack>
      </PageContainer>

      <RequestLeaveDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        balances={balances}
        profile={profile}
        onSubmitted={handleSubmitted}
      />
    </Box>
  );
}
