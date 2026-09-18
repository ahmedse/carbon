// src/shell/AgentRunSurface.jsx
// Graph-first Agent Run surface — progress strip + live Plan DAG hero +
// artifacts strip; fat step list stays behind a List toggle (default off).
import React, { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import CloseIcon from '@mui/icons-material/Close';
import PlanDagGraph from '../components/graph/PlanDagGraph';
import { useIsMobile } from '../hooks/useIsMobile';
import { FONT } from '../theme/themeTokens';
import { useTranslation } from 'react-i18next';
import OpsCanvasShelf from './OpsCanvasShelf';

function formatDuration(ms) {
  if (ms == null || !Number.isFinite(ms)) return null;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/**
 * Merge streamed runSteps onto plan.steps so the DAG + dock see live I/O.
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
  // Steps that only exist in the stream (rare) still appear in the dock merge path.
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
 * @param {Array} [props.artifacts]
 * @param {boolean} [props.artifactsLoading]
 * @param {React.ReactNode} [props.artifactsContent]
 * @param {React.ReactNode} [props.listContent]
 * @param {React.ReactNode} [props.banner]
 * @param {number|string|null} [props.confirmingId]
 * @param {function} [props.onConfirmStep]
 * @param {function} [props.onDeclineStep]
 * @param {function} [props.onRetryStep]
 */
function AgentRunSurface({
  plan,
  runSteps = [],
  phase,
  live = false,
  artifacts = [],
  artifactsLoading = false,
  artifactsContent = null,
  listContent = null,
  banner = null,
  defaultListOpen = false,
  confirmingId = null,
  conversationId = null,
  onConfirmStep,
  onDeclineStep,
  onRetryStep,
}) {
  const { t } = useTranslation('ai');
  const isMobile = useIsMobile();
  const [showList, setShowList] = useState(Boolean(defaultListOpen) || isMobile);
  const [showGraph, setShowGraph] = useState(!isMobile);
  const [jobMapOpen, setJobMapOpen] = useState(false);

  useEffect(() => {
    if (defaultListOpen || isMobile) setShowList(true);
  }, [defaultListOpen, isMobile]);

  useEffect(() => {
    if (isMobile) setShowGraph(false);
  }, [isMobile]);

  const mergedPlan = useMemo(
    () => mergePlanWithRunSteps(plan, runSteps),
    [plan, runSteps],
  );

  const steps = Array.isArray(mergedPlan?.steps) ? mergedPlan.steps : [];
  const terminal = new Set(['completed', 'failed', 'skipped']);
  const settled = steps.filter((s) => terminal.has(s.status)).length;
  const failed = steps.filter((s) => s.status === 'failed').length;
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
    `${settled}/${steps.length || 0} steps`,
    failed ? `${failed} failed` : null,
    tools ? `${tools} tool${tools === 1 ? '' : 's'}` : null,
    artCount ? `${artCount} artifact${artCount === 1 ? '' : 's'}` : null,
    formatDuration(totalLat),
  ].filter(Boolean);

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
          {progressBits.join(' · ') || 'No steps yet'}
        </Typography>
        {live && (
          <Chip
            size="small"
            color="primary"
            label="Live"
            sx={{ height: 18, ...FONT.chip }}
          />
        )}
        {phase === 'finished' && (
          <Chip size="small" color="success" variant="outlined" label="Done" sx={{ height: 18, ...FONT.chip }} />
        )}
        {phase === 'stopped' && (
          <Chip size="small" variant="outlined" label="Stopped" sx={{ height: 18, ...FONT.chip }} />
        )}
        {phase === 'error' && (
          <Chip size="small" color="error" variant="outlined" label="Failed" sx={{ height: 18, ...FONT.chip }} />
        )}
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ fontSize: '0.625rem', display: { xs: 'none', sm: 'block' } }}
        >
          Click a step for tool, inputs, and output
        </Typography>
        <Box sx={{ flex: 1 }} />
        {conversationId && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<MapOutlinedIcon sx={{ fontSize: '0.875rem !important' }} />}
            onClick={() => setJobMapOpen(true)}
            data-testid="agent-run-job-map"
            sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, minHeight: { xs: 40, sm: 'auto' } }}
          >
            Job Map
          </Button>
        )}
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
        {isMobile && (
          <Button
            size="small"
            variant={showGraph ? 'contained' : 'outlined'}
            onClick={() => setShowGraph((v) => !v)}
            aria-pressed={showGraph}
            sx={{ fontSize: '0.6875rem', textTransform: 'none', minWidth: 0, minHeight: 40 }}
          >
            {showGraph ? t('hideGraph') : t('viewGraph')}
          </Button>
        )}
      </Stack>

      {(!isMobile || showGraph) && (
      <Paper variant="outlined" sx={{ overflow: 'hidden', bgcolor: 'background.paper' }}>
        <PlanDagGraph
          plan={mergedPlan}
          height={Math.min(typeof window !== 'undefined' ? window.innerHeight * (isMobile ? 0.4 : 0.52) : 420, isMobile ? 320 : 480)}
          live={live}
          onConfirmStep={onConfirmStep}
          onDeclineStep={onDeclineStep}
          onRetryStep={onRetryStep}
          confirmingId={confirmingId}
        />
      </Paper>
      )}

      {(showList || isMobile) && listContent && (
        <Box data-testid="agent-run-list">
          {listContent}
        </Box>
      )}

      {(artifactsLoading || artCount > 0 || artifactsContent) && (
        <Box data-testid="agent-run-artifacts">
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              fontSize: '0.625rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              mb: 0.5,
            }}
          >
            Artifacts
          </Typography>
          {artifactsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
              <CircularProgress size={18} />
            </Box>
          ) : artifactsContent || (
            <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', gap: 0.75 }}>
              {artifacts.map((a) => (
                <Chip
                  key={a.id ?? a.name}
                  size="small"
                  variant="outlined"
                  label={a.name || 'artifact'}
                  sx={{ height: 22, fontSize: '0.6875rem' }}
                />
              ))}
            </Stack>
          )}
        </Box>
      )}

      {!steps.length && phase === 'working' && (
        <Alert severity="info" sx={{ fontSize: '0.6875rem', py: 0.25 }}>
          Starting… the graph will fill as steps begin.
        </Alert>
      )}

      <Dialog
        open={jobMapOpen}
        onClose={() => setJobMapOpen(false)}
        fullWidth
        maxWidth="md"
        PaperProps={{ sx: { height: '80vh' } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
          Job Map
          <IconButton onClick={() => setJobMapOpen(false)} sx={{ ml: 'auto' }} aria-label="Close">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          <OpsCanvasShelf conversationId={conversationId} />
        </DialogContent>
      </Dialog>
    </Stack>
  );
}

AgentRunSurface.propTypes = {
  plan: PropTypes.object,
  runSteps: PropTypes.array,
  phase: PropTypes.string,
  live: PropTypes.bool,
  artifacts: PropTypes.array,
  artifactsLoading: PropTypes.bool,
  artifactsContent: PropTypes.node,
  listContent: PropTypes.node,
  banner: PropTypes.node,
  defaultListOpen: PropTypes.bool,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  conversationId: PropTypes.string,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  onRetryStep: PropTypes.func,
};

export default AgentRunSurface;
