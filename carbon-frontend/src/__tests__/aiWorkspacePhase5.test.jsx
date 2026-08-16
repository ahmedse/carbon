// src/__tests__/aiWorkspacePhase5.test.jsx
// Phase 5B — suggestions rail + resume catch-up banner.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const mockNotify = vi.fn();
const mockNotifyFromError = vi.fn();
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify, notifyFromError: mockNotifyFromError }),
}));

// Heavy children that fetch/stream on their own — stub them out so the view
// under test is exercised in isolation.
vi.mock('../shell/AIContextPanel', () => ({ default: () => null }));
vi.mock('../shell/AIInputBar', () => ({ default: () => null }));
vi.mock('../shell/AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));

vi.mock('../api/aiWorkspace', () => ({
  getSuggestions: vi.fn(),
  resumeConversation: vi.fn(),
  getConversation: vi.fn(),
  listMessages: vi.fn(),
  sendMessageStream: vi.fn(),
  stopGeneration: vi.fn(),
  acceptSuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
  recordFeedback: vi.fn(),
  createArtifact: vi.fn(),
  exportConversation: vi.fn(),
}));

import { getSuggestions, resumeConversation, getConversation } from '../api/aiWorkspace';
import AISuggestionRail from '../shell/AISuggestionRail';
import AIConversationView from '../shell/AIConversationView';

const SUGGESTIONS = [
  {
    id: 's1',
    severity: 'warn',
    title: 'DQ violation spike',
    narrative: 'A table has exceeded its null threshold.',
    insight_type: 'dq',
    created_at: '2026-08-16T10:00:00Z',
  },
];

const CONVERSATION = {
  id: 'conv-1',
  title: 'Test thread',
  status: 'completed',
  conversation_type: 'chat',
  messages: [
    { id: 'm1', role: 'assistant', content: 'Hello there', created_at: '2026-08-16T10:00:00Z' },
  ],
};

const CATCH_UP = {
  since: '2026-08-15T10:00:00Z',
  hours_since_last_view: 27,
  new_dq_violations: 3,
  new_anomalies: 1,
  new_memory_facts: 2,
  new_suggestions: 0,
  summary_lines: ['3 new DQ violation(s)', '1 new anomaly/anomalies'],
};

beforeEach(() => {
  vi.clearAllMocks();
  getSuggestions.mockReset();
  resumeConversation.mockReset();
  getConversation.mockReset();
});

function renderView() {
  return render(
    <MemoryRouter>
      <AIConversationView conversationId="conv-1" />
    </MemoryRouter>,
  );
}

// ── AISuggestionRail ──────────────────────────────────────────────────────

describe('AISuggestionRail', () => {
  it('renders severity chip, title, and narrative from getSuggestions', async () => {
    getSuggestions.mockResolvedValue({ suggestions: SUGGESTIONS });
    render(<AISuggestionRail conversationId="conv-1" />);

    expect(await screen.findByText('DQ violation spike')).toBeInTheDocument();
    expect(screen.getByText('A table has exceeded its null threshold.')).toBeInTheDocument();
    // Severity is shown as an uppercase chip label.
    expect(screen.getByText('WARN')).toBeInTheDocument();
  });

  it('renders nothing when the response is empty', async () => {
    getSuggestions.mockResolvedValue({ suggestions: [] });
    render(<AISuggestionRail conversationId="conv-1" />);

    await waitFor(() => expect(getSuggestions).toHaveBeenCalled());
    expect(screen.queryByText('Suggestions')).not.toBeInTheDocument();
  });
});

// ── AIConversationView resume catch-up ────────────────────────────────────

describe('AIConversationView resume catch-up', () => {
  it('shows the pinned catch-up banner when resumeConversation resolves catch_up', async () => {
    getConversation.mockResolvedValue(CONVERSATION);
    resumeConversation.mockResolvedValue({ conversation: CONVERSATION, catch_up: CATCH_UP });
    renderView();

    expect(await screen.findByText('Since your last visit')).toBeInTheDocument();
    expect(screen.getByText('3 new DQ violation(s)')).toBeInTheDocument();
    expect(screen.getByText('Hello there')).toBeInTheDocument();
  });

  it('shows no banner when resumeConversation resolves catch_up: null', async () => {
    getConversation.mockResolvedValue(CONVERSATION);
    resumeConversation.mockResolvedValue({ conversation: CONVERSATION, catch_up: null });
    renderView();

    expect(await screen.findByText('Hello there')).toBeInTheDocument();
    expect(screen.queryByText('Since your last visit')).not.toBeInTheDocument();
  });

  it('still renders messages when resumeConversation rejects with 404 (quiet)', async () => {
    getConversation.mockResolvedValue(CONVERSATION);
    resumeConversation.mockRejectedValue(
      Object.assign(new Error('Conversation conv-1 not found.'), { status: 404 }),
    );
    renderView();

    expect(await screen.findByText('Hello there')).toBeInTheDocument();
    expect(screen.queryByText('Since your last visit')).not.toBeInTheDocument();
    // 404 is expected for inaccessible ids — must not surface a toast.
    expect(mockNotifyFromError).not.toHaveBeenCalled();
  });
});
