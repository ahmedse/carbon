// src/__tests__/AIMemoryConsole.test.jsx
// G2 — AIMemoryConsole: Learned / Episodes / Session / Org sub-tabs.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api/aiWorkspace', () => ({
  listFacts: vi.fn(),
  forgetFact: vi.fn(),
  updateMemoryFact: vi.fn(),
  restoreMemoryFact: vi.fn(),
  listOrgMemory: vi.fn(),
  listEpisodes: vi.fn(),
}));

// Default mock: non-admin user
let authMock = { token: 'tok', isGlobalAdminFlag: false };
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError }),
}));

// AIMemoryTab is used by the "Episodes" sub-tab — stub it out.
vi.mock('../shell/AIMemoryTab', () => ({
  default: () => <div data-testid="ai-memory-tab-stub">Episodes stub</div>,
}));

import AIMemoryConsole from '../shell/AIMemoryConsole';
import {
  listFacts,
  forgetFact,
  updateMemoryFact,
  restoreMemoryFact,
  listOrgMemory,
} from '../api/aiWorkspace';

const FACTS = [
  {
    id: 'f1',
    category: 'preference',
    memory_type: 'preference',
    content: 'Prefers dark mode',
    created_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 'f2',
    category: 'context',
    memory_type: 'context',
    content: 'Budget reviews are monthly and require sign-off from the finance lead',
    created_at: '2026-08-15T09:00:00Z',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  authMock = { token: 'tok', isGlobalAdminFlag: false };
  listFacts.mockResolvedValue({ count: 2, results: FACTS });
  forgetFact.mockResolvedValue(undefined);
  updateMemoryFact.mockResolvedValue({ ...FACTS[0], content: 'Updated content' });
  restoreMemoryFact.mockResolvedValue(undefined);
  listOrgMemory.mockResolvedValue({ count: 0, results: [] });
  localStorage.clear();
});

describe('AIMemoryConsole — Learned tab', () => {
  it('renders memory entries from listFacts', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    expect(await screen.findByText('Prefers dark mode')).toBeInTheDocument();
    expect(screen.getByText(/Budget reviews are monthly/)).toBeInTheDocument();
  });

  it('shows empty state when no facts', async () => {
    listFacts.mockResolvedValue({ count: 0, results: [] });
    render(<AIMemoryConsole conversationId="conv-1" />);

    expect(await screen.findByText('No memory entries yet.')).toBeInTheDocument();
  });

  it('clicking Edit opens TextField with current content', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    await screen.findByText('Prefers dark mode');
    const editButtons = screen.getAllByRole('button', { name: 'Edit memory entry' });
    fireEvent.click(editButtons[0]);

    const input = screen.getByRole('textbox', { name: 'Edit memory content' });
    expect(input).toBeInTheDocument();
    expect(input.value).toBe('Prefers dark mode');
  });

  it('Cancel restores original content without calling API', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    await screen.findByText('Prefers dark mode');
    const editBtn = screen.getAllByRole('button', { name: 'Edit memory entry' })[0];
    fireEvent.click(editBtn);

    const input = screen.getByRole('textbox', { name: 'Edit memory content' });
    fireEvent.change(input, { target: { value: 'Changed text' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel edit' }));

    expect(await screen.findByText('Prefers dark mode')).toBeInTheDocument();
    expect(updateMemoryFact).not.toHaveBeenCalled();
  });

  it('Save calls updateMemoryFact and shows updated text', async () => {
    updateMemoryFact.mockResolvedValue({});
    render(<AIMemoryConsole conversationId="conv-1" />);

    await screen.findByText('Prefers dark mode');
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit memory entry' })[0]);

    const input = screen.getByRole('textbox', { name: 'Edit memory content' });
    fireEvent.change(input, { target: { value: 'New content' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }));

    await waitFor(() => {
      expect(updateMemoryFact).toHaveBeenCalledWith('tok', 'f1', 'New content');
    });
  });
});

describe('AIMemoryConsole — Delete with Undo', () => {
  it('Delete removes item and shows Snackbar with Undo button', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    await screen.findByText('Prefers dark mode');
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete memory entry' })[0]);

    await waitFor(() => {
      expect(screen.queryByText('Prefers dark mode')).not.toBeInTheDocument();
    });
    expect(await screen.findByText('Entry deleted · Undo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo delete' })).toBeInTheDocument();
    expect(forgetFact).toHaveBeenCalledWith('tok', 'f1');
  });

  it('clicking Undo calls restoreMemoryFact and re-adds item', async () => {
    restoreMemoryFact.mockResolvedValue(undefined);
    render(<AIMemoryConsole conversationId="conv-1" />);

    await screen.findByText('Prefers dark mode');
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete memory entry' })[0]);
    await waitFor(() => expect(forgetFact).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Undo delete' }));

    await waitFor(() => {
      expect(restoreMemoryFact).toHaveBeenCalledWith('tok', 'f1');
    });
    expect(await screen.findByText('Prefers dark mode')).toBeInTheDocument();
  });
});

describe('AIMemoryConsole — Episodes tab', () => {
  it('renders AIMemoryTab stub in the Episodes sub-tab', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    // Start on Learned tab — switch to Episodes
    fireEvent.click(await screen.findByRole('tab', { name: 'Episodes' }));

    expect(await screen.findByTestId('ai-memory-tab-stub')).toBeInTheDocument();
  });
});

describe('AIMemoryConsole — Session tab', () => {
  it('shows static message in Session tab', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    fireEvent.click(await screen.findByRole('tab', { name: 'Session' }));

    expect(
      await screen.findByText('Working memory is session-scoped and not persisted.'),
    ).toBeInTheDocument();
  });
});

describe('AIMemoryConsole — Org tab', () => {
  it('shows "Admin access required" for non-admin', async () => {
    render(<AIMemoryConsole conversationId="conv-1" />);

    fireEvent.click(await screen.findByRole('tab', { name: 'Org' }));

    expect(await screen.findByText('Admin access required.')).toBeInTheDocument();
    expect(listOrgMemory).not.toHaveBeenCalled();
  });

  it('renders org facts for admin user', async () => {
    authMock = { token: 'tok', isGlobalAdminFlag: true };
    listOrgMemory.mockResolvedValue({
      count: 1,
      results: [{ id: 'o1', memory_type: 'preference', content: 'Org prefers weekly reports' }],
    });

    render(<AIMemoryConsole conversationId="conv-1" />);

    fireEvent.click(await screen.findByRole('tab', { name: 'Org' }));

    expect(await screen.findByText('Org prefers weekly reports')).toBeInTheDocument();
    expect(listOrgMemory).toHaveBeenCalledWith('tok');
  });
});
