// src/features/ai/test/DiscoveryComposer.test.jsx
// W6-B2 — DiscoveryComposer guided-discovery contract:
//   * empty conversation → Pulse greeting + composer
//   * needs_input       → clarifying question bubble + "Respond to AI's question…"
//   * plan_ready        → "Plan ready — review below" banner + Review plan/New task
//   * startDiscoveryPlan / advanceDiscovery wire the token, brief and id.
// Renders the REAL AIMessageBubble/AIInputBar (as AITaskPanel tests do) with
// only auth/notifications/API mocked.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../../../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn(), showFeedback: vi.fn() }),
}));

const { startDiscoveryPlan, advanceDiscovery } = vi.hoisted(() => ({
  startDiscoveryPlan: vi.fn(),
  advanceDiscovery: vi.fn(),
}));

vi.mock('../../../api/aiWorkspace', () => ({
  startDiscoveryPlan: (...args) => startDiscoveryPlan(...args),
  advanceDiscovery: (...args) => advanceDiscovery(...args),
}));

import DiscoveryComposer from '../../../shell/DiscoveryComposer';

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'Audit the emissions dataset for duplicates.',
  pattern: 'skill_chain',
  source: 'user_request',
  skill_name: 'data_quality',
  needs_confirmation: true,
  created_at: '2026-08-20T10:00:00Z',
  steps: Array.from({ length: 7 }, (_, i) => ({
    step_id: i,
    intent: `Step ${i + 1}`,
    tool_name: 'search_entity',
    tool_args: { dataset: 'emissions' },
    status: 'pending',
  })),
};

beforeEach(() => {
  vi.clearAllMocks();
  startDiscoveryPlan.mockReset();
  advanceDiscovery.mockReset();
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
});

describe('DiscoveryComposer — guided discovery (W6-B2)', () => {
  it('renders the composer for an empty conversation', () => {
    render(<DiscoveryComposer conversationId="conv-1" />);

    // Empty state is input-only — the greeting expands once the dialogue starts.
    expect(screen.getByLabelText('Message input')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask a question/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeInTheDocument();
  });

  it('asks a clarifying question while needs_input', async () => {
    render(<DiscoveryComposer conversationId="conv-1" />);

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'Audit duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Which dataset should we audit?')).toBeInTheDocument();
    // Input bar switches to the clarifying-question placeholder.
    expect(screen.getByPlaceholderText("Respond to AI's question…")).toBeInTheDocument();
  });

  it('calls startDiscoveryPlan and advanceDiscovery with the expected payloads', async () => {
    render(<DiscoveryComposer conversationId="conv-1" />);

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'Audit duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(startDiscoveryPlan).toHaveBeenCalledWith('test-token', {
        brief: 'Audit duplicates.',
        conversation_id: 'conv-1',
      });
    });

    fireEvent.change(await screen.findByLabelText('Message input'), { target: { value: 'The emissions dataset' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(advanceDiscovery).toHaveBeenCalledWith('test-token', 'plan-1', 'The emissions dataset');
    });
  });

  it('renders the plan-ready banner and hands the plan to onPlanReady', async () => {
    const onPlanReady = vi.fn();
    render(<DiscoveryComposer conversationId="conv-1" onPlanReady={onPlanReady} />);

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'Audit duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Which dataset should we audit?');

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'The emissions dataset' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByText('Plan ready — review below')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Review plan' }));
    expect(onPlanReady).toHaveBeenCalledTimes(1);
    expect(onPlanReady).toHaveBeenCalledWith(PLAN);

    // The composer resets after review — back to the input-only state.
    expect(await screen.findByLabelText('Message input')).toBeInTheDocument();
  });

  it('resets the composer when New task is chosen', async () => {
    render(<DiscoveryComposer conversationId="conv-1" />);

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'Audit duplicates.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText('Which dataset should we audit?');

    fireEvent.change(screen.getByLabelText('Message input'), { target: { value: 'The emissions dataset' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    fireEvent.click(await screen.findByRole('button', { name: 'New task' }));

    expect(await screen.findByLabelText('Message input')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeInTheDocument();
  });
});
