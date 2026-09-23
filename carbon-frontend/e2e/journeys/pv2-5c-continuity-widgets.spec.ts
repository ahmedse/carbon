/**
 * PV2-5C smoke — Chat continuity chip + Agent inherited-context panel.
 *
 * Presentation-layer only: plans API is mocked (no LLM). Asserts RULE_23
 * outcome copy and that Chat chrome does not grow a host-API Confirm.
 * Nibras credentials: ahmed / AdminPa_132 (universal superuser).
 */
import { test, expect, Page } from '@playwright/test';
import { login, type UserPersona } from '../fixtures/users';
import { PlansApiMock, makePlan, step } from '../helpers/plansApiMock';

const NIBRAS_ADMIN: UserPersona = {
  username: 'ahmed',
  password: 'AdminPa_132',
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

const UI_PATH = '/admin/ai/workspace';

const LOAN_PLAN = makePlan({
  id: 'plan-5c-loan',
  status: 'pending_approval',
  brief: 'Emergency loan 3000 SAR',
  inherited_context: [
    { key: 'loan_type', value: 'emergency' },
    { key: 'amount', value: '3000' },
  ],
  steps: [step({ step_id: 0, intent: 'Submit loan request' })],
});

async function openPulseWorkspace(page: Page) {
  await page.goto(UI_PATH);
  const agent = page.getByLabel('Agent mode');
  if (await agent.isVisible({ timeout: 8000 }).catch(() => false)) {
    return;
  }
  const show = page.getByRole('button', { name: 'Show Pulse' });
  if (await show.count()) {
    await show.click();
  }
  await expect(page.getByLabel('Agent mode')).toBeVisible({ timeout: 20000 });
}

test.describe.serial('PV2-5C continuity widgets', () => {
  let page: Page;
  const mock = new PlansApiMock([LOAN_PLAN]);

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(180_000);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await ctx.newPage();
    expect(await login(page, NIBRAS_ADMIN)).toBe(true);
    await mock.install(page);
  });

  test.afterAll(async () => {
    await page?.context()?.close();
  });

  test('Agent Run shows carried conversation details without engine jargon', async () => {
    mock.reset([LOAN_PLAN]);
    await openPulseWorkspace(page);
    await page.getByLabel('Agent mode').click();
    await expect(page.getByText('Emergency loan 3000 SAR', { exact: false }).first()).toBeVisible({ timeout: 15000 });
    const runTab = page.getByTestId('agent-cockpit').getByLabel('Run', { exact: true });
    if (await runTab.isVisible().catch(() => false)) {
      await runTab.click();
    }
    const panel = page.getByTestId('agent-run-inherited-context').first();
    await expect(panel).toBeVisible({ timeout: 15000 });
    await expect(panel).toContainText(/Carried from this conversation|منقول من هذه المحادثة/i);
    await expect(panel).toContainText(/3000/);
    await expect(panel).not.toContainText(/ConversationState|active_plans|Pulse|slots/i);
  });

  test('Chat chrome has no host-API Confirm', async () => {
    await page.getByLabel('Chat mode').click();
    await expect(page.getByLabel('Chat mode')).toBeVisible();
    await expect(page.getByRole('button', { name: /Confirm & create|Confirm & run/i })).toHaveCount(0);
  });
});
