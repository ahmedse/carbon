// src/apps/team/TeamRequestDetail.jsx
// Team approval detail (/team/:id).
// Layout: Summary → Stepper|Graph → Timeline → act buttons.
// Act UX: SystemDialog (comment) + ConfirmDialog for destructive reject/send-back.
// No Card action bar. No Archive for managers (FSM: requester/admin only).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Skeleton,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import UndoIcon from '@mui/icons-material/Undo';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import SystemDialog from '../../components/SystemDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchCorrespondenceDetail,
  approveCorrespondence,
  acknowledgeCorrespondence,
  reviewCorrespondence,
  rejectCorrespondence,
  sendBackCorrespondence,
} from '../../api/team';
import { SectionTitle } from '../my/components/myRequestsCommon';
import SummaryCard from '../my/components/SummaryCard';
import ApproverChainStepper from '../my/components/ApproverChainStepper';
import WorkflowGraph from '../my/components/WorkflowGraph';
import RequestTimeline from '../my/components/RequestTimeline';

const ACTIONABLE = ['submitted', 'in_review'];

const POSITIVE_INTENTS = {
  approve: {
    api: approveCorrespondence,
    successKey: 'successApproved',
    labelKey: 'approve',
    icon: CheckIcon,
    color: 'success',
  },
  acknowledge: {
    api: acknowledgeCorrespondence,
    successKey: 'successAcknowledged',
    labelKey: 'acknowledge',
    icon: CheckIcon,
    color: 'success',
  },
  review: {
    api: reviewCorrespondence,
    successKey: 'successReviewed',
    labelKey: 'review',
    icon: CheckIcon,
    color: 'primary',
  },
};

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

function currentStepIntent(item) {
  const chain = item?.approver_chain;
  if (!Array.isArray(chain) || chain.length === 0) return 'approve';
  const step = chain[item.current_step];
  const intent = step?.intent;
  if (intent && POSITIVE_INTENTS[intent]) return intent;
  return 'approve';
}

