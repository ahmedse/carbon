/**
 * JOURNEY 13: Dual-language (EN / AR) — I18N-6 E2E gate
 *
 * Validates the full i18n contract end-to-end:
 *  1. English login → dashboard (dir=ltr, lang=en)
 *  2. One app workflow in EN (Catalog Studio)
 *  3. Language switch mid-session (EN → العربية) → dir=rtl + Arabic chrome
 *  4. Persistence across reload (localStorage `carbon.lang`)
 *  5. Logout → login page renders in Arabic → re-login keeps Arabic
 *  6. Switch back to English → dir=ltr restored
 *
 * Each test runs in a fresh browser context (Playwright default), so every
 * test seeds its own language state and logs in explicitly.
 */
import { test, expect } from '@playwright/test';
import { PERSONAS, login, navigateTo, assertVisible } from '../fixtures/users';

// Fixture persona password is stale vs. the live dev DB — use the real one.
const ADMIN = { ...PERSONAS.admin, password: 'dev-admin-5c' };

// ── Bilingual helpers ────────────────────────────────────────────────────

/** Assert <html dir> and lang. */
async function expectHtmlDir(page: import('@playwright/test').Page, dir: string, lang: string) {
  await expect.poll(() => page.evaluate(() => document.documentElement.dir)).toBe(dir);
  await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe(lang);
}

/** Seed the language BEFORE the app boots (localStorage init script). */
async function seedLang(page: import('@playwright/test').Page, code: string) {
  await page.addInitScript((l) => localStorage.setItem('carbon.lang', l), code);
}

/** Click the header language switcher and choose a locale (native labels).
 * NOTE: the switcher aria-label is the CURRENT locale's `language` key —
 * from English it reads "Language", from Arabic "اللغة".
 */
async function switchLanguage(page: import('@playwright/test').Page, code: 'en' | 'ar') {
  const current = await page.evaluate(() => document.documentElement.lang);
  const switcherLabel = current === 'ar' ? 'اللغة' : 'Language';
  await page.getByRole('button', { name: switcherLabel }).first().click();
  const option = code === 'ar' ? 'العربية' : 'English';
  await page.getByRole('menuitem', { name: option }).click();
  await page.waitForTimeout(600); // i18next changeLanguage + RTL re-render
}

/** Login with locale-aware labels (labels come from `auth` namespace). */
async function loginBilingual(page: import('@playwright/test').Page, locale: 'en' | 'ar') {
  const uLabel = locale === 'ar' ? 'اسم المستخدم' : 'Username';
  const pLabel = locale === 'ar' ? 'كلمة المرور' : 'Password';
  const submitLabel = locale === 'ar' ? 'تسجيل الدخول' : 'Sign in';
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.getByLabel(uLabel).waitFor({ state: 'visible', timeout: 10000 });
  await page.getByLabel(uLabel).fill(ADMIN.username);
  await page.getByLabel(pLabel).fill(ADMIN.password);
  await page.getByRole('button', { name: submitLabel }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1500);
  return !page.url().includes('/login');
}

/** Retry-aware login: transient network hiccups are handled by 1 retry. */
async function loginRobust(page: import('@playwright/test').Page, locale: 'en' | 'ar') {
  for (let attempt = 1; attempt <= 2; attempt++) {
    const ok = locale === 'ar' ? await loginBilingual(page, 'ar') : await login(page, ADMIN);
    if (ok) return true;
    console.log(`  ⏳ login attempt ${attempt} failed — retrying...`);
    await page.waitForTimeout(2000);
  }
  return false;
}

test.describe.serial('Journey 13: Dual-Language (EN/AR) — I18N-6', () => {

  test('13A. English login → dashboard is LTR', async ({ page }) => {
    await seedLang(page, 'en');
    const ok = await loginRobust(page, 'en');
    expect(ok, 'EN login succeeded').toBe(true);

    await expectHtmlDir(page, 'ltr', 'en');
    // Dashboard chrome present in English (shell sidebar).
    await assertVisible(page, 'Dashboard', 8000);
  });

  test('13B. One app workflow in English (Catalog Studio)', async ({ page }) => {
    await seedLang(page, 'en');
    const ok = await loginRobust(page, 'en');
    expect(ok, 'EN login succeeded').toBe(true);

    await navigateTo(page, '/catalog');
    await assertVisible(page, 'Catalog Studio', 8000);
    await assertVisible(page, 'Data Products', 8000);
    await expectHtmlDir(page, 'ltr', 'en');
  });

  test('13C. Language switch mid-session → RTL + Arabic chrome', async ({ page }) => {
    await seedLang(page, 'en');
    await login(page, ADMIN);

    // Land on Catalog Studio first (English), then flip mid-session.
    await navigateTo(page, '/catalog');
    await switchLanguage(page, 'ar');

    // Direction + language flipped on <html>.
    await expectHtmlDir(page, 'rtl', 'ar');
    // Persisted for reload (I18N-5 backend pref sync).
    await expect.poll(() => page.evaluate(() => localStorage.getItem('carbon.lang'))).toBe('ar');

    // Same Catalog Studio page now renders Arabic — key resolved, no fallback leak.
    await assertVisible(page, 'استوديو الكتالوج', 8000);
    await assertVisible(page, 'منتجات البيانات', 8000);
  });

  test('13D. Persistence across reload (starts in Arabic)', async ({ page }) => {
    await seedLang(page, 'ar');
    const ok = await loginRobust(page, 'ar');
    expect(ok, 'AR login succeeded').toBe(true);
    await expectHtmlDir(page, 'rtl', 'ar');

    // Navigate to Catalog Studio, then hard-reload.
    await navigateTo(page, '/catalog');
    await assertVisible(page, 'استوديو الكتالوج', 8000);

    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    await expectHtmlDir(page, 'rtl', 'ar');
    // Catalog Studio still Arabic after a hard reload.
    await assertVisible(page, 'استوديو الكتالوج', 8000);
  });

  test('13E. Logout → Arabic login page → re-login keeps Arabic', async ({ page }) => {
    await seedLang(page, 'ar');
    await loginBilingual(page, 'ar');
    await expectHtmlDir(page, 'rtl', 'ar');

    // Logout via the user menu ("تسجيل الخروج" — translated key).
    await page.getByText(ADMIN.username.slice(0, 2).toUpperCase()).first().click(); // avatar initials
    await page.getByText('تسجيل الخروج').click();
    await page.waitForURL((url) => url.pathname.includes('/login'), { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(800);

    // Login page itself renders in Arabic (auth namespace).
    await assertVisible(page, 'تسجيل الدخول', 8000);
    await expectHtmlDir(page, 'rtl', 'ar');

    // Re-login with Arabic labels.
    const ok = await loginRobust(page, 'ar');
    expect(ok, 'AR re-login succeeded').toBe(true);
    await expectHtmlDir(page, 'rtl', 'ar');
  });

  test('13F. Switch back to English restores LTR', async ({ page }) => {
    await seedLang(page, 'ar');
    await loginBilingual(page, 'ar');
    await expectHtmlDir(page, 'rtl', 'ar');

    await switchLanguage(page, 'en');
    await expectHtmlDir(page, 'ltr', 'en');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('carbon.lang'))).toBe('en');
    await assertVisible(page, 'Dashboard', 8000);
  });
});
