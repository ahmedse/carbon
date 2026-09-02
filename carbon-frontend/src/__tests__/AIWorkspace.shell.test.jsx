// src/__tests__/AIWorkspace.shell.test.jsx
// Sprint 16 — shell rewrite: id-keyed tabs (G6) + durable archive on close (G1).
// W5-A (ADR-0014) — Chat/Agent mode split at workspace level: the header owns
// the mode buttons + safety contract; the activity bar is mode-specific.
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

// The REAL AIWorkspaceHeader renders so the W5-A mode buttons + safety
// contract can be exercised. Its AIContextMenu is mount-safe with a null
// conversationId (checkpoint load is gated on open && conversationId).
// vi.mock('../shell/AIWorkspaceHeader', () => ({ default: () => null }));
vi.mock('../shell/AIConversationView', () => ({ default: () => null }));
vi.mock('../shell/AISuggestionRail', () => ({ default: () => null }));
vi.mock('../shell/AIEmptyState', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/InvestigateTab', () => ({ default: () => <div data-testid="investigate-tab" /> }));
vi.mock('../shell/AIUsageTab', () => ({ default: () => <div data-testid="usage-tab" /> }));
vi.mock('../shell/AISettingsTab', () => ({ default: () => <div data-testid="settings-tab" /> }));
vi.mock('../shell/AIMemoryConsole', () => ({ default: () => <div data-testid="memory-console" /> }));
vi.mock('../shell/AIAgentPanel', () => ({ default: () => <div data-testid="agent-tab" /> }));
vi.mock('../shell/AITaskPanel', () => ({
  default: ({ externalTab }) => <div data-testid="task-panel" data-tab={externalTab ?? 'tasks'} />,
}));

vi.mock('../api/aiPulse', () => ({
  listDomainManifests: vi.fn().mockResolvedValue({ apps: [] }),
}));

vi.mock('../api/aiWorkspace', () => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  updateConversation: vi.fn(),
  deleteConversation: vi.fn(),
  sendMessage: vi.fn(),
  findOpenConversation: vi.fn(),
  getUsageSummary: vi.fn(),
  getUsageByConversation: vi.fn(),
  getProfile: vi.fn(),
  patchProfile: vi.fn(),
  listModels: vi.fn(),
  listFacts: vi.fn(),
  listEpisodes: vi.fn(),
  getRelationship: vi.fn(),
  forgetFact: vi.fn(),
  updateMemoryFact: vi.fn(),
  restoreMemoryFact: vi.fn(),
  listOrgMemory: vi.fn(),
  createCheckpoint: vi.fn(),
  listCheckpoints: vi.fn(),
  restoreConversation: vi.fn(),
  forkConversation: vi.fn(),
}));

import { AIWorkspace } from '../shell/AIWorkspace';
import AIConversationTabs from '../shell/AIConversationTabs';
import { createConversation, findOpenConversation, listConversations, updateConversation } from '../api/aiWorkspace';

const conversations = [
  { id: 'conv-1', title: 'Alpha', conversation_type: 'chat', status: 'completed' },
  { id: 'conv-2', title: 'Beta', conversation_type: 'chat', status: 'working' },
];

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  listConversations.mockResolvedValue(conversations);
  createConversation.mockResolvedValue({ id: 'conv-new', conversation_type: 'chat', title: 'New Chat' });
  findOpenConversation.mockResolvedValue(null);
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

    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'false');
    expect(options[1]).toHaveAttribute('aria-selected', 'true');
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

    fireEvent.click(screen.getByRole('option', { name: /Beta/ }));
    expect(onSelect).toHaveBeenCalledWith('conv-2');
  });
});

describe('AIWorkspace durable archive on close (G1)', () => {
  it('calls updateConversation with is_archived:true when a session is archived', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    // Sessions drawer is collapsed by default — open it via the activity bar.
    const sessionsButton = await screen.findByRole('button', { name: 'Sessions' });
    fireEvent.click(sessionsButton);

    const menuButton = await screen.findByRole('button', {
      name: 'Session options for Alpha',
    });
    fireEvent.click(menuButton);

    const archiveItem = await screen.findByRole('menuitem', { name: 'Archive' });
    fireEvent.click(archiveItem);

    await waitFor(() => {
      expect(updateConversation).toHaveBeenCalledWith('test-token', 'conv-1', {
        is_archived: true,
      });
    });
  });
});

describe('AIWorkspace sessions drawer starts collapsed (Phase 23-C)', () => {
  it('does not render the sessions panel until the Sessions icon is clicked', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    expect(screen.queryByRole('listbox', { name: 'Conversation sessions' })).not.toBeInTheDocument();

    const sessionsButton = await screen.findByRole('button', { name: 'Sessions' });
    fireEvent.click(sessionsButton);

    expect(await screen.findByRole('listbox', { name: 'Conversation sessions' })).toBeInTheDocument();
  });
});

