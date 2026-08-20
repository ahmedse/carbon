// src/__tests__/PlanDiffReviewDialog.test.jsx
// W3-F — diff-review consent gate (RULE_21): summarizes edit outcomes in
// plain language (RULE_23) and requires an explicit "Keep changes" before
// the revised plan is re-approved.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PlanDiffReviewDialog from '../shell/PlanDiffReviewDialog';

const DIFF = {
  added: [{ intent: 'Send a summary email' }],
  removed: [{ intent: 'Search for duplicate records' }],
  changed: [{ old: { intent: 'Create a rule' }, new: { intent: 'Create two rules' } }],
};

describe('PlanDiffReviewDialog', () => {
  it('summarizes the diff in outcome terms', () => {
    render(<PlanDiffReviewDialog open diff={DIFF} />);

    expect(screen.getByText('Review plan changes')).toBeInTheDocument();
    expect(screen.getByText('The revised plan has 1 step added, 1 step removed, 1 step changed.')).toBeInTheDocument();
    expect(screen.getByText('New step: Send a summary email')).toBeInTheDocument();
    expect(screen.getByText('Removed step: Search for duplicate records')).toBeInTheDocument();
    expect(screen.getByText('Changed step: Create a rule')).toBeInTheDocument();
    expect(screen.getByText('now: Create two rules')).toBeInTheDocument();
    // The consent gate never auto-executes.
    expect(screen.getByText('Changes apply only after you confirm. Nothing runs until you approve the revised plan.')).toBeInTheDocument();
  });

  it('confirms the reviewed changes explicitly', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<PlanDiffReviewDialog open diff={DIFF} onConfirm={onConfirm} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole('button', { name: 'Keep changes' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('cancels without mutating', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<PlanDiffReviewDialog open diff={DIFF} onConfirm={onConfirm} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('handles an empty diff gracefully', () => {
    render(<PlanDiffReviewDialog open diff={{ added: [], removed: [], changed: [] }} />);
    expect(screen.getByText('The revised plan keeps the same steps.')).toBeInTheDocument();
  });
});
