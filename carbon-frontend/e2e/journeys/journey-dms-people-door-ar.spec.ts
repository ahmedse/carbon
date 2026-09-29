/**
 * DMS usable rank 5 — Arabic People door, then English restore.
 * No row click and no eye click. Server language wins over browser locale.
 *
 * Run from carbon-frontend (does not start the stack):
 *   CI=1 npx playwright test e2e/journeys/journey-dms-people-door-ar.spec.ts --config e2e/playwright.config.ts
 */
import { test, expect, type Page } from '@playwright/test';
import { login } from '../fixtures/users';

const API = `${(process.env.CARBON_API_URL || 'http://127.0.0.1:8009').replace(/\/$/, '')}/carbon-api`;

const PREPARER = {
  username: process.env.NIBRAS_HR_USER || 'emp_2378',
  password: process.env.NIBRAS_HR_PASSWORD || process.env.EMPLOYEE_DEFAULT_PASSWORD || 'mozafNibrasPa_132',
  role: 'people_lead',
  isGlobalAdmin: false,
  expectations: {
    canAccessAdmin: false,
    canSeeDashboard: true,
    canEnterData: false,
    canSeeDQ: false,
    canSeeGovernance: false,
    visibleBranches: [],
  },
};

async function setLanguage(page: Page, token: string, language: 'ar' | 'en') {
  const res = await page.request.patch(`${API}/accounts/me/preferences/`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { language },
  });
  expect(res.ok(), `PATCH language ${language}`).toBeTruthy();
}

test('People import: Arabic names, then English restore', async ({ page }) => {
  let token = '';
  try {
    const signedIn = await login(page, PREPARER);
    expect(signedIn, 'emp_2378 reaches the app').toBe(true);
    token = await page.evaluate(() => localStorage.getItem('access') || '');
    expect(token, 'access token').not.toBe('');

    await setLanguage(page, token, 'ar');
    await page.goto('/people/import');
    await expect.poll(async () => page.locator('html').getAttribute('dir'), {
      timeout: 15_000,
    }).toBe('rtl');
    await expect(page.getByPlaceholder('بحث الدفعات')).toBeVisible();
    await expect(page.getByRole('button', { name: 'استيراد جديد' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'فتح الدفعة' }).first()).toBeVisible();

    await setLanguage(page, token, 'en');
    await page.goto('/people/import');
    await expect.poll(async () => page.locator('html').getAttribute('dir'), {
      timeout: 15_000,
    }).toBe('ltr');
    await expect(page.getByPlaceholder('Search batches')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open batch' }).first()).toBeVisible();
  } finally {
    if (token) {
      await page.request.patch(`${API}/accounts/me/preferences/`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { language: 'en' },
      });
    }
  }
});
