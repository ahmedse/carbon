// src/__tests__/WorkflowGraph.test.jsx
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import WorkflowGraph from '../apps/my/components/WorkflowGraph';

vi.mock('../components/graph/EnterpriseGraph', () => ({
  default: function MockEnterpriseGraph(props) {
    return (
      <div data-testid={props.testId || 'enterprise-graph'}>
        <span data-testid="eg-title">{props.title}</span>
        <span data-testid="eg-summary">{props.summary}</span>
        <span data-testid="eg-live">{String(Boolean(props.live))}</span>
        <span data-testid="eg-nodes">{props.nodes?.length ?? 0}</span>
        <span data-testid="eg-edges">{props.edges?.length ?? 0}</span>
        {props.emptyMessage && !(props.nodes?.length) ? (
          <span data-testid="eg-empty">{props.emptyMessage}</span>
        ) : null}
        {props.legend}
      </div>
    );
  },
}));

const theme = createTheme();

function wrap(ui) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

describe('WorkflowGraph → EnterpriseGraph adapter', () => {
  it('lays out chain + terminal node on the shared Pulse graph surface', () => {
    wrap(
      <WorkflowGraph
        chain={[
          { order: 1, role: 'manager', intent: 'approve', decision: 'auto', user_ids: [] },
          { order: 2, role: 'finance', intent: 'approve', user_ids: [1, 2] },
        ]}
        currentStep={2}
        status="submitted"
      />,
    );
    expect(screen.getByTestId('workflow-graph')).toBeInTheDocument();
    // 2 steps + Completed terminal
    expect(screen.getByTestId('eg-nodes')).toHaveTextContent('3');
    expect(screen.getByTestId('eg-edges')).toHaveTextContent('2');
    expect(screen.getByTestId('eg-live')).toHaveTextContent('true');
  });

  it('shows empty message when chain is missing', () => {
    wrap(<WorkflowGraph chain={[]} />);
    expect(screen.getByTestId('eg-empty')).toBeInTheDocument();
    expect(screen.getByTestId('eg-nodes')).toHaveTextContent('0');
  });
});
