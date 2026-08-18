// src/__tests__/AIConversationView.operations.test.jsx
// Phase 19-B — message-level retry/edit/delete handlers wired through the view.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const mockNotify = vi.fn();
const mockNotifyFromError = vi.fn();
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify, notifyFromError: mockNotifyFromError }),
}));

// Heavy children that fetch/stream on their own — stub them out.
vi.mock('../shell/AIContextPanel', () => ({ default: () => null }));
vi.mock('../shell/AIInputBar', () => ({ default: () => null }));
vi.mock('../shell/AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/AIModelSelect', () => ({ default: () => null }));

vi.mock('../api/aiWorkspace', () => ({
  acceptSuggestion: vi.fn(),
  createArtifact: vi.fn(),
  deleteMessage: vi.fn(),
  exportConversation: vi.fn(),
  getConversation: vi.fn(),
  listMessages: vi.fn(),
  recordFeedback: vi.fn(),
  rejectSuggestion: vi.fn(),
  resumeConversation: vi.fn(),
  retryMessageStream: vi.fn(),
  sendMessageStream: vi.fn(),
  stopGeneration: vi.fn(),
  updateConversation: vi.fn(),
}));

import {
  deleteMessage,
  getConversation,
  resumeConversation,
  retryMessageStream,
} from '../api/aiWorkspace';
import AIConversationView from '../shell/AIConversationView';

const CONVERSATION = {
  id: 'conv-1',
  title: 'Test thread',
  status: 'completed',
  conversation_type: 'chat',
  visibility: 'private',
  user_id: 'user-1',
  messages: [
    { id: 'm1', role: 'user', content: 'Hello', created_at: '2026-08-16T10:00:00Z' },
    { id: 'm2', role: 'assistant', content: 'Hi there', created_at: '2026-08-16T10:00:01Z' },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  getConversation.mockReset();
  resumeConversation.mockReset();
  retryMessageStream.mockReset();
  deleteMessage.mockReset();
  getConversation.mockResolvedValue(CONVERSATION);
  resumeConversation.mockResolvedValue({ conversation: CONVERSATION, catch_up: null });
  retryMessageStream.mockResolvedValue(undefined);
  deleteMessage.mockResolvedValue({ deleted: 'm1' });
});

function renderView() {
  return render(
    <MemoryRouter>
      <AIConversationView conversationId="conv-1" />
    </MemoryRouter>,
  );
}

describe('AIConversationView retry (Phase 19-B)', () => {
  it('retries the parent user turn from an assistant reply', async () => {
    renderView();
    expect(await screen.findByText('Hi there')).toBeInTheDocument();

    // Two bubbles → two "More message actions" buttons (user first, assistant second).
    const moreButtons = screen.getAllByRole('button', { name: 'More message actions' });
    fireEvent.click(moreButtons[1]);
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Retry' }));

    await waitFor(() =>
      expect(retryMessageStream).toHaveBeenCalledWith(
        'test-token',
        'conv-1',
        'm1',
        expect.objectContaining({ content: undefined }),
      ),
    );
  });
});

describe('AIConversationView edit (Phase 19-B)', () => {
  it('updates the user text and regenerates via the retry stream', async () => {
    renderView();
    expect(await screen.findByText('Hello')).toBeInTheDocument();

    const moreButtons = screen.getAllByRole('button', { name: 'More message actions' });
    fireEvent.click(moreButtons[0]);
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Edit' }));

    const input = await screen.findByLabelText('Edit message');
    fireEvent.change(input, { target: { value: 'Hello, revised' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    // Optimistic text update + retry stream carries the new content.
    await waitFor(() => expect(screen.getByText('Hello, revised')).toBeInTheDocument());
    await waitFor(() =>
      expect(retryMessageStream).toHaveBeenCalledWith(
        'test-token',
        'conv-1',
        'm1',
        expect.objectContaining({ content: 'Hello, revised' }),
      ),
    );
  });
});

describe('AIConversationView delete (Phase 19-B)', () => {
  it('deletes a user turn and its descendant reply optimistically', async () => {
    renderView();
    expect(await screen.findByText('Hello')).toBeInTheDocument();

    const moreButtons = screen.getAllByRole('button', { name: 'More message actions' });
    fireEvent.click(moreButtons[0]);
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));

    // Confirm dialog.
    expect(await screen.findByText('Delete message?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(deleteMessage).toHaveBeenCalledWith('test-token', 'conv-1', 'm1'),
    );
    // Thread-cut: both the user message and its descendant reply are removed.
    await waitFor(() => expect(screen.queryByText('Hello')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('Hi there')).not.toBeInTheDocument());
  });

  it('rolls back the optimistic delete when the server call fails', async () => {
    deleteMessage.mockRejectedValue(new Error('server error'));
    renderView();
    expect(await screen.findByText('Hello')).toBeInTheDocument();

    const moreButtons = screen.getAllByRole('button', { name: 'More message actions' });
    fireEvent.click(moreButtons[0]);
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));
    await screen.findByText('Delete message?');
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(mockNotifyFromError).toHaveBeenCalled());
    // The message remains visible after rollback.
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there')).toBeInTheDocument();
  });
});
