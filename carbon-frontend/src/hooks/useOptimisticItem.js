// src/hooks/useOptimisticItem.js
// Optimistic mutation for a single entity (detail pages / inspector).
//
// save(patch) applies the patch synchronously (Beat-1 acknowledge), reconciles
// with the server response on success, and restores the prior snapshot on
// failure WITHOUT clearing the form (the error is rethrown). rollback() undoes
// the last uncommitted save.
//
// Returns { item, loading, error, save, rollback }.

import { useCallback, useEffect, useRef, useState } from "react";

const errorMessage = (err) => (err?.message ? err.message : "Request failed");

/**
 * useOptimisticItem({
 *   fetchItem,                  // () => Promise<item>   (reads token itself)
 *   update,                     // (patch) => Promise<updatedItem>
 *   getKey = (item) => item.id, // accepted for parity with useOptimisticList;
 *                               // a single-entity hook has no cross-item
 *                               // matching, so getKey is unused here.
 * }) -> { item, loading, error, save, rollback }
 */
export function useOptimisticItem({
  fetchItem,
  update,
  getKey: _getKey = (item) => item.id,
}) {
  const [item, setItemState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const itemRef = useRef(null);
  const snapshotRef = useRef(null);
  const fetchItemRef = useRef(fetchItem);
  const updateRef = useRef(update);
  const cancelledRef = useRef(false);

  useEffect(() => {
    fetchItemRef.current = fetchItem;
    updateRef.current = update;
  });

  // Single writer for `item` so the synchronous `itemRef` mirror never drifts
  // from what React renders.
  const setItem = useCallback((next) => {
    itemRef.current = next;
    setItemState(next);
  }, []);

  const run = useCallback(async () => {
    const fn = fetchItemRef.current;
    if (!fn) return;
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      if (!cancelledRef.current) {
        setItem(result);
      }
    } catch (err) {
      if (!cancelledRef.current) {
        setError(errorMessage(err));
      }
    } finally {
      if (!cancelledRef.current) {
        setLoading(false);
      }
    }
  }, [setItem]);

  useEffect(() => {
    run();
    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchItem]);

  const save = useCallback(
    async (patch) => {
      setError(null);
      const snapshot = itemRef.current;
      snapshotRef.current = snapshot;
      // Apply optimistically in the same tick (Beat-1 acknowledge).
      setItem({
        ...(snapshot ?? {}),
        ...patch,
        __optimistic: true,
        __pending: "update",
      });
      try {
        const result = await updateRef.current(patch);
        const { __optimistic: _o, __pending: _p, ...base } = itemRef.current ?? {};
        setItem(result && typeof result === "object" ? { ...base, ...result } : base);
        return result;
      } catch (err) {
        setItem(snapshot);
        setError(errorMessage(err));
        throw err;
      }
    },
    [setItem]
  );

  const rollback = useCallback(() => {
    if (snapshotRef.current !== null && snapshotRef.current !== undefined) {
      setItem(snapshotRef.current);
    }
    setError(null);
  }, [setItem]);

  return { item, loading, error, save, rollback };
}
