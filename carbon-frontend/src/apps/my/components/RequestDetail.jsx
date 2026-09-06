// src/apps/my/components/RequestDetail.jsx
// My (employee self-service) — Request detail page (route /my/requests/:id).
// Fetches a single correspondence record (with events + approver chain) and
// composes SummaryCard + ApproverChainStepper + RequestTimeline. Handles the
// full state matrix: loading / 404 / error / loaded.

import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Skeleton, Stack } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useAuth } from '../../../auth/AuthContext';
import { fetchCorrespondenceDetail } from '../../../api/my';
import SummaryCard from './SummaryCard';
import ApproverChainStepper from './ApproverChainStepper';
import RequestTimeline from './RequestTimeline';

export default function RequestDetail() {
  const { t } = useTranslation('my');
  const { token } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  useDocumentTitle(t('detailTitle'));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

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
            <Button
              size="small"
              variant="outlined"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/my/requests')}
            >
              {t('backToRequests')}
            </Button>
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
            <ApproverChainStepper chain={data.approver_chain} currentStep={data.current_step} />
            <RequestTimeline events={data.events} />
          </Stack>
        ) : null}
      </PageContainer>
    </Box>
  );
}
