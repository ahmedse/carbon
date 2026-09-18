/**
 * JOURNEY 17: Steward Control Plane — API pack for ADR-0036 J1–J7.
 *
 * Browser smoke + control-plane HTTP checks that a steward can:
 *  J1 Contain (learning_freeze)
 *  J4 Evidence requires id / PDP join (happy path if run seeded)
 *  J7 Budget override PATCH
 *  UI: Command Center heading + Platform Roles tab reachable
 *
 * Full offline proofs live in backend/ai/tests/test_steward_journeys.py.
 * This journey is the Playwright companion for CI when servers are up.
 */
import { test, expect } from '@playwright/test';
import { PERSONAS, login, getAuthHeaders, navigateTo, assertVisible } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8009/carbon-api';
const CONTROL = `${API_BASE}/ai/pulse/control`;

test.describe.serial('Journey 17: Steward Control Plane J1–J7', () => {
  let token = '';

  test.beforeAll(async ({ request }) => {
    try {
      const h = await getAuthHeaders(request, API_BASE, ADMIN);
      token = h.Authorization.split(' ')[1];
    } catch (e) {
      console.log('  ⚠️ Failed to get admin token', e);
      token = '';
    }
  });

  const hdr = () => {
    if (!token) throw new Error('No admin token');
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  };

  test('17A. J1 — set learning_freeze containment', async ({ request }) => {
    const res = await request.post(`${CONTROL}/containment/`, {
      headers: hdr(),
      data: { level: 'learning_freeze', reason: 'journey-17 J1' },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.containment_level).toBe('learning_freeze');
    expect(body.learning_admissions_frozen).toBe(true);

    const cmd = await request.get(`${CONTROL}/command/`, { headers: hdr() });
    expect(cmd.status()).toBe(200);
    expect((await cmd.json()).containment.containment_level).toBe('learning_freeze');

    // Reset
    await request.post(`${CONTROL}/containment/`, {
      headers: hdr(),
      data: { level: 'normal', reason: 'journey-17 reset' },
    });
    console.log('  ✅ J1 contain + command round-trip');
  });

  test('17B. J4 — evidence requires id; PDP dry-run reachable', async ({ request }) => {
    const bad = await request.get(`${CONTROL}/evidence/`, { headers: hdr() });
    expect(bad.status()).toBe(400);

    const dry = await request.post(`${CONTROL}/pdp/dry-run/`, {
      headers: hdr(),
      data: {
        action: 'carbon:query',
        autonomy: 'human_only',
        objects: [],
        process_state: {},
      },
    });
    // policy_owner/process_owner/manage — admin should be allowed
    expect([200, 403]).toContain(dry.status());
    console.log(`  ✅ J4 evidence gate + PDP dry-run (${dry.status()})`);
  });

  test('17C. J7 — budget override PATCH', async ({ request }) => {
    const res = await request.patch(`${CONTROL}/budget/`, {
      headers: hdr(),
      data: { daily_budget_usd: 42.5 },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.daily_budget_usd).toBe(42.5);
    console.log('  ✅ J7 budget override');
  });

  test('17D. UI — Command Center + Platform Roles', async ({ page }) => {
    const ok = await login(page, ADMIN);
    expect(ok, 'Login succeeded').toBe(true);

    await navigateTo(page, '/admin/ai');
    await assertVisible(page, 'Command Center', 8000);

    await navigateTo(page, '/admin/ai/platform?tab=roles');
    await assertVisible(page, 'Roles', 8000);
    console.log('  ✅ Command Center + Platform Roles UI');
  });
});
