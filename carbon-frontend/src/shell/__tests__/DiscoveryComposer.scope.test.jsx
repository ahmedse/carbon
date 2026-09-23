import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DiscoveryComposer from '../DiscoveryComposer';

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't' }),
}));
vi.mock('../../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn() }),
}));

const sendBox = vi.hoisted(() => ({ text: 'أريد عمل اجازه' }));
const startDiscoveryPlan = vi.fn();
const advanceDiscovery = vi.fn();
const finalizeDiscovery = vi.fn();
const createPlan = vi.fn();
vi.mock('../../api/aiWorkspace', () => ({
  startDiscoveryPlan: (...a) => startDiscoveryPlan(...a),
  advanceDiscovery: (...a) => advanceDiscovery(...a),
  finalizeDiscovery: (...a) => finalizeDiscovery(...a),
  createPlan: (...a) => createPlan(...a),
}));

vi.mock('../AIMessageBubble', () => ({
  default: ({ message }) => <div data-testid="bubble">{message.content}</div>,
}));
vi.mock('../AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../AIInputBar', () => ({
  default: ({ onSend }) => (
    <button type="button" onClick={() => onSend(sendBox.text)}>
      send-brief
    </button>
  ),
}));

describe('DiscoveryComposer scope gate', () => {
  beforeEach(() => {
    sendBox.text = 'أريد عمل اجازه';
    startDiscoveryPlan.mockReset();
    advanceDiscovery.mockReset();
    finalizeDiscovery.mockReset();
    createPlan.mockReset();
  });

  it('shows recommended leave cards and does not enable Plan now', async () => {
    startDiscoveryPlan.mockResolvedValue({
      id: null,
      status: 'recommended',
      plannable: false,
      route: {
        class: 'TRANSACTION',
        message: 'That sounds like a personal leave request.',
        recommended: 'leave_request',
        plannable: false,
        cards: [
          { id: 'leave_request', label: 'Create a leave-request plan', primary: true },
          { id: 'compliance_report', label: 'Plan a leave-compliance report', primary: false },
          { id: 'handoff_chat', label: 'Ask in Chat instead', primary: false },
        ],
      },
      turns: [],
    });

    render(<DiscoveryComposer conversationId="c1" />);
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));

    expect(await screen.findByTestId('scope-route-card')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create a leave-request plan/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Plan now' })).not.toBeInTheDocument();
  });

  it('leave_request creates an Agent plan and stays off Chat', async () => {
    const onPlanReady = vi.fn();
    const onSwitchToChat = vi.fn();
    startDiscoveryPlan.mockResolvedValue({
      id: null,
      status: 'recommended',
      plannable: false,
      brief: 'أريد عمل اجازه',
      route: {
        class: 'TRANSACTION',
        message: 'That sounds like a personal leave request.',
        recommended: 'leave_request',
        plannable: false,
        cards: [
          { id: 'leave_request', label: 'Create a leave-request plan', primary: true },
          { id: 'handoff_chat', label: 'Ask in Chat instead', primary: false },
        ],
      },
      turns: [],
    });
    createPlan.mockResolvedValue({
      id: 'plan-leave-1',
      status: 'pending_approval',
      brief: 'أريد عمل اجازه',
      steps: [{ step_id: 1, intent: 'Submit leave' }],
    });

    render(
      <DiscoveryComposer
        conversationId="c1"
        onPlanReady={onPlanReady}
        onSwitchToChat={onSwitchToChat}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));
    fireEvent.click(await screen.findByRole('button', { name: /Create a leave-request plan/i }));

    await waitFor(() => {
      expect(createPlan).toHaveBeenCalledWith('t', {
        brief: 'أريد عمل اجازه',
        conversation_id: 'c1',
      });
    });
    expect(onPlanReady).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'plan-leave-1', status: 'pending_approval' }),
    );
    expect(onSwitchToChat).not.toHaveBeenCalled();
  });

  it('Ask in Chat remains an explicit opt-in handoff', async () => {
    const onSwitchToChat = vi.fn();
    startDiscoveryPlan.mockResolvedValue({
      id: null,
      status: 'recommended',
      plannable: false,
      brief: 'أريد عمل اجازه',
      route: {
        class: 'TRANSACTION',
        recommended: 'leave_request',
        plannable: false,
        cards: [
          { id: 'leave_request', label: 'Create a leave-request plan', primary: true },
          { id: 'handoff_chat', label: 'Ask in Chat instead', primary: false },
        ],
      },
      turns: [],
    });

    render(
      <DiscoveryComposer conversationId="c1" onSwitchToChat={onSwitchToChat} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));
    fireEvent.click(await screen.findByRole('button', { name: /Ask in Chat instead/i }));

    expect(onSwitchToChat).toHaveBeenCalledWith('أريد عمل اجازه');
    expect(createPlan).not.toHaveBeenCalled();
  });

  it('leave card plans the leave reply, not the non-leave discovery seed', async () => {
    const onPlanReady = vi.fn();
    const leaveReply = 'اريد طلب اجازة بدون مرتب لمدة 3 شهور, نبدأ من 1 فبراير 2027';
    startDiscoveryPlan.mockResolvedValue({
      id: 'disc-1',
      status: 'needs_input',
      plannable: true,
      question: 'Could you tell me a bit more about what you want to accomplish?',
      turns: [{ question: 'Could you tell me a bit more about what you want to accomplish?', reply: null }],
    });
    advanceDiscovery.mockResolvedValue({
      id: 'disc-1',
      status: 'recommended',
      plannable: false,
      turns: [{
        question: 'Could you tell me a bit more about what you want to accomplish?',
        reply: leaveReply,
      }],
      route: {
        class: 'TRANSACTION',
        recommended: 'leave_request',
        plannable: false,
        cards: [
          { id: 'leave_request', label: 'Create a leave-request plan', primary: true },
        ],
      },
    });
    createPlan.mockResolvedValue({
      id: 'plan-leave-2',
      status: 'pending_approval',
      steps: [{ step_id: 1, intent: 'Submit leave' }],
    });

    render(<DiscoveryComposer conversationId="c1" onPlanReady={onPlanReady} />);
    sendBox.text = 'Run via Agent';
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));
    expect(await screen.findByText(/Could you tell me a bit more/)).toBeInTheDocument();
    sendBox.text = leaveReply;
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));
    fireEvent.click(await screen.findByRole('button', { name: /Create a leave-request plan/i }));

    await waitFor(() => {
      expect(createPlan).toHaveBeenCalledWith('t', {
        brief: `Run via Agent\n${leaveReply}`,
        conversation_id: 'c1',
      });
    });
    expect(onPlanReady).toHaveBeenCalled();
  });

  it('loan process-dial plan_ready skips clarifying UI', async () => {
    const onPlanReady = vi.fn();
    startDiscoveryPlan.mockResolvedValue({
      id: 'plan-loan-1',
      status: 'plan_ready',
      plannable: true,
      plan: {
        id: 'plan-loan-1',
        status: 'pending_approval',
        brief: 'أريد قرض طوارئ 5000 لمدة 12 شهر غدا',
        steps: [{ step_id: 1, intent: 'Submit loan', tool_args: { api_name: 'submit_my_loan' } }],
      },
      turns: [],
      route: { class: 'TRANSACTION', plannable: true, cards: [] },
    });

    render(
      <DiscoveryComposer conversationId="c1" onPlanReady={onPlanReady} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'send-brief' }));

    await waitFor(() => {
      expect(onPlanReady).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'plan-loan-1', status: 'pending_approval' }),
      );
    });
    expect(screen.queryByTestId('scope-route-card')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Plan now' })).not.toBeInTheDocument();
  });
});
