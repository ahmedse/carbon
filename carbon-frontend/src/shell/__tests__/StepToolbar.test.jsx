// src/shell/__tests__/StepToolbar.test.jsx
// U-2 — per-step control toolbar. Verifies the status→controls state machine
// (which buttons render for each step status), that a click calls the matching
// handler with the step id AND stops propagation (never toggles the row), and
// that every control is disabled while busy.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StepToolbar } from '../AITaskPanel';

const HANDLERS = () => ({
  onRetry: vi.fn(),
  onSkip: vi.fn(),
  onCancel: vi.fn(),
  onPause: vi.fn(),
  onResume: vi.fn(),
});

function renderToolbar(status, overrides = {}) {
  const handlers = HANDLERS();
  const onRowClick = vi.fn();
  render(
    <div onClick={onRowClick}>
      <StepToolbar step={{ step_id: 7, status }} {...handlers} {...overrides} />
    </div>,
  );
  return { handlers, onRowClick };
}

describe('StepToolbar — status → controls state machine', () => {
  const CASES = {
    pending: ['Retry', 'Pause', 'Resume', 'Skip', 'Cancel'],
    running: ['Retry', 'Pause', 'Resume', 'Cancel'],
    paused: ['Retry', 'Pause', 'Resume', 'Skip', 'Cancel'],
    failed: ['Retry', 'Pause', 'Resume', 'Skip'],
    completed: ['Retry', 'Pause', 'Resume'],
    awaiting_approval: ['Retry', 'Pause', 'Resume'],
  };

  for (const [status, labels] of Object.entries(CASES)) {
    it(`renders exactly [${labels.join(', ')}] for status "${status}"`, () => {
      renderToolbar(status);
      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(labels.length);
      for (const label of labels) {
        expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
      }
    });
  }

});

describe('StepToolbar — actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls the matching handler with the step id and stops propagation', () => {
    const { handlers, onRowClick } = renderToolbar('paused');

    fireEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(handlers.onResume).toHaveBeenCalledWith(7);

    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));
    expect(handlers.onSkip).toHaveBeenCalledWith(7);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(handlers.onCancel).toHaveBeenCalledWith(7);

    // Row toggle must never fire — every control stops propagation.
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it('routes Retry and Pause to their own handlers', () => {
    const { handlers } = renderToolbar('failed');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(handlers.onRetry).toHaveBeenCalledWith(7);

    const { handlers: running } = renderToolbar('running');
    const pauses = screen.getAllByRole('button', { name: 'Pause' });
    fireEvent.click(pauses[pauses.length - 1]);
    expect(running.onPause).toHaveBeenCalledWith(7);
  });

  it('disables every control and fires nothing when busy', () => {
    const { handlers } = renderToolbar('paused', { busy: true });
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(5);
    for (const button of buttons) {
      expect(button).toBeDisabled();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));
    expect(handlers.onSkip).not.toHaveBeenCalled();
  });
});
