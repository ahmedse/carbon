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
vi.mock('../shell/AISuggestionRail', () => ({ default: () => null }));
vi.mock('../shell/AIEmptyState', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/InvestigateTab', () => ({ default: () => <div data-testid="investigate-tab" /> }));
vi.mock('../shell/AIUsageTab', () => ({ default: () => <div data-testid="usage-tab" /> }));
vi.mock('../shell/AISettingsTab', () => ({ default: () => <div data-testid="settings-tab" /> }));
vi.mock('../shell/AIMemoryTab', () => ({ default: () => <div data-testid="memory-episodes-tab" /> }));
vi.mock('../shell/AILearntTab', () => ({ default: () => <div data-testid="memory-facts-tab" /> }));
vi.mock('../shell/AIRelationshipTab', () => ({ default: () => <div data-testid="memory-relationship-tab" /> }));
vi.mock('../shell/AIAgentPanel', () => ({ default: () => <div data-testid="agent-tab" /> }));

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

describe('AIWorkspace grouped Memory panel (Phase 23-C)', () => {
  it('groups Episodes/Facts/Relationship under one Memory icon with internal tabs', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const memoryButton = await screen.findByRole('button', { name: 'Memory' });
    fireEvent.click(memoryButton);

    // Default tab is Episodes (memory).
    expect(await screen.findByTestId('memory-episodes-tab')).toBeInTheDocument();
    expect(memoryButton).toHaveAttribute('aria-pressed', 'true');

    // Internal MUI Tabs switch between the three surfaces (RULE_17).
    fireEvent.click(screen.getByRole('tab', { name: 'Facts' }));
    expect(await screen.findByTestId('memory-facts-tab')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Relationship' }));
    expect(await screen.findByTestId('memory-relationship-tab')).toBeInTheDocument();
  });

  it('persists the selected memory tab to localStorage (RULE_17)', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const memoryButton = await screen.findByRole('button', { name: 'Memory' });
    fireEvent.click(memoryButton);
    fireEvent.click(screen.getByRole('tab', { name: 'Facts' }));
    expect(await screen.findByTestId('memory-facts-tab')).toBeInTheDocument();

    expect(localStorage.getItem('carbon-ai-memory-tab')).toBe('facts');
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

describe('AIWorkspace Agent surface icon (Phase W2-A)', () => {
  it('renders the Agent panel when Agent is selected from the activity bar', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const agentButton = await screen.findByRole('button', { name: 'Agent' });
    fireEvent.click(agentButton);

    expect(await screen.findByTestId('agent-tab')).toBeInTheDocument();
    expect(agentButton).toHaveAttribute('aria-pressed', 'true');
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
