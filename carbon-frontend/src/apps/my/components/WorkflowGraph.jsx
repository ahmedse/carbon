// src/apps/my/components/WorkflowGraph.jsx
// Thin domain adapter over EnterpriseGraph (ADR-0012) — same Pulse agent
// canvas used by PlanDagGraph. Maps correspondence `approver_chain` to a
// linear left→right DAG. Presentational only (no fetch).
import React, { memo, useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Stack, Typography, useTheme } from '@mui/material';
import { useTranslation } from 'react-i18next';
import EnterpriseGraph from '../../../components/graph/EnterpriseGraph';
import { codeLabel, ROLE_SUFFIX, INTENT_SUFFIX } from './myRequestsLabels';

/** Layout mirrors EXEC_LAYOUT density (ADR-0012 / planGraph.js). */
const LAYOUT = {
  nodeW: 200,
  nodeH: 58,
  colGap: 56,
  padX: 28,
  padY: 32,
};

/**
 * Approver decision / position → EnterpriseGraph node.status (drives pulse +
 * border accent via nodeColor). Labels stay in text (RULE_5).
 */
const STATE_META = {
  current: { status: 'running', colorToken: 'primary.main', label: 'graphNodeCurrent' },
  approved: { status: 'completed', colorToken: 'success.main', label: 'graphNodeApproved' },
  acknowledged: { status: 'completed', colorToken: 'info.main', label: 'graphNodeAcknowledged' },
  reviewed: { status: 'completed', colorToken: 'secondary.main', label: 'graphNodeReviewed' },
  rejected: { status: 'failed', colorToken: 'error.main', label: 'graphNodeRejected' },
  sent_back: { status: 'awaiting_approval', colorToken: 'warning.main', label: 'graphNodeSentBack' },
  skipped_auto: { status: 'skipped', colorToken: 'text.disabled', label: 'graphNodeSkippedAuto' },
  skipped_condition: {
    status: 'skipped',
    colorToken: 'text.disabled',
    label: 'graphNodeSkippedCondition',
  },
  pending: { status: 'pending', colorToken: 'text.disabled', label: 'graphNodePending' },
};

const STATE_ORDER = [
  'current',
  'approved',
  'acknowledged',
  'reviewed',
  'rejected',
  'sent_back',
  'skipped_auto',
  'skipped_condition',
  'pending',
];

function resolveToken(theme, token) {
  if (!token || typeof token !== 'string') return theme.palette.text.disabled;
  return token.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), theme.palette)
    || theme.palette.text.disabled;
}

function stepState(step, order, currentStep) {
  const decision = step?.decision;
  if (decision === 'skip') return 'skipped_condition';
  if (decision === 'auto') return 'skipped_auto';
  if (decision === 'approved') return 'approved';
  if (decision === 'acknowledged') return 'acknowledged';
  if (decision === 'reviewed') return 'reviewed';
  if (decision === 'rejected') return 'rejected';
  if (decision === 'sent_back') return 'sent_back';
  if (currentStep != null && Number(order) === Number(currentStep)) return 'current';
  return 'pending';
}

function terminalState(status) {
  if (status === 'approved') return 'approved';
  if (status === 'rejected') return 'rejected';
  return 'pending';
}

/**
 * Approver-chain workflow graph — EnterpriseGraph adapter.
 * @param {Array} props.chain
 * @param {number} [props.currentStep]
 * @param {string} [props.status]
 * @param {number} [props.height]
 */
