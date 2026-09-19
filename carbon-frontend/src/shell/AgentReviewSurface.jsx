// src/shell/AgentReviewSurface.jsx
// ADR-0043 Plan view — PlanDagGraph is the exclusive hero; Approve/Decline/Fork
// + Rename / Replan / Discuss stay in chrome. Step list behind List toggle.
import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import PlanDagGraph from '../components/graph/PlanDagGraph';
import { agentRoleLabel, isRerunnableStatus, stepStatusMeta, toolLabel } from './aiTaskStatus';
import { buildPlanPhases } from '../utils/planGraph';
import { useTranslation } from 'react-i18next';

/**
 * @param {object} props
 * @param {object} props.plan
 * @param {'review'|'inspect'} [props.mode]
 * @param {boolean} [props.busy]
 * @param {boolean} [props.live]
 * @param {function} props.onApprove
 * @param {function} props.onDecline
 * @param {function} [props.onFork]
 * @param {function} [props.onRenamePlan] — (newBrief) => void — label only
 * @param {function} [props.onReplanPlan] — (newBrief) => void — decompose + diff
 * @param {function} [props.onDiscuss] — jump to Chat with refine draft
 * @param {function} [props.onEditStep] — (step) => void
 * @param {number|string|null} [props.confirmingId]
 * @param {function} [props.onConfirmStep]
 * @param {function} [props.onDeclineStep]
 */
