// src/__tests__/AIWorkspace.shell.test.jsx
// Sprint 16 — shell rewrite: id-keyed tabs (G6) + durable archive on close (G1).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ── Mock hooks, heavy children, and the API layer ────────────────────
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notifyFromError: vi.fn(), notify: vi.fn(), showFeedback: vi.fn() }),
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ pendingTransferId: null, clearPendingTransfer: vi.fn() }),
}));

vi.mock('../shell/AIWorkspaceHeader', () => ({ default: () => null }));
vi.mock('../shell/AIConversationView', () => ({ default: () => null }));
vi.mock('../shell/AIEmptyState', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));

vi.mock('../api/aiWorkspace', () => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  updateConversation: vi.fn(),
  deleteConversation: vi.fn(),
}));

import { AIWorkspace } from '../shell/AIWorkspace';
import AIConversationTabs from '../shell/AIConversationTabs';
import { listConversations, updateConversation } from '../api/aiWorkspace';

const conversations = [
  { id: 'conv-1', title: 'Alpha', conversation_type: 'chat', status: 'completed' },
  { id: 'conv-2', title: 'Beta', conversation_type: 'chat', status: 'working' },
];

beforeEach(() => {
  vi.clearAllMocks();
  listConversations.mockResolvedValue(conversations);
  updateConversation.mockResolvedValue({ id: 'conv-1', is_archived: true });
});

describe('AIConversationTabs id-keyed value (G6)', () => {
  it('highlights the active tab by id, not by index', () => {
    render(
      <AIConversationTabs
        conversations={conversations}
        activeId="conv-2"
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const tabs = screen.getAllByRole('tab');
    expect(tabs[0]).toHaveAttribute('aria-selected', 'false');
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true');
  });

  it('calls onSelect with the conversation id when a tab is clicked', () => {
    const onSelect = vi.fn();
    render(
      <AIConversationTabs
        conversations={conversations}
        activeId="conv-1"
        onSelect={onSelect}
        onNew={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('tab', { name: /Beta/ }));
    expect(onSelect).toHaveBeenCalledWith('conv-2');
  });
});

describe('AIWorkspace durable archive on close (G1)', () => {
  it('calls updateConversation with is_archived:true when a tab is closed', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const closeButtons = await screen.findAllByRole('button', {
      name: /Close conversation/,
    });
    fireEvent.click(closeButtons[0]);

    await waitFor(() => {
      expect(updateConversation).toHaveBeenCalledWith('test-token', 'conv-1', {
        is_archived: true,
      });
    });
  });
});
