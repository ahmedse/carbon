// src/components/graph/AgentTopologyGraph.jsx
// W3-G — AI Admin topology graph: renders GET /ai/catalog/topology/ — the
// system's DECLARED graph (ADR-001): agents as nodes, declared handoffs as
// edges. This is the OBSERVE surface — no chat, no plan controls.
//
// Pure presentational component reusing the shared ForceGraph primitive
// (RULE: no raw d3 in page components — go through ForceGraph.jsx). Theme
// tokens only (RULE_8); outcome labels only (RULE_23). Mirrors the
// PlanDagGraph (W3-F) header/legend/click-to-inspect structure.
import React, { useCallback, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Paper, Stack, Typography, useTheme } from '@mui/material';
import SchemaOutlinedIcon from '@mui/icons-material/SchemaOutlined';
import { chartPalette } from '../../theme/carbonTheme';
import ForceGraph from './ForceGraph';

/** Declared agent roles (backend AGENT_ROLES — engine/core/models.py). */
export const AGENT_ROLES = [
  'orchestrator',
  'researcher',
  'planner',
  'critic',
  'domain_specialist',
];

/** Role → theme color token map (RULE_8 — chartPalette, never raw hex). */
const ROLE_COLORS = {
  orchestrator: chartPalette.blue,
  researcher: chartPalette.green,
  planner: chartPalette.purple,
  critic: chartPalette.orange,
  domain_specialist: chartPalette.teal,
};

/**
 * Agent role → chartPalette color token (exported for tests).
 * @param {string} role
 * @returns {string} theme color token
 */
export function agentRoleColor(role) {
  return ROLE_COLORS[role] || chartPalette.gray;
}

/**
 * Declared agent topology (agents + handoffs).
 * @param {object} props
 * @param {{nodes: Array<{id,name,role,status}>, edges: Array<{from,to,description,max_parallel}>}} props.topology
 * @param {number} [props.height] - graph viewport height
 * @param {string} [props.testId] - data-testid
 */
export default function AgentTopologyGraph({
  topology,
  height = 420,
  testId = 'agent-topology-graph',
}) {
  const theme = useTheme();
  const [selected, setSelected] = useState(null);

  const nodes = useMemo(
    () =>
      (Array.isArray(topology?.nodes) ? topology.nodes : []).map((n) => ({
        id: n.id,
        label: n.name,
        subtitle: `${n.role} · ${n.status}`,
        role: n.role,
        status: n.status,
      })),
    [topology],
  );

  const edges = useMemo(
    () =>
      (Array.isArray(topology?.edges) ? topology.edges : []).map((e) => ({
        source: e.from,
        target: e.to,
        label: e.description || '',
      })),
    [topology],
  );

  const nodesById = useMemo(() => {
    const m = {};
    nodes.forEach((n) => {
      m[n.id] = n;
    });
    return m;
  }, [nodes]);

  const degrees = useMemo(() => {
    const d = {};
    nodes.forEach((n) => {
      d[n.id] = 0;
    });
    edges.forEach((e) => {
      if (d[e.source] !== undefined) d[e.source] += 1;
      if (d[e.target] !== undefined) d[e.target] += 1;
    });
    return d;
  }, [nodes, edges]);

  const colorFor = useCallback(
    (node) => {
      // Inactive agents read gray regardless of role — no work is routed to
      // them while disabled. RULE_23: status shown, no internal detail.
      if (node.status && node.status !== 'active') return theme.palette.text.disabled;
      return agentRoleColor(node.role);
    },
    [theme],
  );

  const radiusFor = useCallback(
    (node) => 8 + Math.min(degrees[node.id] ?? 0, 6) * 1.75,
    [degrees],
  );

  const legend = useMemo(
    () =>
      AGENT_ROLES.map((role) => ({ label: role, color: agentRoleColor(role) })),
    [],
  );

  const handoffSummary = useMemo(() => {
    if (!selected) return '';
    const outgoing = edges.filter((e) => e.source === selected.id).length;
    const incoming = edges.filter((e) => e.target === selected.id).length;
    return `${outgoing} outgoing · ${incoming} incoming handoff${outgoing + incoming === 1 ? '' : 's'}`;
  }, [selected, edges]);

  const selectedName = selected ? selected.label : '';
  const selectedSub = selected
    ? nodesById[selected.id]
      ? `${nodesById[selected.id].subtitle}`
      : ''
    : '';

  return (
    <Paper variant="outlined" sx={{ bgcolor: 'background.paper', overflow: 'hidden' }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.25, py: 0.625, borderBottom: 1, borderColor: 'divider' }}
      >
        <SchemaOutlinedIcon sx={{ fontSize: 15, color: 'text.secondary' }} />
        <Typography variant="body2" sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: '0.75rem' }}>
          Agent topology
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem', whiteSpace: 'nowrap' }}>
          {nodes.length} agent{nodes.length !== 1 ? 's' : ''} · {edges.length} handoff{edges.length !== 1 ? 's' : ''}
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
        ariaLabel="Declared agent topology — agents and their handoffs"
        emptyMessage="No agents registered — the declared topology is empty."
      />

      {selected && (
        <Box sx={{ px: 1.25, py: 0.625, borderTop: 1, borderColor: 'divider' }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem' }}>
              {selectedName}
            </Typography>
            {selectedSub && (
              <Chip
                size="small"
                label={selectedSub}
                sx={{
                  height: 16,
                  fontSize: '0.5625rem',
                  color: colorFor(selected),
                  borderColor: colorFor(selected),
                  bgcolor: 'transparent',
                  '& .MuiChip-label': { px: 0.75 },
                }}
                variant="outlined"
              />
            )}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.6875rem' }}>
            {handoffSummary || 'No declared handoffs'}
          </Typography>
        </Box>
      )}
    </Paper>
  );
}

AgentTopologyGraph.propTypes = {
  topology: PropTypes.shape({
    nodes: PropTypes.array,
    edges: PropTypes.array,
  }),
  height: PropTypes.number,
  testId: PropTypes.string,
};
