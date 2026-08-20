// src/__tests__/PlanDagGraph.test.jsx
// W3-F — live plan DAG: nodes = steps, edges = depends_on, node color =
// step status via theme tokens, legend, live badge, empty state. The d3
// force simulation runs on the real ForceGraph primitive (jsdom-safe).
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import PlanDagGraph, { planStepStatusColor } from '../components/graph/PlanDagGraph';

const theme = createTheme();

const PLAN = {
  id: 'plan-1',
  status: 'running',
  brief: 'Audit duplicates.',
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', status: 'completed', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', status: 'running', depends_on: [0] },
    { step_id: 2, intent: 'Report the findings', tool_name: 'search_entity', status: 'pending', depends_on: [0, 1] },
  ],
};

const renderGraph = (props) =>
  render(
    <ThemeProvider theme={theme}>
      <PlanDagGraph {...props} />
    </ThemeProvider>,
  );

describe('PlanDagGraph', () => {
  it('renders the DAG with step/link counts and legend chips', () => {
    renderGraph({ plan: PLAN });

    expect(screen.getByTestId('plan-dag-graph')).toBeInTheDocument();
    expect(screen.getByText('Plan graph')).toBeInTheDocument();
    expect(screen.getByText('3 steps · 3 links')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Needs approval')).toBeInTheDocument();
    expect(screen.getByText('Finished')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('shows the Live badge only while the run is live', () => {
    const { rerender } = renderGraph({ plan: PLAN, live: true });
    expect(screen.getByText('Live')).toBeInTheDocument();

    rerender(
      <ThemeProvider theme={theme}>
        <PlanDagGraph plan={PLAN} live={false} />
      </ThemeProvider>,
    );
    expect(screen.queryByText('Live')).not.toBeInTheDocument();
  });

  it('shows an empty state when the plan has no steps', () => {
    renderGraph({ plan: { id: 'plan-x', steps: [] } });
    expect(screen.getByText('This plan has no steps to graph yet.')).toBeInTheDocument();
  });
});

describe('planStepStatusColor', () => {
  it('maps step statuses to theme tokens (never raw hex)', () => {
    expect(planStepStatusColor('completed', theme)).toBe(theme.palette.success.main);
    expect(planStepStatusColor('running', theme)).toBe(theme.palette.primary.main);
    expect(planStepStatusColor('awaiting_approval', theme)).toBe(theme.palette.warning.main);
    expect(planStepStatusColor('failed', theme)).toBe(theme.palette.error.main);
    expect(planStepStatusColor('skipped', theme)).toBe(theme.palette.text.disabled);
    expect(planStepStatusColor('pending', theme)).toBe(theme.palette.text.disabled);
    expect(planStepStatusColor('unknown-status', theme)).toBe(theme.palette.text.disabled);
  });
});
