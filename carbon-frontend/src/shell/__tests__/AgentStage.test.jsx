// src/shell/__tests__/AgentStage.test.jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AgentStage, { stageForStatus } from '../AgentStage';

describe('stageForStatus', () => {
  it('maps plan statuses to stages', () => {
    expect(stageForStatus(null)).toBe('idle');
    expect(stageForStatus('discovering')).toBe('clarify');
    expect(stageForStatus('pending_approval')).toBe('review');
    expect(stageForStatus('running')).toBe('run');
    expect(stageForStatus('completed')).toBe('done');
    expect(stageForStatus('cancelled')).toBe('review');
  });

  it('keeps the run stage while a local run phase is active', () => {
    expect(stageForStatus('pending_approval', 'finished')).toBe('run');
    expect(stageForStatus('pending_approval', 'stopped')).toBe('run');
    expect(stageForStatus('approved', 'working')).toBe('run');
    expect(stageForStatus('completed', 'working')).toBe('run');
  });

  it('routes completed plans to done even after finished phase', () => {
    expect(stageForStatus('completed', 'finished')).toBe('done');
    expect(stageForStatus('completed')).toBe('done');
    expect(stageForStatus('completed_with_gaps')).toBe('done');
    expect(stageForStatus('paused')).toBe('run');
  });
});

describe('AgentStage', () => {
  it('renders review body for pending_approval', () => {
    render(
      <AgentStage
        plan={{ id: '1', status: 'pending_approval' }}
        review={<div>Review body</div>}
        run={<div>Run body</div>}
        done={<div>Done body</div>}
      />,
    );
    expect(screen.getByTestId('agent-stage')).toHaveAttribute('data-stage', 'review');
    expect(screen.getByText('Review body')).toBeInTheDocument();
  });

  it('routes to done when all steps finished even if status lagged as running', () => {
    render(
      <AgentStage
        plan={{
          id: '2',
          status: 'running',
          steps: [
            { step_id: 0, status: 'completed' },
            { step_id: 1, status: 'completed' },
          ],
        }}
        review={<div>Review body</div>}
        run={<div>Run body</div>}
        done={<div>Done body</div>}
      />,
    );
    expect(screen.getByTestId('agent-stage')).toHaveAttribute('data-stage', 'done');
    expect(screen.getByText('Done body')).toBeInTheDocument();
  });
});
