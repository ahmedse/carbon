import { describe, it, expect, vi } from 'vitest';
import { withRetry } from '../utils/lazyWithRetry';

const noSleep = async () => {};

describe('withRetry', () => {
  it('resolves on the first attempt without retrying', async () => {
    const factory = vi.fn().mockResolvedValue({ default: 'ok' });

    const result = await withRetry(factory, { _sleep: noSleep });

    expect(result).toEqual({ default: 'ok' });
    expect(factory).toHaveBeenCalledTimes(1);
  });

  it('retries a transient failure and resolves', async () => {
    const factory = vi
      .fn()
      .mockRejectedValueOnce(new Error('Failed to fetch dynamically imported module'))
      .mockResolvedValueOnce({ default: 'ok' });

    const result = await withRetry(factory, { retries: 3, _sleep: noSleep });

    expect(result).toEqual({ default: 'ok' });
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it('rejects with the last error after exhausting all retries', async () => {
    const factory = vi.fn().mockRejectedValue(new Error('still failing'));

    await expect(
      withRetry(factory, { retries: 2, _sleep: noSleep }),
    ).rejects.toThrow('still failing');

    // initial attempt + 2 retries
    expect(factory).toHaveBeenCalledTimes(3);
  });

  it('backs off exponentially between attempts', async () => {
    const sleep = vi.fn().mockResolvedValue(undefined);
    const factory = vi
      .fn()
      .mockRejectedValueOnce(new Error('x'))
      .mockRejectedValueOnce(new Error('x'))
      .mockResolvedValue({ default: 'ok' });

    await withRetry(factory, { retries: 3, baseDelayMs: 100, _sleep: sleep });

    expect(sleep).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenNthCalledWith(1, 100);
    expect(sleep).toHaveBeenNthCalledWith(2, 200);
  });
});
