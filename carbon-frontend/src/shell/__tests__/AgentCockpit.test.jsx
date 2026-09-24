// src/shell/__tests__/AgentCockpit.test.jsx
// Task screens — Now · Plan · Result.
import React, { useState } from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentCockpit, { defaultCockpitSegment, normalizeCockpitSegment } from '../AgentCockpit';

const bodyRenderers = () => ({
  renderPlan: () => <div data-testid="body-plan">PLAN</div>,
  renderRun: () => <div data-testid="body-run">RUN</div>,
  renderOutput: () => <div data-testid="body-output">OUTPUT</div>,
});

function Harness({ initial = 'run', resultReady = false, ...props }) {
  const [segment, setSegment] = useState(initial);
  return (
    <AgentCockpit
      segment={segment}
      onSegment={setSegment}
      resultReady={resultReady}
      {...bodyRenderers()}
      {...props}
    />
  );
}

describe('AgentCockpit — segmented control', () => {
  it('renders Now, Plan and a dimmed Result until an outcome exists', () => {
    const { rerender } = render(<Harness />);
    expect(screen.getByRole('button', { name: 'Now' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Plan' })).toBeInTheDocument();
    const result = screen.getByRole('button', { name: 'Result' });
    expect(result).toBeDisabled();
    expect(result).toHaveAttribute('data-dimmed', 'true');
    expect(screen.queryByRole('button', { name: 'Journey' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Execution' })).not.toBeInTheDocument();
    rerender(<Harness resultReady />);
    const ready = screen.getByRole('button', { name: 'Result' });
    expect(ready).not.toBeDisabled();
    expect(ready).not.toHaveAttribute('data-dimmed');
  });

  it('shows exactly one hero test-id at a time', () => {
    render(<Harness initial="run" />);
    expect(screen.getByTestId('agent-cockpit-hero-run')).toBeInTheDocument();
    expect(screen.queryByTestId('agent-cockpit-hero-plan')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-cockpit-hero-output')).not.toBeInTheDocument();
  });

  it.each([
    ['Plan', 'agent-cockpit-hero-plan', 'body-plan'],
    ['Now', 'agent-cockpit-hero-run', 'body-run'],
  ])('switching to %s renders %s', (label, heroId, bodyId) => {
    render(<Harness initial="plan" />);
    fireEvent.click(screen.getByRole('button', { name: label }));
    expect(screen.getByTestId(heroId)).toBeInTheDocument();
    expect(screen.getByTestId(bodyId)).toBeInTheDocument();
  });

  it('switching to Result renders output when ready', () => {
    render(<Harness initial="plan" resultReady />);
    fireEvent.click(screen.getByRole('button', { name: 'Result' }));
    expect(screen.getByTestId('agent-cockpit-hero-output')).toBeInTheDocument();
    expect(screen.getByTestId('body-output')).toBeInTheDocument();
  });
});

describe('AgentCockpit — inherited Chat context', () => {
  it('shows carried conversation details on Plan (not Result)', () => {
    const plan = {
      id: 'p1',
      inherited_context: [{ key: 'amount', value: '3000' }],
    };
    const { unmount } = render(
      <Harness initial="plan" plan={plan} resultReady />,
    );
    const panel = screen.getByTestId('agent-run-inherited-context');
    expect(panel).toHaveTextContent(/Carried from this conversation/i);
    expect(panel).toHaveTextContent(/Amount · 3000/);
    expect(panel).not.toHaveTextContent(/ConversationState|Pulse|slots/i);
    unmount();

    render(<Harness initial="output" plan={plan} resultReady />);
    expect(screen.queryByTestId('agent-run-inherited-context')).not.toBeInTheDocument();
  });
});

describe('AgentCockpit — no library overflow', () => {
  it('does not render Library / Templates / Scheduled controls', () => {
    render(<Harness />);
    expect(screen.queryByRole('button', { name: 'Library' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Templates' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Scheduled' })).not.toBeInTheDocument();
  });
});

describe('defaultCockpitSegment / normalizeCockpitSegment', () => {
  it('maps lifecycle to soft defaults', () => {
    expect(defaultCockpitSegment('pending_approval', 'idle')).toBe('plan');
    expect(defaultCockpitSegment('running', 'working')).toBe('run');
    expect(defaultCockpitSegment('paused', 'paused')).toBe('run');
    expect(defaultCockpitSegment('completed', 'finished')).toBe('output');
    expect(defaultCockpitSegment('failed', 'error')).toBe('output');
    expect(defaultCockpitSegment('cancelled', 'stopped')).toBe('output');
    expect(defaultCockpitSegment('cancelled', 'idle')).toBe('plan');
  });

  it('does not jump to Output on false finished with unsettled status', () => {
    expect(defaultCockpitSegment('failed', 'finished')).toBe('output');
    expect(defaultCockpitSegment('approved', 'finished')).toBe('run');
    expect(defaultCockpitSegment('running', 'finished')).toBe('run');
  });

  it('migrates legacy segment ids', () => {
    expect(normalizeCockpitSegment('steps')).toBe('run');
    expect(normalizeCockpitSegment('metrics')).toBe('output');
    expect(normalizeCockpitSegment('canvas')).toBe('plan');
  });
});
