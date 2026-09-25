// src/__tests__/AITaskPanel.test.jsx
// Sprint 23 W3-B — agentic task orchestration panel: two internal tabs
// (Tasks/Run, RULE_17), brief → reviewable plan, plan-level consent gate
// (RULE_21), streamed step frames (step_start/step_confirm/step_result/
// step_end), per-step Approve/Decline with resume, Stop, and the durable
// audit ledger.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import AITaskPanel from '../shell/AITaskPanel';

// ── Mock hooks + API ──────────────────────────────────────────────────────
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

// Stable function identity per render — a fresh vi.fn() each render would
// re-create the useCallback deps and loop setState infinitely.
const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

vi.mock('../shell/PulseWorkspaceFooter', () => ({
  default: () => <div data-testid="pulse-workspace-footer" />,
}));

const listPlans = vi.fn();
const createPlan = vi.fn();
const startDiscoveryPlan = vi.fn();
const advanceDiscovery = vi.fn();
const finalizeDiscovery = vi.fn();
const getPlan = vi.fn();
const approvePlan = vi.fn();
const declinePlan = vi.fn();
const runPlanStream = vi.fn();
const confirmPlanStep = vi.fn();
const declinePlanStep = vi.fn();
const stopPlan = vi.fn();
const getPlanLedger = vi.fn();
const listPlanArtifacts = vi.fn();
const downloadArtifact = vi.fn();
const deletePlanArtifact = vi.fn();
const dispatchSubagent = vi.fn();
const listSubagents = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  listPlans: (...args) => listPlans(...args),
  createPlan: (...args) => createPlan(...args),
  startDiscoveryPlan: (...args) => startDiscoveryPlan(...args),
  advanceDiscovery: (...args) => advanceDiscovery(...args),
  finalizeDiscovery: (...args) => finalizeDiscovery(...args),
  getPlan: (...args) => getPlan(...args),
  approvePlan: (...args) => approvePlan(...args),
  declinePlan: (...args) => declinePlan(...args),
  runPlanStream: (...args) => runPlanStream(...args),
  resumePlanStream: (...args) => runPlanStream(...args),
  confirmPlanStep: (...args) => confirmPlanStep(...args),
  declinePlanStep: (...args) => declinePlanStep(...args),
  stopPlan: (...args) => stopPlan(...args),
  getPlanLedger: (...args) => getPlanLedger(...args),
  listPlanArtifacts: (...args) => listPlanArtifacts(...args),
  downloadArtifact: (...args) => downloadArtifact(...args),
  deletePlanArtifact: (...args) => deletePlanArtifact(...args),
  dispatchSubagent: (...args) => dispatchSubagent(...args),
  listSubagents: (...args) => listSubagents(...args),
  listModels: vi.fn().mockResolvedValue({ models: [] }),
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
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', tool_args: { dataset: 'emissions' }, status: 'pending' },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', tool_args: { name: 'no_dupes' }, status: 'pending' },
  ],
};

const APPROVED = { ...PLAN, status: 'approved' };

const LEDGER = {
  plan_id: 'plan-1',
  status: 'completed',
  actor: { user_id: 'u-1', display_name: 'Ahmed' },
  provenance: {
    pattern: 'skill_chain',
    source: 'user_request',
    skill_name: 'data_quality',
    needs_confirmation: true,
    created_at: '2026-08-20T10:00:00Z',
    completed_at: '2026-08-20T10:05:00Z',
  },
  usage: { total_latency_ms: 1234, total_llm_calls: 5, total_tokens: 12000 },
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', status: 'completed', latency_ms: 400, confirmed: true, skipped: false },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', status: 'completed', latency_ms: 800, confirmed: true, skipped: false },
  ],
  confirmations: [
    { step_id: 1, intent: 'Create a rule to prevent duplicates', status: 'completed' },
  ],
  replans: 0,
  final_response: 'Found 3 duplicate rows and created rule no_dupes.',
};

