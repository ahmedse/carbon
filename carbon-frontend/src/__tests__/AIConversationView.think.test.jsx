// The Think switch shows only when the understanding model can return a trace.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const mockNotification = { notify: vi.fn(), notifyFromError: vi.fn() };
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => mockNotification,
}));

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
  listModels: vi.fn(),
  recordFeedback: vi.fn(),
  rejectSuggestion: vi.fn(),
  resumeConversation: vi.fn(),
  retryMessageStream: vi.fn(),
  sendMessageStream: vi.fn(),
  stopGeneration: vi.fn(),
  updateConversation: vi.fn(),
}));

import { getConversation, listModels, resumeConversation } from '../api/aiWorkspace';
import AIConversationView from '../shell/AIConversationView';

const conversation = {
  id: 'conv-1',
  title: 'Thread',
  status: 'completed',
  conversation_type: 'chat',
  visibility: 'private',
  user_id: 'user-1',
  messages: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  getConversation.mockResolvedValue(conversation);
  resumeConversation.mockResolvedValue({ conversation, catch_up: null });
});

function renderView() {
  return render(
    <MemoryRouter>
      <AIConversationView conversationId="conv-1" />
    </MemoryRouter>,
  );
}

describe('Think switch', () => {
  it('shows when the understanding model declares reasoning', async () => {
    listModels.mockResolvedValue({ models: [], thinking_available: true });
    renderView();
    expect(await screen.findByRole('checkbox', { name: /Think/i })).toBeTruthy();
  });

  it('stays hidden when the model has no reasoning mode', async () => {
    listModels.mockResolvedValue({ models: [], thinking_available: false });
    renderView();
    await waitFor(() => expect(listModels).toHaveBeenCalled());
    expect(screen.queryByRole('checkbox', { name: /Think/i })).toBeNull();
  });

  it('stays hidden when the flag cannot be read', async () => {
    listModels.mockRejectedValue(new Error('offline'));
    renderView();
    await waitFor(() => expect(listModels).toHaveBeenCalled());
    expect(screen.queryByRole('checkbox', { name: /Think/i })).toBeNull();
  });
});
