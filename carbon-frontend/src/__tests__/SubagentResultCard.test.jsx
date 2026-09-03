// src/__tests__/SubagentResultCard.test.jsx
// Wave I4-F — self-contained polling card for a conversation-scoped subagent.
// Covers: initial pending render, poll → completed transition with
// result_summary, failed error alert, no polling when already terminal, and
// timer cleanup on unmount.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import SubagentResultCard from '../shell/SubagentResultCard';

const getSubagent = vi.fn();

vi.mock('../api/aiWorkspace', () => ({
  getSubagent: (...args) => getSubagent(...args),
}));

const PENDING = {
  id: 'sub-1',
  name: 'Dedupe auditor',
  status: 'pending',
  scope_restriction: {},
  result_summary: null,
  result_detail: null,
  error: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('SubagentResultCard', () => {
  it('renders the subagent name and a Pending chip initially', () => {
    render(<SubagentResultCard subagent={PENDING} token="test-token" conversationId="conv-1" />);

    expect(screen.getByText('Dedupe auditor')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('polls and transitions to Completed with its result_summary', async () => {
    vi.useFakeTimers();
    getSubagent.mockResolvedValue({ ...PENDING, status: 'completed', result_summary: 'Done' });

    render(<SubagentResultCard subagent={PENDING} token="test-token" conversationId="conv-1" />);

    expect(screen.getByText('Pending')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(getSubagent).toHaveBeenCalledWith('test-token', 'conv-1', 'sub-1');
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('renders an Alert with the error when the subagent failed', () => {
    render(
      <SubagentResultCard
        subagent={{ ...PENDING, status: 'failed', error: 'Boom' }}
        token="test-token"
        conversationId="conv-1"
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Boom');
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('does not poll when the subagent is already terminal', () => {
    vi.useFakeTimers();

    render(
      <SubagentResultCard
        subagent={{ ...PENDING, status: 'completed', result_summary: 'Done' }}
        token="test-token"
        conversationId="conv-1"
      />,
    );

    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(getSubagent).not.toHaveBeenCalled();
  });

  it('clears its poll timer on unmount', () => {
    vi.useFakeTimers();

    const { unmount } = render(
      <SubagentResultCard subagent={PENDING} token="test-token" conversationId="conv-1" />,
    );

    unmount();

    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(getSubagent).not.toHaveBeenCalled();
  });
});
