// src/__tests__/useOptimisticItem.test.jsx
// Pulse 0.2 Phase D2 — regression guards for the optimistic single-item hook.

import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useOptimisticItem } from "../hooks/useOptimisticItem";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useOptimisticItem", () => {
  it("loads the item on mount", async () => {
    const fetchItem = vi.fn(() =>
      Promise.resolve({ id: 1, name: "one", is_active: true })
    );
    const { result } = renderHook(() => useOptimisticItem({ fetchItem, update: vi.fn() }));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.item).toEqual({ id: 1, name: "one", is_active: true });
  });

  it("save applies optimistically and reconciles on success", async () => {
    const fetchItem = vi.fn(() => Promise.resolve({ id: 1, name: "one" }));
    const d = deferred();
    const update = vi.fn(() => d.promise);
    const { result } = renderHook(() => useOptimisticItem({ fetchItem, update }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let savePromise;
    act(() => {
      savePromise = result.current.save({ name: "renamed" });
    });

    // Optimistic patch visible immediately, before `update` settles.
    expect(result.current.item.name).toBe("renamed");
    expect(result.current.item.__optimistic).toBe(true);
    expect(update).toHaveBeenCalledWith({ name: "renamed" });

    d.resolve({ id: 1, name: "renamed", version: 2 });
    await act(async () => {
      await savePromise;
    });

    expect(result.current.item.name).toBe("renamed");
    expect(result.current.item.version).toBe(2);
    expect(result.current.item.__optimistic).toBeUndefined();
    expect(result.current.item.__pending).toBeUndefined();
  });

  it("save rolls back, sets error, rethrows, and does NOT clear the item", async () => {
    const fetchItem = vi.fn(() => Promise.resolve({ id: 1, name: "one" }));
    const d = deferred();
    const update = vi.fn(() => d.promise);
    const { result } = renderHook(() => useOptimisticItem({ fetchItem, update }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let savePromise;
    act(() => {
      savePromise = result.current.save({ name: "renamed" });
    });
    expect(result.current.item.name).toBe("renamed");

    await act(async () => {
      d.reject(new Error("boom"));
      await expect(savePromise).rejects.toThrow("boom");
    });

    expect(result.current.item).toEqual({ id: 1, name: "one" });
    expect(result.current.error).toBe("boom");
  });

  it("rollback restores the last snapshot and clears error", async () => {
    const fetchItem = vi.fn(() => Promise.resolve({ id: 1, name: "one" }));
    const update = vi.fn(() => Promise.resolve({ id: 1, name: "renamed" }));
    const { result } = renderHook(() => useOptimisticItem({ fetchItem, update }));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.save({ name: "renamed" });
    });
    expect(result.current.item.name).toBe("renamed");

    act(() => {
      result.current.rollback();
    });
    expect(result.current.item).toEqual({ id: 1, name: "one" });
    expect(result.current.error).toBe(null);
  });
});
