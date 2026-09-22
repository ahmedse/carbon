// src/apps/my/components/RequestDetail.jsx
// My (employee self-service) — Request detail page (route /my/requests/:id).
// Layout: Summary → Stepper|Graph toggle → Timeline.
// Graph = WorkflowGraph → EnterpriseGraph (same Pulse agent canvas).

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Skeleton, Stack, ToggleButton, ToggleButtonGroup } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
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
  resubmitCorrespondence,
} from '../../../api/my';
import SummaryCard from './SummaryCard';
import ApproverChainStepper from './ApproverChainStepper';
import WorkflowGraph from './WorkflowGraph';
import RequestTimeline from './RequestTimeline';

const CANCELLABLE = new Set(['draft', 'submitted', 'in_review', 'sent_back']);

export default function RequestDetail() {
  const { t } = useTranslation('my');
  const theme = useTheme();
  const isRtl = theme.direction === 'rtl';
  const { token } = useAuth();
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

  const canCancel = data && CANCELLABLE.has(data.status);
  const canResubmit = data && data.status === 'sent_back';

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
            <Stack direction="row" spacing={1}>
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
    </Box>
  );
}
