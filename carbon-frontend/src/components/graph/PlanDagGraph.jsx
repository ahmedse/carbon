// src/components/graph/PlanDagGraph.jsx
// W3-F — LIVE plan DAG as a layered DIRECTED EXECUTION graph.
//
// This is now a THIN domain adapter over the shared `EnterpriseGraph`
// primitive (see `./EnterpriseGraph.jsx`). It supplies the plan-specific
// domain data — laid nodes/edges + phase lanes, the node interior (status bar,
// intent, agent role + tool, status label), and the docked inspection pane — while
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
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowRightAltIcon from '@mui/icons-material/ArrowRightAlt';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import EnterpriseGraph from './EnterpriseGraph';
import RichContent from '../RichContent';
import {
  PLAN_ROLE_ACCENT,
  PLAN_SHAPE_LEGEND,
  legendShapePath,
  resolvePlanEdgeStyle,
  resolvePlanNodeShape,
} from './planGraphShapes';
import { layoutExecutionGraph } from '../../utils/planGraph';
import { NODE_STATUS_DENSE, agentRoleLabel, stepStatusMeta } from '../../shell/aiTaskStatus';

/** Wrap intent for graph cards — prefer readable journey labels over `…` soup. */
export function wrapTitleLines(raw, maxPerLine, maxLines = 2) {
  const text = String(raw || '').trim();
  if (!text) return [''];
  if (text.length <= maxPerLine) return [text];
  const lines = [];
  let rest = text;
  while (rest && lines.length < maxLines) {
    if (rest.length <= maxPerLine) {
      lines.push(rest);
      break;
    }
    let cut = rest.lastIndexOf(' ', maxPerLine);
    if (cut < Math.floor(maxPerLine * 0.45)) cut = maxPerLine;
    lines.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest && lines.length === maxLines) {
    const last = lines[maxLines - 1];
    lines[maxLines - 1] = `${last.slice(0, Math.max(1, maxPerLine - 1))}…`;
  }
  return lines;
}

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
  return stepStatusMeta(status).label;
}

/** Pretty-print JSON / values — kept for structure dock only; Plan operator dock stays business-only. */
function CollapsiblePayload({ label, value, testId }) {
  const [open, setOpen] = useState(false);
  if (value == null || value === '') return null;
  let text;
  try {
    text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  } catch {
    text = String(value);
  }
  if (!text || text === '{}' || text === '[]') return null;
  const preview = text.length > 80 ? `${text.slice(0, 80)}…` : text;
  return (
    <Box sx={{ mt: 0.75 }} data-testid={testId}>
      <Button
        size="small"
        onClick={() => setOpen((v) => !v)}
        sx={{ fontSize: '0.625rem', textTransform: 'none', px: 0, minWidth: 0 }}
      >
        {open ? `Hide ${label}` : `Show ${label}`}
      </Button>
      {!open && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', fontSize: '0.625rem', fontFamily: 'ui-monospace, monospace', wordBreak: 'break-word' }}
        >
          {preview}
        </Typography>
      )}
      <Collapse in={open}>
        <Box
          component="pre"
          sx={{
            m: 0,
            mt: 0.5,
            p: 0.75,
            borderRadius: 1,
            bgcolor: 'background.default',
            fontSize: '0.625rem',
            fontFamily: 'ui-monospace, monospace',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            maxHeight: 180,
            overflow: 'auto',
          }}
        >
          {text}
        </Box>
      </Collapse>
    </Box>
  );
}

CollapsiblePayload.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.any,
  testId: PropTypes.string,
};

/** Compact UPPERCASE status label for the dense node interior. */
const NODE_STATUS = NODE_STATUS_DENSE;