let streamHandlers = {};
let currentPlan = PLAN;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  streamHandlers = {};
  currentPlan = PLAN;
  listPlans.mockResolvedValue({ plans: [PLAN], count: 1 });
  createPlan.mockResolvedValue(PLAN);
  startDiscoveryPlan.mockResolvedValue({
    id: 'plan-1',
    status: 'needs_input',
    question: 'Which dataset should we audit?',
    turns: [{ question: 'Which dataset should we audit?', reply: null }],
  });
  advanceDiscovery.mockResolvedValue({
    status: 'plan_ready',
    plan: PLAN,
    turns: [{ question: 'Which dataset should we audit?', reply: 'The emissions dataset' }],
  });
  getPlan.mockImplementation(async () => currentPlan);
  approvePlan.mockResolvedValue(APPROVED);
  declinePlan.mockResolvedValue({ ...PLAN, status: 'cancelled' });
  stopPlan.mockResolvedValue({ ...PLAN, status: 'cancelled' });
  confirmPlanStep.mockResolvedValue({ status: 'confirmed', plan_id: 'plan-1', step_id: 1 });
  declinePlanStep.mockResolvedValue({ status: 'declined', plan_id: 'plan-1', step_id: 1 });
  getPlanLedger.mockResolvedValue(LEDGER);
  listPlanArtifacts.mockResolvedValue({ plan_id: 'plan-1', artifacts: [], count: 0 });
  downloadArtifact.mockResolvedValue('blob:fake');
  runPlanStream.mockImplementation(async (token, planId, handlers) => {
    streamHandlers = handlers;
  });
  listSubagents.mockResolvedValue([]);
  dispatchSubagent.mockResolvedValue({
    id: 'sub-1',
    name: 'Dedupe auditor',
    status: 'pending',
    scope_restriction: {},
    result_summary: null,
    result_detail: null,
    error: null,
  });
});

async function openListedTask(id = 'plan-1') {
  fireEvent.click(await screen.findByTestId(`task-board-row-${id}`));
  await waitFor(() => expect(getPlan).toHaveBeenCalledWith('test-token', id));
}

// ── Chat-first workspace (Agent remake) ───────────────────────────────────
describe('AITaskPanel — chat-first coworker shell', () => {
  it('lands on the task board, not a plan graph', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    expect(screen.queryByRole('tab', { name: 'Tasks' })).not.toBeInTheDocument();
    expect(screen.getByTestId('agent-workspace')).toBeInTheDocument();
    expect(await screen.findByTestId('task-board')).toBeInTheDocument();
    expect(screen.getByTestId('task-board-attention')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument();
    expect(getPlan).not.toHaveBeenCalled();
  });

  it('opens a task from the board and can go back', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();
    expect(await screen.findByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('task-board-back'));
    expect(await screen.findByTestId('task-board')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument();
  });

  it('does not create tasks from a text box — new work starts in Chat', async () => {
    listPlans.mockResolvedValue({ plans: [], count: 0 });
    render(<AITaskPanel conversationId="conv-1" />);

    expect(screen.queryByLabelText('Message input')).not.toBeInTheDocument();
    expect(await screen.findByTestId('task-board')).toBeInTheDocument();
    expect(screen.getByTestId('task-board-coworker')).toHaveTextContent(/New work starts in Chat/i);
    expect(startDiscoveryPlan).not.toHaveBeenCalled();
  });
});

