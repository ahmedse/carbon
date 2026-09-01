// src/__tests__/useOptimisticList.test.jsx
// Pulse 0.2 Phase D2 — regression guards for the optimistic list CRUD hook.

import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useOptimisticList } from "../hooks/useOptimisticList";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const threeItems = () => [
  { id: 1, name: "one", is_active: true },
  { id: 2, name: "two", is_active: false },
  { id: 3, name: "three", is_active: true },
];

function renderList({ fetchList, create, update, remove }) {
  return renderHook(() =>
    useOptimisticList({
      fetchList,
      create: create || vi.fn(),
      update: update || vi.fn(),
      remove: remove || vi.fn(),
    })
  );
}

describe("useOptimisticList", () => {
  it("loads the list on mount and clears loading", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const { result } = renderList({ fetchList });

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.items).toEqual(threeItems());
    expect(result.current.error).toBe(null);
  });

  it("addItem applies optimistically before create resolves, then reconciles", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const d = deferred();
    const create = vi.fn(() => d.promise);
    const { result } = renderList({ fetchList, create });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let addPromise;
    act(() => {
      addPromise = result.current.addItem({ definition: { name: "four" } });
    });

    // Optimistic row appears in the same tick — before `create` settles.
    const optimistic = result.current.items.find((i) => i.__optimistic);
    expect(optimistic).toBeTruthy();
    expect(optimistic.__pending).toBe("create");
    expect(create).toHaveBeenCalledWith({ definition: { name: "four" } });

    d.resolve({ id: 4, name: "four" });
    await act(async () => {
      await addPromise;
    });

    const added = result.current.items.find((i) => i.id === 4);
    expect(added).toBeTruthy();
    expect(added.__optimistic).toBeUndefined();
    expect(added.__pending).toBeUndefined();
  });

  it("addItem rolls back and rethrows on failure", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const d = deferred();
    const create = vi.fn(() => d.promise);
    const { result } = renderList({ fetchList, create });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let addPromise;
    act(() => {
      addPromise = result.current.addItem({ definition: {} });
    });
    expect(result.current.items.some((i) => i.__optimistic)).toBe(true);

    await act(async () => {
      d.reject(new Error("boom"));
      await expect(addPromise).rejects.toThrow("boom");
    });

    expect(result.current.items.some((i) => i.__optimistic)).toBe(false);
    expect(result.current.items).toHaveLength(3);
    expect(result.current.error).toBe("boom");
  });

  it("updateItem applies synchronously and reconciles on success", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const d = deferred();
    const update = vi.fn(() => d.promise);
    const { result } = renderList({ fetchList, update });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let updatePromise;
    act(() => {
      updatePromise = result.current.updateItem(2, { name: "TWO" });
    });

    // Optimistic patch visible immediately, before `update` settles.
    expect(result.current.items.find((i) => i.id === 2).name).toBe("TWO");
    expect(result.current.items.find((i) => i.id === 2).__optimistic).toBe(true);

    d.resolve({ id: 2, name: "TWO", version: 5 });
    await act(async () => {
      await updatePromise;
    });

    const updated = result.current.items.find((i) => i.id === 2);
    expect(updated.name).toBe("TWO");
    expect(updated.version).toBe(5);
    expect(updated.__optimistic).toBeUndefined();
  });

  it("updateItem rolls back, sets error, and rethrows on failure", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const d = deferred();
    const update = vi.fn(() => d.promise);
    const { result } = renderList({ fetchList, update });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let updatePromise;
    act(() => {
      updatePromise = result.current.updateItem(2, { name: "TWO" });
    });
    expect(result.current.items.find((i) => i.id === 2).name).toBe("TWO");

    await act(async () => {
      d.reject(new Error("boom"));
      await expect(updatePromise).rejects.toThrow("boom");
    });

    expect(result.current.items.find((i) => i.id === 2).name).toBe("two");
    expect(result.current.items.find((i) => i.id === 2).__optimistic).toBeUndefined();
    expect(result.current.error).toBe("boom");
  });

  it("removeItem removes synchronously and returns the server response", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const remove = vi.fn(() => Promise.resolve({ archived: true, results_count: 7 }));
    const { result } = renderList({ fetchList, remove });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let removePromise;
    act(() => {
      removePromise = result.current.removeItem(2);
    });
    expect(result.current.items.map((i) => i.id)).toEqual([1, 3]);

    let outcome;
    await act(async () => {
      outcome = await removePromise;
    });
    expect(outcome).toEqual({ archived: true, results_count: 7 });
    expect(result.current.items.find((i) => i.id === 2)).toBeUndefined();
  });

  it("removeItem failure re-inserts the item at its original index", async () => {
    const fetchList = vi.fn(() => Promise.resolve(threeItems()));
    const d = deferred();
    const remove = vi.fn(() => d.promise);
    const { result } = renderList({ fetchList, remove });
    await waitFor(() => expect(result.current.loading).toBe(false));

    let removePromise;
    act(() => {
      removePromise = result.current.removeItem(2);
    });
    expect(result.current.items.map((i) => i.id)).toEqual([1, 3]);

    await act(async () => {
      d.reject(new Error("boom"));
      await expect(removePromise).rejects.toThrow("boom");
    });

    expect(result.current.items.map((i) => i.id)).toEqual([1, 2, 3]);
    expect(result.current.error).toBe("boom");
  });
});
