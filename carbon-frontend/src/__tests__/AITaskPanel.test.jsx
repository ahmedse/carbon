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

const listPlans = vi.fn();
const createPlan = vi.fn();
const startDiscoveryPlan = vi.fn();
const advanceDiscovery = vi.fn();
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
const dispatchSubagent = vi.fn();
const listSubagents = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  listPlans: (...args) => listPlans(...args),
  createPlan: (...args) => createPlan(...args),
  startDiscoveryPlan: (...args) => startDiscoveryPlan(...args),
  advanceDiscovery: (...args) => advanceDiscovery(...args),
  getPlan: (...args) => getPlan(...args),
  approvePlan: (...args) => approvePlan(...args),
  declinePlan: (...args) => declinePlan(...args),
  runPlanStream: (...args) => runPlanStream(...args),
  confirmPlanStep: (...args) => confirmPlanStep(...args),
  declinePlanStep: (...args) => declinePlanStep(...args),
  stopPlan: (...args) => stopPlan(...args),
  getPlanLedger: (...args) => getPlanLedger(...args),
  listPlanArtifacts: (...args) => listPlanArtifacts(...args),
  downloadArtifact: (...args) => downloadArtifact(...args),
  dispatchSubagent: (...args) => dispatchSubagent(...args),
  listSubagents: (...args) => listSubagents(...args),
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

// ── Tabs + composer ───────────────────────────────────────────────────────
describe('AITaskPanel — two internal tabs (RULE_17)', () => {
  it('renders Tasks/Run tabs and defaults to Tasks', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    expect(screen.getByRole('tab', { name: 'Tasks' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Run' })).toBeInTheDocument();

    expect(screen.getByLabelText('Message input')).toBeInTheDocument();
    expect(await screen.findByText('Audit the emissions dataset for duplicates.')).toBeInTheDocument();
  });

  it('persists the selected tab to localStorage (RULE_17)', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(screen.getByRole('tab', { name: 'Run' }));

    expect(localStorage.getItem('carbon-ai-task-tab')).toBe('run');
    expect(await screen.findByText('Open a task from the Tasks tab to review, approve and run it.')).toBeInTheDocument();
  });

  it('starts a guided discovery and opens the ready plan for review (W5-B)', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'Audit the emissions dataset for duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(startDiscoveryPlan).toHaveBeenCalledWith('test-token', {
        brief: 'Audit the emissions dataset for duplicates.',
        conversation_id: 'conv-1',
      });
    });
    // Pulse's first question renders as a rich message bubble (reuses the
    // main chat's AIMessageBubble).
    expect(await screen.findByText('Which dataset should we audit?')).toBeInTheDocument();

    const reply = screen.getByLabelText('Message input');
    fireEvent.change(reply, { target: { value: 'The emissions dataset' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(advanceDiscovery).toHaveBeenCalledWith('test-token', 'plan-1', 'The emissions dataset');
    });
    // Plan ready banner → review → Run tab with the consent gate. The step
    // intent appears in the step list AND as a node label in the live DAG.
    expect(await screen.findByText('Plan ready — review below')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Review plan' }));

    expect(await screen.findByText('Approve plan')).toBeInTheDocument();
    expect(screen.getAllByText('Search for duplicate records').length).toBeGreaterThan(0);
  });

  it('renders Pulse questions and user replies as bubbles across turns (W5-B)', async () => {
    advanceDiscovery
      .mockResolvedValueOnce({
        status: 'needs_input',
        question: 'What field uniquely identifies a record?',
        turns: [
          { question: 'Which dataset should we audit?', reply: 'The emissions dataset' },
          { question: 'What field uniquely identifies a record?', reply: null },
        ],
      })
      .mockResolvedValueOnce({
        status: 'plan_ready',
        plan: PLAN,
        turns: [
          { question: 'Which dataset should we audit?', reply: 'The emissions dataset' },
          { question: 'What field uniquely identifies a record?', reply: 'report_id' },
        ],
      });

    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'Audit duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Which dataset should we audit?')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'The emissions dataset' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    // Second question AND the user's prior reply both render as bubbles.
    expect(await screen.findByText('What field uniquely identifies a record?')).toBeInTheDocument();
    expect(screen.getByText('The emissions dataset')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'report_id' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Plan ready — review below')).toBeInTheDocument();
    expect(advanceDiscovery).toHaveBeenCalledTimes(2);
  });
});

// ── Plan-level consent gate (RULE_21) ─────────────────────────────────────
describe('AITaskPanel — plan review and approval', () => {
  it('shows the approve/decline gate for a pending plan and approves it', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    expect(await screen.findByRole('button', { name: 'Approve plan' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve plan' }));

    await waitFor(() => expect(approvePlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByRole('button', { name: 'Run plan' })).toBeInTheDocument();
  });

  it('declining a plan leaves nothing executed', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }));

    await waitFor(() => expect(declinePlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByText('This plan was cancelled — nothing was executed.')).toBeInTheDocument();
  });
});

