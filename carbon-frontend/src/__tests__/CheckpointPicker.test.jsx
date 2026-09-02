// src/__tests__/CheckpointPicker.test.jsx
// G3 — CheckpointPicker: drawer with per-row Restore + Fork actions.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api/aiWorkspace', () => ({
  listCheckpoints: vi.fn(),
  restoreConversation: vi.fn(),
  forkConversation: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError }),
}));

import CheckpointPicker from '../shell/CheckpointPicker';
import { listCheckpoints, restoreConversation, forkConversation } from '../api/aiWorkspace';

const CHECKPOINTS = [
  { id: 'cp-1', name: 'Sep 1 · 10:00', note: 'Before refactor', created_at: '2026-09-01T10:00:00Z' },
  { id: 'cp-2', name: 'Sep 2 · 14:30', note: '', created_at: '2026-09-02T14:30:00Z' },
];

function renderPicker(props = {}) {
  const defaults = {
    conversationId: 'conv-42',
    open: true,
    onClose: vi.fn(),
    onFork: vi.fn(),
  };
  return render(
    <MemoryRouter>
      <CheckpointPicker {...defaults} {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listCheckpoints.mockResolvedValue({ checkpoints: CHECKPOINTS });
  restoreConversation.mockResolvedValue({});
  forkConversation.mockResolvedValue({ id: 'conv-forked', title: 'Fork of Sep 1' });
});

describe('CheckpointPicker — list rendering', () => {
  it('renders checkpoint names after loading', async () => {
    renderPicker();

    expect(await screen.findByText('Sep 1 · 10:00')).toBeInTheDocument();
    expect(screen.getByText('Sep 2 · 14:30')).toBeInTheDocument();
    expect(screen.getByText('Before refactor')).toBeInTheDocument();
  });

  it('shows empty state when no checkpoints', async () => {
    listCheckpoints.mockResolvedValue({ checkpoints: [] });
    renderPicker();

    expect(await screen.findByText('No checkpoints yet.')).toBeInTheDocument();
  });

  it('calls listCheckpoints with correct conversationId', async () => {
    renderPicker({ conversationId: 'conv-99' });

    await waitFor(() => {
      expect(listCheckpoints).toHaveBeenCalledWith('test-token', 'conv-99');
    });
  });
});

describe('CheckpointPicker — Restore', () => {
  it('clicking Restore button shows confirmation dialog', async () => {
    renderPicker();

    await screen.findByText('Sep 1 · 10:00');
    const restoreButtons = screen.getAllByRole('button', { name: /Restore checkpoint/ });
    fireEvent.click(restoreButtons[0]);

    expect(
      await screen.findByText(/Restoring will replace your current context/i),
    ).toBeInTheDocument();
  });

  it('confirming restore calls restoreConversation and closes', async () => {
    const onClose = vi.fn();
    renderPicker({ onClose });

    await screen.findByText('Sep 1 · 10:00');
    // Newest first — Sep 2 is first in the drawer (reversed)
    const restoreButtons = screen.getAllByRole('button', { name: /Restore checkpoint/ });
    fireEvent.click(restoreButtons[0]);

    await screen.findByText(/Restoring will replace/i);
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));

    await waitFor(() => {
      expect(restoreConversation).toHaveBeenCalled();
    });
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ message: 'Context restored' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('Cancel on confirmation dialog does not call API', async () => {
    renderPicker();

    await screen.findByText('Sep 1 · 10:00');
    fireEvent.click(screen.getAllByRole('button', { name: /Restore checkpoint/ })[0]);
    await screen.findByText(/Restoring will replace/i);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(screen.queryByText(/Restoring will replace/i)).not.toBeInTheDocument();
    });
    expect(restoreConversation).not.toHaveBeenCalled();
  });
});

describe('CheckpointPicker — Fork', () => {
  it('Fork button calls forkConversation and invokes onFork callback', async () => {
    const onFork = vi.fn();
    const onClose = vi.fn();
    renderPicker({ onFork, onClose });

    await screen.findByText('Sep 1 · 10:00');
    const forkButtons = screen.getAllByRole('button', { name: /Fork from checkpoint/ });
    fireEvent.click(forkButtons[0]);

    await waitFor(() => {
      expect(forkConversation).toHaveBeenCalled();
    });
    expect(onFork).toHaveBeenCalledWith(expect.objectContaining({ id: 'conv-forked' }));
    expect(onClose).toHaveBeenCalled();
  });
});
