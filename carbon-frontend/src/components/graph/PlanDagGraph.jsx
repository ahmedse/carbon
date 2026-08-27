// src/components/graph/PlanDagGraph.jsx
// W3-F — LIVE plan DAG as a layered DIRECTED EXECUTION graph.
//
// This is now a THIN domain adapter over the shared `EnterpriseGraph`
// primitive (see `./EnterpriseGraph.jsx`). It supplies the plan-specific
// domain data — laid nodes/edges + phase lanes, the node interior (status dot,
// intent, tool, status pill), and the docked inspection pane — while
// `EnterpriseGraph` owns ALL the interaction: movable canvas (pan), movable +
// resizable nodes, wheel zoom, zoom-to-fit, redraw, reset, PNG export, and the
// full-screen maximize modal. This guarantees every graph in the platform
// shares ONE modern, enterprise look & feel (RULE_2 reuse, ADR-0012).
//
// Nodes THEMSELVES are movable (drag) + resizable (bottom-right handle), and
// running steps pulse so their status is visible while the plan executes.
// The parent polls the plan during a run and passes fresh data — this
// component stays presentational. Theme tokens only (RULE_8); outcome labels
// only (RULE_23).
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  Collapse,
  Divider,
  IconButton,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowRightAltIcon from '@mui/icons-material/ArrowRightAlt';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import EnterpriseGraph from './EnterpriseGraph';
import { layoutExecutionGraph } from '../../utils/planGraph';

/**
 * Step status → theme color token (RULE_8 — never raw hex).
 * @param {string} status - step lifecycle status (pending/running/…)
 * @param {object} theme - MUI theme
 */
export function planStepStatusColor(status, theme) {
  switch (status) {
    case 'completed':
      return theme.palette.success.main;
    case 'running':
      return theme.palette.primary.main;
    case 'awaiting_approval':
      return theme.palette.warning.main;
    case 'failed':
      return theme.palette.error.main;
    case 'skipped':
      return theme.palette.text.disabled;
    default:
      return theme.palette.text.disabled; // pending
  }
}

/** Human label for a step status (outcome terms, RULE_23). */
export function planStepStatusLabel(status) {
  switch (status) {
    case 'completed':
      return 'Finished';
    case 'running':
      return 'Running';
    case 'awaiting_approval':
      return 'Needs approval';
    case 'failed':
      return 'Failed';
    case 'skipped':
      return 'Skipped';
    default:
      return 'Pending';
  }
}

/** Compact UPPERCASE status label for the dense node interior. */
const NODE_STATUS = {
  completed: 'FINISHED',
  running: 'RUNNING',
  awaiting_approval: 'APPROVAL',
  failed: 'FAILED',
  skipped: 'SKIPPED',
  pending: 'PENDING',
};

/** Step status → MUI Chip color (RULE 5 — chip carries a text label too). */
export function planStepStatusChipColor(status) {
  switch (status) {
    case 'completed':
      return 'success';
    case 'running':
      return 'primary';
    case 'awaiting_approval':
      return 'warning';
    case 'failed':
      return 'error';
    case 'skipped':
      return 'default';
    default:
      return 'default';
  }
}

/**
 * Group steps into parallel lanes (F-26). A lane = steps sharing a non-null
 * `parallel_group` whose enclosing phase declared `strategy === "parallel"`.
 * Steps outside any parallel phase are excluded (they render as ordinary DAG
 * nodes). Lanes are returned in ascending group order for a stable render.
 * @param {Array} steps - serialized plan steps (W7-A contract)
 * @returns {Array<{groupId:number, steps:Array<object>}>}
 */
export function parallelLaneGroups(steps) {
  const lanes = new Map();
  (Array.isArray(steps) ? steps : []).forEach((s) => {
    if (!s || s.strategy !== 'parallel' || s.parallel_group == null) return;
    const key = s.parallel_group;
    if (!lanes.has(key)) lanes.set(key, []);
    lanes.get(key).push(s);
  });
  return [...lanes.entries()]
    .map(([groupId, laneSteps]) => ({ groupId, steps: laneSteps }))
    .sort((a, b) => a.groupId - b.groupId);
}

/**
 * Partial-attention header copy for a parallel lane (RULE_23 outcome words).
 * Returns "1 of 3 steps needs attention" when some (not necessarily all)
 * siblings failed — a precise signal that never collapses to a blanket
 * "failed". Returns null when nothing in the lane needs attention.
 * @param {Array} steps
 * @returns {string|null}
 */
