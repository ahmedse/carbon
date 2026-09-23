// src/apps/my/components/WorkflowGraph.jsx
// Thin domain adapter over EnterpriseGraph (ADR-0012) — same Pulse agent
// canvas used by PlanDagGraph. Maps correspondence `approver_chain` to a
// linear left→right DAG. Presentational only (no fetch).
import React, { memo, useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Stack, Typography, useTheme } from '@mui/material';
import { useTranslation } from 'react-i18next';
import EnterpriseGraph from '../../../components/graph/EnterpriseGraph';
import { GraphNodeForeign } from '../../../components/graph/GraphNodeLabel';
import { dominantDir } from '../../../components/graph/graphText';
import { codeLabel, ROLE_SUFFIX, INTENT_SUFFIX } from './myRequestsLabels';

/** Layout mirrors EXEC_LAYOUT density (ADR-0012 / planGraph.js) — compact for detail pages. */
const LAYOUT = {
  nodeW: 196,
  nodeH: 72,
  colGap: 36,
  padX: 20,
  padY: 16,
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

/** Origin (employee submit) is complete once the request left draft. */
function originState(status) {
  if (!status || status === 'draft') return 'pending';
  return 'approved';
}

/**
 * Approver-chain workflow graph — EnterpriseGraph adapter.
 * Layout: Submitted (origin) → approver_chain → Completed (terminal).
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

    // Origin: employee submit (not an approver step).
    const origin = originState(status);
    const oMeta = STATE_META[origin];
    present.add(origin);
    built.push({
      id: 'submitted',
      label: t('graphNodeSubmitted'),
      subtitle: t('graphNodeRequester'),
      status: oMeta.status,
      statusKey: origin,
      statusLabel: t(oMeta.label),
      metaText: '',
      colorToken: oMeta.colorToken,
      x: L.padX,
      y: L.padY,
      w: L.nodeW,
      h: L.nodeH,
    });

    steps.forEach((step, index) => {
      const order = Number(step.order ?? 0);
      const state = stepState(step, order, currentStep);
      const meta = STATE_META[state];
      present.add(state);
      if (state === 'current') hasCurrent = true;
      // acting_role: HR (or another backup) standing in for a vacant role.
      const role = codeLabel(t, 'role', ROLE_SUFFIX, step.acting_role || step.role);
      const intent = codeLabel(t, 'intent', INTENT_SUFFIX, step.intent);
      const statusLabel = t(meta.label);
      const approverCount = Array.isArray(step.user_ids) ? step.user_ids.length : 0;
      const isSkipped = state === 'skipped_auto' || state === 'skipped_condition';
      const col = index + 1; // after origin
      built.push({
        id: `step-${index}`,
        label: role,
        subtitle: intent,
        status: meta.status,
        statusKey: state,
        statusLabel,
        metaText: isSkipped ? '' : t('stepperApprovers', { count: approverCount }),
        colorToken: meta.colorToken,
        x: L.padX + col * (L.nodeW + L.colGap),
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

  const nodeShape = useCallback((n) => {
    if (n.id === 'submitted' || n.id === 'terminal') return 'stadium';
    return 'roundedRect';
  }, []);

  const renderNode = useCallback(
    (n) => {
      const color = nodeColor(n);
      const title = String(n.label || '');
      const sub = [n.subtitle, n.metaText].filter(Boolean).join(' · ');
      const rtl = dominantDir(title) === 'rtl';
      const terminal = n.id === 'submitted' || n.id === 'terminal';
      return (
        <>
          {terminal ? null : (
            <rect x={rtl ? n.w - 4 : 0} y={0} width={4} height={n.h} fill={color} />
          )}
          <GraphNodeForeign
            width={n.w}
            height={n.h}
            title={title}
            meta={sub}
            status={n.statusLabel || ''}
            statusColor={color}
            center={terminal}
            fontFamily={theme.typography?.fontFamily}
            color={theme.palette.text.primary}
            tip={`${title}${sub ? ` — ${sub}` : ''} — ${n.statusLabel || ''}`}
          />
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

  const summary = t('graphSummary', { steps: nodes.length, links: edges.length });

  return (
    <EnterpriseGraph
      nodes={nodes}
      edges={edges}
      width={width}
      layoutHeight={layoutHeight}
      height={height}
      phaseBands={[]}
      nodeColor={nodeColor}
      nodeShape={nodeShape}
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
      contentSized
      fitZoomCeil={1.75}
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
  // Fallback only when contentSized is off; live height follows layoutHeight.
  height: 140,
};

export default memo(WorkflowGraph);
