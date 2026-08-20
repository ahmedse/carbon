// src/__tests__/AgentTopologyGraph.test.jsx
// W3-G — AI Admin topology graph spec (admin graph spec): renders the
// DECLARED agent topology (GET /ai/catalog/topology/) through the shared
// ForceGraph primitive — nodes/edges mapping, role legend chips, counts,
// empty state, and the pure role→color map. The d3 force simulation runs on
// the real ForceGraph primitive (jsdom-safe, mirroring PlanDagGraph.test.jsx).
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import AgentTopologyGraph, { agentRoleColor, AGENT_ROLES } from '../components/graph/AgentTopologyGraph';
import { chartPalette } from '../theme/carbonTheme';

const theme = createTheme();

const TOPOLOGY = {
  nodes: [
    { id: 'a1', name: 'Architect', role: 'orchestrator', status: 'active' },
    { id: 'a2', name: 'Finder', role: 'researcher', status: 'active' },
  ],
  edges: [
    { from: 'a1', to: 'a2', description: 'delegates search', max_parallel: 2 },
  ],
};

const renderGraph = (props) =>
  render(
    <ThemeProvider theme={theme}>
      <AgentTopologyGraph {...props} />
    </ThemeProvider>,
  );

describe('AgentTopologyGraph', () => {
  it('renders the declared topology header, counts and role legend chips', () => {
    renderGraph({ topology: TOPOLOGY });

    expect(screen.getByText('Agent topology')).toBeInTheDocument();
    expect(screen.getByText('2 agents · 1 handoff')).toBeInTheDocument();
    // ForceGraph legend = one chip per declared role.
    expect(screen.getByText('orchestrator')).toBeInTheDocument();
    expect(screen.getByText('researcher')).toBeInTheDocument();
    expect(screen.getByTestId('agent-topology-graph')).toBeInTheDocument();
  });

  it('shows an empty state when the topology has no nodes', () => {
    renderGraph({ topology: { nodes: [], edges: [] } });
    expect(
      screen.getByText('No agents registered — the declared topology is empty.'),
    ).toBeInTheDocument();
  });

  it('exposes the declared role list for the admin role dropdown', () => {
    expect(AGENT_ROLES).toEqual([
      'orchestrator',
      'researcher',
      'planner',
      'critic',
      'domain_specialist',
    ]);
  });
});

describe('agentRoleColor', () => {
  it('maps declared roles to chartPalette tokens (never raw hex)', () => {
    expect(agentRoleColor('orchestrator')).toBe(chartPalette.blue);
    expect(agentRoleColor('researcher')).toBe(chartPalette.green);
    expect(agentRoleColor('planner')).toBe(chartPalette.purple);
    expect(agentRoleColor('critic')).toBe(chartPalette.orange);
    expect(agentRoleColor('domain_specialist')).toBe(chartPalette.teal);
  });

  it('falls back to gray for unknown roles', () => {
    expect(agentRoleColor('mystery_role')).toBe(chartPalette.gray);
    expect(agentRoleColor(undefined)).toBe(chartPalette.gray);
  });
});
