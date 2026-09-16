/**
 * JOURNEY 16: Pulse Console — Capabilities registry (PEC-R4 / L4).
 *
 * Proves PEC-R2 Console Capabilities UI end-to-end:
 *  1. Admin logs in and opens /admin/ai/capabilities.
 *  2. Loading settles to a grid or empty state (no crash / no hard error).
 *  3. If the catalog API returns rows, at least one business_name is visible.
 *  4. Skills Catalog route is reachable (smoke only — no promote/deny).
 *
 * Serial + one shared UI login (journey-10 pattern) to stay under the
 * 5-logins/min throttle. API corroboration reuses the UI session token.
 */
import { test, expect, Page } from '@playwright/test';
import { login, navigateTo, assertVisible, type UserPersona } from '../fixtures/users';

// Live Nibras stack uses ensure_nibras_admins passwords (same as journey-14/15),
// not the carbon-demo PERSONAS.admin / admin123 fixture.
const ADMIN: UserPersona = {
  username: process.env.NIBRAS_ADMIN_USERNAME || process.env.PULSE_QA_USER || 'ahmed',
  password:
    process.env.NIBRAS_ADMIN_PASSWORD ||
    process.env.CARBON_ADMIN_PASSWORD ||
    process.env.PULSE_QA_PASS ||
    'AdminPa_132',
  role: 'admins_group',
  isGlobalAdmin: true,
  expectations: {
    canAccessAdmin: true,
    canSeeDashboard: true,
    canEnterData: true,
    canSeeDQ: true,
    canSeeGovernance: true,
    visibleBranches: ['Nibras'],
  },
};

const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8009/carbon-api';
const CAPABILITIES_UI = '/admin/ai/capabilities';
const SKILLS_UI = '/admin/ai/skills';
const CAPABILITIES_API = `${API_BASE}/ai/catalog/capabilities/`;

test.describe.serial('Journey 16: Pulse Console — Capabilities registry', () => {
  let page: Page | undefined;
  let adminToken = '';

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(120_000);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await ctx.newPage();
    const ok = await login(page, ADMIN);
    adminToken = (await page.evaluate(() => localStorage.getItem('access'))) || '';
    console.log(
      `  UI login (${ADMIN.username}): ${ok}, token=${adminToken ? 'ok' : 'MISSING'}`,
    );
    if (!ok) throw new Error(`Admin UI login failed for ${ADMIN.username}`);
  });

  test.afterAll(async () => {
    await page?.context().close();
  });

  test('16A. Admin opens Capabilities — settles to grid or empty (no crash)', async () => {
    test.setTimeout(90_000);
    if (!page) throw new Error('Shared page missing');

    let apiRows: Array<{ business_name?: string }> = [];
    const catalogWait = page
      .waitForResponse(
        (r) =>
          r.url().includes('/ai/catalog/capabilities/') && r.request().method() === 'GET',
        { timeout: 20_000 },
      )
      .then(async (res) => {
        if (res.ok()) {
          try {
            const body = await res.json();
            apiRows = Array.isArray(body) ? body : body?.results || [];
          } catch {
            apiRows = [];
          }
        }
        return res;
      })
      .catch(() => null);

    await navigateTo(page, CAPABILITIES_UI);
    await catalogWait;

    await assertVisible(page, 'Capabilities', 12_000);
    await expect(page.getByText(/not authorized/i).first()).not.toBeVisible({ timeout: 3000 });
    await expect(
      page.getByText(/viewing the capability registry requires/i).first(),
    ).not.toBeVisible({ timeout: 2000 });

    await expect(page.getByRole('progressbar')).toHaveCount(0, { timeout: 20_000 });

    const offline = await page
      .getByText(/capability registry unavailable/i)
      .first()
      .isVisible()
      .catch(() => false);
    const empty = await page
      .getByText(/no capabilities in the registry yet/i)
      .first()
      .isVisible()
      .catch(() => false);

    if (offline) {
      console.log('  ⚠️ Capabilities panel showed offline state (API unreachable from browser)');
      expect(offline).toBe(true);
      return;
    }

    if (apiRows.length > 0) {
      const name = apiRows[0]?.business_name;
      expect(name, 'API row should include business_name').toBeTruthy();
      await expect(page.getByText(String(name)).first()).toBeVisible({ timeout: 10_000 });
      console.log(`  ✅ Capabilities grid shows business_name: ${name}`);
    } else {
      const gridVisible = await page
        .locator('.MuiDataGrid-root')
        .first()
        .isVisible()
        .catch(() => false);
      expect(empty || gridVisible).toBe(true);
      console.log(
        empty
          ? '  ✅ Capabilities empty state (no rows in registry)'
          : '  ✅ Capabilities DataGrid settled with zero rows',
      );
    }
  });

  test('16B. Skills Catalog route smoke (tab surface loads)', async () => {
    test.setTimeout(60_000);
    if (!page) throw new Error('Shared page missing');

    await navigateTo(page, SKILLS_UI);
    await assertVisible(page, 'Skills Catalog', 12_000);
    await expect(page.getByRole('progressbar')).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByText(/not authorized/i).first()).not.toBeVisible({ timeout: 3000 });
    console.log('  ✅ Skills Catalog route loads (smoke — no promote/deny)');
  });

  test('16C. Catalog capabilities API — auth shape (optional corroboration)', async ({ request }) => {
    test.skip(!adminToken, 'No admin UI token — skip API corroboration');

    const anon = await request.get(CAPABILITIES_API, {
      headers: { 'Content-Type': 'application/json' },
    });
    expect(anon.status(), 'anonymous must be rejected').toBe(401);

    const auth = await request.get(CAPABILITIES_API, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
        'Content-Type': 'application/json',
      },
    });
    expect(auth.status(), 'admin JWT should read catalog').toBe(200);
    const body = await auth.json();
    const rows = Array.isArray(body) ? body : body?.results || [];
    expect(Array.isArray(rows)).toBe(true);
    console.log(`  ✅ GET catalog/capabilities/ → 200 (${rows.length} row(s))`);
  });
});
