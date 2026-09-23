// src/shell/__tests__/AgentCockpit.test.jsx
// ADR-0043 — Plan · Run · Canvas · Output exclusive heroes.
import React, { useState } from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AgentCockpit, { defaultCockpitSegment, normalizeCockpitSegment } from '../AgentCockpit';

const bodyRenderers = () => ({
  renderPlan: () => <div data-testid="body-plan">PLAN</div>,
  renderRun: () => <div data-testid="body-run">RUN</div>,
  renderCanvas: () => <div data-testid="body-canvas">CANVAS</div>,
  renderOutput: () => <div data-testid="body-output">OUTPUT</div>,
});

function Harness({ initial = 'run', ...props }) {
  const [segment, setSegment] = useState(initial);
  return (
    <AgentCockpit segment={segment} onSegment={setSegment} {...bodyRenderers()} {...props} />
  );
}

describe('AgentCockpit — segmented control', () => {
  const SEGMENTS = ['Plan', 'Run', 'Canvas', 'Output'];

  it('renders all four segments', () => {
    render(<Harness />);
    for (const label of SEGMENTS) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('shows exactly one hero test-id at a time', () => {
    render(<Harness initial="run" />);
    expect(screen.getByTestId('agent-cockpit-hero-run')).toBeInTheDocument();
    expect(screen.queryByTestId('agent-cockpit-hero-plan')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-cockpit-hero-canvas')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-cockpit-hero-output')).not.toBeInTheDocument();
  });

  it.each([
    ['Plan', 'agent-cockpit-hero-plan', 'body-plan'],
    ['Canvas', 'agent-cockpit-hero-canvas', 'body-canvas'],
    ['Output', 'agent-cockpit-hero-output', 'body-output'],
    ['Run', 'agent-cockpit-hero-run', 'body-run'],
  ])('switching to %s renders %s', (label, heroId, bodyId) => {
    render(<Harness initial="plan" />);
    fireEvent.click(screen.getByRole('button', { name: label }));
    expect(screen.getByTestId(heroId)).toBeInTheDocument();
    expect(screen.getByTestId(bodyId)).toBeInTheDocument();
  });
});

describe('AgentCockpit — inherited Chat context', () => {
  it('shows carried conversation details on every segment', () => {
    render(
      <Harness
        plan={{
          id: 'p1',
          inherited_context: [{ key: 'amount', value: '3000' }],
        }}
      />,
    );
    const panel = screen.getByTestId('agent-run-inherited-context');
    expect(panel).toHaveTextContent(/Carried from this conversation/i);
    expect(panel).toHaveTextContent(/Amount · 3000/);
    expect(panel).not.toHaveTextContent(/ConversationState|Pulse|slots/i);
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
    expect(normalizeCockpitSegment('canvas')).toBe('canvas');
  });
});
