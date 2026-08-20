// src/__tests__/AITaskPanel.w3c.test.jsx
// W3-F — Workspace plan controls wired to the W3-C endpoints: edit brief /
// edit step go through the diff-review consent gate (RULE_21), pause a
// running plan, fork into a reviewable copy, and resume a paused plan over
// the SSE resume stream.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AITaskPanel from '../shell/AITaskPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const listPlans = vi.fn();
const createPlan = vi.fn();
const getPlan = vi.fn();
const approvePlan = vi.fn();
const declinePlan = vi.fn();
const runPlanStream = vi.fn();
const resumePlanStream = vi.fn();
const pausePlan = vi.fn();
const forkPlan = vi.fn();
const editPlan = vi.fn();
const editPlanStep = vi.fn();
const confirmPlanStep = vi.fn();
const declinePlanStep = vi.fn();
const stopPlan = vi.fn();
const getPlanLedger = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  listPlans: (...args) => listPlans(...args),
  createPlan: (...args) => createPlan(...args),
  getPlan: (...args) => getPlan(...args),
  approvePlan: (...args) => approvePlan(...args),
  declinePlan: (...args) => declinePlan(...args),
  runPlanStream: (...args) => runPlanStream(...args),
  resumePlanStream: (...args) => resumePlanStream(...args),
  pausePlan: (...args) => pausePlan(...args),
  forkPlan: (...args) => forkPlan(...args),
  editPlan: (...args) => editPlan(...args),
  editPlanStep: (...args) => editPlanStep(...args),
  confirmPlanStep: (...args) => confirmPlanStep(...args),
  declinePlanStep: (...args) => declinePlanStep(...args),
  stopPlan: (...args) => stopPlan(...args),
  getPlanLedger: (...args) => getPlanLedger(...args),
}));

// ── Fixtures ──────────────────────────────────────────────────────────────
const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'Audit the emissions dataset for duplicates.',
  pattern: 'skill_chain',
  source: 'user_request',
  skill_name: 'data_quality',
  needs_confirmation: true,
  created_at: '2026-08-20T10:00:00Z',
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', tool_args: { dataset: 'emissions' }, status: 'pending', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', tool_args: { name: 'no_dupes' }, status: 'pending', depends_on: [0] },
  ],
};

let currentPlan = PLAN;
const streamHandlers = {};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  currentPlan = PLAN;
  Object.keys(streamHandlers).forEach((k) => delete streamHandlers[k]);
  listPlans.mockResolvedValue({ plans: [PLAN], count: 1 });
  createPlan.mockResolvedValue(PLAN);
  getPlan.mockImplementation(async () => currentPlan);
  approvePlan.mockResolvedValue({ ...PLAN, status: 'approved' });
  declinePlan.mockResolvedValue({ ...PLAN, status: 'cancelled' });
  stopPlan.mockResolvedValue({ ...PLAN, status: 'cancelled' });
  confirmPlanStep.mockResolvedValue({ status: 'confirmed', plan_id: 'plan-1', step_id: 1 });
  declinePlanStep.mockResolvedValue({ status: 'declined', plan_id: 'plan-1', step_id: 1 });
  getPlanLedger.mockResolvedValue({ plan_id: 'plan-1', status: 'completed', runs: [] });
  runPlanStream.mockImplementation(async (token, planId, handlers) => {
    streamHandlers.run = handlers;
  });
  resumePlanStream.mockImplementation(async (token, planId, handlers) => {
    streamHandlers.resume = handlers;
  });
});

const openPlanForReview = async () => {
  render(<AITaskPanel conversationId="conv-1" />);
  fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
  // The plan card is on the Run tab (works for any plan status).
  await screen.findByText('Task plan');
};

