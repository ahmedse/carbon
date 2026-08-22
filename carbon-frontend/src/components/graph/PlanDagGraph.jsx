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
import { Box, Button, Chip, Divider, Stack, Typography, useTheme } from '@mui/material';
import ArrowRightAltIcon from '@mui/icons-material/ArrowRightAlt';
import CloseIcon from '@mui/icons-material/Close';
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

/**
 * Live plan execution graph.
 * @param {object} props
 * @param {object} props.plan - plan payload (GET /ai/plans/{id}/)
 * @param {number} [props.height] - graph viewport height
 * @param {boolean} [props.live] - show the "Live" badge (parent is running)
 * @param {string} [props.testId] - data-testid
 */
export default function PlanDagGraph({ plan, height = 380, live = false, testId = 'plan-dag-graph' }) {
  const theme = useTheme();
  const [selected, setSelected] = useState(null);

  const { nodes, edges, width, height: layoutHeight, phaseBands } = useMemo(
    () => layoutExecutionGraph(plan),
    [plan],
  );

  const steps = useMemo(() => (Array.isArray(plan?.steps) ? plan.steps : []), [plan]);

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
          <SmartToyOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
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
              <ArrowRightAltIcon sx={{ fontSize: 11 }} />
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
              <ArrowRightAltIcon sx={{ fontSize: 11 }} />
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
          startIcon={<CloseIcon sx={{ fontSize: 12 }} />}
          onClick={() => setSelected(null)}
          sx={{ mt: 1, fontSize: '0.625rem', textTransform: 'none', minWidth: 0 }}
        >
          Close
        </Button>
      </Box>
    );
  };

  const summary = `${nodes.length} step${nodes.length !== 1 ? 's' : ''} · ${edges.length} link${edges.length !== 1 ? 's' : ''}`;

  return (
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
    />
  );
}

PlanDagGraph.propTypes = {
  plan: PropTypes.object,
  height: PropTypes.number,
  live: PropTypes.bool,
  testId: PropTypes.string,
};
