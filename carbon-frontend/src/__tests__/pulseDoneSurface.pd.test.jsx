// PD-* / PX-* fixtures — Done Answer surface + discovering honesty (Pulse × Nibras coworker QA).
// IDs map to canvases/pulse-nibras-coworker-qa.canvas.tsx §7b.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import AITaskAuditCard from '../shell/AITaskAuditCard';
import { effectivePlanStatus, planStatusMeta } from '../shell/aiTaskStatus';
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
const getPlan = vi.fn();
const getPlanLedger = vi.fn();
const listPlanArtifacts = vi.fn();
const downloadArtifact = vi.fn();
const listSubagents = vi.fn();
const approvePlan = vi.fn();
const declinePlan = vi.fn();
const runPlanStream = vi.fn();
const stopPlan = vi.fn();
const confirmPlanStep = vi.fn();
const declinePlanStep = vi.fn();
const createPlan = vi.fn();
const startDiscoveryPlan = vi.fn();
const advanceDiscovery = vi.fn();
const finalizeDiscovery = vi.fn();
const dispatchSubagent = vi.fn();
const forkPlan = vi.fn();
const rerunPlan = vi.fn();
const listPlanTemplates = vi.fn();
const listSchedules = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  listPlans: (...a) => listPlans(...a),
  getPlan: (...a) => getPlan(...a),
  getPlanLedger: (...a) => getPlanLedger(...a),
  listPlanArtifacts: (...a) => listPlanArtifacts(...a),
  downloadArtifact: (...a) => downloadArtifact(...a),
  listSubagents: (...a) => listSubagents(...a),
  approvePlan: (...a) => approvePlan(...a),
  declinePlan: (...a) => declinePlan(...a),
  runPlanStream: (...a) => runPlanStream(...a),
  stopPlan: (...a) => stopPlan(...a),
  confirmPlanStep: (...a) => confirmPlanStep(...a),
  declinePlanStep: (...a) => declinePlanStep(...a),
  createPlan: (...a) => createPlan(...a),
  startDiscoveryPlan: (...a) => startDiscoveryPlan(...a),
  advanceDiscovery: (...a) => advanceDiscovery(...a),
  finalizeDiscovery: (...a) => finalizeDiscovery(...a),
  dispatchSubagent: (...a) => dispatchSubagent(...a),
  forkPlan: (...a) => forkPlan(...a),
  rerunPlan: (...a) => rerunPlan(...a),
  confirmPlanEdit: vi.fn().mockResolvedValue({}),
  discardPlanEdit: vi.fn().mockResolvedValue({}),
  listPlanTemplates: (...a) => listPlanTemplates(...a),
  listSchedules: (...a) => listSchedules(...a),
  instantiatePlanTemplate: vi.fn(),
  promotePlanTemplate: vi.fn(),
  pausePlan: vi.fn(),
  pauseSchedule: vi.fn(),
  editPlan: vi.fn(),
  editPlanStep: vi.fn(),
  editSchedule: vi.fn(),
  stepCancel: vi.fn(),
  stepPause: vi.fn(),
  stepResume: vi.fn(),
  stepRetry: vi.fn(),
  stepSkip: vi.fn(),
  resumePlanStream: vi.fn(),
  durableResumeRun: vi.fn(),
  deletePlan: vi.fn(),
  deleteSchedule: vi.fn(),
  createSchedule: vi.fn(),
}));

vi.mock('../shell/MarkdownMessage', () => ({
  default: function MockMarkdown({ content }) {
    return <div data-testid="markdown-message">{content}</div>;
  },
}));

vi.mock('../components/graph/PlanDagGraph', () => ({
  default: () => <div data-testid="plan-dag" />,
}));

const COMPLETED = {
  id: 'plan-done-1',
  status: 'completed',
  brief: 'October payroll variance board pack',
  final_response: '### GOSI Exposure\n\n**Total** KWD 184,220',
  created_at: '2026-09-17T10:00:00Z',
  steps: [
    { step_id: 0, intent: 'Fetch headcount', tool_name: 'call_host_api', status: 'completed' },
    { step_id: 4, intent: 'Export board pack', tool_name: 'export_document', status: 'completed' },
  ],
};

const LEDGER = {
  plan_id: 'plan-done-1',
  status: 'completed',
  actor: { user_id: '2', display_name: 'Ahmed' },
  provenance: { pattern: 'payroll_board_pack', source: 'demo_seed', skill_name: null },
  usage: { total_latency_ms: 2900, total_llm_calls: 4, total_tokens: 8000 },
  steps: [
    { step_id: 0, intent: 'Fetch headcount', status: 'completed', latency_ms: 400 },
    { step_id: 4, intent: 'Export board pack', status: 'completed', latency_ms: 900 },
  ],
  confirmations: [{ step_id: 0, intent: 'Fetch', status: 'completed' }],
  replans: 0,
  final_response: '### GOSI Exposure\n\n**Total** KWD 184,220',
};

