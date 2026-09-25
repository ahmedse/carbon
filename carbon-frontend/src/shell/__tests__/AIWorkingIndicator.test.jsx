/**
 * ADR-0054 — the thinking header states the cost, the list states the actions.
 */
import React from 'react';
import { expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AIWorkingIndicator from '../AIWorkingIndicator';

const STEPS = ['You asked for the split, so I will read it.', 'Reading the workforce breakdown…'];

test('a finished turn shows elapsed time and step count', () => {
  render(<AIWorkingIndicator done collapsible seconds={5} history={STEPS} />);
  expect(screen.getByText('Thought for 5s · 2 steps')).toBeInTheDocument();
});

test('an unknown duration still names the step count', () => {
  render(<AIWorkingIndicator done collapsible history={['one']} />);
  expect(screen.getByText('Thought · 1 step')).toBeInTheDocument();
});

test('expanding lists every action in order', async () => {
  const onToggle = vi.fn();
  const { rerender } = render(
    <AIWorkingIndicator done collapsible seconds={2} history={STEPS} onToggle={onToggle} />,
  );
  await userEvent.click(screen.getByRole('button'));
  expect(onToggle).toHaveBeenCalled();
  rerender(
    <AIWorkingIndicator done collapsible expanded seconds={2} history={STEPS} onToggle={onToggle} />,
  );
  expect(screen.getByText(STEPS[0])).toBeInTheDocument();
  expect(screen.getByText(STEPS[1])).toBeInTheDocument();
});

test('a working turn shows the live stage, not a duration', () => {
  render(<AIWorkingIndicator stage="Reading the workforce breakdown…" history={[]} />);
  expect(screen.getByText('Reading the workforce breakdown…')).toBeInTheDocument();
  expect(screen.queryByText(/Thought/)).not.toBeInTheDocument();
});
