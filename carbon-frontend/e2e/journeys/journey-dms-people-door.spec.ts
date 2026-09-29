/**
 * DMS usable rank 4 — People door on the running stack.
 * Row click highlights. The eye opens the batch. A committed batch stays committed.
 *
 * Run from carbon-frontend (does not start the stack):
 *   CI=1 npx playwright test e2e/journeys/journey-dms-people-door.spec.ts --config e2e/playwright.config.ts
 */
import { test, expect } from '@playwright/test';
import { login } from '../fixtures/users';

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

test('People import: eye opens the committed leave-history batch', async ({ page }) => {
  const signedIn = await login(page, PREPARER);
  expect(signedIn, 'emp_2378 reaches the app').toBe(true);

  await page.goto('/people/import');
  await expect(page.getByPlaceholder('Search batches')).toBeVisible();
  await page.getByPlaceholder('Search batches').fill('Leave history');

  const row = page.getByRole('row', { name: /Leave history/ });
  await expect(row).toBeVisible();
  await row.getByText('Leave history', { exact: true }).click();
  await expect(page).toHaveURL(/\/people\/import\/?$/);

  await row.getByRole('button', { name: 'Open batch' }).click();
  await expect(page).toHaveURL(/\/people\/import\/6$/);
  await expect(page.getByText('Leave history').first()).toBeVisible();
  await expect(page.getByText('Committed').first()).toBeVisible();
});