describe('AIWorkspace Memory console (G2)', () => {
  it('renders AIMemoryConsole when Memory icon is clicked', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const memoryButton = await screen.findByRole('button', { name: 'Memory' });
    fireEvent.click(memoryButton);

    expect(await screen.findByTestId('memory-console')).toBeInTheDocument();
    expect(memoryButton).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('AIWorkspace Investigate mode tab (Phase 9-B)', () => {
  it('renders the InvestigateTab when Investigate mode is selected', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const investigateButton = await screen.findByRole('button', { name: 'Investigate' });
    fireEvent.click(investigateButton);

    expect(await screen.findByTestId('investigate-tab')).toBeInTheDocument();
  });
});

describe('AIWorkspace mode split (Phase W5-A / ADR-0014)', () => {
  it('opens in Chat mode: chat contract text and chat activity bar only', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    expect(
      await screen.findByText(/Answers and advice only\. Nothing is created or changed/i),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sessions' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Tasks' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Monitor' })).not.toBeInTheDocument();
  });

  it('switches to Agent mode via the header: task panel + agent contract + agent activity bar', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Agent mode' }));

    expect(await screen.findByTestId('task-panel')).toBeInTheDocument();
    expect(screen.getByText(/The AI will plan before doing anything/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tasks' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Monitor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Results' })).toBeInTheDocument();
    // Chat-only surfaces are hidden in Agent mode.
    expect(screen.queryByRole('button', { name: 'Sessions' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New chat' })).not.toBeInTheDocument();
  });

  it('switches back to Chat mode from the header', async () => {
    localStorage.setItem('carbon-ai-mode', 'agent');
    render(<AIWorkspace onClose={vi.fn()} />);
    await screen.findByTestId('task-panel');

    fireEvent.click(screen.getByRole('button', { name: 'Chat mode' }));

    expect(
      await screen.findByText(/Answers and advice only\. Nothing is created or changed/i),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('task-panel')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sessions' })).toBeInTheDocument();
  });

  it('persists the mode to localStorage and restores it on reopen (RULE_17)', async () => {
    const { unmount } = render(<AIWorkspace onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Agent mode' }));
    await screen.findByTestId('task-panel');
    expect(localStorage.getItem('carbon-ai-mode')).toBe('agent');

    unmount();
    render(<AIWorkspace onClose={vi.fn()} />);
    expect(await screen.findByTestId('task-panel')).toBeInTheDocument();
    expect(localStorage.getItem('carbon-ai-mode')).toBe('agent');
  });

  it('switches the Agent task panel to the Monitor tab via the activity bar (W5-D)', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Agent mode' }));
    await screen.findByTestId('task-panel');

    fireEvent.click(screen.getByRole('button', { name: 'Monitor' }));
    await waitFor(() =>
      expect(screen.getByTestId('task-panel')).toHaveAttribute('data-tab', 'monitor'),
    );
    expect(screen.getByTestId('task-panel')).toBeInTheDocument();
  });

  it('switches the Agent task panel to the Results tab via the activity bar (W5-D)', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Agent mode' }));
    await screen.findByTestId('task-panel');

    fireEvent.click(screen.getByRole('button', { name: 'Results' }));
    await waitFor(() =>
      expect(screen.getByTestId('task-panel')).toHaveAttribute('data-tab', 'results'),
    );
    expect(screen.getByTestId('task-panel')).toBeInTheDocument();
  });
});

describe('AIWorkspace Usage tab (Phase 21-B)', () => {
  it('renders the Usage panel when Usage is selected from the activity bar', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const usageButton = await screen.findByRole('button', { name: 'Usage' });
    fireEvent.click(usageButton);

    expect(await screen.findByTestId('usage-tab')).toBeInTheDocument();
    expect(usageButton).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('AIWorkspace Settings tab (Phase 22-B)', () => {
  it('renders the Settings panel when Settings is selected from the activity bar', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const settingsButton = await screen.findByRole('button', { name: 'Settings' });
    fireEvent.click(settingsButton);

    expect(await screen.findByTestId('settings-tab')).toBeInTheDocument();
    expect(settingsButton).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('AIWorkspace new-chat (Phase 24 — always creates a fresh thread)', () => {
  it('always creates a NEW chat even when an empty open thread exists (Phase 24 fix)', async () => {
    // Regression: reusing the empty "New Chat" placeholder thread made the
    // button look broken — clicking it showed nothing new.
    findOpenConversation.mockResolvedValue({
      id: 'conv-2',
      conversation_type: 'chat',
      title: 'Beta',
      last_message_at: null,
    });

    render(<AIWorkspace onClose={vi.fn()} />);

    const newChatButtons = await screen.findAllByRole('button', { name: 'New chat' });
    fireEvent.click(newChatButtons[0]);

    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith('test-token', {
        conversation_type: 'chat',
        title: 'New Chat',
      });
    });
  });

  it('creates a new chat when no open thread exists', async () => {
    findOpenConversation.mockResolvedValue(null);

    render(<AIWorkspace onClose={vi.fn()} />);

    const newChatButtons = await screen.findAllByRole('button', { name: 'New chat' });
    fireEvent.click(newChatButtons[0]);

    await waitFor(() => {
      expect(createConversation).toHaveBeenCalledWith('test-token', {
        conversation_type: 'chat',
        title: 'New Chat',
      });
    });
  });
});
