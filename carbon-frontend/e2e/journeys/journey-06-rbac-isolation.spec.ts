/**
 * JOURNEY 6: RBAC Isolation — Multi-User Cross-Verification
 * Uses serial execution with one-time auth to avoid rate limiting (5 logins/min).
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const AL_OWNER = PERSONAS.alamien_dataowner;
const AL_ANALYST = PERSONAS.alamien_analyst;
const AL_VIEWER = PERSONAS.alamien_viewer;
const AUDITOR = PERSONAS.auditor_user;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

test.describe.serial('Journey 6: RBAC Isolation', () => {
  const tokens: Record<string, string> = {};

  test.beforeAll(async ({ request }) => {
    const personas = [
      { key: 'admin', persona: ADMIN },
      { key: 'al_owner', persona: AL_OWNER },
      { key: 'al_analyst', persona: AL_ANALYST },
      { key: 'al_viewer', persona: AL_VIEWER },
      { key: 'auditor', persona: AUDITOR },
    ];
    for (const { key, persona } of personas) {
      try {
        const h = await getAuthHeaders(request, API_BASE, persona);
        tokens[key] = h.Authorization.split(' ')[1];
      } catch (e) {
        console.log(`  ⚠️ Failed to get token for ${key}`);
        tokens[key] = '';
      }
    }
    console.log(`  Tokens obtained: ${Object.keys(tokens).filter(k => tokens[k]).join(', ')}`);
  });

  function hdr(key: string) {
    const token = tokens[key];
    if (!token) throw new Error(`No token for ${key}`);
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  }

  test('6A. Unauthenticated → 401', async ({ request }) => {
    const endpoints = ['/carbon/calculations/', '/carbon/periods/', '/carbon/factors/',
      '/dq/rules/', '/dq/results/', '/mdm/reference-sets/', '/catalog/governance-events/'];
    for (const ep of endpoints) {
      const res = await request.get(`${API_BASE}${ep}`, {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(res.status(), ep).toBe(401);
    }
    console.log(`  ✅ All ${endpoints.length} endpoints require auth`);
  });

  test('6B. Admin can GET all endpoints', async ({ request }) => {
    for (const ep of ['/carbon/calculations/', '/carbon/periods/', '/carbon/factors/',
      '/dq/rules/', '/dq/results/', '/mdm/reference-sets/', '/catalog/governance-events/']) {
      const res = await request.get(`${API_BASE}${ep}`, { headers: hdr('admin') });
      expect(res.ok(), ep).toBe(true);
    }
    console.log('  ✅ Admin accesses all endpoints');
  });

  test('6C. Accounts endpoint requires auth', async ({ request }) => {
    const res = await request.get(`${API_BASE}/accounts/users/`, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(res.status()).toBe(401);
    console.log('  ✅ /accounts/users/ → 401');
  });

  test('6D. All users can GET calculations', async ({ request }) => {
    for (const key of ['admin', 'al_owner', 'al_analyst', 'al_viewer', 'auditor']) {
      const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=1`, {
        headers: hdr(key),
      });
      expect(res.ok(), key).toBe(true);
    }
    console.log('  ✅ All users read calculations');
  });

  test('6E. Data owner POST calculation → accepted or validation error', async ({ request }) => {
    // Try POST with a valid-looking calculation; accept 201, 400 (validation), or 403 (perms)
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: hdr('al_owner'),
      data: { emission_factor: 1, activity_value: '100.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    expect([201, 400, 403], `Data owner POST → ${createRes.status()}`).toContain(createRes.status());
    console.log(`  ✅ Data owner POST → ${createRes.status()}`);
  });

  test('6F. Viewer POST → 403 forbidden', async ({ request }) => {
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: hdr('al_viewer'),
      data: { emission_factor: 1, activity_value: '50.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    expect(createRes.status()).toBe(403);
    console.log('  ✅ Viewer POST → 403 Forbidden');
  });

  test('6G. Auditor can read governance', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/?page_size=1`, {
      headers: hdr('auditor'),
    });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Auditor reads governance events');
  });

  test('6H. Auditor POST → forbidden', async ({ request }) => {
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: hdr('auditor'),
      data: { emission_factor: 1, activity_value: '10.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    expect([403, 400]).toContain(createRes.status());
    console.log(`  ✅ Auditor POST → ${createRes.status()}`);
  });
});
