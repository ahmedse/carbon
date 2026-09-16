// src/shell/AgentReviewSurface.jsx
// Graph-first Review — PlanDagGraph is the hero; Approve/Decline/Fork + Edit
// stay in chrome. Step list (edit/control) behind List toggle.
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
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import AgentRunSurface from './AgentRunSurface';
import { agentRoleLabel, toolLabel } from './aiTaskStatus';
import { buildPlanPhases } from '../utils/planGraph';

/**
 * @param {object} props
 * @param {object} props.plan
 * @param {boolean} [props.busy]
 * @param {function} props.onApprove
 * @param {function} props.onDecline
 * @param {function} [props.onFork]
 * @param {function} [props.onEditPlan] — (newBrief) => void
 * @param {function} [props.onEditStep] — (step) => void
 * @param {number|string|null} [props.confirmingId]
 * @param {function} [props.onConfirmStep]
 * @param {function} [props.onDeclineStep]
 */
function AgentReviewSurface({
  plan,
  busy = false,
  onApprove,
  onDecline,
  onFork,
  onEditPlan,
  onEditStep,
  confirmingId = null,
  onConfirmStep,
  onDeclineStep,
}) {
  const [editBriefOpen, setEditBriefOpen] = useState(false);
  const [editBriefValue, setEditBriefValue] = useState(plan?.brief || '');
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const phaseView = useMemo(() => buildPlanPhases(plan || {}), [plan]);
  const cancelled = plan?.status === 'cancelled';

  const saveBrief = () => {
    const next = editBriefValue.trim();
    if (!next || !onEditPlan) return;
    onEditPlan(next);
    setEditBriefOpen(false);
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
              const editable = !cancelled && (step.runnable_state == null || step.runnable_state === 'pending');
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
                  <Chip size="small" label="Pending" sx={{ height: 18, fontSize: '0.5625rem' }} />
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

  const consentBar = cancelled ? (
    <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
      This plan was cancelled — nothing was executed.
    </Typography>
  ) : (
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
      {onEditPlan && (
        <Button
          size="small"
          variant="text"
          startIcon={<EditOutlinedIcon sx={{ fontSize: 13 }} />}
          disabled={busy}
          onClick={() => {
            setEditBriefValue(plan?.brief || '');
            setEditBriefOpen(true);
          }}
          aria-label="Edit plan"
          sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
        >
          Edit brief
        </Button>
      )}
    </Stack>
  );

  return (
    <Stack spacing={1} data-testid="agent-review-surface">
      {editBriefOpen ? (
        <Stack spacing={0.75}>
          <TextField
            multiline
            minRows={2}
            maxRows={4}
            fullWidth
            size="small"
            value={editBriefValue}
            onChange={(e) => setEditBriefValue(e.target.value)}
            inputProps={{ 'aria-label': 'Plan brief' }}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.75rem' } }}
          />
          <Stack direction="row" spacing={0.75}>
            <Button size="small" variant="contained" disabled={busy} onClick={saveBrief} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
              Apply changes
            </Button>
            <Button size="small" variant="text" onClick={() => setEditBriefOpen(false)} sx={{ fontSize: '0.6875rem', textTransform: 'none' }}>
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
      {consentBar}
      <AgentRunSurface
        plan={plan}
        runSteps={[]}
        phase="idle"
        live={false}
        defaultListOpen
        banner={null}
        listContent={listContent}
        confirmingId={confirmingId}
        onConfirmStep={onConfirmStep}
        onDeclineStep={onDeclineStep}
      />
    </Stack>
  );
}

AgentReviewSurface.propTypes = {
  plan: PropTypes.object.isRequired,
  busy: PropTypes.bool,
  onApprove: PropTypes.func.isRequired,
  onDecline: PropTypes.func.isRequired,
  onFork: PropTypes.func,
  onEditPlan: PropTypes.func,
  onEditStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
};

export default AgentReviewSurface;
