// src/hooks/useApi.js
// Generic GET data hook — wraps any apiFetch-based fetch function.
// Pattern from useEnabledApps.js: useRef cancellation + useEffect cleanup.
// Returns { data, loading, error, refetch } — data only, no JSX.

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * useApi(fetchFn, deps) -> { data, loading, error, refetch }
 *
 * - fetchFn(token) must return a Promise (see src/api/*.js helpers)
 * - Auto-fetches when `deps` change; `refetch()` forces a re-fetch
 * - Token read from localStorage.getItem("access")
 * - Stale responses are ignored after unmount / dep change (cancellation)
 */
export function useApi(fetchFn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFnRef = useRef(fetchFn);
  const cancelledRef = useRef(false);

  // Keep ref fresh so callers can swap fetchFn without re-triggering.
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  }, [fetchFn]);

  const run = useCallback(async () => {
    const fn = fetchFnRef.current;
    if (!fn) return;
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access");
      const result = await fn(token);
      if (!cancelledRef.current) {
        setData(result);
      }
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err?.message || "Request failed");
      }
    } finally {
      if (!cancelledRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // Auto-fetch on dependency change; cleanup cancels stale responses.
  useEffect(() => {
    run();
    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const refetch = useCallback(() => {
    run();
  }, [run]);

  return { data, loading, error, refetch };
}
