// src/apps/team/TeamRequestDetail.jsx
// Team approval detail (/team/:id).
// Layout: Summary → Stepper|Graph → Timeline → act buttons.
// Act UX: SystemDialog (comment) + ConfirmDialog for destructive reject/send-back/void/reopen.
// Approver acts while actionable. correspondence:admin may Void / Reopen terminals.

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
import ReplayIcon from '@mui/icons-material/Replay';
import BlockIcon from '@mui/icons-material/Block';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
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
  CORRESPONDENCE_ADMIN,
  expandCapabilities,
  hasCap,
} from '../../capabilities';
import {
  fetchCorrespondenceDetail,
  approveCorrespondence,
  acknowledgeCorrespondence,
  reviewCorrespondence,
  rejectCorrespondence,
  sendBackCorrespondence,
  voidCorrespondence,
  reopenCorrespondence,
} from '../../api/team';
import { SectionTitle } from '../my/components/myRequestsCommon';
import SummaryCard from '../my/components/SummaryCard';
import ApproverChainStepper from '../my/components/ApproverChainStepper';
import WorkflowGraph from '../my/components/WorkflowGraph';
import RequestTimeline from '../my/components/RequestTimeline';

const ACTIONABLE = ['submitted', 'in_review'];
const ADMIN_TERMINAL = ['approved', 'rejected', 'cancelled', 'expired'];
const COMMENT_REQUIRED = new Set(['reject', 'sendBack', 'void', 'reopen']);

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

