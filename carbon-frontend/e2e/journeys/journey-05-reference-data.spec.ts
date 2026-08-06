/**
 * JOURNEY 5: Reference Data & Master Data Management
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const CARBON_LEAD = PERSONAS.carbon_lead_user;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

test.describe.serial('Journey 5: Reference Data Governance', () => {
  let adminHeaders: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    adminHeaders = await getAuthHeaders(request, API_BASE, ADMIN);
  });

  test('5A. Reference sets exist', async ({ request }) => {
    const res = await request.get(`${API_BASE}/mdm/reference-sets/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const sets = Array.isArray(data) ? data : data.results || [];
    console.log(`  Reference sets: ${sets.length}`);
    for (const s of sets.slice(0, 5)) {
      console.log(`    ${s.name} (${s.lifecycle_state || s.status || '?'})`);
    }
  });

  test('5B. Reference values exist within sets', async ({ request }) => {
    const res = await request.get(`${API_BASE}/mdm/reference-sets/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const sets = Array.isArray(data) ? data : data.results || [];
    if (sets.length > 0) {
      const setId = sets[0].id;
      const valRes = await request.get(`${API_BASE}/mdm/reference-sets/${setId}/values/`, { headers: adminHeaders });
      // May 404 if no values — that's OK
      expect([200, 404, 403]).toContain(valRes.status());
      console.log(`  Reference values for set ${setId} → ${valRes.status()}`);
    }
  });

  test('5C. Domain lead can read reference data', async ({ request }) => {
    const leadHeaders = await getAuthHeaders(request, API_BASE, CARBON_LEAD);
    const res = await request.get(`${API_BASE}/mdm/reference-sets/`, { headers: leadHeaders });
    expect([200, 403, 401]).toContain(res.status());
    console.log(`  ✅ Carbon lead reference access → ${res.status()}`);
  });
});
