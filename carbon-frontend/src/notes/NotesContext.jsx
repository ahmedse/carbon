// src/notes/NotesContext.jsx
// Global context for the centralized Notes drawer.
//
// Responsibilities:
//  * Entity context (entityType / entityId / label) — pages opt in via setContext.
//  * Notes list cache per entity key; lazy fetch on context change (once).
//  * Comments cache per note id; lazy fetch on expand (once).
//  * Drawer UI state (open / pinned / width / active tab) persisted to localStorage.
//  * Optimistic reaction toggles reconciled with server responses.

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import * as notesApi from './notesApi';
import { entityKey, mergeReactionCounts, notesListKey } from './notesUtils';

const NotesCtx = createContext(null);

const LS = {
  open: 'carbon-notes-open',
  pin: 'carbon-notes-pin',
  width: 'carbon-notes-width',
  tab: 'carbon-notes-tab',
};

const WIDTH_MIN = () => Math.min(240, Math.floor(window.innerWidth * 0.35));
const WIDTH_MAX = () => Math.max(WIDTH_MIN(), Math.floor(window.innerWidth * 0.5));
const WIDTH_DEFAULT = 340;

function readLs(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null || raw === undefined) return fallback;
    if (typeof fallback === 'boolean') return raw === 'true';
    const num = Number(raw);
    return Number.isFinite(num) ? num : fallback;
  } catch {
    return fallback;
  }
}

function writeLs(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    /* ignore */
  }
}

