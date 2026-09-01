import { useState, useEffect, useCallback } from 'react';
import { listInsights, postDisposition } from '../api/insights';
import { apiFetchStream } from '../api/api';
import { useAuth } from '../auth/AuthContext';

const STREAM_ENDPOINT = 'ai/insights/stream/';

// Shared singleton store — every mounted consumer (bell + panel) subscribes to
// the SAME data and unread count, giving one source of truth.
const sharedStore = {
  insights: [],
  unreadCount: 0,
  total: 0,
  loading: true,
  error: null,
  token: null,
  lastBeatAt: null,
};

const subscribers = new Set();

// Singleton stream guard: exactly ONE active SSE reader process-wide, so the
// bell and the panel never open duplicate streams.
let initInFlight = false;
let activeAbortController = null;
let activeReaderPromise = null;

function notifySubscribers() {
  subscribers.forEach((setState) =>
    setState({
      insights: sharedStore.insights,
      unreadCount: sharedStore.unreadCount,
      total: sharedStore.total,
      loading: sharedStore.loading,
      error: sharedStore.error,
      lastBeatAt: sharedStore.lastBeatAt,
    })
  );
}

/**
 * Passive presence accessor — reads the shared heartbeat timestamp without
 * subscribing or starting a stream (no network side-effects).
 */
export function getLastBeatAt() {
  return sharedStore.lastBeatAt;
}

function updateStore(partial) {
  Object.assign(sharedStore, partial);
  notifySubscribers();
}

function computeUnread(list) {
  return list.filter((item) => item.disposition === 'pending').length;
}

function prependInsight(insight) {
  if (!insight || !insight.id) return;
  const alreadyPresent = sharedStore.insights.some((item) => item.id === insight.id);
  if (alreadyPresent) return;
  const next = [insight, ...sharedStore.insights];
  updateStore({
    insights: next,
    unreadCount: computeUnread(next),
    total: Math.max(sharedStore.total, next.length),
  });
}

/**
 * Parse a buffered chunk of SSE text. Invokes `onFrame` for each complete
 * `data: {json}\n\n` frame; ignores heartbeat/comment (`: ping`) and blank
 * lines. Returns any trailing (incomplete) text to carry into the next chunk.
 */
function parseSseFrames(buffer, onFrame) {
  let rest = buffer;
  let idx;
  let sawHeartbeat = false;
  while ((idx = rest.indexOf('\n\n')) !== -1) {
    const frame = rest.slice(0, idx);
    rest = rest.slice(idx + 2);
    // Every complete frame (heartbeat or data) proves the stream is alive.
    sharedStore.lastBeatAt = Date.now();
    const dataLines = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''));
    if (!dataLines.length) {
      sawHeartbeat = true;
      continue; // heartbeat / comment frame
    }
    const payload = dataLines.join('\n');
    try {
      onFrame(JSON.parse(payload));
    } catch {
      // Ignore malformed frames — never crash the stream reader.
    }
  }
  // Heartbeats carry no data, so notify subscribers explicitly (data frames
  // already notify via prependInsight/updateStore).
  if (sawHeartbeat) notifySubscribers();
  return rest;
}

function startStream(token) {
  if (!token) return null;
  if (activeReaderPromise) return activeReaderPromise;

  const controller = new AbortController();
  activeAbortController = controller;

  activeReaderPromise = (async () => {
    try {
      const response = await apiFetchStream(STREAM_ENDPOINT, {
        token,
        signal: controller.signal,
      });
      const reader =
        response.body && typeof response.body.getReader === 'function'
          ? response.body.getReader()
          : null;
      if (!reader) {
        updateStore({ error: new Error('Streaming unavailable') });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer = parseSseFrames(
          buffer + decoder.decode(value, { stream: true }),
          prependInsight
        );
      }
      parseSseFrames(buffer + decoder.decode(), prependInsight);
    } catch (err) {
      if (err && (err.name === 'AbortError' || controller.signal.aborted)) {
        // Intentional close on unmount — not an error.
      } else {
        console.warn('[useInsightStream] stream error:', err);
        updateStore({ error: err });
      }
    } finally {
      if (activeAbortController === controller) activeAbortController = null;
      activeReaderPromise = null;
    }
  })();

  return activeReaderPromise;
}