export function laneAttentionLabel(steps) {
  const list = Array.isArray(steps) ? steps : [];
  const failed = list.filter((s) => s.status === 'failed').length;
  if (failed === 0) return null;
  const n = list.length;
  return `${failed} of ${n} step${n === 1 ? '' : 's'} ${failed === 1 ? 'needs' : 'need'} attention`;
}

/**
 * Collapsible parallel-lane band (F-26). Groups sibling steps that "run
 * together" into ONE band; each step keeps its own status chip (RULE 5),
 * consent action (Approve/Decline, never blocking siblings), and a persistent
 * failed chip + Retry. Theme tokens only (RULE_8).
 */
function ParallelLaneBand({ groupId, name, steps, onConfirmStep, onDeclineStep, onRetryStep, confirmingId }) {
  const [open, setOpen] = useState(true);
  const attention = laneAttentionLabel(steps);
  return (
    <Paper variant="outlined" sx={{ borderRadius: 1 }} data-testid={`parallel-lane-${groupId}`}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.5}
        sx={{ px: 0.75, py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
        onClick={() => setOpen((v) => !v)}
      >
        <IconButton size="small" sx={{ p: 0, m: 0 }} aria-label={`Toggle parallel lane ${name}`}>
          {open ? <ExpandMoreIcon sx={{ fontSize: '0.9375rem' }} /> : <ChevronRightIcon sx={{ fontSize: '0.9375rem' }} />}
        </IconButton>
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {name}
        </Typography>
        <Chip size="small" variant="outlined" label="Runs together" sx={{ height: 2, fontSize: '0.5625rem' }} />
        {attention && (
          <Chip size="small" color="warning" variant="outlined" label={attention} sx={{ height: 2, fontSize: '0.5625rem' }} />
        )}
      </Stack>
      <Collapse in={open}>
        <Stack spacing={0.5} sx={{ px: 0.75, pb: 0.75 }}>
          {steps.map((s) => {
            const chipColor = planStepStatusChipColor(s.status);
            const label = planStepStatusLabel(s.status);
            return (
              <Stack key={s.step_id} direction="row" alignItems="center" spacing={0.5} sx={{ px: 0.5, flexWrap: 'wrap', rowGap: 0.5 }}>
                <Typography
                  variant="body2"
                  sx={{ flex: 1, minWidth: 0, fontSize: '0.6875rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {s.intent || `Step ${s.step_id}`}
                </Typography>
                <Chip size="small" variant="outlined" label={label} color={chipColor} sx={{ height: 2, fontSize: '0.5625rem' }} />
                {s.status === 'awaiting_approval' && (onConfirmStep || onDeclineStep) && (
                  <Stack direction="row" spacing={0.5}>
                    <Button
                      size="small"
                      variant="contained"
                      disabled={confirmingId === s.step_id}
                      onClick={() => onConfirmStep?.(s.step_id)}
                      sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                    >
                      Approve
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      disabled={confirmingId === s.step_id}
                      onClick={() => onDeclineStep?.(s.step_id)}
                      sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                    >
                      Decline
                    </Button>
                  </Stack>
                )}
                {s.status === 'failed' && onRetryStep && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    onClick={() => onRetryStep?.(s.step_id)}
                    sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0, px: 0.75 }}
                  >
                    Retry
                  </Button>
                )}
                {s.status === 'failed' && s.error && (
                  <Typography variant="caption" color="error.main" sx={{ fontSize: '0.625rem', flexBasis: '100%' }}>
                    {s.error}
                  </Typography>
                )}
              </Stack>
            );
          })}
        </Stack>
      </Collapse>
    </Paper>
  );
}