function AgentReviewSurface({
  plan,
  mode = 'review',
  busy = false,
  live = false,
  onApprove,
  onDecline,
  onFork,
  onRenamePlan,
  onReplanPlan,
  onDiscuss,
  onEditStep,
  confirmingId = null,
  onConfirmStep,
  onDeclineStep,
}) {
  const { t } = useTranslation('ai');
  const [briefEditor, setBriefEditor] = useState(null); // null | 'rename' | 'replan'
  const [editBriefValue, setEditBriefValue] = useState(plan?.brief || '');
  const [showList, setShowList] = useState(true);
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const phaseView = useMemo(() => buildPlanPhases(plan || {}), [plan]);
  const cancelled = plan?.status === 'cancelled';
  const running = plan?.status === 'running' || live;
  const inspect = mode === 'inspect';
  const settled = isRerunnableStatus(plan?.status);
  const canMutateBrief = !cancelled && !running;

  const openEditor = (kind) => {
    setEditBriefValue(plan?.brief || '');
    setBriefEditor(kind);
  };

  const saveBrief = () => {
    const next = editBriefValue.trim();
    if (!next) return;
    if (briefEditor === 'rename' && onRenamePlan) onRenamePlan(next);
    else if (briefEditor === 'replan' && onReplanPlan) onReplanPlan(next);
    setBriefEditor(null);
  };

  const listContent = (
    <Stack spacing={0.75} data-testid="agent-review-step-list">
      {phaseView.phases.map((phase) => (
        <Box key={phase.phase_id || phase.name}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              fontSize: '0.625rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              display: 'block',
              mb: 0.5,
            }}
          >
            {phase.name}
            {phase.strategy === 'parallel' ? ' · parallel' : ''}
          </Typography>
          <Stack spacing={0.5}>
            {phase.step_ids.map((sid) => {
              const step = steps.find((s) => s.step_id === sid);
              if (!step) return null;
              const editable = canMutateBrief
                && (step.runnable_state == null || step.runnable_state === 'pending')
                && (!step.status || step.status === 'pending');
              const meta = stepStatusMeta(step.status);
              return (
                <Paper
                  key={sid}
                  variant="outlined"
                  sx={{ px: 1, py: 0.75, display: 'flex', alignItems: 'center', gap: 0.75 }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.75rem', fontWeight: 500 }}>
                      {step.intent || `Step ${step.step_id}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
                      {[toolLabel(step.tool_name), agentRoleLabel(step.agent_role)].filter(Boolean).join(' · ')}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={meta.label}
                    color={meta.color === 'default' ? undefined : meta.color}
                    sx={{ height: 18, fontSize: '0.5625rem' }}
                  />
                  {editable && onEditStep && (
                    <Tooltip title="Edit step">
                      <IconButton
                        size="small"
                        aria-label={`Edit step ${step.step_id}`}
                        onClick={() => onEditStep(step)}
                        sx={{ p: 0.25 }}
                      >
                        <EditOutlinedIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Paper>
              );
            })}
          </Stack>
        </Box>
      ))}
      {steps.length === 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
          No steps yet — the graph will fill when the plan is ready.
        </Typography>
      )}
    </Stack>
  );

  const verbButtons = (
    <>
      {onFork && (
        <Button
          size="small"
          variant="outlined"
          startIcon={<CallSplitIcon sx={{ fontSize: 13 }} />}
          disabled={busy}
          onClick={onFork}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          Fork
        </Button>
      )}
      {canMutateBrief && onRenamePlan && (
        <Button
          size="small"
          variant="text"
          startIcon={<EditOutlinedIcon sx={{ fontSize: 13 }} />}
          disabled={busy}
          onClick={() => openEditor('rename')}
          aria-label={t('renamePlan')}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {t('renamePlan')}
        </Button>
      )}
      {canMutateBrief && onReplanPlan && (
        <Button
          size="small"
          variant="text"
          startIcon={<AutoFixHighOutlinedIcon sx={{ fontSize: 13 }} />}
          disabled={busy}
          onClick={() => openEditor('replan')}
          aria-label={t('replanPlan')}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {t('replanPlan')}
        </Button>
      )}
      {onDiscuss && (
        <Button
          size="small"
          variant="text"
          startIcon={<ChatBubbleOutlineIcon sx={{ fontSize: 13 }} />}
          disabled={busy}
          onClick={onDiscuss}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {t('discussInChat')}
        </Button>
      )}
    </>
  );

  let chromeBar = null;
  if (cancelled) {
    chromeBar = (
      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
        This plan was cancelled — nothing was executed.
      </Typography>
    );
  } else if (inspect) {
    chromeBar = (
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        data-testid="agent-review-inspect"
      >
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem', mr: 0.5 }}>
          {running
            ? t('inspectRunningHint')
            : t('inspectIdleHint')}
        </Typography>
        {verbButtons}
      </Stack>
    );
  } else {
    chromeBar = (
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        data-testid="agent-review-consent"
      >
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem', mr: 0.5 }}>
          Nothing runs until you approve.
        </Typography>
        <Button
          size="small"
          variant="contained"
          disabled={busy}
          onClick={onApprove}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {busy ? 'Approving…' : 'Approve plan'}
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="error"
          disabled={busy}
          onClick={onDecline}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          Decline
        </Button>
        {verbButtons}
      </Stack>
    );
  }

  return (
    <Stack spacing={1} data-testid="agent-review-surface">
      {briefEditor ? (
        <Stack spacing={0.75} data-testid={`agent-brief-editor-${briefEditor}`}>
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            {briefEditor === 'rename' ? t('renameHint') : t('replanHint')}
          </Typography>
          {briefEditor === 'replan' && settled && (
            <Typography variant="caption" color="warning.main" sx={{ fontSize: '0.6875rem' }}>
              {t('replanCompletedWarn')}
            </Typography>
          )}
          <TextField
            multiline
            minRows={2}
            maxRows={4}
            fullWidth
            size="small"
            value={editBriefValue}
            onChange={(e) => setEditBriefValue(e.target.value)}
            inputProps={{ 'aria-label': briefEditor === 'rename' ? t('renamePlan') : t('replanPlan') }}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
          />
          <Stack direction="row" spacing={0.75}>
            <Button
              size="small"
              variant="contained"
              disabled={busy || !editBriefValue.trim()}
              onClick={saveBrief}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {briefEditor === 'rename' ? t('applyRename') : t('applyReplan')}
            </Button>
            <Button
              size="small"
              variant="text"
              onClick={() => setBriefEditor(null)}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              Cancel
            </Button>
          </Stack>
        </Stack>
      ) : (
        plan?.brief && (
          <Typography
            variant="body2"
            sx={{
              fontSize: '0.8125rem',
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {plan.brief}
          </Typography>
        )
      )}
      {!briefEditor && chromeBar}
      <Paper variant="outlined" sx={{ overflow: 'hidden', bgcolor: 'background.paper' }} data-testid="plan-dag-graph-wrap">
        <PlanDagGraph
          plan={plan}
          height={420}
          live={live}
          onConfirmStep={onConfirmStep}
          onDeclineStep={onDeclineStep}
          confirmingId={confirmingId}
        />
      </Paper>
      <Stack direction="row" justifyContent="flex-end">
        <Button
          size="small"
          variant={showList ? 'contained' : 'outlined'}
          onClick={() => setShowList((v) => !v)}
          aria-pressed={showList}
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          {showList ? t('hideList') : t('list')}
        </Button>
      </Stack>
      {showList && listContent}
    </Stack>
  );
}

AgentReviewSurface.propTypes = {
  plan: PropTypes.object.isRequired,
  mode: PropTypes.oneOf(['review', 'inspect']),
  busy: PropTypes.bool,
  live: PropTypes.bool,
  onApprove: PropTypes.func.isRequired,
  onDecline: PropTypes.func.isRequired,
  onFork: PropTypes.func,
  onRenamePlan: PropTypes.func,
  onReplanPlan: PropTypes.func,
  onDiscuss: PropTypes.func,
  onEditStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
};

export default AgentReviewSurface;
