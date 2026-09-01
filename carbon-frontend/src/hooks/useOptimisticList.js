// src/hooks/useOptimisticList.js
// Optimistic CRUD for list pages — Pulse Wave D, Beat 1 ("it feels alive").
//
// Wraps a fetchList() plus create/update/remove mutations so list pages no
// longer stall for the full round-trip: mutations apply synchronously (<100ms
// acknowledge), reconcile with the server response on success, and roll back
// in place on failure (the error is rethrown so callers can surface it and
// preserve any form input).
//
// Returns { items, loading, error, addItem, updateItem, removeItem }.

import { useCallback, useEffect, useRef, useState } from "react";

const errorMessage = (err) => (err?.message ? err.message : "Request failed");

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.results || [];
}

/**
 * useOptimisticList({
 *   fetchList,                 // () => Promise<list>   (reads token itself)
 *   create,                    // (input) => Promise<createdItem>
 *   update,                    // (id, patch) => Promise<updatedItem>
 *   remove,                    // (id) => Promise<response>
 *   getKey = (item) => item.id,
 * }) -> { items, loading, error, addItem, updateItem, removeItem }
 */
export function useOptimisticList({
  fetchList,
  create,
  update,
  remove,
  getKey = (item) => item.id,
}) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchListRef = useRef(fetchList);
  const createRef = useRef(create);
  const updateRef = useRef(update);
  const removeRef = useRef(remove);
  const getKeyRef = useRef(getKey);
  const cancelledRef = useRef(false);
  const tempSeq = useRef(0);

  // Keep the latest callbacks without re-triggering the fetch.
  useEffect(() => {
    fetchListRef.current = fetchList;
    createRef.current = create;
    updateRef.current = update;
    removeRef.current = remove;
    getKeyRef.current = getKey;
  });

  const run = useCallback(async () => {
    const fn = fetchListRef.current;
    if (!fn) return;
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    try {
      const result = await fn();
      if (!cancelledRef.current) {
        setItems(normalizeList(result));
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
  }, []);

  // Fetch on mount and whenever the fetchList identity changes; ignore stale
  // responses via the cancelled ref (same pattern as useApi).
  useEffect(() => {
    run();
    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchList]);

  const matches = useCallback(
    (item, id) => String(getKeyRef.current(item)) === String(id),
    []
  );

  const addItem = useCallback(async (input) => {
    setError(null);
    const tempKey = `__opt_${Date.now()}_${tempSeq.current++}`;
    const optimistic = {
      ...(input && typeof input === "object" ? input : {}),
      id: input?.id ?? tempKey,
      __optimistic: true,
      __pending: "create",
      __tempKey: tempKey,
    };
    // Apply synchronously (Beat-1): the row is visible before the round-trip.
    setItems((prev) => [...prev, optimistic]);
    try {
      const result = await createRef.current(input);
      setItems((prev) =>
        prev.map((item) => {
          if (item.__tempKey !== tempKey) return item;
          const { __optimistic: _o, __pending: _p, __tempKey: _t, ...base } = item;
          return result && typeof result === "object" ? { ...base, ...result } : base;
        })
      );
      return result;
    } catch (err) {
      setItems((prev) => prev.filter((item) => item.__tempKey !== tempKey));
      setError(errorMessage(err));
      throw err;
    }
  }, []);

  const updateItem = useCallback(
    async (id, patch) => {
      setError(null);
      let snapshot = null;
      setItems((prev) =>
        prev.map((item) => {
          if (!matches(item, id)) return item;
          snapshot = item;
          return { ...item, ...patch, __optimistic: true, __pending: "update" };
        })
      );
      try {
        const result = await updateRef.current(id, patch);
        setItems((prev) =>
          prev.map((item) => {
            if (!matches(item, id)) return item;
            const { __optimistic: _o, __pending: _p, ...base } = item;
            return result && typeof result === "object" ? { ...base, ...result } : base;
          })
        );
        return result;
      } catch (err) {
        if (snapshot !== null) {
          setItems((prev) =>
            prev.map((item) => (matches(item, id) ? snapshot : item))
          );
        }
        setError(errorMessage(err));
        throw err;
      }
    },
    [matches]
  );

  const removeItem = useCallback(
    async (id) => {
      setError(null);
      let removed = null;
      let removedIndex = -1;
      setItems((prev) => {
        const index = prev.findIndex((item) => matches(item, id));
        if (index === -1) return prev;
        removed = prev[index];
        removedIndex = index;
        return prev.filter((_, i) => i !== index);
      });
      try {
        const result = await removeRef.current(id);
        return result;
      } catch (err) {
        if (removed !== null) {
          setItems((prev) => {
            if (prev.some((item) => matches(item, id))) return prev;
            const next = [...prev];
            next.splice(Math.min(removedIndex, next.length), 0, removed);
            return next;
          });
        }
        setError(errorMessage(err));
        throw err;
      }
    },
    [matches]
  );

  return { items, loading, error, addItem, updateItem, removeItem };
}
