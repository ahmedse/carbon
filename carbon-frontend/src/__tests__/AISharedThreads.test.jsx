// src/__tests__/AISharedThreads.test.jsx
// Phase 12 — Shared Threads frontend (read-only collaboration).
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ── Mock hooks, heavy children, and the API layer ────────────────────
// Notification helpers must be STABLE across renders: AIConversationView lists
// notifyFromError in its load/resume effect deps, so a fresh vi.fn() per render
// would recreate the load callback and trigger an infinite re-render loop.
const notificationMocks = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
  showFeedback: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }) => React.createElement(React.Fragment, null, children),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => notificationMocks,
}));

vi.mock('../api/aiWorkspace', () => ({
  acceptSuggestion: vi.fn(),
  createArtifact: vi.fn(),
  exportConversation: vi.fn(),
  getConversation: vi.fn(),
  listMessages: vi.fn(),
  recordFeedback: vi.fn(),
  rejectSuggestion: vi.fn(),
  resumeConversation: vi.fn(),
  sendMessageStream: vi.fn(),
  stopGeneration: vi.fn(),
  updateConversation: vi.fn(),
}));

vi.mock('../api/dq', () => ({ createDQRule: vi.fn() }));

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock('../api/modules', () => ({ fetchModules: vi.fn() }));

vi.mock('../shell/useExecuteMode', () => ({
  useExecuteMode: () => ({ executeMode: false, setExecuteMode: vi.fn() }),
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ transferTask: vi.fn(), pendingTransferId: null, clearPendingTransfer: vi.fn() }),
}));

vi.mock('../shell/AIMessageBubble', () => ({ default: () => null }));
vi.mock('../shell/AIContextPanel', () => ({ default: () => null }));
vi.mock('../shell/AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/AIModelSelect', () => ({ default: () => null }));
vi.mock('../shell/AIInputBar', () => ({
  default: () => React.createElement('div', { 'data-testid': 'input-bar' }),
}));

import { useAuth } from '../auth/AuthContext';
import AIConversationTabs from '../shell/AIConversationTabs';
import AIConversationView from '../shell/AIConversationView';
import { getConversation, resumeConversation, updateConversation } from '../api/aiWorkspace';
import { apiFetch } from '../api/api';

const defaultAuth = {
  user: { id: 7 },
  token: 'test-token',
  userCapabilities: [],
  isGlobalAdminFlag: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  useAuth.mockReturnValue(defaultAuth);
  resumeConversation.mockResolvedValue({});
  updateConversation.mockResolvedValue({});
});

describe('AIConversationTabs shared-thread grouping (a)', () => {
  const conversations = [
    { id: 'owned-1', title: 'My Report', conversation_type: 'report_draft', status: 'completed' },
    {
      id: 'shared-1',
      title: 'Teammate Report',
      conversation_type: 'report_draft',
      status: 'completed',
      visibility: 'shared',
      user_id: 99,
    },
  ];

  it('renders a "Shared" chip on non-owned shared tabs', () => {
    render(
      <AIConversationTabs
        conversations={conversations}
        activeId="owned-1"
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('Shared')).toBeInTheDocument();
  });

  it('hides the close button on non-owned shared tabs but keeps it on owned tabs', () => {
    render(
      <AIConversationTabs
        conversations={conversations}
        activeId="owned-1"
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Close conversation My Report')).toBeInTheDocument();
    expect(screen.queryByLabelText('Close conversation Teammate Report')).not.toBeInTheDocument();
  });

  it('groups owned tabs first, then a divider, then shared tabs', () => {
    render(
      <AIConversationTabs
        conversations={conversations}
        activeId="owned-1"
        onSelect={vi.fn()}
        onNew={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole('separator')).toBeInTheDocument();
    const tabs = screen.getAllByRole('tab');
    expect(tabs[0].textContent).toContain('My Report');
    expect(tabs[1].textContent).toContain('Teammate Report');
  });
});

describe('AIConversationView read-only collaboration (b)', () => {
  it('hides the input bar and shows the read-only banner for a non-owned shared thread', async () => {
    getConversation.mockResolvedValue({
      id: 'shared-1',
      title: 'Shared Thread',
      visibility: 'shared',
      user_id: 99,
      status: 'completed',
      messages: [],
    });

    render(<AIConversationView conversationId="shared-1" />);

    expect(await screen.findByText('You have read-only access to this shared thread.')).toBeInTheDocument();
    expect(screen.queryByTestId('input-bar')).not.toBeInTheDocument();
    // Share toggle must not be shown to non-owners.
    expect(screen.queryByRole('button', { name: 'Share' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Shared' })).not.toBeInTheDocument();
  });
});

describe('AIConversationView Share toggle (c)', () => {
  it('calls updateConversation with {visibility:"shared"} when toggled by the owner', async () => {
    getConversation.mockResolvedValue({
      id: 'owned-1',
      title: 'My Thread',
      visibility: 'private',
      user_id: 7,
      status: 'completed',
      messages: [],
    });

    render(<AIConversationView conversationId="owned-1" />);

    const shareButton = await screen.findByRole('button', { name: 'Share' });
    fireEvent.click(shareButton);

    await waitFor(() => {
      expect(updateConversation).toHaveBeenCalledWith('test-token', 'owned-1', { visibility: 'shared' });
    });

    // Local state flips the label to "Shared".
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Shared' })).toBeInTheDocument();
    });
  });

  it('does not render the Share toggle for a non-owner', async () => {
    getConversation.mockResolvedValue({
      id: 'shared-2',
      title: 'Shared Thread',
      visibility: 'shared',
      user_id: 99,
      status: 'completed',
      messages: [],
    });

    render(<AIConversationView conversationId="shared-2" />);

    await screen.findByText('You have read-only access to this shared thread.');
    expect(screen.queryByRole('button', { name: 'Share' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Shared' })).not.toBeInTheDocument();
  });
});

describe('AuthContext user.id enabler (d)', () => {
  it('exposes user.id after accounts/me/context/ returns data.user.id', async () => {
    apiFetch.mockResolvedValue({
      user: { id: 7 },
      perspectives: ['dashboards'],
      capabilities: [],
      is_global_admin: false,
    });

    // Seed a stored user so the provider restores auth state on mount.
    localStorage.setItem(
      'user',
      JSON.stringify({ username: 'alice', token: 'stored-token', refresh: 'ref', roles: [] }),
    );

    // Use the REAL AuthProvider/useAuth (bypass the top-level mock) so we
    // exercise fetchPerspectiveContext + the mount restore path.
    const actual = await vi.importActual('../auth/AuthContext');
    const { AuthProvider: RealAuthProvider, useAuth: RealUseAuth } = actual;

    function Consumer() {
      const { user } = RealUseAuth();
      return React.createElement('span', { 'data-testid': 'uid' }, String(user?.id ?? ''));
    }

    render(
      <RealAuthProvider>
        <Consumer />
      </RealAuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('uid')).toHaveTextContent('7');
    });
  });
});
