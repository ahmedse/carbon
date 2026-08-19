// src/__tests__/AIConversationTabs.accordion.test.jsx
// Sprint 22 — W2-B: past-chat accordion + scroll containment (design §2.4).
// Covers: collapsible group headers (Today/Yesterday/7d/Older) persisted via
// localStorage `carbon-ai-accordion-{group}`, per-item inline expand, capped
// long lists ("Show N more"), the single vertical message scroll region, and
// wide content scrolling horizontally inside its own card.
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// ── Stable notification mock (AIConversationView lists notifyFromError in its
//    load/resume effect deps — must stay referentially stable across renders). ─
const notificationMocks = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
  showFeedback: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 7 }, userCapabilities: [], isGlobalAdminFlag: false }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => notificationMocks,
}));

vi.mock('../shell/useExecuteMode', () => ({
  useExecuteMode: () => ({ executeMode: false, setExecuteMode: vi.fn() }),
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ pendingTransferId: null, clearPendingTransfer: vi.fn() }),
}));

vi.mock('../shell/AIMessageBubble', () => ({ default: () => null }));
vi.mock('../shell/AIContextPanel', () => ({ default: () => null }));
vi.mock('../shell/AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/AIStatusBar', () => ({ default: () => null }));
vi.mock('../shell/AIModelSelect', () => ({ default: () => null }));
vi.mock('../shell/AIInputBar', () => ({ default: () => <div data-testid="input-bar" /> }));