export function NotesProvider({ children }) {
  // ── Entity context(s) ──────────────────────────────────────────────────
  // Multiple anchors: pages opt in via setContexts([{entityType, entityId, label}, …])
  // so ONE note can surface under a domain app AND a reporting year, while each
  // app's thread stays isolated (Option B — NoteAnchor).
  const [contexts, setContextsState] = useState([]);
  const context = contexts[0] || null; // primary anchor (backward compat)

  // ── Drawer UI state (persisted) ────────────────────────────────────────
  const [open, setOpenState] = useState(() => readLs(LS.open, false));
  const [pinned, setPinned] = useState(() => readLs(LS.pin, false));
  const [width, setWidthState] = useState(() => {
    const stored = readLs(LS.width, WIDTH_DEFAULT);
    return Math.min(WIDTH_MAX(), Math.max(WIDTH_MIN(), stored));
  });
  const [activeTab, setActiveTabState] = useState(() => readLs(LS.tab, 'notes'));

  // ── Data caches ────────────────────────────────────────────────────────
  const [lists, setLists] = useState({}); // key -> {notes, loading, error, page, hasMore, fetched}
  const [comments, setComments] = useState({}); // noteId -> {comments, loading, error, fetched}

  // Abort controllers for in-flight list fetches (keyed).
  const listAborts = useRef({});

  const persistOpen = useCallback((value) => writeLs(LS.open, value), []);
  const persistPin = useCallback((value) => writeLs(LS.pin, value), []);
  const persistWidth = useCallback((value) => writeLs(LS.width, value), []);
  const persistTab = useCallback((value) => writeLs(LS.tab, value), []);

  // ── Actions ────────────────────────────────────────────────────────────

  const setContexts = useCallback((next) => {
    setContextsState((prev) => {
      const nextList = !next ? [] : Array.isArray(next) ? next : [next];
      const keyOf = (list) =>
        list
          .filter((c) => c && c.entityType && c.entityId !== undefined && c.entityId !== null)
          .map((c) => `${c.entityType}:${c.entityId}`)
          .sort()
          .join('|');
      const nextKey = keyOf(nextList);
      // Unpinned drawer auto-collapses only when the ANCHOR SET changes. A
      // payload/label refresh with the same anchors (e.g. async data arriving
      // after the page mounts) must NOT collapse the drawer.
      if (nextKey !== keyOf(prev) && nextList.length && !readLs(LS.pin, false)) {
        setOpenState(false);
        persistOpen(false);
      }
      // Always store the fresh list so payload/label updates propagate to the
      // inspector tabs (they render from context.payload fast-path). Callers
      // memoize their context arrays, so a new reference here implies a real
      // data change, not a render loop.
      return nextList;
    });
  }, [persistOpen]);

  /** Backward-compat single-context setter (delegates to setContexts). */
  const setContext = useCallback((next) => {
    setContexts(next ? [next] : []);
  }, [setContexts]);

  const setOpen = useCallback((value) => {
    setOpenState(value);
    persistOpen(value);
  }, [persistOpen]);

  const toggleOpen = useCallback(() => {
    setOpenState((prev) => {
      persistOpen(!prev);
      return !prev;
    });
  }, [persistOpen]);

  const togglePin = useCallback(() => {
    setPinned((prev) => {
      persistPin(!prev);
      return !prev;
    });
  }, [persistPin]);

  const setWidth = useCallback((value) => {
    const clamped = Math.min(WIDTH_MAX(), Math.max(WIDTH_MIN(), value));
    setWidthState(clamped);
    persistWidth(clamped);
  }, [persistWidth]);

  const setActiveTab = useCallback((value) => {
    setActiveTabState(value);
    persistTab(value);
  }, [persistTab]);

  /** Fetch page `page` for a given list key, appending results. */
  const fetchListPage = useCallback(async (key, ctxs, page = 1, append = false) => {
    // Abort any previous in-flight fetch for this key.
    listAborts.current[key]?.abort();
    const controller = new AbortController();
    listAborts.current[key] = controller;

    setLists((prev) => ({
      ...prev,
      [key]: {
        ...(prev[key] || { notes: [], page: 0, hasMore: false }),
        loading: true,
        error: null,
      },
    }));

    try {
      const data = await notesApi.fetchNotes({
        contexts: ctxs,
        page,
      });
      const incoming = Array.isArray(data?.results) ? data.results : [];
      setLists((prev) => {
        const existing = prev[key]?.notes || [];
        const merged = append ? [...existing, ...incoming] : incoming;
        return {
          ...prev,
          [key]: {
            notes: merged,
            page,
            hasMore: !!data?.next,
            loading: false,
            error: null,
            fetched: true,
          },
        };
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setLists((prev) => ({
        ...prev,
        [key]: {
          ...(prev[key] || { notes: [], page: 0, hasMore: false }),
          loading: false,
          error: err?.message || 'Failed to load notes',
          fetched: true,
        },
      }));
    }
  }, []);

  /** Load more (older) notes for the current key. */
  const loadMore = useCallback(async () => {
    const key = notesListKey(contexts);
    const state = lists[key];
    if (!state || state.loading || !state.hasMore) return;
    await fetchListPage(key, contexts, (state.page || 0) + 1, true);
  }, [contexts, lists, fetchListPage]);

  /** Force refresh the current list (e.g., after creating a note). */
  const refreshList = useCallback(async () => {
    const key = notesListKey(contexts);
    await fetchListPage(key, contexts, 1, false);
  }, [contexts, fetchListPage]);

  /** Lazy-fetch comments for a note — cached per note id. */
  const fetchComments = useCallback(async (noteId) => {
    if (comments[noteId]?.fetched || comments[noteId]?.loading) return;
    setComments((prev) => ({
      ...prev,
      [noteId]: { comments: [], loading: true, error: null, fetched: false },
    }));
    try {
      const data = await notesApi.fetchComments(noteId);
      setComments((prev) => ({
        ...prev,
        [noteId]: {
          comments: Array.isArray(data?.results) ? data.results : [],
          loading: false,
          error: null,
          fetched: true,
        },
      }));
    } catch (err) {
      setComments((prev) => ({
        ...prev,
        [noteId]: {
          comments: [],
          loading: false,
          error: err?.message || 'Failed to load comments',
          fetched: true,
        },
      }));
    }
  }, [comments]);

  /** Add a note to the current context(s) — server round-trip, then refresh.
   *  The FIRST anchor is the primary; the rest become extra anchors so the note
   *  surfaces in every thread (domain app + reporting year, …).
   *  Visibility is implicit (server derives it from the author's scope). */
  const addNote = useCallback(async ({ body }) => {
    if (!contexts.length) throw new Error('No entity context for note');
    await notesApi.createNote({
      entityType: contexts[0].entityType,
      entityId: contexts[0].entityId,
      contexts,
      body,
    });
    await refreshList();
  }, [contexts, refreshList]);

  /** Add a comment — round-trip then refresh cached thread. */
  const addComment = useCallback(async (noteId, body) => {
    await notesApi.addComment(noteId, body);
    setComments((prev) => {
      const existing = prev[noteId];
      if (!existing) return prev; // thread never opened — nothing to refresh
      return { ...prev, [noteId]: { ...existing, fetched: false } };
    });
    await fetchComments(noteId);
    // Bump comments_count on the note in the list.
    setLists((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((key) => {
        next[key] = {
          ...next[key],
          notes: next[key].notes.map((n) =>
            n.id === noteId ? { ...n, comments_count: (n.comments_count || 0) + 1 } : n
          ),
        };
      });
      return next;
    });
  }, [fetchComments]);

  /** Optimistically toggle a reaction on a note, reconcile with server. */
  const toggleReaction = useCallback(async (noteId, reaction) => {
    const optimistic = (current) => {
      const counts = { ...(current.reaction_counts || {}) };
      const had = counts[reaction] || 0;
      counts[reaction] = current.my_reaction === reaction ? Math.max(0, had - 1) : had + 1;
      return {
        ...current,
        reaction_counts: counts,
        my_reaction: current.my_reaction === reaction ? null : reaction,
      };
    };
    setLists((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((key) => {
        next[key] = {
          ...next[key],
          notes: next[key].notes.map((n) => (n.id === noteId ? optimistic(n) : n)),
        };
      });
      return next;
    });
    try {
      const result = await notesApi.toggleNoteReaction(noteId, reaction);
      // Reconcile with the server truth.
      setLists((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((key) => {
          next[key] = {
            ...next[key],
            notes: next[key].notes.map((n) =>
              n.id === noteId
                ? {
                    ...n,
                    reaction_counts: mergeReactionCounts(n.reaction_counts, result),
                    my_reaction: result.my_reaction ?? null,
                  }
                : n
            ),
          };
        });
        return next;
      });
    } catch (err) {
      // Roll back: refetch list to restore server truth.
      await refreshList();
      throw err;
    }
  }, [refreshList]);

  /** Optimistically toggle a reaction on a comment. */
  const toggleCommentReaction = useCallback(async (noteId, commentId, reaction) => {
    const optimistic = (current) => {
      const counts = { ...(current.reaction_counts || {}) };
      const had = counts[reaction] || 0;
      counts[reaction] = current.my_reaction === reaction ? Math.max(0, had - 1) : had + 1;
      return {
        ...current,
        reaction_counts: counts,
        my_reaction: current.my_reaction === reaction ? null : reaction,
      };
    };
    setComments((prev) => {
      const entry = prev[noteId];
      if (!entry) return prev;
      return {
        ...prev,
        [noteId]: {
          ...entry,
          comments: entry.comments.map((c) =>
            c.id === commentId ? optimistic(c) : c
          ),
        },
      };
    });
    try {
      const result = await notesApi.toggleCommentReaction(noteId, commentId, reaction);
      setComments((prev) => {
        const entry = prev[noteId];
        if (!entry) return prev;
        return {
          ...prev,
          [noteId]: {
            ...entry,
            comments: entry.comments.map((c) =>
              c.id === commentId
                ? {
                    ...c,
                    reaction_counts: mergeReactionCounts(c.reaction_counts, result),
                    my_reaction: result.my_reaction ?? null,
                  }
                : c
            ),
          },
        };
      });
    } catch (err) {
      setComments((prev) => {
        const entry = prev[noteId];
        if (!entry) return prev;
        return { ...prev, [noteId]: { ...entry, fetched: false } };
      });
      await fetchComments(noteId);
      throw err;
    }
  }, [fetchComments]);

  /** Soft-delete a note. */
  const removeNote = useCallback(async (noteId) => {
    await notesApi.deleteNote(noteId);
    await refreshList();
  }, [refreshList]);

  /** Soft-delete a comment. */
  const removeComment = useCallback(async (noteId, commentId) => {
    await notesApi.deleteComment(noteId, commentId);
    setComments((prev) => {
      const entry = prev[noteId];
      if (!entry) return prev;
      return {
        ...prev,
        [noteId]: {
          ...entry,
          comments: entry.comments.map((c) =>
            c.id === commentId ? { ...c, is_removed: true } : c
          ),
          fetched: entry.fetched,
        },
      };
    });
    setLists((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((key) => {
        next[key] = {
          ...next[key],
          notes: next[key].notes.map((n) =>
            n.id === noteId ? { ...n, comments_count: Math.max(0, (n.comments_count || 0) - 1) } : n
          ),
        };
      });
      return next;
    });
  }, []);

  /** Edit a note body. */
  const editNote = useCallback(async (noteId, body) => {
    await notesApi.updateNote(noteId, { body });
    await refreshList();
  }, [refreshList]);

  // ── Lazy fetch on context change (once per anchor set) ─────────────────
  const key = notesListKey(contexts);
  const didInit = useRef({});
  useEffect(() => {
    if (didInit.current[key]) return;
    didInit.current[key] = true;
    fetchListPage(key, contexts, 1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Cleanup aborts on unmount.
  useEffect(() => {
    return () => {
      Object.values(listAborts.current).forEach((c) => c?.abort());
    };
  }, []);

  const value = useMemo(
    () => ({
      context,
      contexts,
      setContext,
      setContexts,
      open,
      pinned,
      width,
      activeTab,
      setOpen,
      toggleOpen,
      togglePin,
      setWidth,
      setActiveTab,
      lists,
      comments,
      fetchComments,
      loadMore,
      refreshList,
      addNote,
      addComment,
      toggleReaction,
      toggleCommentReaction,
      removeNote,
      removeComment,
      editNote,
    }),
    [
      context, contexts, setContext, setContexts, open, pinned, width, activeTab,
      setOpen, toggleOpen, togglePin, setWidth, setActiveTab,
      lists, comments, fetchComments, loadMore, refreshList,
      addNote, addComment, toggleReaction, toggleCommentReaction,
      removeNote, removeComment, editNote,
    ]
  );

  return <NotesCtx.Provider value={value}>{children}</NotesCtx.Provider>;
}

export function useNotes() {
  const ctx = useContext(NotesCtx);
  if (!ctx) {
    throw new Error('useNotes must be used within a <NotesProvider>');
  }
  return ctx;
}

export { entityKey };
