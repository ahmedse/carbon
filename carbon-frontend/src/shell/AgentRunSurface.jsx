// src/shell/AgentRunSurface.jsx
// ADR-0043 Run view — timeline + collapsible step detail drawer.
// Plan owns the DAG; Canvas owns Job Map. No bottom "Show details" list.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import { useIsMobile } from '../hooks/useIsMobile';
import { FONT } from '../theme/themeTokens';
import { useTranslation } from 'react-i18next';
import { buildRunChronicle, buildHumanActivityLog } from '../utils/runChronicle';
import RunTimeline from './RunTimeline';
import RunStepDetailDrawer from './RunStepDetailDrawer';
import InheritedContextPanel from './InheritedContextPanel';
import HumanActivityLog from './HumanActivityLog';
import { friendlyStepError } from './humanizeOperatorCopy';

function formatDuration(ms) {
  if (ms == null || !Number.isFinite(ms)) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/**
 * Merge streamed runSteps onto plan.steps so the list / dock see live I/O.
 * @param {object|null} plan
 * @param {Array} runSteps
 */
export function mergePlanWithRunSteps(plan, runSteps) {
  if (!plan) return plan;
  const live = Array.isArray(runSteps) ? runSteps : [];
  if (!live.length) return plan;
  const byId = new Map(live.map((s) => [s.step_id, s]));
  const base = Array.isArray(plan.steps) ? plan.steps : [];
  const merged = base.map((s) => {
    const patch = byId.get(s.step_id);
    return patch ? { ...s, ...patch } : s;
  });
  live.forEach((s) => {
    if (!merged.some((m) => m.step_id === s.step_id)) merged.push(s);
  });
  return { ...plan, steps: merged };
}

/**
 * @param {object} props
 */
function AgentRunSurface({
  plan,
  runSteps = [],
  phase,
  live = false,
  artifacts = [],
  banner = null,
  consentHero = null,
  onOpenOutput = null,
  onRerun = null,
  onOpenPlan = null,
  canRerun = false,
  busy = false,
  onConfirmStep = null,
  onDeclineStep = null,
  confirmingId = null,
  hideInherited = false,
  stepActions = null,
}) {
  const { t } = useTranslation('ai');
  const isMobile = useIsMobile();
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Auto-focus an urgent beat once when it appears — never steal focus again
  // while the operator browses other finished steps (poll/merge re-renders).
  const autoFocusedUrgentRef = useRef(null);

  const mergedPlan = useMemo(
    () => mergePlanWithRunSteps(plan, runSteps),
    [plan, runSteps],
  );

  // Focus the urgent beat when consent / failure first arrives — open drawer.
  useEffect(() => {
    const urgent = (mergedPlan?.steps || []).find(
      (s) => s.status === 'awaiting_approval' || s.status === 'failed',
    );
    if (!urgent) {
      autoFocusedUrgentRef.current = null;
      return;
    }
    const key = `${urgent.step_id}:${urgent.status}`;
    if (autoFocusedUrgentRef.current === key) return;
    autoFocusedUrgentRef.current = key;
    setSelectedStepId(urgent.step_id);
    setDrawerOpen(true);
  }, [mergedPlan, phase]);

  const chronicle = useMemo(
    () => buildRunChronicle(mergedPlan, runSteps),
    [mergedPlan, runSteps],
  );
  const activityLines = useMemo(
    () => buildHumanActivityLog(chronicle, { humanizeError: friendlyStepError }),
    [chronicle],
  );

  const handleSelectStep = (stepId) => {
    if (selectedStepId === stepId && drawerOpen) {
      setDrawerOpen(false);
      return;
    }
    setSelectedStepId(stepId);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
  };

  const steps = Array.isArray(mergedPlan?.steps) ? mergedPlan.steps : [];
  const stepsById = useMemo(
    () => Object.fromEntries(steps.map((s) => [s.step_id, s])),
    [steps],
  );
  const selectedStep = selectedStepId != null ? stepsById[selectedStepId] : null;
  const selectedEvent = useMemo(
    () => chronicle.find((e) => e.stepId === selectedStepId) || null,
    [chronicle, selectedStepId],
  );
  const terminal = new Set(['completed', 'failed', 'skipped']);
  const settled = steps.filter((s) => terminal.has(s.status)).length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const awaiting = steps.some((s) => s.status === 'awaiting_approval');
  const artCount = Array.isArray(artifacts) ? artifacts.length : 0;
  const latencies = steps
    .map((s) => s.latency_ms)
    .filter((v) => typeof v === 'number' && Number.isFinite(v));
  const totalLat = latencies.length
    ? latencies.reduce((a, b) => a + b, 0)
    : null;

  const progressBits = [
    `${settled}/${steps.length || 0} ${t('stepsWord')}`,
    failed ? `${failed} ${t('failedWord')}` : null,
    awaiting ? t('statusConsentNeeded') : null,
    !awaiting && artCount ? `${artCount} ${t('artifactsWord')}` : null,
    !awaiting && formatDuration(totalLat),
  ].filter(Boolean);

  const runSettled = phase === 'finished' || phase === 'stopped' || phase === 'error';
  const showOutputHandoff =
    Boolean(onOpenOutput)
    && artCount > 0
    && runSettled;
  const showPostDone = runSettled && (onRerun || onOpenPlan);

  return (
    <Stack
      spacing={1}
      data-testid="agent-run-surface"
      sx={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      {banner}
      {consentHero}

      {hideInherited ? null : <InheritedContextPanel plan={plan} />}

      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 0.25, flexWrap: 'wrap', rowGap: 0.5 }}
        data-testid="agent-run-progress"
      >
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.02em' }}
        >
          {progressBits.join(' · ') || t('noStepsYet')}
        </Typography>
        {live && !awaiting && (
          <Chip
            size="small"
            color="primary"
            label={t('live')}
            sx={{ height: 18, ...FONT.chip }}
          />
        )}
        {phase === 'finished' && (
          <Chip size="small" color="success" variant="outlined" label={t('runCompleted')} sx={{ height: 18, ...FONT.chip }} />
        )}
        {phase === 'stopped' && (
          <Chip size="small" variant="outlined" label={t('stopped')} sx={{ height: 18, ...FONT.chip }} />
        )}
        {phase === 'error' && (
          <Chip size="small" color="error" variant="outlined" label={t('failedWord')} sx={{ height: 18, ...FONT.chip }} />
        )}
      </Stack>

      <Box
        sx={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: 'stretch',
          gap: 0,
          flex: 1,
          minHeight: { xs: 240, sm: 320 },
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'hidden',
          bgcolor: 'background.default',
        }}
        data-testid="agent-run-timeline-dock"
      >
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            minHeight: 0,
            overflowY: isMobile ? 'visible' : 'auto',
            p: 0.5,
          }}
        >
          {chronicle.length > 0 ? (
            <RunTimeline
              events={chronicle}
              stepsById={stepsById}
              title={t('runTimeline')}
              selectedStepId={selectedStepId}
              onSelectStep={handleSelectStep}
            />
          ) : null}
        </Box>

        <RunStepDetailDrawer
          open={drawerOpen}
          step={selectedStep}
          event={selectedEvent}
          confirming={confirmingId === selectedStepId}
          onConfirm={onConfirmStep}
          onDecline={onDeclineStep}
          onClose={handleCloseDrawer}
          busy={busy}
          stepActions={stepActions}
        />
      </Box>

      <HumanActivityLog lines={activityLines} defaultOpen={failed > 0} />

      {showPostDone && (
        <Stack
          direction="row"
          spacing={1}
          flexWrap="wrap"
          useFlexGap
          data-testid="agent-run-post-done"
          sx={{ px: 0.25 }}
        >
          {onRerun && (
            <Button
              size="small"
              variant="contained"
              disabled={!canRerun || busy}
              onClick={onRerun}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {t('rerunPlanShort')}
            </Button>
          )}
          {onOpenPlan && (
            <Button
              size="small"
              variant="outlined"
              disabled={busy}
              onClick={onOpenPlan}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {t('editOnPlan')}
            </Button>
          )}
          {onOpenOutput && !showOutputHandoff && (
            <Button
              size="small"
              variant="outlined"
              onClick={onOpenOutput}
              sx={{ fontSize: '0.6875rem', textTransform: 'none' }}
            >
              {t('openOutput')}
            </Button>
          )}
        </Stack>
      )}

      {showOutputHandoff && (
        <Alert
          severity="info"
          data-testid="agent-run-output-handoff"
          action={(
            <Button
              color="inherit"
              size="small"
              onClick={onOpenOutput}
              sx={{ fontSize: '0.6875rem', textTransform: 'none', fontWeight: 600 }}
            >
              {t('openOutput')}
            </Button>
          )}
          sx={{ fontSize: '0.6875rem', py: 0.25, '& .MuiAlert-message': { py: 0.25 } }}
        >
          {t('artifactsOnOutput', { count: artCount })}
        </Alert>
      )}

      {!steps.length && phase === 'working' && (
        <Alert severity="info" sx={{ fontSize: '0.6875rem', py: 0.25 }}>
          {t('runStarting')}
        </Alert>
      )}
    </Stack>
  );
}

AgentRunSurface.propTypes = {
  plan: PropTypes.object,
  runSteps: PropTypes.array,
  phase: PropTypes.string,
  live: PropTypes.bool,
  artifacts: PropTypes.array,
  listContent: PropTypes.node, // ignored — bottom details list removed
  banner: PropTypes.node,
  consentHero: PropTypes.node,
  defaultListOpen: PropTypes.bool,
  onOpenOutput: PropTypes.func,
  onRerun: PropTypes.func,
  onOpenPlan: PropTypes.func,
  canRerun: PropTypes.bool,
  busy: PropTypes.bool,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  hideInherited: PropTypes.bool,
  stepActions: PropTypes.object,
};

export default AgentRunSurface;