ParallelLaneBand.propTypes = {
  groupId: PropTypes.number.isRequired,
  name: PropTypes.string.isRequired,
  steps: PropTypes.array.isRequired,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  onRetryStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

/**
 * Live plan execution graph.
 * @param {object} props
 * @param {object} props.plan - plan payload (GET /ai/plans/{id}/)
 * @param {number} [props.height] - graph viewport height
 * @param {boolean} [props.live] - show the "Live" badge (parent is running)
 * @param {boolean} [props.fill] - render to fill the container (full-screen modal)
 * @param {string} [props.testId] - data-testid
 * @param {function} [props.onConfirmStep] - (stepId) => void, consent inside a lane
 * @param {function} [props.onDeclineStep] - (stepId) => void, skip inside a lane
 * @param {function} [props.onRetryStep] - (stepId) => void, retry a failed lane step
 * @param {number|string|null} [props.confirmingId] - step currently consenting
 */
export default function PlanDagGraph({
  plan,
  height = 380,
  live = false,
  fill = false,
  testId = 'plan-dag-graph',
  onConfirmStep,
  onDeclineStep,
  onRetryStep,
  confirmingId = null,
}) {
  const theme = useTheme();
  const [selected, setSelected] = useState(null);

  const { nodes, edges, width, height: layoutHeight, phaseBands } = useMemo(
    () => layoutExecutionGraph(plan),
    [plan],
  );

  const steps = useMemo(() => (Array.isArray(plan?.steps) ? plan.steps : []), [plan]);

  // F-26 — parallel lanes: sibling steps that "run together" become one
  // collapsible band (MUI Collapse/Stack), each keeping its own status chip.
  const parallelLanes = useMemo(() => parallelLaneGroups(steps), [steps]);
  const laneNameByGroup = useMemo(() => {
    const m = new Map();
    (Array.isArray(phaseBands) ? phaseBands : []).forEach((b) => {
      if (b.strategy === 'parallel') m.set(b.phase_id, b.name);
    });
    return m;
  }, [phaseBands]);
  const attentionSummary = useMemo(() => {
    const counts = parallelLanes
      .map((lane) => laneAttentionLabel(lane.steps))
      .filter(Boolean);
    return counts[0] || null;
  }, [parallelLanes]);

  // feeds-into: which steps depend on a given step (reverse depends_on).
  const feedsInto = useMemo(() => {
    const map = new Map();
    steps.forEach((s) => {
      (Array.isArray(s.depends_on) ? s.depends_on : []).forEach((dep) => {
        if (!map.has(dep)) map.set(dep, []);
        map.get(dep).push(s);
      });
    });
    return map;
  }, [steps]);

  const stepById = useMemo(() => {
    const m = new Map();
    steps.forEach((s) => m.set(s.step_id, s));
    return m;
  }, [steps]);

  const colorFor = useCallback((status) => planStepStatusColor(status, theme), [theme]);
  const phaseColor = useCallback(
    (phaseId) => theme.chartPalette?.[(phaseId ?? 0) % (theme.chartPalette?.length || 6)],
    [theme],
  );

  const legend = useMemo(
    () => [
      { label: 'Pending', color: theme.palette.text.disabled },
      { label: 'Running', color: theme.palette.primary.main },
      { label: 'Needs approval', color: theme.palette.warning.main },
      { label: 'Finished', color: theme.palette.success.main },
      { label: 'Failed', color: theme.palette.error.main },
    ],
    [theme],
  );

  const selectedStep = selected ? stepById.get(selected.id) : null;
  const selectedDeps = selectedStep
    ? (Array.isArray(selectedStep.depends_on) ? selectedStep.depends_on : [])
        .map((id) => stepById.get(id))
        .filter(Boolean)
    : [];
  const selectedFeeds = selected ? (feedsInto.get(selected.id) || []) : [];
  const selectedPhase = selectedStep
    ? (phaseBands.find((b) => {
        const node = nodes.find((n) => n.id === selectedStep.step_id);
        return node && b.phase_id === node.phase_id;
      }) || null)
    : null;

  // ── Node interior (drawn inside the EnterpriseGraph rect) ──────────────
  // Linear/Temporal-style compact node: a 3px status accent bar on the left,
  // the intent on the title row with the status label right-aligned, and the
  // tool/kind on the meta row. The running pulse outline is drawn by
  // EnterpriseGraph from the node status.
  const renderNode = useCallback(
    (n) => {
      const color = colorFor(n.status);
      const statusLabel = NODE_STATUS[n.status] || 'PENDING';
      const rawTitle = String(n.label || `Step ${n.id}`);
      const rawTool = String(n.tool_name || 'Reasoning (LLM)');
      // Title is truncated to leave room for the right-aligned status label.
      const titleMax = Math.max(6, Math.floor((n.w - 66) / 5.4));
      const title = rawTitle.length > titleMax ? `${rawTitle.slice(0, titleMax - 1)}…` : rawTitle;
      const toolMax = Math.max(6, Math.floor((n.w - 26) / 4.5));
      const tool = rawTool.length > toolMax ? `${rawTool.slice(0, toolMax - 1)}…` : rawTool;
      return (
        <>
          {/* Status accent bar — the primary at-a-glance signal */}
          <rect x={3} y={5} width={3} height={n.h - 10} rx={1.5} fill={color} />
          {/* Intent */}
          <text x={13} y={n.h / 2 - 1} fontSize={11} fontWeight={600} fill={theme.palette.text.primary}>
            {title}
          </text>
          {/* Status — right-aligned on the title row, always visible while running */}
          <text x={n.w - 9} y={n.h / 2 + 1.5} fontSize={8} fontWeight={700} fill={color} textAnchor="end">
            {statusLabel}
          </text>
          {/* Tool / kind */}
          <text x={13} y={n.h / 2 + 11} fontSize={9} fill={theme.palette.text.secondary}>
            {tool}
          </text>
        </>
      );
    },
    [colorFor, theme],
  );

  const nodeAriaLabel = useCallback(
    (n) => `Step ${n.id}: ${n.label} — ${planStepStatusLabel(n.status)}`,
    [],
  );

  // ── Legend (rendered above the canvas, inline + modal) ─────────────────
  const legendEl = (
    <Stack
      direction="row"
      spacing={1}
      alignItems="center"
      sx={{ px: 1, py: 0.5, flexWrap: 'wrap', rowGap: 0.25 }}
    >
      {legend.map((l) => (
        <Stack key={l.label} direction="row" spacing={0.5} alignItems="center">
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: l.color }} />
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
            {l.label}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );

  // ── Docked detail pane (never floats over the graph) ───────────────────
  // `variant` is supplied by EnterpriseGraph so inline + modal panes get
  // distinct test ids and widths.
  const renderDetailPane = (variant) => {
    if (!selected || !selectedStep) return null;
    const width = variant === 'modal' ? 300 : 236;
    const paneTestId = variant === 'modal' ? 'plan-step-detail-modal' : 'plan-step-detail';
    return (
      <Box
        sx={{
          width,
          flexShrink: 0,
          borderLeft: 1,
          borderColor: 'divider',
          p: 1.25,
          overflowY: 'auto',
          bgcolor: 'background.paper',
        }}
        data-testid={paneTestId}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.75 }}>
          <SmartToyOutlinedIcon sx={{ fontSize: '0.9375rem', color: 'text.secondary' }} />
          <Typography variant="body2" fontWeight={600} sx={{ flex: 1, fontSize: '0.75rem' }}>
            Step {selectedStep.step_id}
          </Typography>
          <Chip
            size="small"
            label={planStepStatusLabel(selectedStep.status)}
            sx={{
              height: 16,
              fontSize: '0.5625rem',
              bgcolor: colorFor(selectedStep.status),
              color: theme.palette.getContrastText(colorFor(selectedStep.status)),
            }}
          />
        </Stack>

        <Typography variant="body2" sx={{ fontSize: '0.75rem', lineHeight: 1.4, mb: 0.75 }}>
          {selectedStep.intent || 'No description'}
        </Typography>

        {selectedPhase && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', mb: 0.5 }}>
            Phase: <strong>{selectedPhase.name}</strong>
            {selectedPhase.strategy === 'parallel' ? ' (parallel)' : ''}
          </Typography>
        )}

        <Divider sx={{ my: 0.75 }} />

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
          Tool
        </Typography>
        <Typography variant="body2" sx={{ fontSize: '0.6875rem', mb: 0.5 }}>
          {selectedStep.tool_name ? (
            selectedStep.tool_name
          ) : (
            <Box component="span" sx={{ color: 'text.secondary' }}>
              None — pure reasoning step (LLM)
            </Box>
          )}
        </Typography>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
          Agent role
        </Typography>
        <Typography variant="body2" sx={{ fontSize: '0.6875rem', mb: 0.5 }}>
          {selectedStep.agent_role || 'orchestrator'}
        </Typography>

        {typeof selectedStep.latency_ms === 'number' && (
          <>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
              Latency
            </Typography>
            <Typography variant="body2" sx={{ fontSize: '0.6875rem', mb: 0.5 }}>
              {selectedStep.latency_ms} ms
            </Typography>
          </>
        )}

        <Divider sx={{ my: 0.75 }} />

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
          Depends on
        </Typography>
        {selectedDeps.length ? (
          selectedDeps.map((d) => (
            <Typography key={d.step_id} variant="body2" sx={{ fontSize: '0.6875rem', display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ArrowRightAltIcon sx={{ fontSize: '0.6875rem' }} />
              {d.intent || `Step ${d.step_id}`}
            </Typography>
          ))
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.6875rem', mb: 0.5 }}>
            Nothing — starts the workflow
          </Typography>
        )}

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem', mt: 0.5 }}>
          Feeds into
        </Typography>
        {selectedFeeds.length ? (
          selectedFeeds.map((d) => (
            <Typography key={d.step_id} variant="body2" sx={{ fontSize: '0.6875rem', display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ArrowRightAltIcon sx={{ fontSize: '0.6875rem' }} />
              {d.intent || `Step ${d.step_id}`}
            </Typography>
          ))
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
            Nothing — ends the workflow
          </Typography>
        )}

        {selectedStep.draft_text && (
          <>
            <Divider sx={{ my: 0.75 }} />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
              Draft
            </Typography>
            <Typography variant="body2" sx={{ fontSize: '0.6875rem' }}>
              {selectedStep.draft_text}
            </Typography>
          </>
        )}

        {selectedStep.critic_verdict && (
          <>
            <Divider sx={{ my: 0.75 }} />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
              Critic verdict
            </Typography>
            <Typography variant="body2" sx={{ fontSize: '0.6875rem' }}>
              {selectedStep.critic_verdict}
            </Typography>
          </>
        )}

        {selectedStep.error && (
          <>
            <Divider sx={{ my: 0.75 }} />
            <Typography variant="caption" color="error.main" sx={{ display: 'block', fontSize: '0.625rem' }}>
              Error
            </Typography>
            <Typography variant="body2" color="error.main" sx={{ fontSize: '0.6875rem' }}>
              {selectedStep.error}
            </Typography>
          </>
        )}

        <Button
          size="small"
          startIcon={<CloseIcon sx={{ fontSize: '0.75rem' }} />}
          onClick={() => setSelected(null)}
          sx={{ mt: 1, fontSize: '0.625rem', textTransform: 'none', minWidth: 0 }}
        >
          Close
        </Button>
      </Box>
    );
  };

  const summary = `${nodes.length} step${nodes.length !== 1 ? 's' : ''} · ${edges.length} link${edges.length !== 1 ? 's' : ''}${
    attentionSummary ? ` · ${attentionSummary}` : ''
  }`;

  return (
    <>
      {parallelLanes.length > 0 && (
        <Stack spacing={0.75} sx={{ mb: 0.75 }} data-testid="parallel-lanes">
          {parallelLanes.map((lane) => (
            <ParallelLaneBand
              key={lane.groupId}
              groupId={lane.groupId}
              name={laneNameByGroup.get(lane.groupId) || 'Runs together'}
              steps={lane.steps}
              onConfirmStep={onConfirmStep}
              onDeclineStep={onDeclineStep}
              onRetryStep={onRetryStep}
              confirmingId={confirmingId}
            />
          ))}
        </Stack>
      )}
      <EnterpriseGraph
        nodes={nodes}
        edges={edges}
        width={width}
        layoutHeight={layoutHeight}
        height={height}
        phaseBands={phaseBands}
        phaseColor={phaseColor}
        nodeColor={(n) => colorFor(n.status)}
        renderNode={renderNode}
        selected={selected}
        onSelect={setSelected}
        legend={legendEl}
        sidebar={renderDetailPane}
        title="Plan graph"
        modalTitle="Plan graph — full view"
        summary={summary}
        live={live}
        emptyMessage="This plan has no steps to graph yet."
        nodeAriaLabel={nodeAriaLabel}
        markerId="plan-arrow"
        modalMarkerId="plan-arrow-modal"
        testId={testId}
        modalTestId="plan-graph-modal"
        modalCloseTestId="plan-graph-modal-close"
        expandTestId="plan-graph-expand"
        exportFileName="plan-graph"
        fill={fill}
      />
    </>
  );
}

PlanDagGraph.propTypes = {
  plan: PropTypes.object,
  height: PropTypes.number,
  live: PropTypes.bool,
  fill: PropTypes.bool,
  testId: PropTypes.string,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  onRetryStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};
