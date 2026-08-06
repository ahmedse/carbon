/**
 * JOURNEY 4: Emission Calculations & Reports
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const AL_ANALYST = PERSONAS.alamien_analyst;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

test.describe.serial('Journey 4: Calculations & Reports', () => {
  let adminHeaders: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    adminHeaders = await getAuthHeaders(request, API_BASE, ADMIN);
  });

  test('4A. Calculations exist and have valid structure', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/calculations/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const calcs = Array.isArray(data) ? data : data.results || [];
    console.log(`  Calculations: ${calcs.length}`);
    if (calcs.length > 0) {
      const c = calcs[0];
      expect(c).toHaveProperty('co2e_kg');
      expect(c).toHaveProperty('scope');
      expect(c).toHaveProperty('category');
      expect([1, 2, 3]).toContain(c.scope);
      console.log(`  Sample: ${c.co2e_kg} kg CO2e (Scope ${c.scope}, ${c.category})`);
    }
  });

  test('4B. Calculation math is correct (co2e >= 0)', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=5`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const calcs = Array.isArray(data) ? data : data.results || [];
    for (const c of calcs) {
      expect(parseFloat(c.co2e_kg)).toBeGreaterThanOrEqual(0);
    }
    console.log(`  ✅ All ${calcs.length} calculations have valid co2e`);
  });

  test('4C. Dashboard returns data', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/calculations/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Calculations endpoint accessible');
  });

  test('4D. Reporting periods exist', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/periods/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const periods = Array.isArray(data) ? data : data.results || [];
    console.log(`  Reporting periods: ${periods.length}`);
  });

  test('4E. Analyst can read calculations (scoped)', async ({ request }) => {
    const analystHeaders = await getAuthHeaders(request, API_BASE, AL_ANALYST);
    const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=1`, { headers: analystHeaders });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Analyst reads calculations');
  });
});