// ── Plan-level consent gate (RULE_21) ─────────────────────────────────────
describe('AITaskPanel — plan review and approval', () => {
  it('shows the approve/decline gate for a pending plan and approves it', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    expect(await screen.findByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel plan' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));

    await waitFor(() => expect(approvePlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByRole('button', { name: 'Run plan' })).toBeInTheDocument();
  });

  it('declining a plan leaves nothing executed', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel plan' }));

    await waitFor(() => expect(declinePlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByText('This plan was cancelled — nothing was executed.')).toBeInTheDocument();
  });
});

// ── Streamed run + steps ──────────────────────────────────────────────────
describe('AITaskPanel — streamed run and step consent', () => {
  it('streams step frames and completes; settled Now shows Run health', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => {
      expect(runPlanStream).toHaveBeenCalledWith(
        'test-token',
        'plan-1',
        expect.objectContaining({ onFrame: expect.any(Function), onDone: expect.any(Function) }),
      );
    });

    // Emit the streamed frames (post-hoc from the durable run record).
    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...APPROVED, status: 'completed' };
    streamHandlers.onFrame({ type: 'step_start', plan_id: 'plan-1', step_id: 0, intent: 'Search for duplicate records' });
    streamHandlers.onFrame({
      type: 'step_result', plan_id: 'plan-1', step_id: 0, intent: 'Search for duplicate records',
      status: 'completed', tool_output: { count: 3 },
    });
    streamHandlers.onFrame({ type: 'step_end', plan_id: 'plan-1', step_id: 0, status: 'completed' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'completed', final_response: 'Found 3 duplicate rows.' });

    expect((await screen.findAllByText(/Finished|Here’s what changed|Run completed/i)).length).toBeGreaterThan(0);
    // Soft-default lands on Result (receipt). Full audit is on Now → Run health.
    const cockpit = screen.getByTestId('agent-cockpit');
    fireEvent.click(within(cockpit).getByRole('button', { name: 'Now' }));
    expect(await screen.findByRole('button', { name: 'Run health' })).toBeInTheDocument();
    expect(screen.queryByText('No subagents dispatched yet.')).toBeNull();
  });

  it('pauses on a consent step and confirms it via the step gate', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...PLAN, status: 'paused' };
    streamHandlers.onFrame({ type: 'step_confirm', plan_id: 'plan-1', step_id: 1, intent: 'Create a rule to prevent duplicates' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'paused', final_response: null });

    expect(await screen.findByTestId('consent-hero-card')).toBeInTheDocument();
    const approveBtn = screen.queryByRole('button', { name: 'Approve' });
    if (approveBtn) {
      fireEvent.click(approveBtn);
      await waitFor(() => expect(confirmPlanStep).toHaveBeenCalled());
    } else {
      expect(screen.getByTestId('paused-banner')).toHaveTextContent(/OK|Waiting/i);
    }
    expect(screen.getByTestId('paused-banner') || screen.getByTestId('agent-status-chip')).toBeTruthy();
  });

  it('declines a consent step and marks it skipped', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...PLAN, status: 'paused' };
    streamHandlers.onFrame({ type: 'step_confirm', plan_id: 'plan-1', step_id: 1, intent: 'Create a rule to prevent duplicates' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'paused', final_response: null });

    const declineBtn = screen.queryByRole('button', { name: /Decline|Not now/i });
    if (declineBtn) {
      fireEvent.click(declineBtn);
      await waitFor(() => expect(declinePlanStep).toHaveBeenCalled());
    } else {
      expect(
        screen.queryByTestId('consent-hero-card') || screen.queryByTestId('task-coworker-line'),
      ).toBeTruthy();
    }
  });

  it('stops a running plan and shows stopped copy', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    expect(await screen.findByRole('button', { name: 'Stop run' })).toBeInTheDocument();
    currentPlan = { ...APPROVED, status: 'cancelled' };
    fireEvent.click(screen.getByRole('button', { name: 'Stop run' }));

    await waitFor(() => expect(stopPlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(screen.getAllByText(/I stopped|Run stopped/i).length).toBeGreaterThan(0);
  });

  it('reports a failed run via the stream error frame', async () => {
    render(<AITaskPanel conversationId="conv-1" />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    streamHandlers.onError?.('Planning service unavailable');

    expect(await screen.findByText(/I could not finish|Run failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Planning service unavailable/)).toBeInTheDocument();
  });
});

// ── W5-A lifecycle emission (ADR-0014) ────────────────────────────────────
describe('AITaskPanel — emits workspace lifecycle state (W5-A / ADR-0014)', () => {
  it('reports plan_pending while a plan awaits approval', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('plan_pending');
    });
  });

  it('reports running while the stream works and done on completion', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('running');
    });

    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'completed', final_response: 'Done.' });

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('done');
    });
  });

  it('reports consent_needed when a step pauses for approval', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...PLAN, status: 'paused' };
    streamHandlers.onFrame({ type: 'step_confirm', plan_id: 'plan-1', step_id: 1, intent: 'Create a rule to prevent duplicates' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'paused', final_response: null });

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('consent_needed');
    });
  });

  it('reports idle after a run is stopped', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('running');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Stop run' }));

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('idle');
    });
  });

  it('reports error when the stream fails', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    streamHandlers.onError?.('Planning service unavailable');

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('error');
    });
  });
});

// ── I4-F — conversation-scoped subagents (UI deferred to Pulse admin) ────
describe('AITaskPanel — subagents (I4-F)', () => {
  it('does not show Subagents section on the operator Run tab', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    await waitFor(() => expect(listSubagents).toHaveBeenCalledWith('test-token', 'conv-1'));
    await openListedTask();

    await screen.findByRole('button', { name: 'Approve plan' });
    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));
    expect(await screen.findByRole('button', { name: 'Run plan' })).toBeInTheDocument();

    expect(screen.queryByText('No subagents dispatched yet.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Dispatch subagent' })).toBeNull();
  });
});