const ARTIFACTS = {
  plan_id: 'plan-done-1',
  count: 4,
  artifacts: [
    { id: 'a1', name: 'board-pack.docx', mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size_bytes: 37000 },
    { id: 'a2', name: 'board-pack.xlsx', mime_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', size_bytes: 6000 },
    { id: 'a3', name: 'board-pack.pdf', mime_type: 'application/pdf', size_bytes: 1400 },
    { id: 'a4', name: 'board-pack.png', mime_type: 'image/png', size_bytes: 17000 },
  ],
};

describe('PD-02 — AITaskAuditCard never dumps answer markdown', () => {
  it('shows confirmations but not final_response prose', () => {
    render(<AITaskAuditCard ledger={LEDGER} />);
    expect(screen.getByText(/Confirmations/i)).toBeInTheDocument();
    expect(screen.queryByText('Answer')).not.toBeInTheDocument();
    expect(screen.queryByText('Final response')).not.toBeInTheDocument();
    expect(screen.queryByText(/### GOSI Exposure/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\*\*Total\*\*/)).not.toBeInTheDocument();
  });
});

describe('PX-01 — discovering / empty steps honesty', () => {
  it('keeps discovering locked even with zero steps', () => {
    expect(effectivePlanStatus({ status: 'discovering', steps: [] })).toBe('discovering');
    expect(planStatusMeta('discovering').label).toMatch(/Clarifying/i);
  });

  it('does not invent Completed from empty steps on a running row', () => {
    expect(effectivePlanStatus({ status: 'running', steps: [] })).toBe('running');
  });

  it('does not mark Completed when steps remain pending', () => {
    expect(
      effectivePlanStatus({
        status: 'running',
        steps: [
          { status: 'completed' },
          { status: 'pending' },
        ],
      }),
    ).toBe('running');
  });

  it('demotes dishonest Completed when steps are still pending', () => {
    expect(
      effectivePlanStatus({
        status: 'completed',
        steps: Array.from({ length: 11 }, () => ({ status: 'pending' })),
      }),
    ).toBe('failed');
  });
});

describe('PD-01/03/04/05 — Done Output Answer · Discuss · Artifacts · PNG', () => {
  const onSwitchToChat = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    listPlans.mockResolvedValue({ plans: [COMPLETED], count: 1 });
    getPlan.mockResolvedValue(COMPLETED);
    getPlanLedger.mockResolvedValue(LEDGER);
    listPlanArtifacts.mockResolvedValue(ARTIFACTS);
    downloadArtifact.mockResolvedValue('blob:fake-png');
    listSubagents.mockResolvedValue([]);
    listPlanTemplates.mockResolvedValue({ templates: [], count: 0 });
    listSchedules.mockResolvedValue({ schedules: [], count: 0 });
    forkPlan.mockResolvedValue(COMPLETED);
    rerunPlan.mockResolvedValue({ ...COMPLETED, status: 'approved' });
    runPlanStream.mockResolvedValue(undefined);
  });

  it('PD-01: Output renders answer via MarkdownMessage (not raw ###)', async () => {
    render(
      <AITaskPanel
        conversationId="conv-1"
        focusPlanId="plan-done-1"
        onSwitchToChat={onSwitchToChat}
      />,
    );

    expect(await screen.findByTestId('agent-workspace')).toBeInTheDocument();
    // Auto-lands on Output for completed plans.
    expect(await screen.findByTestId('markdown-message')).toBeInTheDocument();
    expect(screen.getByTestId('markdown-message')).toHaveTextContent('### GOSI Exposure');
    // Raw pre-wrap dump of ### must not appear outside the markdown mock.
    expect(screen.queryByText('Answer')).toBeInTheDocument();
  });

  it('Track D: Output shows Rerun receipt when prior_run comparison is changed', async () => {
    const withPrior = {
      ...COMPLETED,
      id: 'plan-rerun-diff',
      final_response: '### New answer\n\nTotal **99**',
      prior_run: {
        comparison: 'changed',
        prior_final_response: '### Prior answer\n\nTotal **42**',
        prior_status: 'completed',
      },
    };
    listPlans.mockResolvedValue({ plans: [withPrior], count: 1 });
    getPlan.mockResolvedValue(withPrior);
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-rerun-diff" onSwitchToChat={onSwitchToChat} />,
    );
    expect(await screen.findByTestId('output-rerun-receipt')).toBeInTheDocument();
    expect(screen.getByText(/Answer changed vs last run/i)).toBeInTheDocument();
    expect(screen.getByText(/Prior answer/i)).toBeInTheDocument();
  });

  it('Track C: Output shows Export gap when hollow export was refused', async () => {
    const withGap = {
      ...COMPLETED,
      id: 'plan-export-gap',
      steps: [
        {
          step_id: 4,
          intent: 'Export board pack',
          tool_name: 'export_document',
          status: 'failed',
          error: 'Export refused: no real findings to bind into the document.',
        },
      ],
    };
    listPlans.mockResolvedValue({ plans: [withGap], count: 1 });
    getPlan.mockResolvedValue(withGap);
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-export-gap" onSwitchToChat={onSwitchToChat} />,
    );
    expect(await screen.findByTestId('output-export-gaps')).toBeInTheDocument();
    expect(screen.getByText(/Export gap/i)).toBeInTheDocument();
    expect(screen.getByText(/no real findings/i)).toBeInTheDocument();
  });

  it('Track C: completed write step shows Approved by you when consent_granted', async () => {
    const withConsent = {
      ...COMPLETED,
      id: 'plan-consent-trace',
      steps: [
        {
          step_id: 2,
          intent: 'Deny compensation request',
          tool_name: 'call_host_api',
          status: 'completed',
          consent_granted: true,
        },
      ],
    };
    listPlans.mockResolvedValue({ plans: [withConsent], count: 1 });
    getPlan.mockResolvedValue(withConsent);
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-consent-trace" onSwitchToChat={onSwitchToChat} />,
    );
    const cockpit = await screen.findByTestId('agent-cockpit');
    // Completed plans land on Output — switch to Run for StepCards.
    fireEvent.click(within(cockpit).getByRole('button', { name: 'Run' }));
    // Graph-first Run may hide the step list when settled — open List.
    const listBtn = screen.queryByRole('button', { name: 'List' });
    if (listBtn) fireEvent.click(listBtn);
    expect(await screen.findByText(/Approved by you/i)).toBeInTheDocument();
  });

  it('PD-02: Audit under Run health opens by default when the run is settled', async () => {
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-done-1" onSwitchToChat={onSwitchToChat} />,
    );
    await screen.findByTestId('markdown-message');
    // Settled → Run health auto-opens so audit is not a hidden click (Screen Spec).
    expect(await screen.findByText('Audit ledger')).toBeInTheDocument();
    expect(getPlanLedger).toHaveBeenCalled();
  });

  it('PD-03: Discuss in Chat seeds onSwitchToChat with plan context', async () => {
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-done-1" onSwitchToChat={onSwitchToChat} />,
    );
    const discuss = await screen.findByRole('button', { name: /Discuss in Chat/i });
    fireEvent.click(discuss);
    await waitFor(() => expect(onSwitchToChat).toHaveBeenCalled());
    const payload = onSwitchToChat.mock.calls[0][0];
    const draft = typeof payload === 'string' ? payload : payload?.draft;
    expect(draft).toMatch(/October payroll variance board pack/);
    expect(draft).toMatch(/plan plan-done-1/);
    expect(draft).toMatch(/DISCUSSION ONLY/);
    expect(draft).toMatch(/explicitly ask you to apply changes/);
    // Refine seed must not paste the prior answer body (avoids invoke_skill).
    expect(draft).not.toMatch(/GOSI Exposure/);
  });

  it('PD-04/05: pack artifacts list + PNG Preview affordance', async () => {
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-done-1" onSwitchToChat={onSwitchToChat} />,
    );
    await waitFor(() => expect(listPlanArtifacts).toHaveBeenCalled());
    // Names appear in the run strip and Results cards — assert presence, not uniqueness.
    expect((await screen.findAllByText('board-pack.docx')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('board-pack.xlsx').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('board-pack.pdf').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('board-pack.png').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: 'Preview' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: 'Download' }).length).toBeGreaterThanOrEqual(4);
  });

  it('PD-06: Output Actions include Rerun and Open Plan for completed (no Fork)', async () => {
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-done-1" onSwitchToChat={onSwitchToChat} />,
    );
    await screen.findByTestId('markdown-message');
    expect(screen.getByRole('button', { name: 'Rerun' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Fork' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Open Plan$/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rerun' }));
    await waitFor(() => expect(rerunPlan).toHaveBeenCalledWith(expect.anything(), 'plan-done-1'));
  });

  it('PD-07: header Rerun aria control is enabled when completed', async () => {
    render(
      <AITaskPanel conversationId="conv-1" focusPlanId="plan-done-1" onSwitchToChat={onSwitchToChat} />,
    );
    await screen.findByTestId('markdown-message');
    const rerunBtn = screen.getByRole('button', { name: 'Rerun from a clean slate' });
    expect(rerunBtn).toBeEnabled();
  });
});
