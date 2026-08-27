// src/__tests__/notes.drawer.test.jsx
// Phase 2 — centralized Notes drawer: open/collapse/pin, localStorage
// persistence, lazy comments fetch, optimistic reactions, RTL mirror.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent, within } from '@testing-library/react';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
}));

vi.mock('../notes/notesApi', () => ({
  fetchNotes: vi.fn(),
  createNote: vi.fn(),
  updateNote: vi.fn(),
  deleteNote: vi.fn(),
  toggleNoteReaction: vi.fn(),
  fetchComments: vi.fn(),
  addComment: vi.fn(),
  updateComment: vi.fn(),
  deleteComment: vi.fn(),
  toggleCommentReaction: vi.fn(),
}));

import { NotesProvider, useNotes } from '../notes/NotesContext';
import { NotesDrawer } from '../notes/NotesDrawer';
import * as notesApi from '../notes/notesApi';

const NOTE = {
  id: 1,
  entity_type: 'org_unit',
  entity_id: 42,
  body: 'Hello world',
  author: { id: 7, username: 'ahmed', full_name: 'Ahmed Ali' },
  visibility: 'public',
  created_at: '2025-01-01T10:00:00Z',
  updated_at: '2025-01-01T10:00:00Z',
  comments_count: 2,
  reaction_counts: { like: 1, question: 0, star: 0 },
  my_reaction: null,
  can_edit: true,
  is_removed: false,
};

const COMMENT = {
  id: 11,
  body: 'Nice point',
  author: { id: 8, username: 'sara', full_name: 'Sara H' },
  created_at: '2025-01-01T11:00:00Z',
  updated_at: '2025-01-01T11:00:00Z',
  reaction_counts: { like: 0, question: 0, star: 0 },
  my_reaction: null,
  can_edit: true,
  is_removed: false,
};

function Harness({ nextContext }) {
  const notes = useNotes();
  return (
    <div>
      <button onClick={() => notes.setContext(nextContext)}>set-context</button>
      <button onClick={() => notes.toggleOpen()}>toggle-open</button>
      <button onClick={() => notes.togglePin()}>toggle-pin</button>
      <NotesDrawer />
    </div>
  );
}

function renderDrawer(context = { entityType: 'org_unit', entityId: 42, label: 'Org Unit A' }) {
  return render(
    <NotesProvider>
      <Harness context={context} nextContext={{ entityType: 'org_unit', entityId: 43, label: 'Org Unit B' }} />
    </NotesProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  notesApi.fetchNotes.mockResolvedValue({
    count: 1,
    next: null,
    results: [NOTE],
  });
  notesApi.fetchComments.mockResolvedValue({
    count: 1,
    next: null,
    results: [COMMENT],
  });
});

describe('NotesDrawer — layout & state', () => {
  it('renders collapsed rail by default — no count badge on the arrow', async () => {
    renderDrawer();
    // Rail is visible; panel is not.
    const rail = screen.getByRole('navigation', { name: /notes drawer/i });
    expect(rail).toBeInTheDocument();
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();

    // The arrow is a single toggle — per user mandate, no note-count badge.
    // (The lazy list fetch still happens for the active view.)
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));
    expect(within(rail).queryByText('1')).not.toBeInTheDocument();
    expect(rail.querySelector('.MuiBadge-badge')).toBeNull();
  });

  it('disables the composer when there is no entity context', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    const panel = screen.getByRole('complementary');

    // Global "All notes" view: composer is replaced by a hint, and nothing can be submitted.
    expect(screen.getByText(/open a record to attach a note/i)).toBeInTheDocument();
    expect(within(panel).queryByRole('textbox')).not.toBeInTheDocument();
    expect(within(panel).queryByRole('button', { name: /add note/i })).not.toBeInTheDocument();
  });

  it('expands to the panel when the rail is clicked and collapses again', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    expect(screen.getByRole('complementary')).toBeInTheDocument();
    expect(screen.getByText('Hello world')).toBeInTheDocument();

    // Collapse via the close button.
    fireEvent.click(screen.getByRole('button', { name: /collapse/i }));
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: /notes drawer/i })).toBeInTheDocument();
  });

  it('persists open state to localStorage', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    expect(localStorage.getItem('carbon-notes-open')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: /collapse/i }));
    expect(localStorage.getItem('carbon-notes-open')).toBe('false');
  });

  it('reads persisted open state on mount', async () => {
    localStorage.setItem('carbon-notes-open', 'true');
    renderDrawer();
    // Panel should be expanded immediately.
    expect(await screen.findByRole('complementary')).toBeInTheDocument();
  });
});

