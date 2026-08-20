// src/components/graph/PlanDagGraph.jsx
// W3-F — LIVE plan DAG for the AI Workspace (the ENGAGE surface): nodes =
// the current user's own plan steps, edges = depends_on, node color = step
// status. The parent polls the plan during a run and passes fresh data —
// this component is presentational. Theme tokens only (RULE_8); outcome
// labels only (RULE_23). This is NOT the admin topology graph (W3-G).
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Paper, Stack, Typography, useTheme } from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import { buildPlanGraph } from '../../utils/planGraph';
import ForceGraph from './ForceGraph';

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

/**
 * Live plan DAG.
 * @param {object} props
 * @param {object} props.plan - plan payload (GET /ai/plans/{id}/)
 * @param {number} [props.height] - graph viewport height
 * @param {boolean} [props.live] - show the "Live" badge (parent is running)
 * @param {string} [props.testId] - data-testid
 */
export default function PlanDagGraph({ plan, height = 380, live = false, testId = 'plan-dag-graph' }) {
  const theme = useTheme();
  const [selected, setSelected] = useState(null);

  const { nodes, edges, degrees } = useMemo(() => {
    const graph = buildPlanGraph(plan);
    const d = {};
    graph.nodes.forEach((n) => {
      d[n.id] = 0;
    });
    graph.edges.forEach((e) => {
      if (d[e.source] !== undefined) d[e.source] += 1;
      if (d[e.target] !== undefined) d[e.target] += 1;
    });
    return { ...graph, degrees: d };
  }, [plan]);

  const steps = useMemo(() => (Array.isArray(plan?.steps) ? plan.steps : []), [plan]);

  const colorFor = useCallback((node) => planStepStatusColor(node.status, theme), [theme]);
  const radiusFor = useCallback(
    (node) => 8 + Math.min(degrees[node.id] ?? 0, 6) * 1.75,
    [degrees],
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

  const dependsOnLabels = useMemo(() => {
    if (!selected) return '';
    const step = steps.find((s) => s.step_id === selected.id);
    const deps = Array.isArray(step?.depends_on) ? step.depends_on : [];
    return deps
      .map((depId) => {
        const dep = steps.find((s) => s.step_id === depId);
        return dep ? dep.intent || `Step ${dep.step_id}` : null;
      })
      .filter(Boolean)
      .join(', ');
  }, [selected, steps]);

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.25, py: 0.625, borderBottom: 1, borderColor: 'divider' }}
      >
        <AccountTreeOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem' }}>
          Plan graph
        </Typography>
        {live && (
          <Chip size="small" color="primary" variant="outlined" label="Live" sx={{ height: 16, fontSize: '0.5625rem' }} />
        )}
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', whiteSpace: 'nowrap' }}>
          {nodes.length} step{nodes.length !== 1 ? 's' : ''} · {edges.length} link{edges.length !== 1 ? 's' : ''}
        </Typography>
      </Stack>

      <ForceGraph
        nodes={nodes}
        edges={edges}
        nodeColor={colorFor}
        nodeRadius={radiusFor}
        height={height}
        legend={legend}
        onSelect={setSelected}
        selectedId={selected?.id}
        testId={testId}
        ariaLabel="Live plan DAG — steps and their dependencies"
        emptyMessage="This plan has no steps to graph yet."
      />

      {selected && (
        <Box sx={{ px: 1.25, py: 0.625, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem' }}>
            {selected.label}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
            {selected.tool_name ? `Tool: ${selected.tool_name}` : 'No tool'} ·{' '}
            {dependsOnLabels ? `Depends on: ${dependsOnLabels}` : 'No dependencies'}
          </Typography>
        </Box>
      )}
    </Paper>
  );
}

PlanDagGraph.propTypes = {
  plan: PropTypes.object,
  height: PropTypes.number,
  live: PropTypes.bool,
  testId: PropTypes.string,
};
