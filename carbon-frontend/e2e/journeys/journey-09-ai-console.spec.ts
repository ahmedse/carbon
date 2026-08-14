/**
 * JOURNEY 9: AI Admin Console — read-only Pulse surface + CBAC capability gating.
 *
 * Proves the Phase H AI read surface end-to-end:
 *  1. Every gated /carbon-api/ai/pulse/* read path rejects anonymous (401).
 *  2. A global admin (admins_group) can read every panel (200).
 *  3. A plain branch data owner (no capability) is forbidden (403) — CBAC gating.
 *  4. Admin opens the Pulse console in-browser and sees the Overview heading.
 *  5. Admin drills into a PulseDataPanel-backed route (Knowledge Base) and the
 *     panel renders without crashing (no "Not authorized", no hard error).
 *
 * Serial execution + one-time auth to stay under the 5-logins/min throttle.
 */
import { test, expect } from '@playwright/test';
import { PERSONAS, login, getAuthHeaders, navigateTo, assertVisible } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const AL_OWNER = PERSONAS.alamien_dataowner;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8009/carbon-api';
const PULSE = `${API_BASE}/ai/pulse`;

// The full gated read surface (see backend/ai/ops_urls.py).
const GATED_PATHS = [
  '/health/',
  '/modules/',
  '/tasks/unknown-task/',
  '/inventory/',
  '/data/knowledge/',
  '/archetypes/',
  '/graph/',
  '/usage/',
  '/settings/',
  '/sweeps/',
];

// Paths guaranteed to return a 200 payload for an authorized global admin
// (tasks/<id>/ is a dynamic lookup, so it is exercised only for 401 above).
const ADMIN_OK_PATHS = [
  '/health/',
  '/modules/',
  '/inventory/',
  '/data/knowledge/',
  '/archetypes/',
  '/graph/',
  '/usage/',
  '/settings/',
  '/sweeps/',
];

test.describe.serial('Journey 9: AI Admin Console — Pulse + CBAC', () => {
  const tokens: Record<string, string> = {};

  test.beforeAll(async ({ request }) => {
    for (const [key, persona] of [['admin', ADMIN], ['owner', AL_OWNER]] as const) {
      try {
        const h = await getAuthHeaders(request, API_BASE, persona);
        tokens[key] = h.Authorization.split(' ')[1];
      } catch (e) {
        console.log(`  ⚠️ Failed to get token for ${key}`);
        tokens[key] = '';
      }
    }
    console.log(`  Tokens obtained: ${Object.keys(tokens).filter((k) => tokens[k]).join(', ')}`);
  });

  const hdr = (key: string) => {
    const token = tokens[key];
    if (!token) throw new Error(`No token for ${key}`);
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  };

  test('9A. Unauthenticated → 401 on every gated Pulse read path', async ({ request }) => {
    for (const path of GATED_PATHS) {
      const res = await request.get(`${PULSE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(res.status(), `${path} should reject anonymous`).toBe(401);
    }
    console.log(`  ✅ All ${GATED_PATHS.length} Pulse paths reject anonymous`);
  });

  test('9B. Global admin → 200 on the read surface', async ({ request }) => {
    for (const path of ADMIN_OK_PATHS) {
      const res = await request.get(`${PULSE}${path}`, { headers: hdr('admin') });
      expect(res.status(), `${path} should be readable by admin`).toBe(200);
    }
    console.log(`  ✅ Admin reads all ${ADMIN_OK_PATHS.length} panels`);
  });

  test('9C. Plain data owner (no capability) → 403', async ({ request }) => {
    for (const path of ['/health/', '/inventory/', '/graph/']) {
      const res = await request.get(`${PULSE}${path}`, { headers: hdr('owner') });
      expect(res.status(), `${path} should forbid a plain data owner`).toBe(403);
    }
    console.log('  ✅ Data owner is CBAC-forbidden from the AI console');
  });

  test('9D. Admin opens the Pulse console and drills into a panel', async ({ page }) => {
    const ok = await login(page, ADMIN);
    expect(ok, 'Login succeeded').toBe(true);

    // Same browser context throughout: the SPA keeps its auth in localStorage,
    // so client-side (and same-context) navigation must not drop the session.
    await navigateTo(page, '/admin/ai');
    await assertVisible(page, 'Pulse Overview', 8000);

    // Drill into a PulseDataPanel-backed route (Knowledge Base) — still the
    // same authenticated session, so the read-only panel must render and must
    // NOT hard-error into the "Not authorized" state.
    await navigateTo(page, '/admin/ai/knowledge');
    await assertVisible(page, 'Knowledge Base', 8000);
    await expect(page.getByText(/not authorized/i).first()).not.toBeVisible({ timeout: 5000 });
    console.log('  ✅ /admin/ai renders the Overview and /admin/ai/knowledge renders the panel');
  });
});
