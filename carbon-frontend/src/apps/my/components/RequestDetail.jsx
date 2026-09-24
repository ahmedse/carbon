// src/apps/my/components/RequestDetail.jsx
// My (employee self-service) — Request detail page (route /my/requests/:id).
// Layout: Summary → Stepper|Graph toggle → Timeline.
// Graph = WorkflowGraph → EnterpriseGraph (same Pulse agent canvas).
// sent_back: Edit payload (typed SystemDialog) then Resubmit — separate actions.

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Skeleton, Stack, ToggleButton, ToggleButtonGroup } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import {
  cancelCorrespondence,
  fetchCorrespondenceDetail,
  fetchLeaveBalance,
  fetchMyProfile,
  resubmitCorrespondence,
} from '../../../api/my';
import SummaryCard from './SummaryCard';
import ApproverChainStepper from './ApproverChainStepper';
import WorkflowGraph from './WorkflowGraph';
import RequestTimeline from './RequestTimeline';
import RequestLeaveDialog from './RequestLeaveDialog';
import RequestLoanDialog from './RequestLoanDialog';
import RequestAttendanceDialog from './RequestAttendanceDialog';
import RequestProfileChangeDialog from './RequestProfileChangeDialog';
import RequestMemoDialog from './RequestMemoDialog';

const CANCELLABLE = new Set(['draft', 'submitted', 'in_review', 'sent_back']);

function resolveEditKind(data) {
  if (!data) return null;
  const code = data.corr_type_code || '';
  const subject = data.subject_type || '';
  if (code === 'leave_request' || subject === 'people.LeaveRecord') return 'leave';
  if (code === 'loan_request' || subject === 'people.Loan') return 'loan';
  if (code === 'attendance_permission' || subject === 'people.AttendancePermission') {
    return 'attendance';
  }
  if (code === 'profile_change' || subject === 'people.Employee') return 'profile';
  if (code === 'internal_memo' || code === 'circular' || code === 'decision') {
    return 'memo';
  }
  return null;
}