export function useInsightStream() {
  const { token } = useAuth();
  const [state, setState] = useState({
    insights: sharedStore.insights,
    unreadCount: sharedStore.unreadCount,
    total: sharedStore.total,
    loading: sharedStore.loading,
    error: sharedStore.error,
    lastBeatAt: sharedStore.lastBeatAt,
  });

  useEffect(() => {
    subscribers.add(setState);
    setState({
      insights: sharedStore.insights,
      unreadCount: sharedStore.unreadCount,
      total: sharedStore.total,
      loading: sharedStore.loading,
      error: sharedStore.error,
      lastBeatAt: sharedStore.lastBeatAt,
    });

    if (token && token !== sharedStore.token && !initInFlight) {
      initInFlight = true;
      updateStore({ loading: true, error: null, token });
      (async () => {
        try {
          const data = await listInsights(token, 1);
          const results = data.results || [];
          updateStore({
            insights: results,
            total: data.count || 0,
            unreadCount: computeUnread(results),
            loading: false,
          });
        } catch (err) {
          updateStore({ loading: false, error: err });
        } finally {
          initInFlight = false;
          // Open the SSE stream after the initial page (best-effort).
          startStream(token).catch(() => {});
        }
      })();
    } else if (
      token &&
      sharedStore.token === token &&
      !initInFlight &&
      !activeReaderPromise
    ) {
      // Re-attach a stream that dropped (e.g. transient network error).
      startStream(token).catch(() => {});
    }

    return () => {
      subscribers.delete(setState);
      if (!subscribers.size) {
        // Last consumer gone — abort the reader and reset the singleton.
        if (activeAbortController) {
          activeAbortController.abort();
          activeAbortController = null;
        }
        activeReaderPromise = null;
        initInFlight = false;
        sharedStore.insights = [];
        sharedStore.unreadCount = 0;
        sharedStore.total = 0;
        sharedStore.loading = true;
        sharedStore.error = null;
        sharedStore.token = null;
        sharedStore.lastBeatAt = null;
      }
    };
  }, [token]);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      updateStore({ loading: true, error: null });
      const data = await listInsights(token, 1);
      const results = data.results || [];
      updateStore({
        insights: results,
        total: data.count || 0,
        unreadCount: computeUnread(results),
        loading: false,
      });
    } catch (err) {
      updateStore({ loading: false, error: err });
    }
  }, [token]);

  const markRead = useCallback(
    async (id, disposition = 'read') => {
      const prev = sharedStore.insights;
      const next = prev.map((item) =>
        item.id === id ? { ...item, disposition } : item
      );
      updateStore({ insights: next, unreadCount: computeUnread(next) });
      try {
        await postDisposition(token, id, disposition, '');
      } catch (_) {
        updateStore({ insights: prev, unreadCount: computeUnread(prev) });
        await refresh();
      }
    },
    [token, refresh]
  );

  const markAllRead = useCallback(async () => {
    const prev = sharedStore.insights;
    const pending = prev.filter((item) => item.disposition === 'pending');
    if (!pending.length) return;
    const next = prev.map((item) =>
      item.disposition === 'pending' ? { ...item, disposition: 'read' } : item
    );
    updateStore({ insights: next, unreadCount: 0 });
    try {
      await Promise.all(
        pending.map((item) => postDisposition(token, item.id, 'read', ''))
      );
    } catch (_) {
      updateStore({ insights: prev, unreadCount: computeUnread(prev) });
      await refresh();
    }
  }, [token, refresh]);

  return { ...state, markRead, markAllRead, refresh };
}