function WorkflowGraph({ chain, currentStep, status, height }) {
  const { t } = useTranslation('my');
  const theme = useTheme();
  const [selected, setSelected] = useState(null);

  const steps = useMemo(() => {
    const list = Array.isArray(chain) ? chain : [];
    return [...list].sort((a, b) => Number(a.order ?? 0) - Number(b.order ?? 0));
  }, [chain]);

  const { nodes, edges, width, layoutHeight, presentStates, live } = useMemo(() => {
    if (steps.length === 0) {
      return {
        nodes: [],
        edges: [],
        width: 480,
        layoutHeight: 160,
        presentStates: new Set(),
        live: false,
      };
    }

    const L = LAYOUT;
    const built = [];
    const present = new Set();
    let hasCurrent = false;

    steps.forEach((step, index) => {
      const order = Number(step.order ?? 0);
      const state = stepState(step, order, currentStep);
      const meta = STATE_META[state];
      present.add(state);
      if (state === 'current') hasCurrent = true;
      const role = codeLabel(t, 'role', ROLE_SUFFIX, step.role);
      const intent = codeLabel(t, 'intent', INTENT_SUFFIX, step.intent);
      const statusLabel = t(meta.label);
      const approverCount = Array.isArray(step.user_ids) ? step.user_ids.length : 0;
      const isSkipped = state === 'skipped_auto' || state === 'skipped_condition';
      built.push({
        id: `step-${index}`,
        label: role,
        subtitle: intent,
        status: meta.status,
        statusKey: state,
        statusLabel,
        metaText: isSkipped ? '' : t('stepperApprovers', { count: approverCount }),
        colorToken: meta.colorToken,
        x: L.padX + index * (L.nodeW + L.colGap),
        y: L.padY,
        w: L.nodeW,
        h: L.nodeH,
      });
    });

    const terminal = terminalState(status);
    const tMeta = STATE_META[terminal];
    present.add(terminal);
    const termIndex = built.length;
    built.push({
      id: 'terminal',
      label: t('graphNodeCompleted'),
      subtitle: '',
      status: tMeta.status,
      statusKey: terminal,
      statusLabel: t(tMeta.label),
      metaText: '',
      colorToken: tMeta.colorToken,
      x: L.padX + termIndex * (L.nodeW + L.colGap),
      y: L.padY,
      w: L.nodeW,
      h: L.nodeH,
    });

    const linkEdges = [];
    for (let i = 0; i < built.length - 1; i += 1) {
      const s = built[i];
      const tgt = built[i + 1];
      linkEdges.push({
        source: s.id,
        target: tgt.id,
        sourceX: s.x + s.w,
        sourceY: s.y + s.h / 2,
        targetX: tgt.x,
        targetY: tgt.y + tgt.h / 2,
      });
    }

    const graphW = L.padX * 2 + built.length * L.nodeW + (built.length - 1) * L.colGap;
    const graphH = L.padY * 2 + L.nodeH;

    return {
      nodes: built,
      edges: linkEdges,
      width: graphW,
      layoutHeight: graphH,
      presentStates: present,
      live: hasCurrent,
    };
  }, [steps, currentStep, status, t]);

  const nodeColor = useCallback(
    (n) => resolveToken(theme, n.colorToken || 'text.disabled'),
    [theme],
  );

  const renderNode = useCallback(
    (n) => {
      const color = nodeColor(n);
      const titleMax = Math.max(8, Math.floor((n.w - 78) / 6.6));
      const rawTitle = String(n.label || '');
      const title = rawTitle.length > titleMax ? `${rawTitle.slice(0, titleMax - 1)}…` : rawTitle;
      const statusText = String(n.statusLabel || '').toUpperCase();
      const sub = n.subtitle || n.metaText || '';
      const subMax = Math.max(8, Math.floor((n.w - 28) / 5.6));
      const subShown = sub.length > subMax ? `${sub.slice(0, subMax - 1)}…` : sub;
      return (
        <>
          <rect x={4} y={6} width={3} height={n.h - 12} rx={1.5} fill={color} />
          <text x={16} y={n.h / 2 - 2} fontSize={13} fontWeight={650} fill={theme.palette.text.primary}>
            {title}
          </text>
          <text x={n.w - 10} y={n.h / 2 + 1} fontSize={10} fontWeight={700} fill={color} textAnchor="end">
            {statusText}
          </text>
          {subShown ? (
            <text x={16} y={n.h / 2 + 14} fontSize={11} fill={theme.palette.text.secondary}>
              {subShown}
            </text>
          ) : null}
        </>
      );
    },
    [nodeColor, theme],
  );

  const nodeAriaLabel = useCallback(
    (n) => `${n.label}${n.subtitle ? ` — ${n.subtitle}` : ''} — ${n.statusLabel}`,
    [],
  );

  const legendEl = useMemo(() => {
    const items = STATE_ORDER.filter((s) => presentStates.has(s)).map((s) => ({
      key: s,
      label: t(STATE_META[s].label),
      color: resolveToken(theme, STATE_META[s].colorToken),
    }));
    if (items.length === 0) return null;
    return (
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        sx={{ flexWrap: 'wrap', rowGap: 0.25, px: 1, py: 0.5 }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem', mr: 0.5 }}>
          {t('graphLegend')}
        </Typography>
        {items.map((l) => (
          <Stack key={l.key} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: l.color }} />
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
              {l.label}
            </Typography>
          </Stack>
        ))}
      </Stack>
    );
  }, [presentStates, t, theme]);

  const summary = `${nodes.length} step${nodes.length !== 1 ? 's' : ''} · ${edges.length} link${edges.length !== 1 ? 's' : ''}`;

  return (
    <EnterpriseGraph
      nodes={nodes}
      edges={edges}
      width={width}
      layoutHeight={layoutHeight}
      height={height}
      phaseBands={[]}
      nodeColor={nodeColor}
      renderNode={renderNode}
      selected={selected}
      onSelect={setSelected}
      legend={legendEl}
      title={t('graphTitle')}
      modalTitle={t('graphTitle')}
      summary={summary}
      live={live}
      emptyMessage={t('graphEmpty')}
      nodeAriaLabel={nodeAriaLabel}
      markerId="workflow-arrow"
      modalMarkerId="workflow-arrow-modal"
      testId="workflow-graph"
      modalTestId="workflow-graph-modal"
      modalCloseTestId="workflow-graph-modal-close"
      expandTestId="workflow-graph-expand"
      exportFileName="approval-workflow"
      fill={false}
    />
  );
}

WorkflowGraph.propTypes = {
  chain: PropTypes.array,
  currentStep: PropTypes.number,
  status: PropTypes.string,
  height: PropTypes.number,
};

WorkflowGraph.defaultProps = {
  chain: [],
  currentStep: null,
  status: null,
  height: 220,
};

export default memo(WorkflowGraph);