// ── Streamed run + steps ──────────────────────────────────────────────────
describe('AITaskPanel — streamed run and step consent', () => {
  it('streams step frames and shows the audit ledger on completion', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
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
    streamHandlers.onFrame({ type: 'step_start', plan_id: 'plan-1', step_id: 0, intent: 'Search for duplicate records' });
    streamHandlers.onFrame({
      type: 'step_result', plan_id: 'plan-1', step_id: 0, intent: 'Search for duplicate records',
      status: 'completed', tool_output: { count: 3 },
    });
    streamHandlers.onFrame({ type: 'step_end', plan_id: 'plan-1', step_id: 0, status: 'completed' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'completed', final_response: 'Found 3 duplicate rows.' });

    expect(await screen.findByText('Run completed')).toBeInTheDocument();
    expect(await screen.findByText('Audit ledger')).toBeInTheDocument();
    await waitFor(() => expect(getPlanLedger).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(screen.getByText('12000')).toBeInTheDocument();
    expect(screen.getByText('1234 ms')).toBeInTheDocument();
  });

  it('pauses on a consent step and confirms it via the step gate', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...PLAN, status: 'paused' };
    streamHandlers.onFrame({ type: 'step_confirm', plan_id: 'plan-1', step_id: 1, intent: 'Create a rule to prevent duplicates' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'paused', final_response: null });

    expect(await screen.findByText('Run paused — a step needs your approval')).toBeInTheDocument();
    expect(screen.getByText('This action writes to Carbon. Approve it to run, or decline to skip it.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));

    await waitFor(() => expect(confirmPlanStep).toHaveBeenCalledWith('test-token', 'plan-1', 1));
    expect(await screen.findByText('Resume run')).toBeInTheDocument();
  });

  it('declines a consent step and marks it skipped', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    currentPlan = { ...PLAN, status: 'paused' };
    streamHandlers.onFrame({ type: 'step_confirm', plan_id: 'plan-1', step_id: 1, intent: 'Create a rule to prevent duplicates' });
    streamHandlers.onDone({ type: 'done', plan_id: 'plan-1', status: 'paused', final_response: null });

    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }));

    await waitFor(() => expect(declinePlanStep).toHaveBeenCalledWith('test-token', 'plan-1', 1));
    expect(await screen.findByText('Skipped — not executed.')).toBeInTheDocument();
  });

  it('stops a running plan and shows stopped copy', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    expect(await screen.findByRole('button', { name: 'Stop run' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Stop run' }));

    await waitFor(() => expect(stopPlan).toHaveBeenCalledWith('test-token', 'plan-1'));
    expect(await screen.findByText('Run stopped')).toBeInTheDocument();
  });

  it('reports a failed run via the stream error frame', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    streamHandlers.onError?.('Planning service unavailable');

    expect(await screen.findByText('Run failed')).toBeInTheDocument();
    expect(screen.getByText('Planning service unavailable')).toBeInTheDocument();
  });
});

// ── W5-A lifecycle emission (ADR-0014) ────────────────────────────────────
describe('AITaskPanel — emits workspace lifecycle state (W5-A / ADR-0014)', () => {
  it('reports plan_pending while a plan awaits approval', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('plan_pending');
    });
  });

  it('reports running while the stream works and done on completion', async () => {
    const onLifecycleStateChange = vi.fn();
    render(<AITaskPanel conversationId="conv-1" onLifecycleStateChange={onLifecycleStateChange} />);

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
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

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
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

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
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

    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run plan' }));

    await waitFor(() => expect(streamHandlers.onFrame).toBeDefined());
    streamHandlers.onError?.('Planning service unavailable');

    await waitFor(() => {
      expect(onLifecycleStateChange).toHaveBeenLastCalledWith('error');
    });
  });
});

// ── I4-F — conversation-scoped subagents ─────────────────────────────────
describe('AITaskPanel — subagents (I4-F)', () => {
  it('lists empty subagents and dispatches one via the dialog', async () => {
    render(<AITaskPanel conversationId="conv-1" />);

    // Hydration loads the conversation's subagents (empty here).
    await waitFor(() => expect(listSubagents).toHaveBeenCalledWith('test-token', 'conv-1'));

    // Open a plan so the Run tab (and its Subagents section) renders.
    fireEvent.click(await screen.findByText('Audit the emissions dataset for duplicates.'));

    // Empty state caption before any dispatch.
    expect(await screen.findByText('No subagents dispatched yet.')).toBeInTheDocument();

    // Open the dispatch dialog and submit a named subagent.
    fireEvent.click(screen.getByRole('button', { name: 'Dispatch subagent' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Dedupe auditor' } });
    fireEvent.change(within(dialog).getByLabelText('Brief / instructions'), {
      target: { value: 'Find duplicate rows in the emissions table.' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Dispatch subagent' }));

    await waitFor(() => {
      expect(dispatchSubagent).toHaveBeenCalledWith('test-token', 'conv-1', {
        name: 'Dedupe auditor',
        brief: 'Find duplicate rows in the emissions table.',
      });
    });

    // The new SubagentResultCard renders with the subagent's name.
    expect(await screen.findByText('Dedupe auditor')).toBeInTheDocument();
  });
});
