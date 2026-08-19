// src/__tests__/AIContextMenu.test.jsx
// Sprint 23 — W2-C: header kebab for context lifecycle.
// Covers: 4 menu items render; clear-context confirm (durable chat kept);
// save-checkpoint form (name required); restore picker 4-states
// (loading / error+retry / empty / loaded list + selection); fork flow
// (picker → confirm → new conversation via onForked).
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ── Stable notification mock ────────────────────────────────────────────────
const notificationMocks = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => notificationMocks,
}));

vi.mock('../api/aiWorkspace', () => ({
  listCheckpoints: vi.fn(),
  checkpointConversation: vi.fn(),
  restoreConversation: vi.fn(),
  forkConversation: vi.fn(),
  clearContext: vi.fn(),
}));

import AIContextMenu from '../shell/AIContextMenu';
import {
  listCheckpoints,
  checkpointConversation,
  restoreConversation,
  forkConversation,
  clearContext,
} from '../api/aiWorkspace';

const { notify, notifyFromError } = notificationMocks;

const CHECKPOINT = {
  id: 'cp-1',
  name: 'Baseline setup',
  note: 'Server + DB wired',
  snapshot: { message_count: 12 },
  created_at: '2025-01-10T10:00:00Z',
};

const openMenu = () =>
  fireEvent.click(screen.getByRole('button', { name: 'Context actions' }));

beforeEach(() => {
  vi.clearAllMocks();
  listCheckpoints.mockResolvedValue({ checkpoints: [] });
  checkpointConversation.mockResolvedValue({ id: 'cp-x' });
  restoreConversation.mockResolvedValue({ id: 'c-1', title: 'Chat' });
  forkConversation.mockResolvedValue({ id: 'fork-1', title: 'Chat — fork' });
  clearContext.mockResolvedValue({ id: 'c-1', title: 'Chat' });
});

describe('AIContextMenu', () => {
  it('renders the kebab with all four actions when opened', () => {
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();

    expect(screen.getByRole('menuitem', { name: 'Clear context' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Save checkpoint' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Restore' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Fork from here' })).toBeInTheDocument();
  });

  it('disables the kebab when there is no active conversation', () => {
    render(<AIContextMenu conversationId={null} />);
    expect(screen.getByRole('button', { name: 'Context actions' })).toBeDisabled();
  });

  it('clear context: confirms, calls clearContext, notifies, reports the update', async () => {
    const onUpdated = vi.fn();
    render(<AIContextMenu conversationId="c-1" onConversationUpdated={onUpdated} />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Clear context' }));

    // Confirm dialog — copy must make visible that the durable chat is kept.
    expect(screen.getByText('Clear working context?')).toBeInTheDocument();
    expect(screen.getByText(/nothing is deleted/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Clear context' }));

    await waitFor(() => {
      expect(clearContext).toHaveBeenCalledWith('test-token', 'c-1');
    });
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success' }),
    );
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: 'c-1' }));
  });

  it('save checkpoint: name is required and a named save calls the API', async () => {
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Save checkpoint' }));

    const saveButton = screen.getByRole('button', { name: 'Save' });
    expect(saveButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Checkpoint name'), {
      target: { value: 'Baseline setup' },
    });
    fireEvent.change(screen.getByLabelText('Checkpoint note'), {
      target: { value: 'Server + DB wired' },
    });
    expect(saveButton).toBeEnabled();

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(checkpointConversation).toHaveBeenCalledWith('test-token', 'c-1', {
        name: 'Baseline setup',
        note: 'Server + DB wired',
      });
    });
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success' }),
    );
  });

  it('restore picker: shows a spinner while loading', async () => {
    listCheckpoints.mockReturnValueOnce(new Promise(() => {})); // pending forever
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Restore' }));

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('restore picker: error state offers a Retry that reloads', async () => {
    listCheckpoints
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ checkpoints: [CHECKPOINT] });
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Restore' }));

    expect(await screen.findByText(/network down/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Baseline setup')).toBeInTheDocument();
  });

  it('restore picker: empty state tells the user to save a checkpoint first', async () => {
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Restore' }));

    expect(
      await screen.findByText(/no checkpoints saved yet/i),
    ).toBeInTheDocument();
  });

  it('restore picker: selecting a checkpoint restores and refreshes in place', async () => {
    listCheckpoints.mockResolvedValue({
      checkpoints: [
        CHECKPOINT,
        { ...CHECKPOINT, id: 'cp-2', name: 'After refactor', note: '', snapshot: { message_count: 30 } },
      ],
    });
    const onUpdated = vi.fn();
    render(<AIContextMenu conversationId="c-1" onConversationUpdated={onUpdated} />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Restore' }));

    // Loaded list shows name, note, message count and a disabled action until
    // a checkpoint is selected.
    expect(await screen.findByText('Baseline setup')).toBeInTheDocument();
    expect(screen.getByText('After refactor')).toBeInTheDocument();
    expect(screen.getByText(/12 messages/i)).toBeInTheDocument();
    expect(screen.getByText(/30 messages/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Restore' })).toBeDisabled();

    fireEvent.click(screen.getByText('After refactor'));
    expect(screen.getByRole('button', { name: 'Restore' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));

    await waitFor(() => {
      expect(restoreConversation).toHaveBeenCalledWith('test-token', 'c-1', 'cp-2');
    });
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: 'c-1' }));
  });

  it('fork: picker → confirm → forkConversation and onForked with the new id', async () => {
    listCheckpoints.mockResolvedValue({ checkpoints: [CHECKPOINT] });
    const onForked = vi.fn();
    render(<AIContextMenu conversationId="c-1" onForked={onForked} />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Fork from here' }));

    await screen.findByText('Baseline setup');
    fireEvent.click(screen.getByText('Baseline setup'));
    fireEvent.click(screen.getByRole('button', { name: 'Fork' }));

    // Confirm dialog — copy must make visible that the current chat is kept.
    expect(screen.getByText('Fork a new chat?')).toBeInTheDocument();
    expect(screen.getByText(/stays exactly as it is/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Fork' }));

    await waitFor(() => {
      expect(forkConversation).toHaveBeenCalledWith('test-token', 'c-1', 'cp-1');
    });
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }));
    expect(onForked).toHaveBeenCalledWith(expect.objectContaining({ id: 'fork-1' }));
  });

  it('failure paths route through notifyFromError without crashing', async () => {
    clearContext.mockRejectedValueOnce(new Error('boom'));
    render(<AIContextMenu conversationId="c-1" />);
    openMenu();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Clear context' }));
    fireEvent.click(screen.getByRole('button', { name: 'Clear context' }));

    await waitFor(() => {
      expect(notifyFromError).toHaveBeenCalledWith(expect.any(Error), 'Could not clear context');
    });
  });
});
