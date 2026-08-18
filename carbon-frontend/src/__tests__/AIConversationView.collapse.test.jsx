// src/__tests__/AIConversationView.collapse.test.jsx
// Phase 21-C — Copilot-style thread chrome: session divider and the
// older-messages collapse toggle on long threads.
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

import { getConversation, resumeConversation } from '../api/aiWorkspace';
import AIConversationView from '../shell/AIConversationView';

// 18 messages → older region = 18 - 14 = 4 messages behind the toggle.
function buildMessages(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: `m${i + 1}`,
    role: i % 2 === 0 ? 'user' : 'assistant',
    content: `Message ${i + 1}`,
    created_at: `2026-08-16T10:00:${String(i).padStart(2, '0')}Z`,
  }));
}

function makeConversation(messages) {
  return {
    id: 'conv-1',
    title: 'Long thread',
    status: 'completed',
    conversation_type: 'chat',
    visibility: 'private',
    user_id: 'user-1',
    messages,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getConversation.mockReset();
  resumeConversation.mockReset();
  getConversation.mockResolvedValue(makeConversation(buildMessages(18)));
  resumeConversation.mockResolvedValue({ conversation: makeConversation(buildMessages(18)), catch_up: null });
});

function renderView() {
  return render(
    <MemoryRouter>
      <AIConversationView conversationId="conv-1" />
    </MemoryRouter>,
  );
}

describe('AIConversationView Copilot-style thread chrome (Phase 21-C)', () => {
  it('shows a Session divider above the thread', async () => {
    renderView();
    expect(await screen.findByText('Session')).toBeInTheDocument();
  });

  it('collapses older messages behind a toggle on long threads', async () => {
    renderView();
    const toggle = await screen.findByRole('button', { name: 'Show older messages' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('Show 4 older messages')).toBeInTheDocument();

    // Recent messages are visible while older ones are inside the collapsed region.
    expect(screen.getByText('Message 18')).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(await screen.findByRole('button', { name: 'Hide older messages' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(screen.getByText('Message 1')).toBeInTheDocument();
  });

  it('does not render the toggle on short threads', async () => {
    getConversation.mockResolvedValue(makeConversation(buildMessages(4)));
    resumeConversation.mockResolvedValue({
      conversation: makeConversation(buildMessages(4)),
      catch_up: null,
    });
    renderView();
    await waitFor(() => expect(screen.getByText('Message 4')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /older messages/i })).not.toBeInTheDocument();
  });
});