export default function TeamRequestDetail() {
  const { t } = useTranslation('team');
  const theme = useTheme();
  const isRtl = theme.direction === 'rtl';
  const { token } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { notify } = useNotification();
  useDocumentTitle(t('detailTitle'));

  const fromHistory = location.state?.from === 'history';
  const backPath = fromHistory ? '/team/history' : '/team';
  const backLabel = fromHistory ? t('backToHistory') : t('backToInbox');

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [view, setView] = useState('graph');
  const [submitting, setSubmitting] = useState(false);

  /** @type {null | 'positive' | 'reject' | 'sendBack'} */
  const [dialogAction, setDialogAction] = useState(null);
  const [comment, setComment] = useState('');
  const [commentError, setCommentError] = useState(null);
  /** ConfirmDialog open after SystemDialog validates destructive act. */
  const [confirmDestructive, setConfirmDestructive] = useState(false);

  const isActionable = Boolean(data && ACTIONABLE.includes(data.status));
  const positiveIntent = useMemo(() => currentStepIntent(data), [data]);
  const positiveDef = POSITIVE_INTENTS[positiveIntent];

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

  const closeDialog = useCallback(() => {
    if (submitting) return;
    setDialogAction(null);
    setComment('');
    setCommentError(null);
    setConfirmDestructive(false);
  }, [submitting]);

  const openAction = useCallback((action) => {
    setComment('');
    setCommentError(null);
    setConfirmDestructive(false);
    setDialogAction(action);
  }, []);

  const runAction = useCallback(
    async (action, trimmedComment) => {
      setSubmitting(true);
      try {
        if (action === 'positive') {
          await positiveDef.api(token, id, { comment: trimmedComment || '' });
          notify({ message: t(positiveDef.successKey), type: 'success' });
        } else if (action === 'reject') {
          await rejectCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successRejected'), type: 'success' });
        } else if (action === 'sendBack') {
          await sendBackCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successSentBack'), type: 'success' });
        }
        navigate(fromHistory ? '/team/history' : '/team');
      } catch (err) {
        notify({ message: extractErrorMessage(err, t('error')), type: 'error' });
      } finally {
        setSubmitting(false);
        closeDialog();
      }
    },
    [positiveDef, token, id, t, notify, navigate, closeDialog, fromHistory],
  );

  const handleDialogPrimary = useCallback(() => {
    const trimmed = comment.trim();
    if (dialogAction === 'reject' || dialogAction === 'sendBack') {
      if (!trimmed) {
        setCommentError(t('commentRequired'));
        return;
      }
      setCommentError(null);
      setConfirmDestructive(true);
      return;
    }
    runAction('positive', trimmed);
  }, [comment, dialogAction, t, runAction]);

  const handleConfirmDestructive = useCallback(() => {
    const trimmed = comment.trim();
    if (!dialogAction || dialogAction === 'positive') return;
    runAction(dialogAction, trimmed);
  }, [comment, dialogAction, runAction]);

  const dialogTitle = useMemo(() => {
    if (dialogAction === 'reject') return t('rejectConfirmTitle');
    if (dialogAction === 'sendBack') return t('sendBackConfirmTitle');
    return t(positiveDef.labelKey);
  }, [dialogAction, t, positiveDef]);

  const dialogPrimaryLabel = useMemo(() => {
    if (dialogAction === 'reject') return t('reject');
    if (dialogAction === 'sendBack') return t('sendBack');
    return t(positiveDef.labelKey);
  }, [dialogAction, t, positiveDef]);

  const PositiveIcon = positiveDef.icon;

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
              startIcon={
                <ArrowBackIcon sx={isRtl ? { transform: 'scaleX(-1)' } : undefined} />
              }
              onClick={() => navigate(backPath)}
            >
              {backLabel}
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
              <Button color="inherit" size="small" onClick={() => navigate(backPath)}>
                {backLabel}
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
              <WorkflowGraph
                chain={data.approver_chain}
                currentStep={data.current_step}
                status={data.status}
              />
            )}
            <RequestTimeline events={data.events} />

            <Box sx={{ pt: 1 }}>
              <SectionTitle icon={HowToVoteIcon} title={t('actionsTitle')} />
              {!isActionable ? (
                <Typography variant="body2" color="text.secondary">
                  {t('actionsNotAvailable')}
                </Typography>
              ) : (
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1 }}>
                  <Button
                    size="small"
                    variant="contained"
                    color={positiveDef.color}
                    startIcon={<PositiveIcon />}
                    disabled={submitting}
                    onClick={() => openAction('positive')}
                  >
                    {t(positiveDef.labelKey)}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<CloseIcon />}
                    disabled={submitting}
                    onClick={() => openAction('reject')}
                  >
                    {t('reject')}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    startIcon={<UndoIcon />}
                    disabled={submitting}
                    onClick={() => openAction('sendBack')}
                  >
                    {t('sendBack')}
                  </Button>
                </Stack>
              )}
            </Box>
          </Stack>
        ) : null}
      </PageContainer>

      <SystemDialog
        open={Boolean(dialogAction) && !confirmDestructive}
        title={dialogTitle}
        onClose={closeDialog}
        onCancel={closeDialog}
        cancelLabel={t('cancel')}
        height={360}
        width={520}
        actions={
          <Button
            variant="contained"
            color={dialogAction === 'reject' ? 'error' : dialogAction === 'sendBack' ? 'warning' : positiveDef.color}
            onClick={handleDialogPrimary}
            disabled={submitting}
            startIcon={submitting ? <CircularProgress size={14} color="inherit" /> : null}
          >
            {dialogPrimaryLabel}
          </Button>
        }
      >
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <Typography variant="body2" color="text.secondary">
            {dialogAction === 'reject' || dialogAction === 'sendBack'
              ? t('actDialogDestructiveHint')
              : t('actDialogPositiveHint')}
          </Typography>
          <TextField
            fullWidth
            size="small"
            multiline
            minRows={3}
            maxRows={6}
            value={comment}
            onChange={(e) => {
              setComment(e.target.value);
              setCommentError(null);
            }}
            label={t('commentLabel')}
            placeholder={
              dialogAction === 'reject' || dialogAction === 'sendBack'
                ? t('commentRequiredPlaceholder')
                : t('commentPlaceholder')
            }
            required={dialogAction === 'reject' || dialogAction === 'sendBack'}
            error={Boolean(commentError)}
            helperText={commentError || undefined}
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={confirmDestructive}
        title={dialogAction === 'reject' ? t('rejectConfirmTitle') : t('sendBackConfirmTitle')}
        message={
          dialogAction === 'reject' ? t('rejectConfirmMessage') : t('sendBackConfirmMessage')
        }
        confirmLabel={dialogAction === 'reject' ? t('reject') : t('sendBack')}
        cancelLabel={t('cancel')}
        destructive={dialogAction === 'reject'}
        onCancel={() => setConfirmDestructive(false)}
        onConfirm={handleConfirmDestructive}
      />
    </Box>
  );
}