/** Step status → MUI Chip color (RULE 5 — chip carries a text label too). */
export function planStepStatusChipColor(status) {
  return stepStatusMeta(status).color;
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
 * Live plan execution graph — or structure-only Plan preview.
 * @param {object} props
 * @param {object} props.plan - plan payload (GET /ai/plans/{id}/)
 * @param {number} [props.height] - graph viewport height
 * @param {boolean} [props.live] - show the "Live" badge (parent is running)
 * @param {boolean} [props.fill] - render to fill the container (full-screen modal)
 * @param {'execution'|'structure'} [props.mode]
 *   - execution: status colors, Finished/Running legend, docked analyst pane (Run/classic)
 *   - structure: Plan view — topology only; tooltips; click → light scrollable drawer
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
  mode = 'execution',
  testId = 'plan-dag-graph',
  onConfirmStep,
  onDeclineStep,
  onRetryStep,
  confirmingId = null,
}) {
  const theme = useTheme();
  const structure = mode === 'structure';
  const [selected, setSelected] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [paneOpen, setPaneOpen] = useState(true);

  const { nodes, edges, width, height: layoutHeight, phaseBands, direction } = useMemo(
    () => layoutExecutionGraph(plan, {
      // Always auto: parallel → LR fan, pure chain → TB (fills the rail).
      direction: 'auto',
    }),
    [plan],
  );

  const visibleNodes = useMemo(() => nodes.filter((n) => !n.is_dummy), [nodes]);

  const steps = useMemo(() => (Array.isArray(plan?.steps) ? plan.steps : []), [plan]);

  // F-26 — parallel lanes (execution only): sibling steps that "run together".
  const parallelLanes = useMemo(
    () => (structure ? [] : parallelLaneGroups(steps)),
    [steps, structure],
  );
  const laneNameByGroup = useMemo(() => {
    const m = new Map();
    (Array.isArray(phaseBands) ? phaseBands : []).forEach((b) => {
      if (b.strategy === 'parallel') m.set(b.phase_id, b.name);
    });
    return m;
  }, [phaseBands]);
  const attentionSummary = useMemo(() => {
    if (structure) return null;
    const counts = parallelLanes
      .map((lane) => laneAttentionLabel(lane.steps))
      .filter(Boolean);
    return counts[0] || null;
  }, [parallelLanes, structure]);

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
    () => (structure
      ? []
      : [
        { label: 'Pending', color: theme.palette.text.disabled },
        { label: 'Running', color: theme.palette.primary.main },
        { label: 'Needs approval', color: theme.palette.warning.main },
        { label: 'Finished', color: theme.palette.success.main },
        { label: 'Failed', color: theme.palette.error.main },
      ]),
    [theme, structure],
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

  const edgeSourceStep = selectedEdge ? stepById.get(selectedEdge.source) : null;
  const edgeTargetStep = selectedEdge ? stepById.get(selectedEdge.target) : null;

  const clearSelection = useCallback(() => {
    setSelected(null);
    setSelectedEdge(null);
  }, []);

  const handleSelectNode = useCallback((node) => {
    setSelectedEdge(null);
    setSelected(node);
    if (node) setPaneOpen(true);
  }, []);

  const handleSelectEdge = useCallback((edge) => {
    setSelected(null);
    setSelectedEdge(edge);
    if (edge) setPaneOpen(true);
  }, []);

  // Structure / execution node interiors — card boxes with clear accent bar.
  const renderNode = useCallback(
    (n) => {
      const shape = resolvePlanNodeShape(n);
      const isDiamond = shape === 'diamond' || shape === 'diamondPlus';
      const isCircle = shape === 'circle' || shape === 'doubleCircle' || shape === 'thickCircle';
      const center = isDiamond || isCircle;
      const padX = center ? 0 : 14;
      const textX = center ? n.w / 2 : padX + 8;
      const anchor = center ? 'middle' : 'start';
      const roleKey = String(n.agent_role || 'orchestrator').toLowerCase();
      const accentToken = PLAN_ROLE_ACCENT[roleKey] || 'primary';
      const accent = structure
        ? (theme.palette[accentToken]?.main || phaseColor(n.phase_id) || theme.palette.primary.main)
        : colorFor(n.status);

      if (structure) {
        const rawTitle = String(n.label || `Step ${n.id}`);
        const titleMax = Math.max(18, Math.floor((n.w - (center ? n.w * 0.35 : 40)) / 6.6));
        const titleLines = wrapTitleLines(rawTitle, titleMax, 2);
        const isGateway = n.is_gateway
          || ['choice', 'parallel', 'observe', 'map', 'loop', 'wait', 'fail', 'succeed'].includes(n.node_type);
        const meta = isGateway
          ? String(n.node_type || 'gateway')
          : (agentRoleLabel(n.agent_role || 'orchestrator') || n.phase_name || '');
        const metaMax = Math.max(8, Math.floor((n.w - (center ? n.w * 0.4 : 40)) / 5.6));
        const metaTrim = meta.length > metaMax ? `${meta.slice(0, metaMax - 1)}…` : meta;
        const lineCount = titleLines.length + (metaTrim ? 1 : 0);
        const blockH = lineCount * 13;
        const startY = n.h / 2 - blockH / 2 + 10;
        return (
          <>
            {!center ? (
              <>
                <rect x={0} y={0} width={5} height={n.h} rx={0} fill={accent} />
                <rect x={5} y={0} width={1} height={n.h} fill={theme.palette.divider} opacity={0.35} />
              </>
            ) : null}
            {titleLines.map((line, i) => (
              <text
                key={`t${i}`}
                x={textX}
                y={startY + i * 14}
                fontSize={center ? 11 : 12.5}
                fontWeight={650}
                fill={theme.palette.text.primary}
                textAnchor={anchor}
              >
                {line}
              </text>
            ))}
            {metaTrim ? (
              <text
                x={textX}
                y={startY + titleLines.length * 14 + 2}
                fontSize={10}
                fill={theme.palette.text.secondary}
                textAnchor={anchor}
              >
                {metaTrim}
              </text>
            ) : null}
          </>
        );
      }

      const color = colorFor(n.status);
      const statusLabel = NODE_STATUS[n.status] || 'PENDING';
      const rawTitle = String(n.label || `Step ${n.id}`);
      const isGateway = n.is_gateway
        || ['choice', 'parallel', 'observe', 'map', 'loop', 'wait', 'fail', 'succeed'].includes(n.node_type);
      // Cards stay light — tool ids / cast live in the dock under "More detail".
      const metaRaw = isGateway ? String(n.node_type || 'gateway').toUpperCase() : '';
      const titleMax = Math.max(22, Math.floor((n.w - 72) / 6.6));
      const titleLines = wrapTitleLines(rawTitle, titleMax, 2);
      const metaMax = Math.max(10, Math.floor((n.w - 28) / 5.6));
      const meta = metaRaw.length > metaMax ? `${metaRaw.slice(0, metaMax - 1)}…` : metaRaw;
      const startY = titleLines.length > 1 ? n.h / 2 - (meta ? 8 : 4) : n.h / 2 + (meta ? -2 : 4);
      return (
        <>
          {!center ? (
            <>
              <rect x={0} y={0} width={5} height={n.h} fill={color} />
              <rect x={5} y={0} width={1} height={n.h} fill={theme.palette.divider} opacity={0.35} />
            </>
          ) : null}
          {titleLines.map((line, i) => (
            <text
              key={`et${i}`}
              x={padX + 8}
              y={startY + i * 13}
              fontSize={12.5}
              fontWeight={650}
              fill={theme.palette.text.primary}
            >
              {line}
            </text>
          ))}
          <text x={n.w - 10} y={14} fontSize={9} fontWeight={700} fill={color} textAnchor="end">
            {statusLabel}
          </text>
          {meta ? (
            <text x={padX + 8} y={startY + titleLines.length * 13 + 2} fontSize={10} fill={theme.palette.text.secondary}>
              {meta}
            </text>
          ) : null}
        </>
      );
    },
    [colorFor, theme, structure, phaseColor],
  );

  const nodeAriaLabel = useCallback(
    (n) => {
      if (structure) {
        return `Step: ${n.label || n.id}`;
      }
      const role = n.is_gateway
        ? ''
        : ` · ${agentRoleLabel(n.agent_role || 'orchestrator')}`;
      return `Step ${n.id}: ${n.label}${role} — ${planStepStatusLabel(n.status)}`;
    },
    [structure],
  );

  const nodeTitleTip = useCallback(
    (n) => {
      const intent = String(n.label || `Step ${n.id}`);
      if (structure) {
        const phase = n.phase_name ? ` · ${n.phase_name}` : '';
        return `${intent}${phase}`;
      }
      return `${intent} — ${planStepStatusLabel(n.status)}`;
    },
    [structure],
  );

  const edgeTitleTip = useCallback(
    (e) => {
      const from = stepById.get(e.source);
      const to = stepById.get(e.target);
      const a = from?.intent || `Step ${e.source}`;
      const b = to?.intent || `Step ${e.target}`;
      return `${a} → ${b}`;
    },
    [stepById],
  );

  const legendEl = structure ? (
    <Stack spacing={0.35} sx={{ px: 1, py: 0.5 }} data-testid="plan-shape-legend">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: 'wrap', rowGap: 0.35 }}>
        {PLAN_SHAPE_LEGEND.map((row) => (
          <Stack key={row.shape} direction="row" spacing={0.5} alignItems="center">
            <Box
              component="svg"
              width={12}
              height={12}
              viewBox="0 0 12 12"
              aria-hidden
              sx={{ flexShrink: 0, color: 'text.secondary' }}
            >
              <path
                d={legendShapePath(row.shape)}
                fill="none"
                stroke="currentColor"
                strokeWidth={1.25}
              />
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
              {row.label}
            </Typography>
          </Stack>
        ))}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.5625rem' }}>
        Solid arrow = sequence · Dashed = conditional · Open arrowhead = guarded
      </Typography>
    </Stack>
  ) : legend.length > 0 ? (
    <Stack spacing={0.25} sx={{ px: 1, py: 0.5 }}>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        sx={{ flexWrap: 'wrap', rowGap: 0.25 }}
      >
        {legend.map((l) => (
          <Stack key={l.label} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: l.color }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              {l.label}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Stack>
  ) : null;

  // Light Operator dock (structure) — RichContent in chat-message style; collapsible.
  const structureMarkdown = (() => {
    if (selectedStep) {
      const lines = [
        `### ${selectedStep.intent || 'Step'}`,
        '',
      ];
      if (selectedPhase) {
        const parallel = selectedPhase.strategy === 'parallel' ? ' · runs with siblings' : '';
        lines.push(`**Stage:** ${selectedPhase.name}${parallel}`, '');
      }
      const role = agentRoleLabel(selectedStep.agent_role || 'orchestrator');
      if (role) lines.push(`**Who:** ${role}`, '');
      lines.push('**Needs first**', '');
      if (selectedDeps.length) {
        selectedDeps.forEach((d) => lines.push(`- ${d.intent || `Step ${d.step_id}`}`));
      } else {
        lines.push('_Starts here_');
      }
      lines.push('', '**Then**', '');
      if (selectedFeeds.length) {
        selectedFeeds.forEach((d) => lines.push(`- ${d.intent || `Step ${d.step_id}`}`));
      } else {
        lines.push('_Ends the plan_');
      }
      return lines.join('\n');
    }
    if (selectedEdge && (edgeSourceStep || edgeTargetStep)) {
      return [
        '### Link',
        '',
        '**From**',
        '',
        edgeSourceStep?.intent || `Step ${selectedEdge.source}`,
        '',
        '**To**',
        '',
        edgeTargetStep?.intent || `Step ${selectedEdge.target}`,
        '',
        '_The later step waits on the earlier one._',
      ].join('\n');
    }
    const brief = String(plan?.brief || '').trim();
    if (!brief) return '_Select a step or link for details._';
    return brief;
  })();

  const renderStructurePane = (variant) => {
    const railH = variant === 'modal' ? '100%' : height;
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
            height: railH,
          }}
          data-testid="plan-structure-detail-collapsed"
        >
          <Tooltip title="Show details">
            <IconButton
              size="small"
              aria-label="Show details"
              data-testid="plan-structure-expand"
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
    const paneWidth = variant === 'modal' ? 340 : 288;
    const paneTestId = variant === 'modal' ? 'plan-structure-detail-modal' : 'plan-structure-detail';
    return (
      <Box
        sx={{
          width: paneWidth,
          flexShrink: 0,
          height: railH,
          alignSelf: 'stretch',
          minHeight: 0,
          p: 1,
          pl: 0.75,
          boxSizing: 'border-box',
        }}
      >
        <Paper
          variant="outlined"
          data-testid={paneTestId}
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            borderRadius: 1.5,
            borderColor: 'divider',
            bgcolor: 'background.paper',
            overflow: 'hidden',
            boxShadow: (t) => `inset 0 0 0 1px ${t.palette.action.hover}`,
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
              {selectedStep ? 'Step' : selectedEdge ? 'Link' : 'Brief'}
            </Typography>
            {(selectedStep || selectedEdge) && (
              <Button
                size="small"
                onClick={clearSelection}
                sx={{ fontSize: '0.625rem', textTransform: 'none', minWidth: 0 }}
              >
                Brief
              </Button>
            )}
            <Tooltip title="Hide details">
              <IconButton
                size="small"
                aria-label="Hide details"
                data-testid="plan-structure-collapse"
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
            <Box data-testid="plan-structure-message" sx={{ width: '100%', minWidth: 0 }}>
              <RichContent content={structureMarkdown} testId="plan-structure-rich" variant="message" />
            </Box>
          </Box>
        </Paper>
      </Box>
    );
  };

  // Operator dock — intent + action first; engine internals behind "More detail".
  const renderDetailPane = (variant) => {
    if (structure) return renderStructurePane(variant);
    if (!selected || !selectedStep) return null;
    const paneWidth = variant === 'modal' ? 280 : 220;
    const paneTestId = variant === 'modal' ? 'plan-step-detail-modal' : 'plan-step-detail';
    const needsApproval = selectedStep.status === 'awaiting_approval';
    const nextStep = selectedFeeds[0] || null;
    return (
      <Box
        sx={{
          width: paneWidth,
          flexShrink: 0,
          borderLeft: 1,
          borderColor: 'divider',
          p: 1.25,
          overflowY: 'auto',
          bgcolor: 'background.paper',
        }}
        data-testid={paneTestId}
      >
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.75 }}>
          <Typography variant="body2" fontWeight={600} sx={{ flex: 1, fontSize: '0.75rem' }}>
            This step
          </Typography>
          <Chip
            size="small"
            label={planStepStatusLabel(selectedStep.status)}
            sx={{
              height: 18,
              fontSize: '0.5625rem',
              bgcolor: colorFor(selectedStep.status),
              color: theme.palette.getContrastText(colorFor(selectedStep.status)),
            }}
          />
          <IconButton size="small" aria-label="Close step details" onClick={clearSelection} sx={{ p: 0.25 }}>
            <CloseIcon sx={{ fontSize: '0.875rem' }} />
          </IconButton>
        </Stack>

        <Typography variant="body2" sx={{ fontSize: '0.8125rem', lineHeight: 1.4, mb: 1, fontWeight: 600 }}>
          {selectedStep.intent || 'No description'}
        </Typography>

        {needsApproval && (onConfirmStep || onDeclineStep) && (
          <Stack direction="row" spacing={0.75} sx={{ mb: 1 }}>
            <Button
              size="small"
              variant="contained"
              disabled={confirmingId === selectedStep.step_id}
              onClick={() => onConfirmStep?.(selectedStep.step_id)}
              sx={{ flex: 1, fontSize: '0.6875rem', textTransform: 'none', py: 0.5 }}
            >
              Approve
            </Button>
            <Button
              size="small"
              variant="outlined"
              disabled={confirmingId === selectedStep.step_id}
              onClick={() => onDeclineStep?.(selectedStep.step_id)}
              sx={{ flex: 1, fontSize: '0.6875rem', textTransform: 'none', py: 0.5 }}
            >
              Skip
            </Button>
          </Stack>
        )}

        {selectedStep.error && (
          <Typography variant="body2" color="error.main" sx={{ fontSize: '0.6875rem', mb: 1 }}>
            {selectedStep.error}
          </Typography>
        )}

        {nextStep && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem', mb: 0.5 }}>
            Next: {nextStep.intent || `Step ${nextStep.step_id}`}
          </Typography>
        )}

        {selectedPhase?.name && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.625rem' }}>
            Stage: {selectedPhase.name}
          </Typography>
        )}
      </Box>
    );
  };

  const summary = `${visibleNodes.length} step${visibleNodes.length !== 1 ? 's' : ''} · ${
    edges.filter((e) => !String(e.source).startsWith('__d')).length
  } link${edges.filter((e) => !String(e.source).startsWith('__d')).length !== 1 ? 's' : ''}${
    attentionSummary ? ` · ${attentionSummary}` : ''
  }`;

  // Enrich nodes with phase_name for structure tooltips / meta row.
  const nodesWithPhase = useMemo(() => {
    if (!structure) return nodes;
    const byId = new Map((phaseBands || []).map((b) => [b.phase_id, b.name]));
    return nodes.map((n) => ({
      ...n,
      phase_name: byId.get(n.phase_id) || n.phase_name,
    }));
  }, [nodes, phaseBands, structure]);

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
        nodes={nodesWithPhase}
        edges={edges}
        width={width}
        layoutHeight={layoutHeight}
        height={height}
        phaseBands={phaseBands}
        phaseColor={phaseColor}
        nodeColor={(n) => (structure
          ? (phaseColor(n.phase_id) || theme.palette.primary.main)
          : colorFor(n.status))}
        renderNode={renderNode}
        nodeShape={resolvePlanNodeShape}
        edgeStyle={resolvePlanEdgeStyle}
        selected={selected}
        onSelect={handleSelectNode}
        selectedEdge={selectedEdge}
        onSelectEdge={handleSelectEdge}
        nodeTitle={nodeTitleTip}
        edgeTitle={edgeTitleTip}
        showStatusPulse={!structure}
        legend={legendEl}
        sidebar={renderDetailPane}
        title={structure ? 'Plan' : 'Plan graph'}
        modalTitle={structure ? 'Plan — full view' : 'Plan graph — full view'}
        summary={summary}
        live={!structure && live}
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
        direction={direction || 'tb'}
        fitMode="contain"
        // Never auto-upscale — meet×zoom>1 blew compact plans into one giant card.
        fitZoomCeil={1}
      />
    </>
  );
}

PlanDagGraph.propTypes = {
  plan: PropTypes.object,
  height: PropTypes.number,
  live: PropTypes.bool,
  fill: PropTypes.bool,
  mode: PropTypes.oneOf(['execution', 'structure']),
  testId: PropTypes.string,
  onConfirmStep: PropTypes.func,
  onDeclineStep: PropTypes.func,
  onRetryStep: PropTypes.func,
  confirmingId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};
