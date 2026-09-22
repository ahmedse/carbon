/**
 * NSR-9 — Nibras staff go-live: employee leave request → manager approve.
 *
 * Journey:
 *   1. Employee logs in → My Leave → Request Leave → submit
 *   2. Manager logs in → Team Approvals Inbox → open item → Approve
 *   3. Employee sees approved status (optional balance check)
 *
 * Credentials (override via env for seeded GOFSCO users):
 *   NIBRAS_EMPLOYEE_USER / NIBRAS_EMPLOYEE_PASSWORD
 *   NIBRAS_MANAGER_USER / NIBRAS_MANAGER_PASSWORD
 *
 * Defaults match docs/QA-MANUAL-PEOPLE-MY-TEAM.md when emp_* users exist
 * after link_employee_users (see GOFSCO-ONBOARDING-RUNBOOK.md).
 *
 * Run from carbon-frontend:
 *   npx playwright test e2e/journeys/nibras-leave-approve.spec.ts
 */
import { test, expect, Page } from '@playwright/test';
import { login, navigateTo } from '../fixtures/users';

const EMPLOYEE = {
  username: process.env.NIBRAS_EMPLOYEE_USER || 'emp_1067',
  password: process.env.NIBRAS_EMPLOYEE_PASSWORD || process.env.EMPLOYEE_DEFAULT_PASSWORD || 'mozafNibrasPa_132',
  role: 'employee',
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

const MANAGER = {
  username: process.env.NIBRAS_MANAGER_USER || 'emp_1712',
  password: process.env.NIBRAS_MANAGER_PASSWORD || process.env.EMPLOYEE_DEFAULT_PASSWORD || 'mozafNibrasPa_132',
  role: 'manager',
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

/** ISO date N weekdays ahead (Mon–Fri) for leave start. */
function weekdayOffset(daysAhead: number): string {
  const d = new Date();
  let added = 0;
  while (added < daysAhead) {
    d.setDate(d.getDate() + 1);
    const day = d.getDay();
    if (day !== 0 && day !== 6) added += 1;
  }
  return d.toISOString().slice(0, 10);
}

async function loginRobust(page: Page, persona: typeof EMPLOYEE) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    const ok = await login(page, persona as Parameters<typeof login>[1]);
    if (ok) return true;
    console.log(`  ⏳ login attempt ${attempt} failed for ${persona.username} — retrying...`);
    await page.waitForTimeout(2000);
  }
  return false;
}

async function logoutIfNeeded(page: Page) {
  // Clear session storage so the next persona gets a clean JWT.
  await page.goto('/login');
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.waitForTimeout(400);
}

test.describe.serial('NSR-9: Nibras leave request → manager approve', () => {
  let leaveReferenceHint: string | null = null;

  test('N9A. Employee requests leave from My Leave', async ({ page }) => {
    const ok = await loginRobust(page, EMPLOYEE);
    expect(ok, `Employee login (${EMPLOYEE.username})`).toBe(true);

    await navigateTo(page, '/my/leave');
    await expect(page.getByRole('button', { name: /Request Leave/i })).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: /Request Leave/i }).click();

    // Leave type select (MUI TextField select)
    const typeField = page.getByLabel(/Leave type|Type/i).first();
    await typeField.waitFor({ state: 'visible', timeout: 10000 });
    await typeField.click();
    // Prefer Annual; fall back to first option.
    const annual = page.getByRole('option', { name: /Annual/i });
    if (await annual.isVisible({ timeout: 3000 }).catch(() => false)) {
      await annual.click();
    } else {
      await page.getByRole('option').first().click();
    }

    const start = weekdayOffset(5);
    const end = weekdayOffset(6);
    await page.getByLabel(/Start/i).first().fill(start);
    await page.getByLabel(/End/i).first().fill(end);

    const submit = page.getByRole('button', { name: /Submit|Request/i }).last();
    await submit.click();

    // Success: dialog closes and history shows a new row, or snackbar success.
    await expect(
      page.getByText(/submitted|success|pending|draft/i).first(),
    ).toBeVisible({ timeout: 20000 });

    // Capture a reference-looking token if present for manager lookup.
    const refCandidate = page.locator('text=/LR-|LEAVE-|CORR-/i').first();
    if (await refCandidate.isVisible({ timeout: 3000 }).catch(() => false)) {
      leaveReferenceHint = (await refCandidate.textContent())?.trim() || null;
    }
    console.log(`  ✅ Employee submitted leave${leaveReferenceHint ? ` (${leaveReferenceHint})` : ''}`);
  });

  test('N9B. Manager approves from Team inbox', async ({ page }) => {
    await logoutIfNeeded(page);
    const ok = await loginRobust(page, MANAGER);
    expect(ok, `Manager login (${MANAGER.username})`).toBe(true);

    await navigateTo(page, '/team');
    await expect(page.getByText(/Approvals Inbox/i).first()).toBeVisible({ timeout: 15000 });

    // Open first actionable DataGrid row (or matching reference).
    const row = leaveReferenceHint
      ? page.getByText(leaveReferenceHint, { exact: false }).first()
      : page.locator('.MuiDataGrid-row').first();

    await expect(row).toBeVisible({ timeout: 20000 });
    await row.click();

    await expect(page.getByRole('button', { name: /^Approve$/i })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /^Approve$/i }).click();

    await expect(page.getByText(/approved|success/i).first()).toBeVisible({ timeout: 20000 });
    console.log('  ✅ Manager approved leave request');
  });

  test('N9C. Employee sees approved status', async ({ page }) => {
    await logoutIfNeeded(page);
    const ok = await loginRobust(page, EMPLOYEE);
    expect(ok, `Employee re-login (${EMPLOYEE.username})`).toBe(true);

    await navigateTo(page, '/my/leave');
    await expect(page.getByRole('button', { name: /Request Leave/i })).toBeVisible({ timeout: 15000 });

    // Approved chip/label somewhere on the leave history.
    await expect(page.getByText(/Approved/i).first()).toBeVisible({ timeout: 20000 });
    console.log('  ✅ Employee sees Approved status');
  });
});
