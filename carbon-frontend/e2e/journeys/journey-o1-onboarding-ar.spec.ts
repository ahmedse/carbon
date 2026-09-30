/**
 * O1 usable rank 5. Arabic onboarding, then English restore.
 * Does not start the stack. CI=1 so Playwright reuses the servers already up.
 *
 *   CI=1 npx playwright test e2e/journeys/journey-o1-onboarding-ar.spec.ts --config e2e/playwright.config.ts
 */
import { test, expect, type Page } from '@playwright/test';
import { login, type UserPersona } from '../fixtures/users';

const API = `${(process.env.CARBON_API_URL || 'http://127.0.0.1:8009').replace(/\/$/, '')}/carbon-api`;

const ADMIN: UserPersona = {
  username: process.env.CARBON_ADMIN_USER || 'ahmed',
  password: process.env.CARBON_ADMIN_PASSWORD || 'AdminPa_132',
  role: 'superuser',
  isGlobalAdmin: true,
  expectations: {
    canAccessAdmin: true,
    canSeeDashboard: true,
    canEnterData: true,
    canSeeDQ: true,
    canSeeGovernance: true,
    visibleBranches: [],
  },
};

async function setLanguage(page: Page, token: string, language: 'ar' | 'en') {
  const res = await page.request.patch(`${API}/accounts/me/preferences/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { language },
  });
  expect(res.ok(), `PATCH language ${language}`).toBeTruthy();
  await page.evaluate((lang) => localStorage.setItem('carbon.lang', lang), language);
}

test('Onboarding: Arabic heading and refresh name, then English restore', async ({ page }) => {
  let token = '';
  try {
    const signedIn = await login(page, ADMIN);
    expect(signedIn, 'ahmed reaches the app').toBe(true);
    token = await page.evaluate(() => localStorage.getItem('access') || '');
    expect(token, 'access token').not.toBe('');

    await setLanguage(page, token, 'ar');
    await page.goto('/carbon/onboarding');
    await expect.poll(async () => page.locator('html').getAttribute('dir')).toBe('rtl');
    await expect.poll(async () => page.locator('html').getAttribute('lang')).toBe('ar');
    await expect(page.getByRole('heading', { level: 1, name: 'تهيئة المخزون' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'تحديث' })).toBeVisible();
    await expect.poll(async () => page.title()).toContain('تهيئة المخزون');

    await setLanguage(page, token, 'en');
    await page.goto('/carbon/onboarding');
    await expect.poll(async () => page.locator('html').getAttribute('dir')).toBe('ltr');
    await expect(page.getByRole('heading', { level: 1, name: 'Inventory onboarding' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Refresh' })).toBeVisible();
  } finally {
    if (token) {
      await page.request.patch(`${API}/accounts/me/preferences/`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { language: 'en' },
      });
    }
  }
});
