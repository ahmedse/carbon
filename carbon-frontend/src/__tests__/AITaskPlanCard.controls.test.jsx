// src/__tests__/AITaskPlanCard.controls.test.jsx
// W3-F — plan card lifecycle controls: edit brief, per-step edit, pause,
// fork, resume/run labels, live DAG + diagram preview toggle. The Mermaid
// preview is stubbed (it is covered by its own spec); the live d3 DAG runs
// on the real ForceGraph primitive.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AITaskPlanCard from '../shell/AITaskPlanCard';

vi.mock('../components/graph/PlanMermaidPreview', () => ({
  default: () => null,
}));

const handlers = {
  onApprove: vi.fn(),
  onDecline: vi.fn(),
  onRun: vi.fn(),
  onPause: vi.fn(),
  onFork: vi.fn(),
  onEditPlan: vi.fn(),
  onEditStep: vi.fn(),
};

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'Audit the emissions dataset for duplicates.',
  pattern: 'skill_chain',
  source: 'user_request',
  skill_name: 'data_quality',
  needs_confirmation: true,
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', tool_args: { dataset: 'emissions' }, status: 'pending', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', tool_args: { name: 'no_dupes' }, status: 'pending', depends_on: [0] },
  ],
};

const renderCard = (props = {}) =>
  render(<AITaskPlanCard plan={PLAN} {...handlers} {...props} />);

describe('AITaskPlanCard — W3-F controls', () => {
  it('renders the consent gate plus Fork for a pending plan', () => {
    renderCard();
    expect(screen.getByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fork' })).toBeInTheDocument();
  });

  it('shows Run plan for approved and Resume run for paused', () => {
    const { unmount } = renderCard({ plan: { ...PLAN, status: 'approved' } });
    expect(screen.getByRole('button', { name: 'Run plan' })).toBeInTheDocument();
    unmount();

    renderCard({ plan: { ...PLAN, status: 'paused' } });
    expect(screen.getByRole('button', { name: 'Resume run' })).toBeInTheDocument();
  });

  it('shows Pause run while the run is active and wires onPause', () => {
    renderCard({ plan: { ...PLAN, status: 'running' }, running: true });
    fireEvent.click(screen.getByRole('button', { name: 'Pause run' }));
    expect(handlers.onPause).toHaveBeenCalledTimes(1);
  });

  it('forks a plan through the Fork control', () => {
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: 'Fork' }));
    expect(handlers.onFork).toHaveBeenCalledTimes(1);
  });

  it('edits the brief inline and calls onEditPlan', () => {
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: 'Edit plan' }));

    const input = screen.getByLabelText('Plan brief');
    fireEvent.change(input, { target: { value: 'Audit duplicates and triples.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));

    expect(handlers.onEditPlan).toHaveBeenCalledWith('Audit duplicates and triples.');
  });

  it('opens the per-step editor from the step row', () => {
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: 'Edit step 1' }));
    expect(handlers.onEditStep).toHaveBeenCalledWith(PLAN.steps[1]);
  });

  it('renders the live DAG preview and toggles to the diagram view', () => {
    renderCard({ plan: { ...PLAN, status: 'approved' }, live: true });

    // Live DAG is the default preview.
    expect(screen.getByText('Plan graph')).toBeInTheDocument();
    expect(screen.getByText('Live')).toBeInTheDocument();

    const diagramToggle = screen.getByRole('button', { name: 'Diagram' });
    fireEvent.click(diagramToggle);
    expect(diagramToggle.className).toContain('Mui-selected');
  });

  it('labels a forked copy', () => {
    renderCard({ plan: { ...PLAN, forked_from: 'plan-0' } });
    expect(screen.getByText('Forked copy')).toBeInTheDocument();
  });

  it('keeps a completed plan read-only with the audit pointer', () => {
    renderCard({
      plan: { ...PLAN, status: 'completed', final_response: 'Done.', steps: [] },
    });
    expect(screen.getByText('Completed — see the audit ledger for the outcome.')).toBeInTheDocument();
  });
});
