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
  it('renders Accept / Reject / Correct buttons for assistant messages', () => {
    renderBubble(assistantMessage, {
      onAccept: vi.fn(),
      onReject: vi.fn(),
      onCorrect: vi.fn(),
    });

    expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Correct' })).toBeInTheDocument();
  });

  it('does not render feedback buttons for user messages', () => {
    renderBubble(
      { id: 'msg-2', role: 'user', content: 'Hello', created_at: '2026-08-15T10:00:00Z' },
      { onAccept: vi.fn(), onReject: vi.fn(), onCorrect: vi.fn() },
    );

    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Correct' })).not.toBeInTheDocument();
  });

  it('invokes onAccept with the message when Accept is clicked', () => {
    const onAccept = vi.fn();
    renderBubble(assistantMessage, {
      onAccept,
      onReject: vi.fn(),
      onCorrect: vi.fn(),
    });

    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

    expect(onAccept).toHaveBeenCalledTimes(1);
    expect(onAccept).toHaveBeenCalledWith(assistantMessage);
  });

  it('reveals a TextField on Correct and calls onCorrect(message, text) on Save', () => {
    const onCorrect = vi.fn();
    renderBubble(assistantMessage, {
      onAccept: vi.fn(),
      onReject: vi.fn(),
      onCorrect,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Correct' }));

    const input = screen.getByLabelText(/correction/i);
    fireEvent.change(input, { target: { value: 'The correct answer is 42.' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(onCorrect).toHaveBeenCalledTimes(1);
    expect(onCorrect).toHaveBeenCalledWith(assistantMessage, 'The correct answer is 42.');
  });

  it('renders an Accepted chip and hides feedback buttons when outcome is set', () => {
    renderBubble({ ...assistantMessage, outcome: 'accepted' });

    expect(screen.getByText('Accepted')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Correct' })).not.toBeInTheDocument();
  });
});
