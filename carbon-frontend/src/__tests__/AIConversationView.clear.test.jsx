// /clear empties the thread and shows a dotted Restore divider; Restore undoes.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 'test-token',
    user: { id: 'user-1' },
    userCapabilities: [],
    isGlobalAdminFlag: false,
  }),
}));

const mockNotify = vi.fn();
const mockNotifyFromError = vi.fn();
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify, notifyFromError: mockNotifyFromError }),
}));

vi.mock('../shell/AIContextPanel', () => ({ default: () => null }));
vi.mock('../shell/AIWorkingIndicator', () => ({ default: () => null }));
vi.mock('../shell/AIOfflineBanner', () => ({ default: () => null }));
vi.mock('../shell/AIModelSelect', () => ({ default: () => null }));
vi.mock('../shell/AIStatusBar', () => ({ default: () => null }));
vi.mock('../shell/PulsePresence', () => ({ default: () => null }));
vi.mock('../shell/KeyboardShortcutsHelp', () => ({ KeyboardShortcutsHelp: () => null }));
vi.mock('../components/ai/CheckpointDialogs', () => ({
  CheckpointPickerDialog: () => null,
  SaveCheckpointDialog: () => null,
}));

const mockOnCommand = vi.fn();
vi.mock('../shell/AIInputBar', () => ({
  default: ({ onCommand }) => {
    mockOnCommand.mockImplementation(onCommand);
    return (
      <button type="button" onClick={() => onCommand?.('clear')}>
        trigger-clear
      </button>
    );
  },
}));

vi.mock('../api/aiWorkspace', () => ({
  acceptSuggestion: vi.fn(),
  clearContext: vi.fn(),
  createArtifact: vi.fn(),
  deleteMessage: vi.fn(),
  exportConversation: vi.fn(),
  forkConversation: vi.fn(),
  getConversation: vi.fn(),
  listMessages: vi.fn(),
  recordFeedback: vi.fn(),
  rejectSuggestion: vi.fn(),
  resumeConversation: vi.fn(),
  retryMessageStream: vi.fn(),
  sendMessageStream: vi.fn(),
  stopGeneration: vi.fn(),
  undoClearContext: vi.fn(),
  updateConversation: vi.fn(),
}));

import {
  clearContext,
  getConversation,
  resumeConversation,
  undoClearContext,
} from '../api/aiWorkspace';
import AIConversationView from '../shell/AIConversationView';

const MESSAGES = [
  { id: 'm1', role: 'user', content: 'Hello', created_at: '2026-08-16T10:00:00Z' },
  { id: 'm2', role: 'assistant', content: 'Hi there', created_at: '2026-08-16T10:00:01Z' },
];

function makeConversation(extra = {}) {
  return {
    id: 'conv-1',
    title: 'Thread',
    status: 'completed',
    conversation_type: 'chat',
    visibility: 'private',
    user_id: 'user-1',
    summary: 'prior summary',
    context_snapshot_json: { budget: { T2_history: 2 } },
    messages: MESSAGES,
    ...extra,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getConversation.mockResolvedValue(makeConversation());
  resumeConversation.mockResolvedValue({ conversation: makeConversation(), catch_up: null });
  clearContext.mockResolvedValue(
    makeConversation({
      summary: '',
      context_snapshot_json: {
        _clear_break: {
          summary: 'prior summary',
          prior_snapshot: { budget: { T2_history: 2 } },
          message_boundary_id: 'm2',
          cleared_at: '2026-08-16T10:00:02Z',
        },
      },
      messages: undefined,
    }),
  );
  undoClearContext.mockResolvedValue(makeConversation());
});

function renderView(props = {}) {
  return render(
    <MemoryRouter>
      <AIConversationView conversationId="conv-1" {...props} />
    </MemoryRouter>,
  );
}

describe('AIConversationView /clear Restore divider', () => {
  it('empties the window and shows a Restore divider after /clear', async () => {
    renderView();
    await screen.findByText('Hi there');

    fireEvent.click(screen.getByRole('button', { name: 'trigger-clear' }));

    await waitFor(() => {
      expect(clearContext).toHaveBeenCalledWith('test-token', 'conv-1');
    });
    expect(await screen.findByTestId('context-clear-divider')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Restore' })).toBeInTheDocument();
    expect(screen.queryByText('Hello')).not.toBeInTheDocument();
    expect(screen.queryByText('Hi there')).not.toBeInTheDocument();
  });

  it('Restore brings messages and working context back', async () => {
    renderView();
    await screen.findByText('Hi there');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-clear' }));
    await screen.findByTestId('context-clear-divider');

    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));

    await waitFor(() => {
      expect(undoClearContext).toHaveBeenCalledWith('test-token', 'conv-1');
    });
    expect(await screen.findByText('Hi there')).toBeInTheDocument();
    expect(screen.queryByTestId('context-clear-divider')).not.toBeInTheDocument();
  });

  it('adopts clear-break from workspace contextPulse (kebab clear)', async () => {
    const { rerender } = renderView();
    await screen.findByText('Hi there');

    const pulsed = makeConversation({
      summary: '',
      context_snapshot_json: {
        _clear_break: {
          summary: 'prior summary',
          prior_snapshot: {},
          message_boundary_id: 'm2',
          cleared_at: '2026-08-16T10:00:02Z',
        },
      },
      messages: undefined,
    });
    rerender(
      <MemoryRouter>
        <AIConversationView
          conversationId="conv-1"
          contextPulse={{ id: 'conv-1', at: 1, conversation: pulsed }}
        />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('context-clear-divider')).toBeInTheDocument();
    expect(screen.queryByText('Hi there')).not.toBeInTheDocument();
  });
});