export default function RequestDetail() {
  const { t } = useTranslation('my');
  const theme = useTheme();
  const isRtl = theme.direction === 'rtl';
  const { token, user } = useAuth();
  const { notify } = useNotification();
  const { id } = useParams();
  const navigate = useNavigate();
  useDocumentTitle(t('detailTitle'));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [view, setView] = useState('graph');
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [balances, setBalances] = useState([]);
  const [profile, setProfile] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      setData(await fetchCorrespondenceDetail(token, id));
    } catch (err) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setError(err?.message || t('error'));
      }
    } finally {
      setLoading(false);
    }
  }, [token, id, t]);

  useEffect(() => {
    load();
  }, [load]);

  const editKind = resolveEditKind(data);
  // Cancel / resubmit / edit are requester-only (backend FSM + permission).
  // Approvers and correspondence:admin can still *view* the detail.
  const isRequester =
    data != null
    && user?.id != null
    && Number(data.requester) === Number(user.id);
  const canCancel = Boolean(isRequester && CANCELLABLE.has(data.status));
  const canResubmit = Boolean(isRequester && data.status === 'sent_back');
  const canEdit = Boolean(canResubmit && editKind);

  const openEdit = useCallback(async () => {
    setEditOpen(true);
    if (editKind !== 'leave' && editKind !== 'attendance') return;
    try {
      const tasks = [fetchMyProfile(token)];
      if (editKind === 'leave') tasks.unshift(fetchLeaveBalance(token));
      const results = await Promise.all(tasks);
      if (editKind === 'leave') {
        setBalances(Array.isArray(results[0]) ? results[0] : []);
        setProfile(results[1] || null);
      } else {
        setProfile(results[0] || null);
      }
    } catch {
      setBalances([]);
    }
  }, [token, editKind]);

  const handleCancel = useCallback(async () => {
    if (!window.confirm(t('cancelRequestConfirm'))) return;
    setBusy(true);
    try {
      await cancelCorrespondence(token, id);
      notify({ message: t('successCancelled'), type: 'success' });
      await load();
    } catch (err) {
      notify({ message: err?.message || t('error'), type: 'error' });
    } finally {
      setBusy(false);
    }
  }, [token, id, t, notify, load]);

  const handleResubmit = useCallback(async () => {
    if (!window.confirm(t('resubmitRequestConfirm'))) return;
    setBusy(true);
    try {
      await resubmitCorrespondence(token, id);
      notify({ message: t('successResubmitted'), type: 'success' });
      await load();
    } catch (err) {
      notify({ message: err?.message || t('error'), type: 'error' });
    } finally {
      setBusy(false);
    }
  }, [token, id, t, notify, load]);

  const handleEdited = useCallback(async () => {
    setEditOpen(false);
    notify({ message: t('successEdited'), type: 'success' });
    await load();
  }, [notify, t, load]);

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader
          title={t('detailTitle')}
          subtitle={t('detailSubtitle')}
          actions={
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              {canEdit ? (
                <Button
                  size="small"
                  variant="outlined"
                  color="primary"
                  startIcon={<EditIcon />}
                  disabled={busy}
                  onClick={openEdit}
                >
                  {t('editRequest')}
                </Button>
              ) : null}
              {canResubmit ? (
                <Button
                  size="small"
                  variant="contained"
                  color="primary"
                  disabled={busy}
                  onClick={handleResubmit}
                >
                  {t('resubmitRequest')}
                </Button>
              ) : null}
              {canCancel ? (
                <Button
                  size="small"
                  variant="outlined"
                  color="warning"
                  disabled={busy}
                  onClick={handleCancel}
                >
                  {t('cancelRequest')}
                </Button>
              ) : null}
              <Button
                size="small"
                variant="outlined"
                startIcon={
                  <ArrowBackIcon sx={isRtl ? { transform: 'scaleX(-1)' } : undefined} />
                }
                onClick={() => navigate('/my/requests')}
              >
                {t('backToRequests')}
              </Button>
            </Stack>
          }
        />
        {loading ? (
          <Stack spacing={1} aria-label={t('loading')}>
            <Skeleton variant="rounded" height={120} />
            <Skeleton variant="rounded" height={120} />
            <Skeleton variant="rounded" height={120} />
          </Stack>
        ) : notFound ? (
          <Alert
            severity="warning"
            action={
              <Button color="inherit" size="small" onClick={() => navigate('/my/requests')}>
                {t('backToRequests')}
              </Button>
            }
          >
            {t('detailNotFound')}
          </Alert>
        ) : error ? (
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={load}>
                {t('retry')}
              </Button>
            }
          >
            {error}
          </Alert>
        ) : data ? (
          <Stack spacing={1}>
            {canResubmit ? (
              <Alert severity="warning">
                {t('sentBackHint')}
              </Alert>
            ) : null}
            <SummaryCard item={data} />
            <Stack direction="row" justifyContent="flex-end">
              <ToggleButtonGroup
                value={view}
                exclusive
                size="small"
                onChange={(event, next) => {
                  if (next !== null) setView(next);
                }}
                aria-label={t('viewToggleLabel')}
              >
                <ToggleButton value="stepper">{t('workflowStepper')}</ToggleButton>
                <ToggleButton value="graph">{t('workflowGraph')}</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
            {view === 'stepper' ? (
              <ApproverChainStepper
                chain={data.approver_chain}
                currentStep={data.current_step}
                status={data.status}
              />
            ) : (
              <WorkflowGraph
                chain={data.approver_chain}
                currentStep={data.current_step}
                status={data.status}
              />
            )}
            <RequestTimeline events={data.events} />
          </Stack>
        ) : null}
      </PageContainer>

      {canEdit && editKind === 'leave' ? (
        <RequestLeaveDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          balances={balances}
          profile={profile}
          mode="edit"
          correspondenceId={data?.id}
          initialPayload={data?.payload}
          onSubmitted={handleEdited}
        />
      ) : null}
      {canEdit && editKind === 'loan' ? (
        <RequestLoanDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          mode="edit"
          correspondenceId={data?.id}
          initialPayload={data?.payload}
          onSubmitted={handleEdited}
        />
      ) : null}
      {canEdit && editKind === 'attendance' ? (
        <RequestAttendanceDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          profile={profile}
          mode="edit"
          correspondenceId={data?.id}
          initialPayload={data?.payload}
          onSubmitted={handleEdited}
        />
      ) : null}
      {canEdit && editKind === 'profile' ? (
        <RequestProfileChangeDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          correspondenceId={data?.id}
          initialPayload={data?.payload}
          onSubmitted={handleEdited}
        />
      ) : null}
      {canEdit && editKind === 'memo' ? (
        <RequestMemoDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          correspondenceId={data?.id}
          initialTitle={data?.title}
          initialPayload={data?.payload}
          corrTypeCode={data?.corr_type_code}
          onSubmitted={handleEdited}
        />
      ) : null}
    </Box>
  );
}
