// src/shell/AgentRunSurface.jsx
// ADR-0043 Run view — progress · blockers · consent list · StepToolbar.
// Plan graph lives on Plan; Job Map lives on Canvas. Do NOT stack either here.
import React, { useEffect, useMemo, useState } from 'react';
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
 * @param {object} props.plan
 * @param {Array} props.runSteps
 * @param {string} props.phase
 * @param {boolean} props.live
 * @param {Array} [props.artifacts] — count only for QoS strip (cards live on Output)
 * @param {React.ReactNode} [props.listContent]
 * @param {React.ReactNode} [props.banner]
 * @param {boolean} [props.defaultListOpen]
 * @param {function} [props.onOpenOutput] — optional handoff when artifacts exist
 * @param {function} [props.onRerun] — post-done CTA (ADR-0043 Screen Spec)
 * @param {function} [props.onOpenPlan] — jump to Plan to edit brief / fork
 * @param {boolean} [props.canRerun]
 * @param {boolean} [props.busy]
 */
function AgentRunSurface({
  plan,
  runSteps = [],
  phase,
  live = false,
  artifacts = [],
  listContent = null,
  banner = null,
  defaultListOpen = true,
  onOpenOutput = null,
  onRerun = null,
  onOpenPlan = null,
  canRerun = false,
  busy = false,
}) {
  const { t } = useTranslation('ai');
  const isMobile = useIsMobile();
  const [showList, setShowList] = useState(Boolean(defaultListOpen) || isMobile);

  useEffect(() => {
    if (defaultListOpen || isMobile) setShowList(true);
  }, [defaultListOpen, isMobile]);

  const mergedPlan = useMemo(
    () => mergePlanWithRunSteps(plan, runSteps),
    [plan, runSteps],
  );

  const steps = Array.isArray(mergedPlan?.steps) ? mergedPlan.steps : [];
  const terminal = new Set(['completed', 'failed', 'skipped']);
  const settled = steps.filter((s) => terminal.has(s.status)).length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const awaiting = steps.some((s) => s.status === 'awaiting_approval');
  const tools = new Set(
    steps.map((s) => s.tool_name).filter(Boolean),
  ).size;
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
    tools ? `${tools} ${t('toolsWord')}` : null,
    artCount ? `${artCount} ${t('artifactsWord')}` : null,
    formatDuration(totalLat),
  ].filter(Boolean);

  const runSettled = phase === 'finished' || phase === 'stopped' || phase === 'error';
  const showOutputHandoff =
    Boolean(onOpenOutput)
    && artCount > 0
    && runSettled;
  const showPostDone = runSettled && (onRerun || onOpenPlan || onOpenOutput);

  return (
    <Stack spacing={1} data-testid="agent-run-surface">
      {banner}

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
        {live && (
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
        <Box sx={{ flex: 1 }} />
        {listContent != null && (
          <Button
            size="small"
            variant={showList ? 'contained' : 'outlined'}
            onClick={() => setShowList((v) => !v)}
            aria-pressed={showList}
            sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, minHeight: { xs: 40, sm: 'auto' } }}
          >
            {showList ? t('hideList') : t('list')}
          </Button>
        )}
      </Stack>

      {(showList || isMobile) && listContent && (
        <Box data-testid="agent-run-list">
          {listContent}
        </Box>
      )}

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
  listContent: PropTypes.node,
  banner: PropTypes.node,
  defaultListOpen: PropTypes.bool,
  onOpenOutput: PropTypes.func,
  onRerun: PropTypes.func,
  onOpenPlan: PropTypes.func,
  canRerun: PropTypes.bool,
  busy: PropTypes.bool,
};

export default AgentRunSurface;
