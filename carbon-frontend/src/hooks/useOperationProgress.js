import { useEffect, useRef, useState } from 'react';
import { apiFetchStream } from '../api/api';
import { useAuth } from '../auth/AuthContext';

// Wave D1 (Pulse 0.2): a shared, process-wide SSE reader for the operations
// progress stream. Multiple mounted components (the DQ jobs grid, an import
// panel, a report panel) all subscribe to ONE stream and receive the same
// frames — no duplicate connections. Frames are OUTCOME-shaped (RULE_23):
// `{ op_type, op_id, status, message, percent }`.
const STREAM_ENDPOINT = 'ai/operations/stream/';

// The set of live `onFrame` callbacks registered by mounted consumers.
const handlers = new Set();

// Singleton stream guard — exactly one active reader process-wide.
let activeAbortController = null;
let activeReaderPromise = null;
let reconnectTimer = null;

// How long to wait before re-attaching a stream that dropped unexpectedly
// (e.g. transient network error). A dropped stream means no live progress, so
// we retry while there are still consumers mounted.
const RECONNECT_DELAY_MS = 5000;

/**
 * Parse a buffered chunk of SSE text. Invokes `onFrame` for each complete
 * `data: {json}\n\n` frame; ignores heartbeat/comment (`: ping`) and blank
 * lines. Returns any trailing (incomplete) text to carry into the next chunk.
 */
function parseSseFrames(buffer, onFrame) {
  let rest = buffer;
  let idx;
  while ((idx = rest.indexOf('\n\n')) !== -1) {
    const frame = rest.slice(0, idx);
    rest = rest.slice(idx + 2);
    const dataLines = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''));
    if (!dataLines.length) continue; // heartbeat / comment frame
    try {
      onFrame(JSON.parse(dataLines.join('\n')));
    } catch {
      // Ignore malformed frames — never crash the stream reader.
    }
  }
  return rest;
}

function dispatch(frame) {
  handlers.forEach((onFrame) => {
    try {
      onFrame(frame);
    } catch {
      // A consumer callback must never break the reader or other consumers.
    }
  });
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
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer = parseSseFrames(
          buffer + decoder.decode(value, { stream: true }),
          dispatch
        );
      }
      parseSseFrames(buffer + decoder.decode(), dispatch);
    } catch (err) {
      if (err && (err.name === 'AbortError' || controller.signal.aborted)) {
        // Intentional close on unmount — not an error.
      } else {
        console.warn('[useOperationProgress] stream error:', err);
        scheduleReconnect(token);
      }
    } finally {
      if (activeAbortController === controller) {
        activeAbortController = null;
        activeReaderPromise = null;
      }
    }
  })();

  return activeReaderPromise;
}

function scheduleReconnect(token) {
  if (reconnectTimer || handlers.size === 0) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    if (handlers.size > 0 && !activeReaderPromise) {
      startStream(token).catch(() => {});
    }
  }, RECONNECT_DELAY_MS);
}

/**
 * Subscribe to the shared operations-progress SSE stream.
 *
 * @param {(frame: object) => void} onFrame - called with each OUTCOME-shaped
 *   `op.progress` frame. Consumers filter by `frame.op_type` themselves.
 * @returns {{ connected: boolean, error: Error | null }}
 */
export function useOperationProgress(onFrame) {
  const { token } = useAuth();
  const [state, setState] = useState({ connected: false, error: null });
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  useEffect(() => {
    if (!token) {
      setState({ connected: false, error: null });
      return undefined;
    }

    const handler = (frame) => {
      if (onFrameRef.current) onFrameRef.current(frame);
    };
    handlers.add(handler);

    if (activeReaderPromise) {
      setState({ connected: true, error: null });
    } else {
      startStream(token)
        .then(() => setState({ connected: true, error: null }))
        .catch((err) => setState({ connected: false, error: err }));
    }

    return () => {
      handlers.delete(handler);
      if (handlers.size === 0) {
        // Last consumer gone — tear down the singleton reader and any retry.
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
        if (activeAbortController) {
          activeAbortController.abort();
          activeAbortController = null;
        }
        activeReaderPromise = null;
      }
    };
  }, [token]);

  return state;
}
