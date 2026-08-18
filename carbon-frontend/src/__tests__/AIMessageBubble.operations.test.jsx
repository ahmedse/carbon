// src/__tests__/AIMessageBubble.operations.test.jsx
// Phase 19-B — hover/overflow menu: Copy, Retry, Edit, Delete + confirm dialog
// and soft-deleted placeholder rendering.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AIMessageBubble from '../shell/AIMessageBubble';

const assistantMessage = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the answer.',
  created_at: '2026-08-15T10:00:00Z',
  outcome: null,
};

const userMessage = {
  id: 'msg-2',
  role: 'user',
  content: 'What is the answer?',
  created_at: '2026-08-15T10:00:00Z',
};

function renderBubble(message, props = {}) {
  return render(
    <MemoryRouter>
      <AIMessageBubble message={message} {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe('AIMessageBubble overflow menu (Phase 19-B)', () => {
  it('offers Retry and Delete for assistant replies', async () => {
    renderBubble(assistantMessage, { onRetry: vi.fn(), onDelete: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));

    expect(await screen.findByRole('menuitem', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toBeInTheDocument();
  });

  it('offers Edit and Delete for user messages', async () => {
    renderBubble(userMessage, { onEdit: vi.fn(), onDelete: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));

    expect(await screen.findByRole('menuitem', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toBeInTheDocument();
  });

  it('invokes onRetry with the assistant message when Retry is clicked', async () => {
    const onRetry = vi.fn();
    renderBubble(assistantMessage, { onRetry, onDelete: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Retry' }));

    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onRetry).toHaveBeenCalledWith(assistantMessage);
  });

  it('reveals an Edit field and calls onEdit(message, text) on Save', async () => {
    const onEdit = vi.fn();
    renderBubble(userMessage, { onEdit, onDelete: vi.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Edit' }));

    const input = await screen.findByLabelText('Edit message');
    fireEvent.change(input, { target: { value: 'What is the revised answer?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(userMessage, 'What is the revised answer?');
  });
});

describe('AIMessageBubble delete confirmation (Phase 19-B)', () => {
  it('shows a confirm dialog and calls onDelete on confirm', async () => {
    const onDelete = vi.fn();
    renderBubble(assistantMessage, { onRetry: vi.fn(), onDelete });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));

    expect(await screen.findByText('Delete message?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith(assistantMessage);
  });

  it('does not call onDelete when Cancel is clicked', async () => {
    const onDelete = vi.fn();
    renderBubble(userMessage, { onEdit: vi.fn(), onDelete });

    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));
    await screen.findByText('Delete message?');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onDelete).not.toHaveBeenCalled();
  });
});

describe('AIMessageBubble soft-deleted placeholder (Phase 19-B)', () => {
  it('renders a dimmed placeholder for a deleted assistant reply', () => {
    renderBubble({ ...assistantMessage, is_deleted: true });

    expect(screen.getByText('This reply was removed.')).toBeInTheDocument();
    expect(screen.queryByText('Here is the answer.')).not.toBeInTheDocument();
  });

  it('renders a dimmed placeholder for a deleted user message', () => {
    renderBubble({ ...userMessage, is_deleted: true });

    expect(screen.getByText('Your message was removed.')).toBeInTheDocument();
    expect(screen.queryByText('What is the answer?')).not.toBeInTheDocument();
  });
});
