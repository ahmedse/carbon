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

describe('AIWorkspace Investigate mode tab (Phase 9-B)', () => {
  it('renders the InvestigateTab when Investigate mode is selected', async () => {
    render(<AIWorkspace onClose={vi.fn()} />);

    const investigateButton = await screen.findByRole('button', { name: 'Investigate' });
    fireEvent.click(investigateButton);

    expect(await screen.findByTestId('investigate-tab')).toBeInTheDocument();
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

describe('AIWorkspace new-chat resume (Phase 16)', () => {
  it('reuses the most recent open chat thread instead of creating a new one', async () => {
    findOpenConversation.mockResolvedValue({
      id: 'conv-2',
      conversation_type: 'chat',
      title: 'Beta',
    });

    render(<AIWorkspace onClose={vi.fn()} />);

    const newChatButtons = await screen.findAllByRole('button', { name: 'New chat' });
    fireEvent.click(newChatButtons[0]);

    await waitFor(() => {
      expect(createConversation).not.toHaveBeenCalled();
    });

    // The resumed thread (conv-2) becomes the active session.
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /Beta/ })).toHaveAttribute(
        'aria-selected',
        'true',
      );
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