function capabilityKeys(raw) {
  return (Array.isArray(raw) ? raw : []).map((c) => (typeof c === 'string' ? c : c?.key)).filter(Boolean);
}

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
  const { token, user, userCapabilities, isGlobalAdminFlag } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { notify } = useNotification();
  useDocumentTitle(t('detailTitle'));

  const fromHistory = location.state?.from === 'history';
  const peopleBack = {
    'people-leave': { path: '/people/leave', label: t('backToPeopleLeave') },
    'people-loans': { path: '/people/loans', label: t('backToPeopleLoans') },
    'people-attendance': { path: '/people/attendance', label: t('backToPeopleAttendance') },
    'people-employee': location.state?.employeeId
      ? {
          path: `/people/employees/${location.state.employeeId}`,
          label: t('backToEmployee'),
        }
      : null,
    'people-requests': { path: '/people/requests', label: t('backToPeopleRequests') },
  }[location.state?.from];
  const backPath = peopleBack?.path || (fromHistory ? '/team/history' : '/team');
  const backLabel = peopleBack?.label || (fromHistory ? t('backToHistory') : t('backToInbox'));

  const canCorrAdmin = useMemo(() => {
    if (isGlobalAdminFlag === true) return true;
    return hasCap(expandCapabilities(capabilityKeys(userCapabilities)), CORRESPONDENCE_ADMIN);
  }, [isGlobalAdminFlag, userCapabilities]);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [view, setView] = useState('graph');
  const [submitting, setSubmitting] = useState(false);

  /** @type {null | 'positive' | 'reject' | 'sendBack' | 'void' | 'reopen'} */
  const [dialogAction, setDialogAction] = useState(null);
  const [comment, setComment] = useState('');
  const [commentError, setCommentError] = useState(null);
  /** ConfirmDialog open after SystemDialog validates destructive act. */
  const [confirmDestructive, setConfirmDestructive] = useState(false);

  const isActionable = Boolean(data && ACTIONABLE.includes(data.status));
  const userId = Number(user?.id);
  const canDecide = Boolean(
    isActionable
    && Number.isFinite(userId)
    && (data.current_approver_ids || []).some((id) => Number(id) === userId),
  );
  const showAdminActs = Boolean(
    data && canCorrAdmin && ADMIN_TERMINAL.includes(data.status),
  );
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
          navigate(fromHistory ? '/team/history' : '/team');
        } else if (action === 'reject') {
          await rejectCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successRejected'), type: 'success' });
          navigate(fromHistory ? '/team/history' : '/team');
        } else if (action === 'sendBack') {
          await sendBackCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successSentBack'), type: 'success' });
          navigate(fromHistory ? '/team/history' : '/team');
        } else if (action === 'void') {
          await voidCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successVoided'), type: 'success' });
          navigate('/team/history');
        } else if (action === 'reopen') {
          await reopenCorrespondence(token, id, { comment: trimmedComment });
          notify({ message: t('successReopened'), type: 'success' });
          navigate('/team');
        }
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
    if (COMMENT_REQUIRED.has(dialogAction)) {
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
    if (dialogAction === 'void') return t('voidConfirmTitle');
    if (dialogAction === 'reopen') return t('reopenConfirmTitle');
    return t(positiveDef.labelKey);
  }, [dialogAction, t, positiveDef]);

  const dialogPrimaryLabel = useMemo(() => {
    if (dialogAction === 'reject') return t('reject');
    if (dialogAction === 'sendBack') return t('sendBack');
    if (dialogAction === 'void') return t('void');
    if (dialogAction === 'reopen') return t('reopen');
    return t(positiveDef.labelKey);
  }, [dialogAction, t, positiveDef]);

  const confirmTitle = useMemo(() => {
    if (dialogAction === 'reject') return t('rejectConfirmTitle');
    if (dialogAction === 'sendBack') return t('sendBackConfirmTitle');
    if (dialogAction === 'void') return t('voidConfirmTitle');
    if (dialogAction === 'reopen') return t('reopenConfirmTitle');
    return '';
  }, [dialogAction, t]);

  const confirmMessage = useMemo(() => {
    if (dialogAction === 'reject') return t('rejectConfirmMessage');
    if (dialogAction === 'sendBack') return t('sendBackConfirmMessage');
    if (dialogAction === 'void') return t('voidConfirmMessage');
    if (dialogAction === 'reopen') return t('reopenConfirmMessage');
    return '';
  }, [dialogAction, t]);

  const confirmLabel = useMemo(() => {
    if (dialogAction === 'reject') return t('reject');
    if (dialogAction === 'sendBack') return t('sendBack');
    if (dialogAction === 'void') return t('void');
    if (dialogAction === 'reopen') return t('reopen');
    return '';
  }, [dialogAction, t]);

  const dialogColor = useMemo(() => {
    if (dialogAction === 'reject' || dialogAction === 'void') return 'error';
    if (dialogAction === 'sendBack' || dialogAction === 'reopen') return 'warning';
    return positiveDef.color;
  }, [dialogAction, positiveDef]);

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

            <Box sx={{ pt: 1 }}>
              {canDecide || !showAdminActs ? (
                <>
                  <SectionTitle icon={HowToVoteIcon} title={t('actionsTitle')} />
                  {canDecide ? (
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
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {isActionable ? t('actionsNotYourStep') : t('actionsNotAvailable')}
                    </Typography>
                  )}
                </>
              ) : null}
            </Box>

            {showAdminActs ? (
              <Box sx={{ pt: 0.5 }}>
                <SectionTitle icon={AdminPanelSettingsIcon} title={t('adminActionsTitle')} />
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    startIcon={<ReplayIcon />}
                    disabled={submitting}
                    onClick={() => openAction('reopen')}
                  >
                    {t('reopen')}
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<BlockIcon />}
                    disabled={submitting}
                    onClick={() => openAction('void')}
                  >
                    {t('void')}
                  </Button>
                </Stack>
              </Box>
            ) : null}
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
            color={dialogColor}
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
            {COMMENT_REQUIRED.has(dialogAction)
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
              COMMENT_REQUIRED.has(dialogAction)
                ? t('commentRequiredPlaceholder')
                : t('commentPlaceholder')
            }
            required={COMMENT_REQUIRED.has(dialogAction)}
            error={Boolean(commentError)}
            helperText={commentError || undefined}
          />
        </Stack>
      </SystemDialog>

      <ConfirmDialog
        open={confirmDestructive}
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel={confirmLabel}
        cancelLabel={t('cancel')}
        destructive={dialogAction === 'reject' || dialogAction === 'void'}
        onCancel={() => setConfirmDestructive(false)}
        onConfirm={handleConfirmDestructive}
      />
    </Box>
  );
}
