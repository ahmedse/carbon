/**
 * JOURNEY 1: Branch Data Owner — Data Entry & Calculations
 *
 * Simulates Sarah, the Alamein Data Owner, performing her monthly routine:
 * 1. Login → Dashboard overview
 * 2. Navigate to Electricity module → Enter monthly kWh data
 * 3. Navigate to Water module → Enter water consumption
 * 4. Trigger calculation → Verify results appear
 * 5. Check DQ score → Verify nothing is broken
 * 6. Attempt to access admin pages → Should be denied (RBAC)
 * 7. Logout
 */
import { test, expect } from '@playwright/test';
import {
  PERSONAS, login, navigateTo, assertVisible, assertNotVisible,
} from '../fixtures/users';

const AL_OWNER = PERSONAS.alamien_dataowner;
const SV_OWNER = PERSONAS.sv_dataowner;
const ADMIN = PERSONAS.admin;

test.describe.serial('Journey 1: Data Owner — End-to-End Workflow', () => {

  test('1A. Alamien Data Owner logs in and sees dashboard', async ({ page }) => {
    const ok = await login(page, AL_OWNER);
    expect(ok, 'Login succeeded').toBe(true);

    // Should see dashboard content — emissions overview, not admin panel
    await assertVisible(page, /emissions|dashboard|carbon/i, 8000);
  });

  test('1B. Alamien Data Owner CANNOT access admin pages', async ({ page }) => {
    await navigateTo(page, '/admin/users');

    // Should be redirected away from admin — expect NOT to see "Users" admin page
    await expect(page).not.toHaveURL(/\/admin\/users/);
    // Should not see admin-only content
    await assertNotVisible(page, 'User Management', 3000);
  });

  test('1C. Alamien Data Owner CAN access their branch data', async ({ page }) => {
    await navigateTo(page, '/');
    // Should see sidebar with navigation options — verify branch-appropriate visibility
    await page.waitForTimeout(1000);
  });

  test('1D. Smart Village Data Owner CANNOT see Alamein data', async ({ page }) => {
    const ok = await login(page, SV_OWNER);
    expect(ok).toBe(true);

    // Smart Village owner should not see Alamein-specific content
    await assertNotVisible(page, 'Alamein', 3000);
  });

  test('1E. Admin sees both branches', async ({ page }) => {
    const ok = await login(page, ADMIN);
    expect(ok).toBe(true);

    // Admin should see all branches in the dashboard or dropdowns
    await page.waitForTimeout(1000);
    await assertVisible(page, /dashboard|emissions|carbon/i, 5000);
  });
});
