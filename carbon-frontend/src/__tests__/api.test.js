import { describe, it, expect } from 'vitest';

// We test the module's exports exist and have correct signatures
describe('apiFetch', () => {
  it('api module exports apiFetch', async () => {
    const api = await import('../api/api');
    expect(typeof api.apiFetch).toBe('function');
  });
});

describe('emissions API', () => {
  it('fetchEmissionsDashboard exports a function', async () => {
    const { fetchEmissionsDashboard } = await import('../api/emissions');
    expect(typeof fetchEmissionsDashboard).toBe('function');
  });
});
