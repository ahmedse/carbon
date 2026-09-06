// src/apps/team/TeamRequestDetail.jsx
// Team (manager approvals inbox) — Approval detail page (route /team/:id).
// Fetches a single correspondence record (events + approver chain), reuses the
// my-app SummaryCard / ApproverChainStepper / RequestTimeline, and adds the
// manager act bar (approve / reject / send back). Reject and send-back require
// a non-empty comment (client-side validation + localized inline error).

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import UndoIcon from '@mui/icons-material/Undo';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchCorrespondenceDetail,
  approveCorrespondence,
  rejectCorrespondence,
  sendBackCorrespondence,
} from '../../api/team';
import { SectionTitle } from '../my/components/myRequestsCommon';
import SummaryCard from '../my/components/SummaryCard';
import ApproverChainStepper from '../my/components/ApproverChainStepper';
import WorkflowGraph from '../my/components/WorkflowGraph';
import RequestTimeline from '../my/components/RequestTimeline';

/** Pull a human-readable message out of an apiFetch-thrown error. */
function extractErrorMessage(err, fallback) {
  if (!err) return fallback;
  const candidates = [
    err?.message,
    err?.feedback?.detail,
    err?.data?.detail,
    err?.data?.message,
    err?.data?.error,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate;
  }
  return fallback;
}

export default function TeamRequestDetail() {
  const { t } = useTranslation('team');
  const { token } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const { notify } = useNotification();
  useDocumentTitle(t('detailTitle'));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

  const [comment, setComment] = useState('');
  const [validation, setValidation] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [view, setView] = useState('stepper');

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

  const handleCommentChange = useCallback((event) => {
    setComment(event.target.value);
    setValidation(null);
  }, []);

  const handleAction = useCallback(
    async (action) => {
      const trimmed = comment.trim();
      if ((action === 'reject' || action === 'sendBack') && !trimmed) {
        setValidation(t('commentRequired'));
        return;
      }
      setValidation(null);
      setSubmitting(true);
      try {
        if (action === 'approve') {
          await approveCorrespondence(token, id, { comment: trimmed || '' });
          notify({ message: t('successApproved'), type: 'success' });
        } else if (action === 'reject') {
          await rejectCorrespondence(token, id, { comment: trimmed });
          notify({ message: t('successRejected'), type: 'success' });
        } else {
          await sendBackCorrespondence(token, id, { comment: trimmed });
          notify({ message: t('successSentBack'), type: 'success' });
        }
        navigate('/team');
      } catch (err) {
        notify({ message: extractErrorMessage(err, t('error')), type: 'error' });
      } finally {
        setSubmitting(false);
      }
    },
    [comment, token, id, t, notify, navigate],
  );

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
              onClick={() => navigate('/team')}
            >
              {t('backToInbox')}
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
              <Button color="inherit" size="small" onClick={() => navigate('/team')}>
                {t('backToInbox')}
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
              <ApproverChainStepper chain={data.approver_chain} currentStep={data.current_step} />
            ) : (
              <WorkflowGraph chain={data.approver_chain} currentStep={data.current_step} status={data.status} />
            )}
            <RequestTimeline events={data.events} />

            {/* Manager act bar — approve / reject / send back */}
            <Card variant="outlined">
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <SectionTitle icon={HowToVoteIcon} title={t('actionsTitle')} />
                <TextField
                  fullWidth
                  size="small"
                  multiline
                  minRows={2}
                  maxRows={4}
                  value={comment}
                  onChange={handleCommentChange}
                  label={t('commentLabel')}
                  placeholder={t('commentPlaceholder')}
                  error={Boolean(validation)}
                  helperText={validation || undefined}
                  sx={{ mb: 1 }}
                />
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<CheckIcon />}
                    disabled={submitting}
                    onClick={() => handleAction('approve')}
                  >
                    {t('approve')}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<CloseIcon />}
                    disabled={submitting}
                    onClick={() => handleAction('reject')}
                  >
                    {t('reject')}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    startIcon={<UndoIcon />}
                    disabled={submitting}
                    onClick={() => handleAction('sendBack')}
                  >
                    {t('sendBack')}
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          </Stack>
        ) : null}
      </PageContainer>
    </Box>
  );
}
