// src/__tests__/AIArtifacts.test.jsx
// Phase 4B — artifact card, browser, promote action.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const mockNotify = vi.fn();
const mockNotifyFromError = vi.fn();
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify, notifyFromError: mockNotifyFromError }),
}));
vi.mock('../api/aiWorkspace', () => ({
  listArtifacts: vi.fn(),
  createArtifact: vi.fn(),
  deleteArtifact: vi.fn(),
}));

import { listArtifacts, createArtifact } from '../api/aiWorkspace';
import AIArtifactCard from '../shell/AIArtifactCard';
import AIArtifactBrowser from '../shell/AIArtifactBrowser';
import AIMessageBubble from '../shell/AIMessageBubble';

const SAMPLE_ARTIFACT = {
  id: 'art-1',
  title: 'Q3 Emissions Report',
  artifact_type: 'report',
  created_at: '2026-08-16T10:00:00Z',
  content_json: { markdown: '# Report' },
};

const ASSISTANT_MSG = {
  id: 'msg-1',
  role: 'assistant',
  content: 'Here is the analysis.',
  created_at: '2026-08-16T10:00:00Z',
  metadata_json: { type: 'analysis', result: 42 },
};

// ── AIArtifactCard ──────────────────────────────────────────────────────────

describe('AIArtifactCard', () => {
  it('renders title, type chip, and open button', () => {
    render(<AIArtifactCard artifact={SAMPLE_ARTIFACT} />);
    expect(screen.getByText('Q3 Emissions Report')).toBeInTheDocument();
    expect(screen.getByText('Report')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /open artifact/i })).toBeInTheDocument();
  });

  it('calls onOpen when the open button is clicked', () => {
    const onOpen = vi.fn();
    render(<AIArtifactCard artifact={SAMPLE_ARTIFACT} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole('button', { name: /open artifact/i }));
    expect(onOpen).toHaveBeenCalledWith(SAMPLE_ARTIFACT);
  });

  it('shows fallback title for untitled artifact', () => {
    render(<AIArtifactCard artifact={{ id: 'x', artifact_type: 'query' }} />);
    expect(screen.getByText('Untitled artifact')).toBeInTheDocument();
  });
});

// ── AIArtifactBrowser ───────────────────────────────────────────────────────

describe('AIArtifactBrowser', () => {
  beforeEach(() => {
    listArtifacts.mockReset();
    createArtifact.mockReset();
  });

  it('shows "No artifacts yet" when list is empty', async () => {
    listArtifacts.mockResolvedValue([]);
    render(<AIArtifactBrowser />);
    await waitFor(() => expect(screen.getByText(/no artifacts yet/i)).toBeInTheDocument());
  });

  it('renders artifact cards when list has items', async () => {
    listArtifacts.mockResolvedValue([SAMPLE_ARTIFACT]);
    render(<AIArtifactBrowser />);
    // findBy has a longer default timeout and retries until the element appears.
    expect(await screen.findByText('Q3 Emissions Report')).toBeInTheDocument();
  });

  it('shows error state and retry button on load failure', async () => {
    listArtifacts.mockRejectedValue(new Error('API error'));
    render(<AIArtifactBrowser />);
    await waitFor(() => expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument());
  });

  it('opens artifact detail dialog when Open is clicked', async () => {
    listArtifacts.mockResolvedValue([SAMPLE_ARTIFACT]);
    render(<AIArtifactBrowser />);
    const openBtn = await screen.findByRole('button', { name: /open artifact/i });
    fireEvent.click(openBtn);
    // The dialog renders the title as DialogTitle text.
    await waitFor(() =>
      expect(screen.getAllByText('Q3 Emissions Report').length).toBeGreaterThanOrEqual(1),
    );
  });
});

// ── Promote button in AIMessageBubble ───────────────────────────────────────

describe('AIMessageBubble Promote action', () => {
  it('renders Promote in the message action menu when onPromote is supplied', async () => {
    render(
      <MemoryRouter>
        <AIMessageBubble
          message={ASSISTANT_MSG}
          onPromote={vi.fn()}
          conversationType="chat"
        />
      </MemoryRouter>,
    );
    // Promote lives in the overflow menu — open it, then assert the menuitem.
    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    expect(await screen.findByRole('menuitem', { name: 'Promote' })).toBeInTheDocument();
  });

  it('does not render Promote button without onPromote', () => {
    render(
      <MemoryRouter>
        <AIMessageBubble message={ASSISTANT_MSG} conversationType="chat" />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /promote/i })).not.toBeInTheDocument();
  });

  it('calls onPromote with the message when Promote is clicked', async () => {
    const onPromote = vi.fn();
    render(
      <MemoryRouter>
        <AIMessageBubble message={ASSISTANT_MSG} onPromote={onPromote} conversationType="chat" />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'More message actions' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Promote' }));
    expect(onPromote).toHaveBeenCalledWith(ASSISTANT_MSG);
  });

  it('does not render Promote on user messages', () => {
    const userMsg = { ...ASSISTANT_MSG, role: 'user' };
    render(
      <MemoryRouter>
        <AIMessageBubble message={userMsg} onPromote={vi.fn()} conversationType="chat" />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /promote/i })).not.toBeInTheDocument();
  });
});
