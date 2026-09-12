import { lazy } from 'react';

/**
 * Retry an async import factory with exponential backoff.
 *
 * `React.lazy` caches a REJECTED import forever — once a transient network or
 * dev-server error (e.g. "Failed to fetch dynamically imported module" after a
 * Vite restart invalidates the browser's module graph) rejects the import, the
 * component stays broken until a full page reload. This retries the factory a
 * few times so transient failures self-heal without a reload.
 *
 * @param {() => Promise<{default: React.ComponentType}>} factory  dynamic import fn
 * @param {object} [options]
 * @param {number} [options.retries=3]   additional attempts after the first
 * @param {number} [options.baseDelayMs=500]  initial backoff, doubles per attempt
 * @param {(ms: number) => Promise<void>} [options._sleep]  injectable for tests
 * @returns {Promise<{default: React.ComponentType}>}
 */
export async function withRetry(factory, { retries = 3, baseDelayMs = 500, _sleep } = {}) {
  const sleep = _sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await factory();
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        await sleep(baseDelayMs * 2 ** attempt);
      }
    }
  }
  throw lastError;
}

/**
 * `React.lazy` with transient-failure retry. Drop-in replacement for `lazy`.
 *
 * @param {() => Promise<{default: React.ComponentType}>} factory
 * @param {object} [options]  forwarded to `withRetry`
 * @returns {React.LazyExoticComponent}
 */
export function lazyWithRetry(factory, options) {
  return lazy(() => withRetry(factory, options));
}