vi.mock('../api/aiWorkspace', () => ({
  acceptSuggestion: vi.fn(),
  confirmToolExecution: vi.fn(),
  createArtifact: vi.fn(),
  declineToolExecution: vi.fn(),
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

vi.mock('../api/dq', () => ({ createDQRule: vi.fn() }));
vi.mock('../api/api', () => ({ apiFetch: vi.fn(), refreshAccessToken: vi.fn() }));
vi.mock('../api/modules', () => ({ fetchModules: vi.fn() }));

import AIConversationTabs from '../shell/AIConversationTabs';
import AIConversationView from '../shell/AIConversationView';
import LongContent from '../shell/LongContent';
import { getConversation, resumeConversation } from '../api/aiWorkspace';

const ACCORDION_PREFIX = 'carbon-ai-accordion-';

const hoursAgo = (h) => new Date(Date.now() - h * 3600e3).toISOString();

const mkConv = (id, title, updatedAt) => ({
  id,
  title,
  conversation_type: 'chat',
  status: 'completed',
  updated_at: updatedAt,
});

const renderTabs = (conversations, overrides = {}) =>
  render(
    <AIConversationTabs
      conversations={conversations}
      activeId={overrides.activeId || conversations[0]?.id}
      onSelect={overrides.onSelect || vi.fn()}
      onNew={overrides.onNew || vi.fn()}
      onClose={overrides.onClose || vi.fn()}
    />,
  );

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getConversation.mockResolvedValue(null);
  resumeConversation.mockResolvedValue({});
});

describe('AIConversationTabs — W2-B accordion groups', () => {
  it('renders all four group headers and every item expanded by default', () => {
    const convs = [
      mkConv('c-today', 'Today one', hoursAgo(0.5)),
      mkConv('c-yest', 'Yesterday one', hoursAgo(30)),
      mkConv('c-week', 'Week one', hoursAgo(120)),
      mkConv('c-old', 'Old one', hoursAgo(30 * 24)),
    ];
    renderTabs(convs);

    for (const group of ['Today', 'Yesterday', 'Previous 7 days', 'Older']) {
      const header = screen.getByRole('button', { name: `Toggle ${group} sessions` });
      expect(header).toHaveAttribute('aria-expanded', 'true');
    }
    expect(screen.getByRole('option', { name: /Today one/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Yesterday one/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Week one/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Old one/ })).toBeInTheDocument();
  });

  it('collapses a group on header click, hides its items and persists to localStorage', () => {
    const convs = [
      mkConv('c-today', 'Today one', hoursAgo(0.5)),
      mkConv('c-old', 'Old one', hoursAgo(30 * 24)),
    ];
    renderTabs(convs);

    fireEvent.click(screen.getByRole('button', { name: 'Toggle Today sessions' }));

    expect(screen.queryByRole('option', { name: /Today one/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Old one/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Toggle Today sessions' })).toHaveAttribute('aria-expanded', 'false');
    expect(localStorage.getItem(ACCORDION_PREFIX + 'Today')).toBe('collapsed');
  });

  it('restores a collapsed group from localStorage on mount', () => {
    localStorage.setItem(ACCORDION_PREFIX + 'Today', 'collapsed');
    const convs = [
      mkConv('c-today', 'Today one', hoursAgo(0.5)),
      mkConv('c-old', 'Old one', hoursAgo(30 * 24)),
    ];
    renderTabs(convs);

    expect(screen.getByRole('button', { name: 'Toggle Today sessions' })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('option', { name: /Today one/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Old one/ })).toBeInTheDocument();
  });

  it('re-expands a collapsed group and persists the expanded state', () => {
    const convs = [mkConv('c-today', 'Today one', hoursAgo(0.5))];
    renderTabs(convs);

    const header = screen.getByRole('button', { name: 'Toggle Today sessions' });
    fireEvent.click(header);
    expect(localStorage.getItem(ACCORDION_PREFIX + 'Today')).toBe('collapsed');

    fireEvent.click(header);
    expect(screen.getByRole('option', { name: /Today one/ })).toBeInTheDocument();
    expect(localStorage.getItem(ACCORDION_PREFIX + 'Today')).toBe('expanded');
  });

  it('expands a single item inline within an expanded group', () => {
    const convs = [mkConv('c-today', 'Today one', hoursAgo(0.5))];
    renderTabs(convs);

    fireEvent.click(screen.getByRole('button', { name: 'Expand Today one details' }));

    // The full title is now duplicated in the inline detail row.
    expect(screen.getAllByText('Today one').length).toBeGreaterThanOrEqual(2);
    // Timestamp detail line is present (same locale formatter as the component).
    expect(screen.getByText(new Date(convs[0].updated_at).toLocaleString())).toBeInTheDocument();
  });

  it('caps long groups in the DOM and reveals the rest via Show N more', () => {
    const convs = Array.from({ length: 55 }, (_, i) =>
      mkConv(`c-${i}`, `Session ${i}`, hoursAgo(0.1)),
    );
    renderTabs(convs);

    expect(screen.getAllByRole('option')).toHaveLength(50);

    fireEvent.click(screen.getByRole('button', { name: 'Show 5 more' }));
    expect(screen.getAllByRole('option')).toHaveLength(55);
  });

  it('calls onSelect with the conversation id when an item is clicked', () => {
    const onSelect = vi.fn();
    const convs = [mkConv('c-today', 'Today one', hoursAgo(0.5))];
    renderTabs(convs, { onSelect });

    fireEvent.click(screen.getByRole('option', { name: /Today one/ }));
    expect(onSelect).toHaveBeenCalledWith('c-today');
  });
});

describe('AIConversationView — W2-B scroll containment', () => {
  it('keeps the message list as its own vertical scroll region, distinct from the input bar', async () => {
    getConversation.mockResolvedValue({
      id: 'conv-1',
      title: 'Thread',
      visibility: 'private',
      user_id: 7,
      status: 'completed',
      messages: [{ id: 'm1', role: 'user', content: 'hi', created_at: hoursAgo(0.1) }],
    });

    const { container } = render(<AIConversationView conversationId="conv-1" />);

    const scroll = await screen.findByTestId('messages-scroll');
    const inputBar = screen.getByTestId('input-bar');

    expect(scroll).toBeInTheDocument();
    expect(inputBar).toBeInTheDocument();
    // The input bar is a fixed footer — NOT inside the message scroll region.
    expect(scroll).not.toContainElement(inputBar);
    // The message region is the flex scroller (overflowY auto, no horizontal).
    expect(scroll).toHaveStyle({ overflowY: 'auto' });
    expect(scroll).toHaveStyle({ overflowX: 'hidden' });
    // It participates in the flex column (flex:1 + minHeight:0 so it can
    // shrink and scroll under the fixed header/input rather than growing).
    expect(getComputedStyle(container.querySelector('[data-testid="messages-scroll"]')).flexGrow).toBe('1');
  });
});

describe('LongContent — W2-B wide content containment', () => {
  it('scrolls wide content horizontally inside its own card', () => {
    const { container } = render(
      <LongContent content={'x'.repeat(2000)}>
        <pre style={{ width: 800 }}>wide terminal output</pre>
      </LongContent>,
    );

    const inner = container.querySelector('pre').parentElement;
    expect(getComputedStyle(inner).overflowX).toBe('auto');
  });

  it('still toggles Show more / Show less for long content', () => {
    render(
      <LongContent content={'x'.repeat(2000)}>
        <p>Long body</p>
      </LongContent>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Show more/i }));
    expect(screen.getByRole('button', { name: /Show less/i })).toBeInTheDocument();
  });
});
