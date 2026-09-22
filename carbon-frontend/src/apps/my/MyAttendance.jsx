// src/apps/my/MyAttendance.jsx
// Employee self-service — short-hours attendance permissions (route /my/attendance).

import React, { useCallback, useEffect, useState } from 'react';
import { Box, Button, Stack } from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { fetchMyAttendancePermissions, fetchMyProfile } from '../../api/my';
import AttendanceHistoryTable from './components/AttendanceHistoryTable';
import RequestAttendanceDialog from './components/RequestAttendanceDialog';

export default function MyAttendance() {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const { notify } = useNotification();
  useDocumentTitle(t('attendanceTitle'));

  const [profile, setProfile] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMyAttendancePermissions(token);
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  const loadProfile = useCallback(async () => {
    try {
      setProfile(await fetchMyProfile(token));
    } catch {
      setProfile(null);
    }
  }, [token]);

  useEffect(() => {
    loadRows();
    loadProfile();
  }, [loadRows, loadProfile]);

  const handleSubmitted = useCallback(async () => {
    setDialogOpen(false);
    notify({ message: t('successSubmitted'), type: 'success' });
    await loadRows();
  }, [loadRows, notify, t]);

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader
          icon={AccessTimeIcon}
          title={t('attendanceTitle')}
          subtitle={t('attendanceSubtitle')}
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
        <Stack spacing={1}>
          <AttendanceHistoryTable
            records={rows}
            loading={loading}
            error={error}
            onRetry={loadRows}
          />
        </Stack>
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