describe('NotesDrawer — pin behavior', () => {
  it('auto-collapses when context changes while unpinned', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    expect(screen.getByRole('complementary')).toBeInTheDocument();

    // Change entity → drawer auto-collapses (unpinned).
    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'set-context' }));
    });
    await waitFor(() => expect(screen.queryByRole('complementary')).not.toBeInTheDocument());
    expect(screen.getByRole('navigation', { name: /notes drawer/i })).toBeInTheDocument();
  });

  it('stays open on context change when pinned', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    fireEvent.click(within(screen.getByRole('complementary')).getByRole('button', { name: /pin/i }));
    expect(localStorage.getItem('carbon-notes-pin')).toBe('true');

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'set-context' }));
    });
    // Pinned → still expanded, and it refetches for the new entity.
    expect(screen.getByRole('complementary')).toBeInTheDocument();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(2));
    // With an entity context active, the composer is available again.
    expect(within(screen.getByRole('complementary')).getByRole('textbox')).toBeInTheDocument();
  });
});

describe('NotesDrawer — comments', () => {
  it('lazily fetches comments only when the thread is expanded', async () => {
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));
    expect(notesApi.fetchComments).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    // Expand the thread on the note card.
    const expand = screen.getByRole('button', { name: /comments/i });
    fireEvent.click(expand);

    await waitFor(() => expect(notesApi.fetchComments).toHaveBeenCalledWith(1));
    await screen.findByText('Nice point');
  });
});

describe('NotesDrawer — reactions (optimistic)', () => {
  it('toggles a like optimistically and reconciles with the server', async () => {
    notesApi.toggleNoteReaction.mockResolvedValue({
      reaction_counts: { like: 2, question: 0, star: 0 },
      my_reaction: 'like',
    });
    renderDrawer();
    await waitFor(() => expect(notesApi.fetchNotes).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: /notes/i }));
    const like = screen.getByRole('button', { name: /👍/ });
    expect(like).toHaveAttribute('aria-pressed', 'false');
    expect(within(like).getByText('1')).toBeInTheDocument();

    fireEvent.click(like);
    // Optimistic bump immediately.
    expect(within(like).getByText('2')).toBeInTheDocument();
    await waitFor(() => expect(notesApi.toggleNoteReaction).toHaveBeenCalledWith(1, 'like'));
    // Reconcile with server payload.
    await waitFor(() => expect(like).toHaveAttribute('aria-pressed', 'true'));
  });
});

describe('NotesDrawer — width clamp', () => {
  it('clamps width to min/max bounds', async () => {
    function WidthHarness() {
      const { setWidth, width } = useNotes();
      return (
        <div>
          <button onClick={() => setWidth(10)}>set-min</button>
          <button onClick={() => setWidth(99999)}>set-max</button>
          <span data-testid="width">{width}</span>
        </div>
      );
    }
    render(
      <NotesProvider>
        <WidthHarness />
      </NotesProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'set-min' }));
    expect(Number(screen.getByTestId('width').textContent)).toBe(240);
    fireEvent.click(screen.getByRole('button', { name: 'set-max' }));
    expect(Number(screen.getByTestId('width').textContent)).toBeLessThanOrEqual(
      Math.max(240, Math.floor(window.innerWidth * 0.5)),
    );
  });
});
