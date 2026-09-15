// src/shell/__tests__/AgentCockpit.test.jsx
// U-1 — the presentational run-cockpit shell (DESIGN-AGENT-WORKFLOW-AND-UI §6).
// Verifies the four segments render and switch the body, the Library overflow
// exposes Templates/Scheduled/classic-view and fires their callbacks, and the
// parent-supplied run header (global toolbar) renders and routes clicks. Pure
// layout — no network, no AITaskPanel contexts.
import React, { useState } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentCockpit from '../AgentCockpit';

const bodyRenderers = () => ({
  renderPlan: () => <div data-testid="body-plan">PLAN</div>,
  renderSteps: () => <div data-testid="body-steps">STEPS</div>,
  renderOutput: () => <div data-testid="body-output">OUTPUT</div>,
  renderMetrics: () => <div data-testid="body-metrics">METRICS</div>,
});

// Controlled harness so clicking a segment actually re-renders the body.
function Harness({ initial = 'steps', ...props }) {
  const [segment, setSegment] = useState(initial);
  return (
    <AgentCockpit segment={segment} onSegment={setSegment} {...bodyRenderers()} {...props} />
  );
}

describe('AgentCockpit — segmented control', () => {
  const SEGMENTS = ['Plan', 'Steps', 'Output', 'Metrics'];

  it('renders all four segments', () => {
    render(<Harness />);
    for (const label of SEGMENTS) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('shows the Steps body by default', () => {
    render(<Harness />);
    expect(screen.getByTestId('body-steps')).toBeInTheDocument();
    expect(screen.queryByTestId('body-plan')).not.toBeInTheDocument();
  });

  it.each([
    ['Plan', 'body-plan'],
    ['Output', 'body-output'],
    ['Metrics', 'body-metrics'],
    ['Steps', 'body-steps'],
  ])('switching to %s renders %s', (label, testId) => {
    render(<Harness initial="plan" />);
    fireEvent.click(screen.getByRole('button', { name: label }));
    expect(screen.getByTestId(testId)).toBeInTheDocument();
  });
});

describe('AgentCockpit — Library overflow', () => {
  beforeEach(() => vi.clearAllMocks());

  it('exposes Templates, Scheduled and classic-view and fires their callbacks', () => {
    const onOpenTemplates = vi.fn();
    const onOpenScheduled = vi.fn();
    const onSwitchToClassic = vi.fn();
    render(
      <Harness
        onOpenTemplates={onOpenTemplates}
        onOpenScheduled={onOpenScheduled}
        onSwitchToClassic={onSwitchToClassic}
      />,
    );

    // Menu is closed until the overflow button is clicked.
    expect(screen.queryByRole('menuitem', { name: 'Templates' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Library' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Templates' }));
    expect(onOpenTemplates).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Library' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Scheduled' }));
    expect(onOpenScheduled).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Library' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Switch to classic view' }));
    expect(onSwitchToClassic).toHaveBeenCalledTimes(1);
  });
});

describe('AgentCockpit — run header', () => {
  it('renders the parent-supplied global run toolbar and routes clicks', () => {
    const onRun = vi.fn();
    const onFork = vi.fn();
    render(
      <Harness
        header={
          <div>
            <button type="button" onClick={onRun}>Run plan</button>
            <button type="button" onClick={onFork}>Fork into a reviewable copy</button>
          </div>
        }
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Run plan' }));
    expect(onRun).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Fork into a reviewable copy' }));
    expect(onFork).toHaveBeenCalledTimes(1);
  });
});
