// src/__tests__/StatusBar.badge.test.jsx
// Phase 11-B — AI Workspace toggle notification badge (pending suggestions).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', context: null }),
}));

vi.mock('../api/aiWorkspace', () => ({
  listWorkspaceSuggestions: vi.fn(),
}));

import { listWorkspaceSuggestions } from '../api/aiWorkspace';
import { StatusBar } from '../shell/StatusBar';

function renderStatusBar(props = {}) {
  return render(
    <MemoryRouter>
      <StatusBar
        sidebarMode="hidden"
        copilotVisible={false}
        onToggleSidebar={vi.fn()}
        onToggleCopilot={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('StatusBar AI Workspace badge', () => {
  it('shows the pending-suggestion count when the workspace is closed', async () => {
    listWorkspaceSuggestions.mockResolvedValue({
      suggestions: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
    });
    renderStatusBar({ copilotVisible: false });

    expect(await screen.findByText('3')).toBeInTheDocument();
    expect(listWorkspaceSuggestions).toHaveBeenCalledWith('test-token');
  });

  it('hides the badge when the workspace is open', async () => {
    listWorkspaceSuggestions.mockResolvedValue({
      suggestions: [{ id: 'a' }, { id: 'b' }, { id: 'c' }],
    });
    renderStatusBar({ copilotVisible: true });

    // Give the async fetch a tick to resolve; the badge must stay hidden.
    await waitFor(() => expect(listWorkspaceSuggestions).toHaveBeenCalled());
    expect(screen.queryByText('3')).not.toBeInTheDocument();
  });
});
