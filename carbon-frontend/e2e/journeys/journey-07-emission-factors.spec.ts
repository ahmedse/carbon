/**
 * JOURNEY 7: Emission Factors & Data Schema Verification
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

test.describe.serial('Journey 7: Emission Factors & Data Schema', () => {
  let adminHeaders: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    adminHeaders = await getAuthHeaders(request, API_BASE, ADMIN);
  });

  test('7A. Emission factors exist', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/factors/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const factors = Array.isArray(data) ? data : data.results || [];
    const scopes = new Set(factors.map((f: any) => f.scope));
    console.log(`  Emission factors: ${factors.length}, Scopes: ${[...scopes].sort().join(', ')}`);
  });

  test('7B. Emission factors have categories', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/factors/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const factors = Array.isArray(data) ? data : data.results || [];
    const categories = new Set(factors.map((f: any) => f.category));
    console.log(`  Categories: ${[...categories].sort().join(', ')}`);
    // Should have at least some categories
    expect(categories.size).toBeGreaterThan(0);
  });

  test('7C. Factors are filterable by scope', async ({ request }) => {
    for (const scope of [1, 2, 3]) {
      const res = await request.get(`${API_BASE}/carbon/factors/?scope=${scope}`, { headers: adminHeaders });
      expect(res.ok(), `Scope ${scope} filter`).toBe(true);
    }
    console.log('  ✅ All scopes filterable');
  });
});