// ── Edit brief → diff consent gate (RULE_21) ─────────────────────────────
describe('AITaskPanel — edit brief with diff consent gate', () => {
  it('edits the brief, shows the diff gate, and keeps changes on confirm', async () => {
    const revised = {
      ...PLAN,
      status: 'pending_approval',
      brief: 'Audit duplicates AND triples.',
      replan_gate: true,
      diff: {
        added: [{ intent: 'Send a summary email' }],
        removed: [{ intent: 'Search for duplicate records' }],
        changed: [{ old: { intent: 'Create a rule' }, new: { intent: 'Create two rules' } }],
      },
    };
    editPlan.mockResolvedValue(revised);
    currentPlan = revised;

    await openPlanForReview();
    fireEvent.click(screen.getByRole('button', { name: 'Edit plan' }));
    const input = screen.getByLabelText('Plan brief');
    fireEvent.change(input, { target: { value: 'Audit duplicates AND triples.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));

    await waitFor(() => expect(editPlan).toHaveBeenCalledWith('test-token', 'plan-1', { brief: 'Audit duplicates AND triples.' }));

    // Consent gate summarizes the diff in outcome terms.
    expect(await screen.findByText('Review plan changes')).toBeInTheDocument();
    expect(screen.getByText('New step: Send a summary email')).toBeInTheDocument();
    expect(screen.getByText('Removed step: Search for duplicate records')).toBeInTheDocument();
    expect(screen.getByText('Changed step: Create a rule')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Keep changes' }));

    // Revised plan is applied and needs the plan-level gate again.
    expect(await screen.findByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    expect(notify).toHaveBeenCalledWith('Changes kept — the plan needs your approval again.', 'info');
  });

  it('applies an empty diff directly without the dialog', async () => {
    editPlan.mockResolvedValue({ ...PLAN, status: 'pending_approval', diff: { added: [], removed: [], changed: [] } });

    await openPlanForReview();
    fireEvent.click(screen.getByRole('button', { name: 'Edit plan' }));
    const input = screen.getByLabelText('Plan brief');
    fireEvent.change(input, { target: { value: 'Same plan, no step changes.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));

    await waitFor(() => expect(editPlan).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Review plan changes')).not.toBeInTheDocument();
    expect(notify).toHaveBeenCalledWith('Plan updated.', 'success');
  });
});

// ── Step edit → diff consent gate ────────────────────────────────────────
describe('AITaskPanel — edit step with diff consent gate', () => {
  it('edits a step and gates the changed step through the dialog', async () => {
    editPlanStep.mockResolvedValue({
      ...PLAN,
      status: 'pending_approval',
      diff: { added: [], removed: [], changed: [{ old: { intent: 'Create a rule to prevent duplicates' }, new: { intent: 'Create two rules' } }] },
    });

    await openPlanForReview();
    fireEvent.click(screen.getByRole('button', { name: 'Edit step 1' }));
    expect(screen.getByText('Edit step')).toBeInTheDocument();

    const title = screen.getByLabelText('Step title');
    fireEvent.change(title, { target: { value: 'Create two rules' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(editPlanStep).toHaveBeenCalledWith('test-token', 'plan-1', 1, {
        title: 'Create two rules',
        instructions: '',
        depends_on: [0],
      }),
    );

    expect(await screen.findByText('Review plan changes')).toBeInTheDocument();
    expect(screen.getByText('Changed step: Create a rule to prevent duplicates')).toBeInTheDocument();
  });
});

// ── Pause / Fork / Resume ────────────────────────────────────────────────
describe('AITaskPanel — pause, fork, resume (W3-C endpoints)', () => {
  it('pauses a running plan', async () => {
    pausePlan.mockResolvedValue({ ...PLAN, status: 'paused' });

    await openPlanForReview();
    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));
    await waitFor(() => expect(streamHandlers.run).toBeDefined());

    fireEvent.click(screen.getByRole('button', { name: 'Pause run' }));
    await waitFor(() => expect(pausePlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByRole('button', { name: 'Resume run' })).toBeInTheDocument();
  });

  it('forks a plan into a reviewable copy and opens it', async () => {
    const forked = { ...PLAN, id: 'plan-fork', status: 'pending_approval', forked_from: 'plan-1' };
    forkPlan.mockResolvedValue(forked);
    // The original plan is open; only the post-fork load returns the copy.
    getPlan.mockImplementation(async (_t, id) => (id === 'plan-fork' ? forked : currentPlan));

    await openPlanForReview();
    fireEvent.click(screen.getByRole('button', { name: 'Fork' }));

    await waitFor(() => expect(forkPlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    // The forked plan is loaded into the Run tab as a new reviewable copy.
    await waitFor(() => expect(getPlan).toHaveBeenCalledWith('test-token', 'plan-fork'));
    expect(await screen.findByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    expect(screen.getByText('Forked copy')).toBeInTheDocument();
    expect(notify).toHaveBeenCalledWith('Forked — a reviewable copy was created.', 'success');
  });

  it('resumes a paused plan through the W3-C SSE resume stream', async () => {
    currentPlan = { ...PLAN, status: 'paused' };

    await openPlanForReview();
    fireEvent.click(await screen.findByRole('button', { name: 'Resume run' }));

    await waitFor(() =>
      expect(resumePlanStream).toHaveBeenCalledWith(
        'test-token',
        'plan-1',
        expect.objectContaining({ onFrame: expect.any(Function), onDone: expect.any(Function) }),
      ),
    );
    expect(runPlanStream).not.toHaveBeenCalled();

    // Frames flow through the same handler shape as a normal run.
    await waitFor(() => expect(streamHandlers.resume.onFrame).toBeDefined());
    streamHandlers.resume.onFrame({ type: 'step_start', plan_id: 'plan-1', step_id: 0, intent: 'Search for duplicate records' });
    expect(screen.getAllByText('Running…').length).toBeGreaterThan(0);
  });
});

// ── Chat → Tasks jump (plan_created open_panel action) ───────────────────
describe('AITaskPanel — chat "Open in Tasks" focus jump', () => {
  it('auto-opens the focused plan and consumes the focus', async () => {
    const onFocusPlanConsumed = vi.fn();
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-1" onFocusPlanConsumed={onFocusPlanConsumed} />,
    );

    await waitFor(() => expect(getPlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    // The plan detail (Run tab) is shown — this is where approve/run/pause live.
    expect(await screen.findByText('Task plan')).toBeInTheDocument();
    expect(onFocusPlanConsumed).toHaveBeenCalled();
  });

  it('opens a new focus plan id but does not re-open the same id', async () => {
    const onFocusPlanConsumed = vi.fn();
    const { rerender } = render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-1" onFocusPlanConsumed={onFocusPlanConsumed} />,
    );
    await waitFor(() => expect(getPlan).toHaveBeenCalledWith('test-token', 'plan-1'));

    // Re-render with the same focus id (e.g. panel toggled) → no duplicate fetch.
    rerender(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-1" onFocusPlanConsumed={onFocusPlanConsumed} />,
    );
    expect(getPlan).toHaveBeenCalledTimes(1);

    // New plan id → opened again.
    rerender(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-2" onFocusPlanConsumed={onFocusPlanConsumed} />,
    );
    await waitFor(() => expect(getPlan).toHaveBeenCalledWith('test-token', 'plan-2'));
    expect(getPlan).toHaveBeenCalledTimes(2);
  });
});
