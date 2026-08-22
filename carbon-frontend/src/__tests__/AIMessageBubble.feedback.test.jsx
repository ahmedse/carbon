// src/__tests__/AIMessageBubble.feedback.test.jsx
// Sprint 9-B feedback controls on assistant AI messages.
// Avoids metadata.type === 'nl_query_result' (that triggers the lazy
// CarbonDataGrid import) — all fixtures here are plain chat messages.
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const assistantMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
  correction_text: '',
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

describe('AIMessageBubble feedback controls', () => {
  it('renders Accept / Reject / Correct affordances for assistant messages', async () => {
    renderBubble(assistantMessage, {
      onAccept: vi.fn(),
      onReject: vi.fn(),
      onCorrect: vi.fn(),
    });

    expect(screen.getByRole('button', { name: 'Accept response' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject response' })).toBeInTheDocument();
    // Correct lives in the overflow menu (compact hover toolbar).
    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    expect(await screen.findByRole('menuitem', { name: 'Correct' })).toBeInTheDocument();
  });

  it('does not render feedback buttons for user messages', () => {
    renderBubble(
      { id: 'msg-2', role: 'user', content: 'Hello', created_at: '2026-08-15T10:00:00Z' },
      { onAccept: vi.fn(), onReject: vi.fn(), onCorrect: vi.fn() },
    );

    expect(screen.queryByRole('button', { name: 'Accept response' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject response' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'More message actions' })).not.toBeInTheDocument();
  });

  it('invokes onAccept with the message when Accept is clicked', () => {
    const onAccept = vi.fn();
    renderBubble(assistantMessage, {
      onAccept,
      onReject: vi.fn(),
      onCorrect: vi.fn(),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Accept response' }));

    expect(onAccept).toHaveBeenCalledTimes(1);
    expect(onAccept).toHaveBeenCalledWith(assistantMessage);
  });

  it('reveals a TextField on Correct and calls onCorrect(message, text) on Save', async () => {
    const onCorrect = vi.fn();
    renderBubble(assistantMessage, {
      onAccept: vi.fn(),
      onReject: vi.fn(),
      onCorrect,
    });

    // Correct is behind the overflow menu.
    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Correct' }));

    const input = screen.getByLabelText(/correction/i);
    fireEvent.change(input, { target: { value: 'The correct answer is 42.' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(onCorrect).toHaveBeenCalledTimes(1);
    expect(onCorrect).toHaveBeenCalledWith(assistantMessage, 'The correct answer is 42.');
  });

  it('colors the thumb-up green but keeps the other tools when outcome is accepted', () => {
    renderBubble({ ...assistantMessage, outcome: 'accepted' }, {
      onAccept: vi.fn(),
      onReject: vi.fn(),
      onCorrect: vi.fn(),
    });

    // No text label anywhere.
    expect(screen.queryByText('Accepted')).not.toBeInTheDocument();
    // The up thumb is filled + light green.
    expect(screen.getByTestId('message-outcome-accepted')).toBeInTheDocument();
    expect(screen.getByTestId('ThumbUpAltIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('ThumbDownAltIcon')).not.toBeInTheDocument();
    expect(screen.getByTestId('message-outcome-accepted')).toHaveStyle({
      backgroundColor: 'rgba(46, 125, 50, 0.1)',
    });
    // The down thumb stays outlined (not colored).
    expect(screen.getByTestId('ThumbDownAltOutlinedIcon')).toBeInTheDocument();
    // Other tools are still there.
    expect(screen.getByRole('button', { name: 'Reject response' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy message' })).toBeInTheDocument();
  });
});

describe('AIMessageBubble outcome indicator (light thumbs)', () => {
  it('shows a light green thumb-up for accepted feedback', () => {
    renderBubble({ ...assistantMessage, outcome: 'accepted' }, { onAccept: vi.fn(), onReject: vi.fn() });

    expect(screen.getByTestId('message-outcome-accepted')).toBeInTheDocument();
    expect(screen.getByTestId('ThumbUpAltIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('ThumbDownAltIcon')).not.toBeInTheDocument();
    expect(screen.queryByText('Accepted')).not.toBeInTheDocument();
    // Other buttons remain visible.
    expect(screen.getByRole('button', { name: 'Reject response' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy message' })).toBeInTheDocument();
  });

  it('shows a light red thumb-down for rejected feedback', () => {
    renderBubble({ ...assistantMessage, outcome: 'rejected' }, { onAccept: vi.fn(), onReject: vi.fn() });

    expect(screen.getByTestId('message-outcome-rejected')).toBeInTheDocument();
    expect(screen.getByTestId('ThumbDownAltIcon')).toBeInTheDocument();
    expect(screen.queryByTestId('ThumbUpAltIcon')).not.toBeInTheDocument();
    expect(screen.queryByText('Rejected')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Accept response' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy message' })).toBeInTheDocument();
  });
});

describe('AIMessageBubble follow-up chips (G7 regression)', () => {
  const followUpMessage = {
    ...assistantMessage,
    metadata: {
      follow_up_questions: ['What is the trend?', 'Show anomalies'],
    },
  };

  it('invokes onFollowUp with the question when a follow-up chip is clicked', () => {
    const onFollowUp = vi.fn();
    renderBubble(followUpMessage, { onFollowUp });

    fireEvent.click(screen.getByRole('button', { name: 'What is the trend?' }));

    expect(onFollowUp).toHaveBeenCalledTimes(1);
    expect(onFollowUp).toHaveBeenCalledWith('What is the trend?');
  });

  it('renders both follow-up questions as clickable chips', () => {
    renderBubble(followUpMessage, { onFollowUp: vi.fn() });

    expect(screen.getByRole('button', { name: 'What is the trend?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show anomalies' })).toBeInTheDocument();
  });
});

describe('AIMessageBubble usage + status chips', () => {
  it('renders a usage chip from token_usage_json', () => {
    renderBubble({
      ...assistantMessage,
      token_usage_json: {
        model: 'gpt-4o',
        total_tokens: 1234,
        cost_usd: 0.0042,
        latency_ms: 950,
      },
    });

    expect(screen.getByText('gpt-4o · 1234 tok · $0.0042 · 950ms')).toBeInTheDocument();
  });

  it('omits missing usage fields from the usage chip', () => {
    renderBubble({
      ...assistantMessage,
      token_usage_json: { total_tokens: 512 },
    });

    expect(screen.getByText('512 tok')).toBeInTheDocument();
  });

  it('humanizes latency to seconds / minutes instead of raw ms', () => {
    renderBubble({
      ...assistantMessage,
      token_usage_json: {
        model: 'gpt-4o',
        total_tokens: 1234,
        cost_usd: 0.0042,
        latency_ms: 2702,
      },
    });

    expect(screen.getByText('gpt-4o · 1234 tok · $0.0042 · 2.7s')).toBeInTheDocument();

    // Over a minute → "m s" instead of a giant ms dump.
    expect(screen.queryByText(/2702ms/)).not.toBeInTheDocument();
  });

  it('shares the usage chip line with the time-ago timestamp (merged meta)', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    renderBubble({
      ...assistantMessage,
      created_at: fiveMinutesAgo,
      token_usage_json: { total_tokens: 1234, latency_ms: 950 },
    });

    // Both meta snippets live inside the same hover action row.
    expect(screen.getByText('1234 tok · 950ms')).toBeInTheDocument();
    expect(screen.getByText(/^[45]m ago$/)).toBeInTheDocument();
  });

  it('renders an "Interrupted" chip when status is stopped', () => {
    renderBubble({ ...assistantMessage, status: 'stopped' });

    expect(screen.getByText('Interrupted')).toBeInTheDocument();
  });

  it('renders an "Error" chip when status is failed', () => {
    renderBubble({ ...assistantMessage, status: 'failed' });

    expect(screen.getByText('Error')).toBeInTheDocument();
  });
});
