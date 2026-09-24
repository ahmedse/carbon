// src/shell/__tests__/AgentRunSurface.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AgentRunSurface, { mergePlanWithRunSteps } from '../AgentRunSurface';

const PLAN = {
  id: 'plan-1',
  status: 'completed',
  brief: 'Audit duplicates',
  steps: [
    {
      step_id: 0,
      intent: 'Search for duplicate records',
      tool_name: 'search_entity',
      tool_args: { dataset: 'emissions' },
      status: 'completed',
      finished_at: '2026-09-20T10:00:00Z',
      depends_on: [],
    },
    {
      step_id: 1,
      intent: 'Create a rule',
      tool_name: 'create_dq_rule',
      status: 'completed',
      finished_at: '2026-09-20T10:01:00Z',
      depends_on: [0],
    },
  ],
};

describe('mergePlanWithRunSteps', () => {
  it('overlays streamed tool_output onto plan steps', () => {
    const merged = mergePlanWithRunSteps(PLAN, [
      { step_id: 0, tool_output: { count: 3 }, status: 'completed' },
    ]);
    expect(merged.steps[0].tool_output).toEqual({ count: 3 });
    expect(merged.steps[0].tool_name).toBe('search_entity');
  });
});

describe('AgentRunSurface', () => {
  it('does not stack Job Map, DAG, token strip, or bottom details list on Run', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        conversationId="conv-1"
        listContent={<div>Step list body</div>}
      />,
    );
    expect(screen.queryByTestId('agent-run-job-map')).toBeNull();
    expect(screen.queryByTestId('agent-run-job-map-board')).toBeNull();
    expect(screen.queryByTestId('plan-dag-graph')).toBeNull();
    expect(screen.queryByTestId('agent-run-token-strip')).toBeNull();
    expect(screen.queryByTestId('plan-dag-token')).toBeNull();
    expect(screen.queryByTestId('agent-run-list')).toBeNull();
    expect(screen.queryByTestId('agent-run-toggle-details')).toBeNull();
  });

  it('renders visual timeline spine with beat nodes', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
        artifacts={[{ id: 1, name: 'report.csv' }]}
      />,
    );

    expect(screen.getByTestId('agent-run-surface')).toBeInTheDocument();
    const timeline = screen.getByTestId('agent-run-chronicle');
    expect(timeline).toHaveAttribute('data-timeline', 'visual');
    expect(timeline).toHaveTextContent('Search for duplicate records');
    expect(screen.getByTestId('run-timeline-node-0')).toBeInTheDocument();
    expect(screen.getByTestId('agent-run-progress')).toHaveTextContent(/2\/2/);
    expect(screen.queryByText('report.csv')).toBeNull();
  });

  it('opens collapsible step detail drawer on beat select', async () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
      />,
    );
    expect(screen.queryByTestId('run-step-detail-drawer')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('run-timeline-open-0'));
    expect(screen.getByTestId('run-step-detail-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('beat-detail-body')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('run-step-detail-close'));
    await waitFor(() => {
      expect(screen.queryByTestId('run-step-detail-drawer')).not.toBeInTheDocument();
    });
  });

  it('does not steal focus back to consent when browsing another step', async () => {
    const consentPlan = {
      id: 'plan-focus',
      status: 'paused',
      brief: 'Send the GOSI file',
      steps: [
        {
          step_id: 0,
          intent: 'Payroll records',
          tool_name: 'call_host_api',
          status: 'completed',
          depends_on: [],
        },
        {
          step_id: 1,
          intent: 'System check',
          tool_name: 'call_host_api',
          tool_args: { api_name: 'submit_gosi_wps_sif' },
          status: 'awaiting_approval',
          depends_on: [0],
        },
      ],
    };
    const { rerender } = render(
      <AgentRunSurface
        plan={consentPlan}
        runSteps={[]}
        phase="paused"
      />,
    );
    // Auto-focus opens the consent step once.
    expect(screen.getByTestId('run-step-detail-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('run-chronicle-row-1')).toHaveAttribute('data-selected', 'true');

    // Operator opens a finished step to read it.
    fireEvent.click(screen.getByTestId('run-timeline-open-0'));
    expect(screen.getByTestId('run-chronicle-row-0')).toHaveAttribute('data-selected', 'true');
    expect(screen.getByTestId('run-chronicle-row-1')).not.toHaveAttribute('data-selected');

    // Poll/merge re-render must not snap selection back to consent.
    rerender(
      <AgentRunSurface
        plan={{ ...consentPlan, steps: [...consentPlan.steps] }}
        runSteps={[]}
        phase="paused"
      />,
    );
    expect(screen.getByTestId('run-chronicle-row-0')).toHaveAttribute('data-selected', 'true');
    expect(screen.getByTestId('run-chronicle-row-1')).not.toHaveAttribute('data-selected');
  });

  it('does not host Run health accordion', () => {
    render(
      <AgentRunSurface
        plan={PLAN}
        runSteps={[]}
        phase="finished"
      />,
    );
    expect(screen.queryByTestId('agent-run-health')).toBeNull();
  });

  it('shows summary Approve for a resolved consent step (no blank form)', () => {
    const onConfirm = vi.fn();
    const onDecline = vi.fn();
    const consentPlan = {
      id: 'plan-consent',
      status: 'paused',
      brief: 'تقديم طلب إجازة مرضية ليوم واحد غدًا',
      steps: [
        {
          step_id: 0,
          intent: 'Submit leave',
          tool_name: 'call_host_api',
          // Slots + governed options come from the host catalog; the body was
          // already resolved server-side (governed code, grounded dates).
          consent_slots: [
            {
              field: 'leave_type',
              label: 'Leave Type',
              type: 'governed',
              required: true,
              options: [
                { code: 'annual', label: 'Annual Leave' },
                { code: 'sick', label: 'Sick Leave' },
              ],
            },
            { field: 'start_date', label: 'Start Date', type: 'date', required: true },
            { field: 'end_date', label: 'End Date', type: 'date', required: true },
            { field: 'days', label: 'Days', type: 'days', required: true },
          ],
          tool_args: {
            api_name: 'submit_my_leave',
            body: {
              leave_type: 'sick',
              start_date: '2026-09-22',
              end_date: '2026-09-22',
              days: 1,
            },
          },
          status: 'awaiting_approval',
          depends_on: [],
        },
      ],
    };
    render(
      <AgentRunSurface
        plan={consentPlan}
        runSteps={[]}
        phase="paused"
        onConfirmStep={onConfirm}
        onDeclineStep={onDecline}
        confirmingId={null}
        consentHero={(
          <div data-testid="consent-hero-card" data-consent-mode="status-strip">
            Needs your approval
          </div>
        )}
      />,
    );
    expect(screen.getByTestId('run-step-detail-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('timeline-consent-0')).toHaveAttribute('data-consent-mode', 'summary');
    const preview = screen.getByTestId('timeline-consent-summary-0');
    expect(preview).toHaveTextContent(/What will change/i);
    expect(preview).toHaveTextContent(/Submit leave request/i);
    expect(preview).toHaveTextContent(/Sick Leave/i);
    expect(preview).toHaveTextContent(/Creates a leave request/i);
    expect(preview).toHaveTextContent(/Nothing is submitted until you Approve/i);
    expect(preview).not.toHaveTextContent(/System check/i);
    expect(screen.queryByTestId('timeline-consent-form-0')).toBeNull();
    expect(screen.getAllByRole('button', { name: /^Approve$/i })).toHaveLength(1);
    fireEvent.click(screen.getByTestId('timeline-approve-0'));
    expect(onConfirm).toHaveBeenCalledWith(0, {
      body: {
        leave_type: 'sick',
        start_date: '2026-09-22',
        end_date: '2026-09-22',
        days: 1,
      },
    });
    const row = screen.getByTestId('run-chronicle-row-0');
    expect(row.querySelector('[data-testid="timeline-consent-0"]')).toBeNull();
  });

  it('shows inherited Chat details without engine jargon', () => {
    render(
      <AgentRunSurface
        plan={{
          ...PLAN,
          inherited_context: [
            { key: 'loan_type', value: 'emergency' },
            { key: 'amount', value: '3000' },
          ],
        }}
        runSteps={[]}
        phase="idle"
      />,
    );
    const panel = screen.getByTestId('agent-run-inherited-context');
    expect(panel).toHaveTextContent(/Carried from this conversation/i);
    expect(panel).toHaveTextContent(/Loan type · emergency/i);
    expect(panel).toHaveTextContent(/Amount · 3000/i);
    expect(panel).not.toHaveTextContent(/ConversationState|active_plans|Pulse|slots/i);
    expect(screen.queryByRole('button', { name: /Confirm/i })).toBeNull();
  });
});

describe('AgentRunSurface — step controls + plain-language log (Now only)', () => {
  const FAILED_PLAN = {
    ...PLAN,
    status: 'failed',
    steps: [
      PLAN.steps[0],
      {
        step_id: 1,
        intent: 'Load payroll records',
        tool_name: 'call_host_api',
        status: 'failed',
        error: "Missing required path parameter 'id'. Provide it in path_params.",
        depends_on: [0],
      },
    ],
  };

  it('offers Retry / Skip / Edit in Plan / Discuss in Plan mode on a failed step', () => {
    const onRetry = vi.fn();
    const onDiscussInPlan = vi.fn();
    render(
      <AgentRunSurface
        plan={FAILED_PLAN}
        runSteps={[]}
        phase="error"
        stepActions={{
          onRetry,
          onSkip: vi.fn(),
          onEditInPlan: vi.fn(),
          onDiscussInPlan,
        }}
      />,
    );
    // Failure auto-selects the urgent beat and opens the drawer.
    expect(screen.getByTestId('run-step-detail-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('beat-fail-fix')).toHaveTextContent(/Open Plan, edit this step/i);
    fireEvent.click(screen.getByTestId('step-action-retry'));
    expect(onRetry).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByTestId('step-action-discuss'));
    expect(onDiscussInPlan).toHaveBeenCalledWith(expect.objectContaining({ step_id: 1 }));
    expect(screen.getByTestId('step-action-edit')).toBeInTheDocument();
    expect(screen.getByTestId('step-action-skip')).toBeInTheDocument();
  });

  it('shows the plain-language activity log, open by default when something failed', () => {
    render(<AgentRunSurface plan={FAILED_PLAN} runSteps={[]} phase="error" />);
    const log = screen.getByTestId('human-activity-log');
    expect(log).toBeInTheDocument();
    expect(screen.getByTestId('human-activity-log-panel')).toHaveTextContent(/Couldn’t finish — Load payroll records/);
    expect(screen.getByTestId('human-activity-log-panel')).not.toHaveTextContent(/path_params/);
  });
});
