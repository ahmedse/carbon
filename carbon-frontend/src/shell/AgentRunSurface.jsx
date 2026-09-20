// src/shell/AgentRunSurface.jsx
// ADR-0043 V6 Run view — visual timeline + docked step detail (Plan-parity).
// Plan graph lives on Plan; Job Map on Canvas. No health / audit / subagents here.
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useIsMobile } from '../hooks/useIsMobile';
import { FONT } from '../theme/themeTokens';
import { useTranslation } from 'react-i18next';
import { buildRunChronicle } from '../utils/runChronicle';
import RunTimeline from './RunTimeline';
import BeatDetailContent from './BeatDetailContent';

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
  listContent = null,
  banner = null,
  consentHero = null,
  defaultListOpen = false,
  onOpenOutput = null,
  onRerun = null,
  onOpenPlan = null,
  canRerun = false,
  busy = false,
  onConfirmStep = null,
  onDeclineStep = null,
  confirmingId = null,
}) {
  const { t } = useTranslation('ai');
  const isMobile = useIsMobile();
  const [showList, setShowList] = useState(Boolean(defaultListOpen) || isMobile);
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [paneOpen, setPaneOpen] = useState(true);

  const mergedPlan = useMemo(
    () => mergePlanWithRunSteps(plan, runSteps),
    [plan, runSteps],
  );

  useEffect(() => {
    if (defaultListOpen || isMobile) setShowList(true);
  }, [defaultListOpen, isMobile]);

  // Focus the urgent beat when consent / failure arrives.
  useEffect(() => {
    const urgent = (mergedPlan?.steps || []).find(
      (s) => s.status === 'awaiting_approval' || s.status === 'failed',
    );
    if (urgent) {
      setSelectedStepId(urgent.step_id);
      setPaneOpen(true);
    }
  }, [mergedPlan, phase]);

  const chronicle = useMemo(
    () => buildRunChronicle(mergedPlan, runSteps),
    [mergedPlan, runSteps],
  );

  const selectedStep = useMemo(() => {
    if (selectedStepId == null) return null;
    return (mergedPlan?.steps || []).find((s) => s.step_id === selectedStepId) || null;
  }, [mergedPlan, selectedStepId]);

  const selectedEvent = useMemo(
    () => chronicle.find((e) => e.stepId === selectedStepId) || null,
    [chronicle, selectedStepId],
  );

  const handleSelectStep = (stepId) => {
    setSelectedStepId(stepId);
    setPaneOpen(true);
  };

  const clearSelection = () => setSelectedStepId(null);

  const steps = Array.isArray(mergedPlan?.steps) ? mergedPlan.steps : [];
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
  // Post-done CTAs for classic Run tab; chat-first uses AgentRunToolbar.
  const showPostDone = runSettled && (onRerun || onOpenPlan);

  const renderDetailPane = () => {
    if (!paneOpen) {
      return (
        <Box
          sx={{
            width: 40,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            pt: 1,
            pr: 0.5,
            alignSelf: 'stretch',
          }}
          data-testid="run-structure-detail-collapsed"
        >
          <Tooltip title="Show step details">
            <IconButton
              size="small"
              aria-label="Show step details"
              data-testid="run-structure-expand"
              onClick={() => setPaneOpen(true)}
              sx={{
                p: 0.5,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                bgcolor: 'background.paper',
              }}
            >
              <ChevronLeftIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Box>
      );
    }

    return (
      <Box
        sx={{
          width: { xs: '100%', sm: 288 },
          flexShrink: 0,
          alignSelf: 'stretch',
          minHeight: { xs: 220, sm: 320 },
          p: 1,
          pl: { xs: 1, sm: 0.75 },
          boxSizing: 'border-box',
        }}
      >
        <Paper
          variant="outlined"
          data-testid="run-structure-detail"
          sx={{
            height: '100%',
            minHeight: 220,
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            borderRadius: 1.5,
            borderColor: 'divider',
            bgcolor: 'background.paper',
            overflow: 'hidden',
            boxShadow: (th) => `inset 0 0 0 1px ${th.palette.action.hover}`,
          }}
        >
          <Stack
            direction="row"
            spacing={0.5}
            alignItems="center"
            sx={{ px: 1, py: 0.625, borderBottom: 1, borderColor: 'divider', flexShrink: 0, bgcolor: 'action.hover' }}
          >
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ flex: 1, fontSize: '0.625rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              {selectedStep ? t('beatDetailTitle') : t('runTimeline')}
            </Typography>
            {selectedStep && (
              <Button
                size="small"
                onClick={clearSelection}
                sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0 }}
              >
                Clear
              </Button>
            )}
            <Tooltip title="Hide step details">
              <IconButton
                size="small"
                aria-label="Hide step details"
                data-testid="run-structure-collapse"
                onClick={() => setPaneOpen(false)}
                sx={{ p: 0.25 }}
              >
                <ChevronRightIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Stack>
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              p: 1.25,
            }}
          >
            {selectedStep ? (
              <BeatDetailContent
                step={selectedStep}
                event={selectedEvent}
                busy={busy || confirmingId === selectedStepId}
                onApprove={onConfirmStep
                  ? async (id) => {
                    await onConfirmStep(id);
                  }
                  : undefined}
                onDecline={onDeclineStep
                  ? async (id) => {
                    await onDeclineStep(id);
                  }
                  : undefined}
              />
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {t('beatTooltipOpen')}
              </Typography>
            )}
          </Box>
        </Paper>
      </Box>
    );
  };

  return (
    <Stack spacing={1} data-testid="agent-run-surface">
      {banner}
      {consentHero}

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
        <Box sx={{ flex: 1 }} />
        {listContent != null && (
          <Button
            size="small"
            variant={showList ? 'contained' : 'outlined'}
            onClick={() => setShowList((v) => !v)}
            aria-pressed={showList}
            data-testid="agent-run-toggle-details"
            sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, minHeight: { xs: 40, sm: 'auto' } }}
          >
            {showList ? t('hideDetails') : t('showDetails')}
          </Button>
        )}
      </Stack>

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        alignItems="stretch"
        spacing={0}
        sx={{ minHeight: 280 }}
        data-testid="agent-run-timeline-dock"
      >
        <Box sx={{ flex: 1, minWidth: 0, overflowY: 'auto', pr: { sm: 0.5 } }}>
          {chronicle.length > 0 ? (
            <RunTimeline
              events={chronicle}
              title={t('runTimeline')}
              selectedStepId={paneOpen ? selectedStepId : null}
              onSelectStep={handleSelectStep}
            />
          ) : null}
        </Box>
        {chronicle.length > 0 ? renderDetailPane() : null}
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
};

export default AgentRunSurface;
