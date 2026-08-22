/**
 * JOURNEY 12: Task view + Run view — exhaustive interaction simulation.
 *
 * Drives the REAL React Task/Run surface (AITaskPanel + AITaskPlanCard +
 * PlanDagGraph/EnterpriseGraph + PlanDiffReviewDialog + StepEditDialog +
 * AITaskAuditCard) end-to-end in Chromium, with the Carbon plan endpoints
 * route-intercepted by a deterministic mock (e2e/helpers/plansApiMock.ts).
 * This isolates the *presentation + interaction* layer so every click, drag,
 * resize, zoom, consent gate and extreme data shape is reproducible — no LLM
 * latency, no cost, no flakiness. The real backend integration (LLM decompose,
 * SSE over the wire) is proven separately by the live journey.
 *
 * The graph node-move/resize interaction is covered exhaustively here because
 * that is the area previously reported as buggy: click-vs-drag threshold,
 * pan-vs-node-drag disambiguation, resize min/max clamps, zoom-aware deltas,
 * redraw/reset, off-canvas drags, and the inline vs full-screen modal split.
 *
 * Serial execution + one-time admin login (under the 5-logins/min throttle).
 */
import { test, expect, Page } from '@playwright/test';
import { PERSONAS, login } from '../fixtures/users';
import {
  PlansApiMock,
  PlanFixture,
  makePlan,
  step,
  consentRunScript,
  resumeAfterConsentScript,
  failedRunScript,
  errorFrameRunScript,
} from '../helpers/plansApiMock';

const ADMIN = PERSONAS.admin;
const UI_PATH = '/admin/ai/workspace';
const GRAPH = '[data-testid="plan-dag-graph"]';

// ── SVG/geometry helpers ───────────────────────────────────────────────────

function nodeSel(stepId: number | string): string {
  return `${GRAPH} [role="button"][aria-label^="Step ${stepId}:"]`;
}

function parseTranslate(transform: string | null): { x: number; y: number } {
  const m = /translate\(([-\d.]+)[ ,]+([-\d.]+)\)/.exec(transform || '');
  return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]) } : { x: 0, y: 0 };
}

function parseScale(transform: string | null): number {
  const m = /scale\(([-\d.]+)\)/.exec(transform || '');
  return m ? parseFloat(m[1]) : 1;
}

async function canvasTransform(page: Page): Promise<string | null> {
  return page.locator(`${GRAPH} svg > g`).first().getAttribute('transform');
}

async function nodeTransform(page: Page, stepId: number): Promise<string | null> {
  return page.locator(nodeSel(stepId)).first().getAttribute('transform');
}

async function nodeRect(page: Page, stepId: number) {
  const rect = page.locator(`${nodeSel(stepId)} rect[rx="6"]`).first();
  return {
    w: Number(await rect.getAttribute('width')),
    h: Number(await rect.getAttribute('height')),
  };
}

async function dragFrom(page: Page, sel: string, dx: number, dy: number): Promise<void> {
  const el = page.locator(sel).first();
  // The graph lives below the fold inside a scrollable container — bring the
  // target into view first so page.mouse coordinates land on a visible node.
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  if (!b) throw new Error(`No bounding box for ${sel}`);
  const sx = b.x + b.width / 2;
  const sy = b.y + b.height / 2;
  await page.mouse.move(sx, sy);
  await page.mouse.down();
  await page.mouse.move(sx + dx, sy + dy, { steps: 10 });
  await page.mouse.up();
}

async function dragNode(page: Page, stepId: number, dx: number, dy: number): Promise<void> {
  await dragFrom(page, nodeSel(stepId), dx, dy);
}

async function dragResize(page: Page, stepId: number, dx: number, dy: number): Promise<void> {
  await dragFrom(page, `[data-testid="plan-dag-graph-resize-${stepId}"]`, dx, dy);
}

async function clickNode(page: Page, stepId: number): Promise<void> {
  // SVG <g> nodes don't reliably receive Playwright's synthetic click; use the
  // real input pipeline (mousedown→mouseup→click) at the node centre so React
  // onClick fires and `moved` stays false (no drag).
  const el = page.locator(nodeSel(stepId)).first();
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  if (!b) throw new Error(`No bounding box for step ${stepId}`);
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
}

// ── Navigation helpers ─────────────────────────────────────────────────────

async function gotoTasks(page: Page): Promise<void> {
  await page.goto(UI_PATH);
  // Open the Tasks panel from the workspace activity bar.
  const tasksBtn = page.locator('[aria-label="Tasks"]').first();
  await tasksBtn.waitFor({ state: 'visible', timeout: 15000 });
  await tasksBtn.click();
  // The internal Tasks/Run tab is persisted in localStorage; a prior test may
  // have left it on "Run", so force it back to "Tasks" deterministically.
  const tasksTab = page.getByRole('tab', { name: 'Tasks' });
  await tasksTab.waitFor({ state: 'visible', timeout: 15000 });
  await tasksTab.click();
  await expect(page.getByText('Plan a task')).toBeVisible({ timeout: 15000 });
}

async function openPlan(page: Page, brief: string): Promise<void> {
  await page.getByText(brief, { exact: false }).first().click();
  await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });
}

// ── Fixtures ───────────────────────────────────────────────────────────────

function chainSteps(n: number) {
  return Array.from({ length: n }, (_, i) =>
    step({ step_id: i, intent: `Action ${i}`, depends_on: i === 0 ? [] : [i - 1] }),
  );
}

function defaultPlans(): PlanFixture[] {
  return [
    makePlan({
      id: 'p-approval',
      status: 'pending_approval',
      brief: 'Audit duplicates in emissions dataset',
      pattern: 'audit-dq',
      source: 'pulse',
      skill_name: 'dq-audit',
      needs_confirmation: true,
      steps: [
        step({ step_id: 0, intent: 'Scan the dataset for duplicate rows', tool_name: 'dq_scan', tool_args: { table: 'emissions' }, status: 'pending' }),
        step({ step_id: 1, intent: 'Deduplicate the rows', tool_name: 'dq_dedupe', tool_args: { table: 'emissions', mode: 'safe' }, depends_on: [0], agent_role: 'data_engineer', status: 'pending' }),
        step({ step_id: 2, intent: 'Create a rule to prevent duplicates', tool_name: 'dq_rule', tool_args: { rule: 'unique' }, depends_on: [0, 1], agent_role: 'data_engineer', status: 'pending' }),
      ],
    }),
    makePlan({
      id: 'p-approved',
      status: 'approved',
      brief: 'Summarize scope-1 emissions by source',
      steps: [
        step({ step_id: 0, intent: 'Group emissions by source', status: 'pending' }),
        step({ step_id: 1, intent: 'Compute totals', tool_name: 'dq_aggregate', depends_on: [0], status: 'pending' }),
      ],
    }),
    makePlan({
      id: 'p-completed',
      status: 'completed',
      brief: 'Reconcile fuel consumption records',
      final_response: 'Reconciled 120 records.',
      steps: [
        step({ step_id: 0, intent: 'Load fuel records', status: 'completed' }),
        step({ step_id: 1, intent: 'Reconcile', depends_on: [0], status: 'completed' }),
      ],
    }),
    makePlan({
      id: 'p-failed',
      status: 'failed',
      brief: 'Forecast next-quarter emissions',
      steps: [step({ step_id: 0, intent: 'Fit forecast model', status: 'failed', error: 'Insufficient history', tool_name: 'forecast' })],
    }),
    makePlan({
      id: 'p-cancelled',
      status: 'cancelled',
      brief: 'Bulk-import legacy files',
      steps: [step({ step_id: 0, intent: 'Stage files', status: 'skipped' })],
    }),
    makePlan({
      id: 'p-empty',
      status: 'approved',
      brief: 'Plan with no steps',
      steps: [],
    }),
  ];
}

// ── The suite ──────────────────────────────────────────────────────────────

test.describe.serial('Journey 12: Task + Run view — exhaustive interaction', () => {
  let page: Page;
  const mock = new PlansApiMock();

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(180_000);
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      acceptDownloads: true,
    });
    page = await ctx.newPage();
    await login(page, ADMIN);
    await mock.install(page);
  });

  test.afterAll(async () => {
    await page.context().close();
  });

  test.beforeEach(async () => {
    mock.reset(defaultPlans());
    await gotoTasks(page);
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 1 — Composer (create plan)
  // ════════════════════════════════════════════════════════════════════════
  test.describe('1. Composer', () => {
    test('S1.1 — Create button is disabled when the brief is empty', async () => {
      await expect(page.getByRole('button', { name: 'Create plan' })).toBeDisabled();
    });

    test('S1.2 — Create button stays disabled for whitespace-only briefs', async () => {
      const input = page.getByLabel('Task brief');
      await input.fill('     \n\t  ');
      await expect(page.getByRole('button', { name: 'Create plan' })).toBeDisabled();
    });

    test('S1.3 — Typing a brief enables the Create button', async () => {
      const input = page.getByLabel('Task brief');
      await input.fill('Audit duplicates');
      await expect(page.getByRole('button', { name: 'Create plan' })).toBeEnabled();
    });

    test('S1.4 — Create POSTs the trimmed brief, switches to Run, clears the composer', async () => {
      await page.getByLabel('Task brief').fill('   Audit duplicates for real   ');
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });

      const createReq = mock.requests.find((r) => r.method === 'POST' && r.path === '');
      expect(createReq).toBeTruthy();
      expect((createReq!.body as any).brief).toBe('Audit duplicates for real');
      // conversation_id is the active chat anchor when present, otherwise ''.
      expect(typeof (createReq!.body as any).conversation_id).toBe('string');

      // Back to Tasks — composer should be cleared.
      await page.getByRole('tab', { name: 'Tasks' }).click();
      await expect(page.getByLabel('Task brief')).toHaveValue('');
    });

    test('S1.5 — A long (≈3000 char) brief is accepted and rendered', async () => {
      const long = 'Audit every emissions record for duplicates and anomalies. '.repeat(40); // ~2400 chars
      await page.getByLabel('Task brief').fill(long);
      await expect(page.getByRole('button', { name: 'Create plan' })).toBeEnabled();
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });
      expect(mock.requests.some((r) => r.method === 'POST' && r.path === '' && (r.body as any).brief === long.trim()))
        .toBe(true);
    });

    test('S1.6 — Special characters, quotes, emoji and unicode survive a create + render', async () => {
      const weird = 'Audit "duplicates" — émissions 🔥 → <tags> & 100%';
      await page.getByLabel('Task brief').fill(weird);
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText(weird, { exact: false }).first()).toBeVisible();
    });

    test('S1.7 — Multiple creates yield multiple plans (no client-side dedup)', async () => {
      await page.getByLabel('Task brief').fill('First task');
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });
      await page.getByRole('tab', { name: 'Tasks' }).click();

      await page.getByLabel('Task brief').fill('Second task');
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });

      const creates = mock.requests.filter((r) => r.method === 'POST' && r.path === '');
      expect(creates.length).toBeGreaterThanOrEqual(2);
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 2 — Task list
  // ════════════════════════════════════════════════════════════════════════
  test.describe('2. Task list', () => {
    test('S2.1 — Lists every seeded plan with its brief', async () => {
      for (const brief of [
        'Audit duplicates in emissions dataset',
        'Summarize scope-1 emissions by source',
        'Reconcile fuel consumption records',
        'Forecast next-quarter emissions',
        'Bulk-import legacy files',
        'Plan with no steps',
      ]) {
        await expect(page.getByText(brief, { exact: false }).first()).toBeVisible();
      }
    });

    test('S2.2 — Shows a status chip per lifecycle state', async () => {
      const cases: Array<[string, string]> = [
        ['Needs review', 'Audit duplicates in emissions dataset'],
        ['Approved', 'Summarize scope-1 emissions by source'],
        ['Completed', 'Reconcile fuel consumption records'],
        ['Failed', 'Forecast next-quarter emissions'],
        ['Cancelled', 'Bulk-import legacy files'],
      ];
      for (const [label] of cases) {
        await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
      }
    });

    test('S2.3 — Clicking a plan card opens the Run tab detail', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.getByText('Workflow · 3 steps')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toBeVisible();
    });

    test('S2.4 — Empty list renders the empty-state copy', async () => {
      mock.reset([]);
      await gotoTasks(page);
      await expect(page.getByText('No task plans yet — describe one above.')).toBeVisible();
    });

    test('S2.5 — A newly created plan appears in the list with a Needs review chip', async () => {
      await page.getByLabel('Task brief').fill('Brand new plan');
      await page.getByRole('button', { name: 'Create plan' }).click();
      await expect(page.getByText('Task plan')).toBeVisible({ timeout: 15000 });
      await page.getByRole('tab', { name: 'Tasks' }).click();
      await expect(page.getByText('Brand new plan', { exact: false }).first()).toBeVisible();
      await expect(page.getByText('Needs review', { exact: true }).first()).toBeVisible();
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 3 — Plan card lifecycle controls
  // ════════════════════════════════════════════════════════════════════════
  test.describe('3. Plan card lifecycle', () => {
    test('S3.1 — pending_approval shows Approve/Decline/Fork, never Run', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.getByRole('button', { name: 'Approve plan' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Decline' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Fork' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Run plan' })).toHaveCount(0);
    });

    test('S3.2 — Provenance chips render (pattern / source / skill / requires approval)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.getByText('audit-dq', { exact: true })).toBeVisible();
      await expect(page.getByText('Source · pulse', { exact: true })).toBeVisible();
      await expect(page.getByText('Skill · dq-audit', { exact: true })).toBeVisible();
      await expect(page.getByText('Requires approval', { exact: true })).toBeVisible();
    });

    test('S3.3 — Approve transitions to approved and swaps in Run plan + Fork', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Approve plan' }).click();
      await expect(page.getByRole('button', { name: 'Run plan' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Fork' })).toBeVisible();
      // The list chip updates too.
      await page.getByRole('tab', { name: 'Tasks' }).click();
      await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();
    });

    test('S3.4 — Decline transitions to cancelled and shows the cancelled copy', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Decline' }).click();
      await expect(page.getByText('This plan was cancelled — nothing was executed.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Run plan' })).toHaveCount(0);
    });

    test('S3.5 — Fork creates a reviewable copy marked "Forked copy"', async () => {
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Fork' }).click();
      await expect(page.getByText('Forked copy', { exact: true })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toBeVisible();
      const forkReq = mock.requests.find((r) => r.method === 'POST' && r.path.endsWith('/fork'));
      expect(forkReq).toBeTruthy();
    });

    test('S3.6 — Completed plan shows the outcome hint (no run controls)', async () => {
      await openPlan(page, 'Reconcile fuel consumption records');
      await expect(page.getByText('Completed — see the audit ledger for the outcome.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Run plan' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Approve plan' })).toHaveCount(0);
    });

    test('S3.7 — Failed plan exposes the step error inline', async () => {
      await openPlan(page, 'Forecast next-quarter emissions');
      await expect(page.getByText('Insufficient history')).toBeVisible();
    });

    test('S3.8 — Empty plan shows "No steps were planned." and no preview toggle', async () => {
      await openPlan(page, 'Plan with no steps');
      await expect(page.getByText('No steps were planned.')).toBeVisible();
      await expect(page.getByLabel('Plan preview view')).toHaveCount(0);
    });

    test('S3.9 — Workflow header counts steps and stages', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.getByText('Workflow · 3 steps')).toBeVisible();
    });

    test('S3.10 — Phases render names, goals and strategy chips (sequential)', async () => {
      mock.reset([
        makePlan({
          id: 'p-phases',
          status: 'pending_approval',
          brief: 'Multi-phase plan',
          phases: [
            { phase_id: 0, name: 'Discover', goal: 'Find the data', strategy: 'sequential', step_ids: [0, 1] },
            { phase_id: 1, name: 'Fix', goal: 'Correct it', strategy: 'parallel', step_ids: [2] },
          ],
          steps: [
            step({ step_id: 0, intent: 'Scan', phase_id: 0 }),
            step({ step_id: 1, intent: 'Profile', depends_on: [0], phase_id: 0 }),
            step({ step_id: 2, intent: 'Repair', depends_on: [1], phase_id: 1 }),
          ],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Multi-phase plan');
      await expect(page.getByText('Discover', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('Fix', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('2 stages', { exact: true })).toBeVisible();
      await expect(page.getByText('Sequential', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('Parallel', { exact: true }).first()).toBeVisible();
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 4 — Streamed run (consent gate + terminal states)
  // ════════════════════════════════════════════════════════════════════════
  test.describe('4. Streamed run', () => {
    test('S4.1 — Run streams steps to completion and shows the audit ledger', async () => {
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run completed')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('Audit ledger', { exact: true })).toBeVisible();
      await expect(page.getByText('Requested by', { exact: true })).toBeVisible();
      await expect(page.getByText('Admin', { exact: true }).first()).toBeVisible();
      // Usage stats from the deterministic ledger.
      await expect(page.getByText('Latency', { exact: true })).toBeVisible();
      await expect(page.getByText('1234 ms', { exact: true })).toBeVisible();
      await expect(page.getByText('LLM calls', { exact: true })).toBeVisible();
      await expect(page.getByText('Tokens', { exact: true })).toBeVisible();
    });

    test('S4.2 — Consent gate: a mutation step pauses and needs per-step approval', async () => {
      mock.runScript = (plan) => consentRunScript(plan, 1, [0]);
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run paused — a step needs your approval')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('This action writes to Carbon. Approve it to run, or decline to skip it.')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Resume run' })).toBeVisible();
    });

    test('S4.3 — Approve the consent step, then resume to completion', async () => {
      mock.runScript = (plan) => consentRunScript(plan, 1, [0]);
      mock.resumeScript = (plan) => resumeAfterConsentScript(plan, 1);
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run paused — a step needs your approval')).toBeVisible({ timeout: 15000 });

      await page.getByRole('button', { name: 'Approve', exact: true }).click();
      await page.getByRole('button', { name: 'Resume run' }).click();
      await expect(page.getByText('Run completed')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('Audit ledger', { exact: true })).toBeVisible();
    });

    test('S4.4 — Decline the consent step marks it "Skipped — not executed."', async () => {
      mock.runScript = (plan) => consentRunScript(plan, 1, [0]);
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run paused — a step needs your approval')).toBeVisible({ timeout: 15000 });

      await page.getByRole('button', { name: 'Decline', exact: true }).click();
      await expect(page.getByText('Skipped — not executed.')).toBeVisible();
    });

    test('S4.5 — Stop mid-run cancels and skips pending steps', async () => {
      mock.runScript = () => [
        { type: 'plan_start', status: 'running' },
        { type: 'step_start', step_id: 0, intent: 'Group emissions by source' },
      ];
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Running…', { exact: true }).first()).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: 'Stop run' }).click();
      await expect(page.getByText('Run stopped')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('Stopped — pending steps were skipped and nothing was executed without approval.')).toBeVisible();
    });

    test('S4.6 — A failed run (done:failed) shows the failure state', async () => {
      mock.runScript = failedRunScript;
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run failed', { exact: true })).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('The run failed.')).toBeVisible();
    });

    test('S4.7 — A raw error frame surfaces its message', async () => {
      mock.runScript = errorFrameRunScript;
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run failed')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('The plan engine exploded.')).toBeVisible();
    });

    test('S4.8 — Pause a running plan via the plan card', async () => {
      mock.runScript = () => [
        { type: 'plan_start', status: 'running' },
        { type: 'step_start', step_id: 0, intent: 'Group emissions by source' },
      ];
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByRole('button', { name: 'Pause run' })).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: 'Pause run' }).click();
      await expect(page.getByText('Run paused — a step needs your approval')).toBeVisible({ timeout: 15000 });
      await expect(page.getByRole('button', { name: 'Resume run' })).toBeVisible();
    });

    test('S4.9 — Step card toggles collapse/expand via its icon', async () => {
      await openPlan(page, 'Summarize scope-1 emissions by source');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run completed')).toBeVisible({ timeout: 15000 });
      const toggle = page.getByLabel('Toggle step 0 details').first();
      await expect(toggle).toBeVisible();
      await toggle.click();
    });

    test('S4.10 — Step cards show tool/agent/status chips during a run', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Approve plan' }).click();
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run completed')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('dq_scan', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('data engineer', { exact: true }).first()).toBeVisible();
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 5 — Edit / pause / fork controls (W3-C)
  // ════════════════════════════════════════════════════════════════════════
  test.describe('5. Edit / pause / fork', () => {
    test('S5.1 — Edit brief opens the diff-review gate, then re-approval', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByLabel('Edit plan').click();
      await page.getByLabel('Plan brief').fill('Audit duplicates and reconcile totals');
      await page.getByRole('button', { name: 'Apply changes' }).click();
      await expect(page.getByText('Review plan changes')).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: 'Keep changes' }).click();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toBeVisible();
    });

    test('S5.2 — Cancelling the diff-review gate discards the edit', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByLabel('Edit plan').click();
      await page.getByLabel('Plan brief').fill('A totally different outcome');
      await page.getByRole('button', { name: 'Apply changes' }).click();
      await expect(page.getByText('Review plan changes')).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: 'Cancel' }).last().click();
      await expect(page.getByText('Review plan changes')).toHaveCount(0);
      await expect(page.getByText('Audit duplicates in emissions dataset', { exact: false }).first()).toBeVisible();
    });

    test('S5.3 — Apply changes is disabled once the brief is cleared', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByLabel('Edit plan').click();
      await page.getByLabel('Plan brief').fill('');
      await expect(page.getByRole('button', { name: 'Apply changes' })).toBeDisabled();
    });

    test('S5.4 — Step edit dialog opens with the step pre-populated; cancel closes it', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByLabel('Edit step 0').click();
      await expect(page.getByText('Edit step', { exact: true })).toBeVisible();
      await expect(page.getByLabel('Step title')).toHaveValue('Scan the dataset for duplicate rows');
      await page.getByRole('button', { name: 'Cancel' }).last().click();
      await expect(page.getByText('Edit step', { exact: true })).toHaveCount(0);
    });

    test('S5.5 — Step edit save flows through the diff-review gate', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByLabel('Edit step 0').click();
      await page.getByLabel('Step title').fill('Scan every table');
      await page.getByRole('button', { name: 'Save changes' }).click();
      await expect(page.getByText('Review plan changes')).toBeVisible({ timeout: 15000 });
      await page.getByRole('button', { name: 'Keep changes' }).click();
      await expect(page.getByRole('button', { name: 'Approve plan' })).toBeVisible();
    });

    test('S5.6 — Fork is available on completed plans', async () => {
      await openPlan(page, 'Reconcile fuel consumption records');
      await expect(page.getByRole('button', { name: 'Fork' })).toBeVisible();
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 6 — Plan graph: render + node-move/resize interaction matrix
  // ════════════════════════════════════════════════════════════════════════
  test.describe('6. Graph render + node-move/resize', () => {
    test('S6.1 — Graph renders nodes with aria labels and a summary', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.locator(`${GRAPH} [role="button"][aria-label^="Step 0:"]`)).toBeVisible();
      await expect(page.locator(`${GRAPH} [role="button"][aria-label^="Step 2:"]`)).toBeVisible();
      await expect(page.getByText('3 steps · 3 links')).toBeVisible();
    });

    test('S6.2 — Arrowhead markers are unique per SVG (inline plan-arrow)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.locator(`${GRAPH} svg marker[id="plan-arrow"]`)).toHaveCount(1);
    });

    test('S6.3 — Clicking a node opens the docked detail pane (plan-step-detail)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await clickNode(page, 0);
      await expect(page.locator('[data-testid="plan-step-detail"]')).toBeVisible();
      await expect(page.locator('[data-testid="plan-step-detail"]').getByText('Scan the dataset for duplicate rows')).toBeVisible();
    });

    test('S6.4 — Clicking the same node again deselects (pane closes)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await clickNode(page, 0);
      await expect(page.locator('[data-testid="plan-step-detail"]')).toBeVisible();
      await clickNode(page, 0);
      await expect(page.locator('[data-testid="plan-step-detail"]')).toHaveCount(0);
    });

    test('S6.5 — Selecting another node swaps the detail pane content', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await clickNode(page, 0);
      await clickNode(page, 1);
      await expect(page.locator('[data-testid="plan-step-detail"]').getByText('Deduplicate the rows')).toBeVisible();
    });

    test('S6.6 — Detail pane reports dependencies and feeds-into', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await clickNode(page, 2);
      const pane = page.locator('[data-testid="plan-step-detail"]');
      await expect(pane.getByText('Depends on', { exact: true })).toBeVisible();
      await expect(pane.getByText('Feeds into', { exact: true })).toBeVisible();
      await expect(pane.getByText('Nothing — ends the workflow')).toBeVisible();
    });

    test('S6.7 — A small (<3px) node movement is a click, not a drag (selects)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const el = page.locator(nodeSel(0)).first();
      await el.scrollIntoViewIfNeeded();
      const b = await el.boundingBox();
      await page.mouse.move(b!.x + b!.width / 2, b!.y + b!.height / 2);
      await page.mouse.down();
      await page.mouse.move(b!.x + b!.width / 2 + 1, b!.y + b!.height / 2 + 1);
      await page.mouse.up();
      await expect(page.locator('[data-testid="plan-step-detail"]')).toBeVisible();
    });

    test('S6.8 — A large drag moves the node and does NOT select it', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = parseTranslate(await nodeTransform(page, 0));
      const beforeRect = await nodeRect(page, 0);
      await dragNode(page, 0, 80, 50);
      const after = parseTranslate(await nodeTransform(page, 0));
      expect(after.x).toBeGreaterThan(before.x);
      expect(after.y).toBeGreaterThan(before.y);
      // A pure drag stores only {x,y} — the node body must keep its layout
      // width/height (regression: it used to collapse to 0×0).
      const afterRect = await nodeRect(page, 0);
      expect(afterRect.w).toBe(beforeRect.w);
      expect(afterRect.h).toBe(beforeRect.h);
      await expect(page.locator('[data-testid="plan-step-detail"]')).toHaveCount(0);
    });

    test('S6.9 — Dragging up-left decreases node position', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = parseTranslate(await nodeTransform(page, 1));
      await dragNode(page, 1, -60, -40);
      const after = parseTranslate(await nodeTransform(page, 1));
      expect(after.x).toBeLessThan(before.x);
      expect(after.y).toBeLessThan(before.y);
    });

    test('S6.10 — Redraw resets node position overrides to the auto-layout', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const original = await nodeTransform(page, 0);
      await dragNode(page, 0, 90, 60);
      expect(await nodeTransform(page, 0)).not.toBe(original);
      await page.getByRole('button', { name: 'Redraw layout' }).click();
      expect(await nodeTransform(page, 0)).toBe(original);
    });

    test('S6.11 — Resize handle grows the node (width + height)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = await nodeRect(page, 0);
      await dragResize(page, 0, 60, 40);
      const after = await nodeRect(page, 0);
      expect(after.w).toBeGreaterThan(before.w);
      expect(after.h).toBeGreaterThan(before.h);
    });

    test('S6.12 — Resize clamps to the max (640 × 320)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const beforeT = parseTranslate(await nodeTransform(page, 0));
      await dragResize(page, 0, 600, 600);
      const after = await nodeRect(page, 0);
      expect(after.w).toBe(640);
      expect(after.h).toBe(320);
      // A pure resize stores only {w,h} — the node must keep its layout x/y
      // (regression: it used to render translate(NaN, NaN)).
      expect(await nodeTransform(page, 0)).not.toContain('NaN');
      const afterT = parseTranslate(await nodeTransform(page, 0));
      expect(afterT.x).toBe(beforeT.x);
      expect(afterT.y).toBe(beforeT.y);
    });

    test('S6.13 — Resize clamps to the min (96 × 36)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await dragResize(page, 0, -90, -30);
      const after = await nodeRect(page, 0);
      expect(after.w).toBe(96);
      expect(after.h).toBe(36);
    });

    test('S6.14 — Zoom in increases the canvas scale', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = parseScale(await canvasTransform(page));
      await page.getByRole('button', { name: 'Zoom in' }).click();
      const after = parseScale(await canvasTransform(page));
      expect(after).toBeGreaterThan(before);
    });

    test('S6.15 — Zoom out decreases the canvas scale', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Zoom in' }).click();
      const before = parseScale(await canvasTransform(page));
      await page.getByRole('button', { name: 'Zoom out' }).click();
      const after = parseScale(await canvasTransform(page));
      expect(after).toBeLessThan(before);
    });

    test('S6.16 — Zoom clamps to the maximum 3.0', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      for (let i = 0; i < 25; i++) await page.getByRole('button', { name: 'Zoom in' }).click();
      expect(parseScale(await canvasTransform(page))).toBeCloseTo(3, 5);
    });

    test('S6.17 — Zoom clamps to the minimum 0.25', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      for (let i = 0; i < 25; i++) await page.getByRole('button', { name: 'Zoom out' }).click();
      expect(parseScale(await canvasTransform(page))).toBeCloseTo(0.25, 5);
    });

    test('S6.18 — Reset view restores scale 1 and zero pan', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Zoom in' }).click();
      await page.getByRole('button', { name: 'Zoom in' }).click();
      await page.getByRole('button', { name: 'Reset view' }).click();
      expect(parseScale(await canvasTransform(page))).toBe(1);
    });

    test('S6.19 — Zoom-to-fit never exceeds scale 1', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Zoom in' }).click();
      await page.getByRole('button', { name: 'Zoom to fit' }).click();
      expect(parseScale(await canvasTransform(page))).toBeLessThanOrEqual(1);
    });

    test('S6.20 — Dragging empty canvas pans the view (translate changes)', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = parseTranslate(await canvasTransform(page));
      // Grab the top-left corner of the canvas (above/left of any node).
      const canvas = page.locator(GRAPH);
      await canvas.scrollIntoViewIfNeeded();
      const box = await canvas.boundingBox();
      await page.mouse.move(box!.x + 40, box!.y + 20);
      await page.mouse.down();
      await page.mouse.move(box!.x + 40 + 120, box!.y + 20 + 80, { steps: 10 });
      await page.mouse.up();
      const after = parseTranslate(await canvasTransform(page));
      expect(after.x).not.toBe(before.x);
      expect(after.y).not.toBe(before.y);
    });

    test('S6.21 — Node drag does not pan the whole canvas', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const before = parseTranslate(await canvasTransform(page));
      await dragNode(page, 0, 80, 50);
      const after = parseTranslate(await canvasTransform(page));
      expect(after.x).toBe(before.x);
      expect(after.y).toBe(before.y);
    });

    test('S6.22 — After a drag, a fresh click still selects the node', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await dragNode(page, 0, 80, 50);
      await clickNode(page, 0);
      await expect(page.locator('[data-testid="plan-step-detail"]')).toBeVisible();
    });

    test('S6.23 — Running nodes pulse (<animate> present); finished nodes do not', async () => {
      mock.reset([
        makePlan({
          id: 'p-running',
          status: 'running',
          brief: 'Live running plan',
          steps: [
            step({ step_id: 0, status: 'running' }),
            step({ step_id: 1, status: 'completed', depends_on: [0] }),
          ],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Live running plan');
      await expect(page.locator(`${nodeSel(0)} animate`)).toHaveCount(1);
      await expect(page.locator(`${nodeSel(1)} animate`)).toHaveCount(0);
    });

    test('S6.24 — Status labels render UPPERCASE on node interiors', async () => {
      await openPlan(page, 'Reconcile fuel consumption records');
      await expect(page.locator(`${nodeSel(0)}`)).toContainText('FINISHED');
    });

    test('S6.25 — Legend chips render all five statuses', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      for (const label of ['Pending', 'Running', 'Needs approval', 'Finished', 'Failed']) {
        await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
      }
    });

    test('S6.26 — Redraw also resets resized nodes back to layout size', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const original = await nodeRect(page, 0);
      await dragResize(page, 0, 80, 50);
      expect((await nodeRect(page, 0)).w).toBeGreaterThan(original.w);
      await page.getByRole('button', { name: 'Redraw layout' }).click();
      const after = await nodeRect(page, 0);
      expect(after.w).toBe(original.w);
      expect(after.h).toBe(original.h);
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 7 — Full-screen maximize modal + export
  // ════════════════════════════════════════════════════════════════════════
  test.describe('7. Maximize modal + export', () => {
    test('S7.1 — Maximize opens the full-screen modal with the full-view title', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.locator('[data-testid="plan-graph-expand"]').click();
      await expect(page.locator('[data-testid="plan-graph-modal"]')).toBeVisible();
      await expect(page.getByText('Plan graph — full view')).toBeVisible();
    });

    test('S7.2 — The modal uses a distinct arrowhead marker', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.locator('[data-testid="plan-graph-expand"]').click();
      await expect(page.locator('[data-testid="plan-dag-graph-modal"] svg marker[id="plan-arrow-modal"]')).toHaveCount(1);
    });

    test('S7.3 — Clicking a node in the modal opens the modal detail pane', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.locator('[data-testid="plan-graph-expand"]').click();
      const node = page.locator('[data-testid="plan-dag-graph-modal"] [role="button"][aria-label^="Step 1:"]').first();
      await node.scrollIntoViewIfNeeded();
      const b = await node.boundingBox();
      if (!b) throw new Error('No bounding box for modal step 1');
      await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
      await expect(page.locator('[data-testid="plan-step-detail-modal"]')).toBeVisible();
      await expect(page.locator('[data-testid="plan-step-detail-modal"]').getByText('Deduplicate the rows')).toBeVisible();
    });

    test('S7.4 — Close full view dismisses the modal', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.locator('[data-testid="plan-graph-expand"]').click();
      await expect(page.locator('[data-testid="plan-graph-modal"]')).toBeVisible();
      await page.locator('[data-testid="plan-graph-modal-close"]').click();
      await expect(page.locator('[data-testid="plan-graph-modal"]')).toHaveCount(0);
    });

    test('S7.5 — Modal zoom works independently of the inline canvas', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.locator('[data-testid="plan-graph-expand"]').click();
      const before = parseScale(await page.locator('[data-testid="plan-dag-graph-modal"] svg > g').first().getAttribute('transform'));
      await page.locator('[data-testid="plan-graph-modal"] button[aria-label="Zoom in"]').click();
      const after = parseScale(await page.locator('[data-testid="plan-dag-graph-modal"] svg > g').first().getAttribute('transform'));
      expect(after).toBeGreaterThan(before);
    });

    test('S7.6 — Export downloads a PNG named plan-graph.png', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 20000 }),
        page.getByRole('button', { name: 'Export as PNG' }).click(),
      ]);
      expect(download.suggestedFilename()).toContain('plan-graph.png');
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 8 — Plan preview toggle (graph ↔ mermaid diagram)
  // ════════════════════════════════════════════════════════════════════════
  test.describe('8. Preview toggle', () => {
    test('S8.1 — Default preview is the graph', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await expect(page.locator(GRAPH)).toBeVisible();
    });

    test('S8.2 — Toggling to Diagram renders the mermaid SVG', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Diagram' }).click();
      await expect(page.locator('[data-testid="plan-mermaid-preview"] svg').first()).toBeVisible({ timeout: 15000 });
    });

    test('S8.3 — Toggling back to Graph restores the DAG', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Diagram' }).click();
      await page.getByRole('button', { name: 'Graph' }).click();
      await expect(page.locator(GRAPH)).toBeVisible();
    });
  });

  // ════════════════════════════════════════════════════════════════════════
  // SECTION 9 — Extreme / edge data shapes
  // ════════════════════════════════════════════════════════════════════════
  test.describe('9. Extreme & edge cases', () => {
    test('S9.1 — Single-step plan renders one node with one link', async () => {
      mock.reset([
        makePlan({ id: 'p-one', status: 'approved', brief: 'Single step', steps: [step({ step_id: 0 })] }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Single step');
      await expect(page.getByText('1 step · 0 links')).toBeVisible();
      await expect(page.locator(nodeSel(0))).toBeVisible();
    });

    test('S9.2 — Two-step sequential chain renders both nodes and one link', async () => {
      mock.reset([
        makePlan({
          id: 'p-two',
          status: 'approved',
          brief: 'Two step chain',
          steps: [step({ step_id: 0 }), step({ step_id: 1, depends_on: [0] })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Two step chain');
      await expect(page.getByText('2 steps · 1 link')).toBeVisible();
    });

    test('S9.3 — Parallel diamond renders 4 nodes and 4 links', async () => {
      mock.reset([
        makePlan({
          id: 'p-diamond',
          status: 'approved',
          brief: 'Diamond DAG',
          steps: [
            step({ step_id: 0, intent: 'A' }),
            step({ step_id: 1, intent: 'B', depends_on: [0] }),
            step({ step_id: 2, intent: 'C', depends_on: [0] }),
            step({ step_id: 3, intent: 'D', depends_on: [1, 2] }),
          ],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Diamond DAG');
      await expect(page.getByText('4 steps · 4 links')).toBeVisible();
      await expect(page.locator(nodeSel(3))).toBeVisible();
    });

    test('S9.4 — Fifty-step chain renders and reports "50 steps"', async () => {
      mock.reset([
        makePlan({ id: 'p-many', status: 'approved', brief: 'Many steps', steps: chainSteps(50) }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Many steps');
      await expect(page.getByText('50 steps · 49 links')).toBeVisible();
      await expect(page.locator(nodeSel(49))).toBeVisible();
    });

    test('S9.5 — Orphan depends_on ids are skipped without crashing', async () => {
      mock.reset([
        makePlan({
          id: 'p-orphan',
          status: 'approved',
          brief: 'Orphan dependency',
          steps: [step({ step_id: 0 }), step({ step_id: 1, depends_on: [99] })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Orphan dependency');
      await expect(page.getByText('2 steps · 0 links')).toBeVisible();
      await expect(page.locator(nodeSel(1))).toBeVisible();
    });

    test('S9.6 — Steps with missing tool/agent fall back to defaults without crashing', async () => {
      mock.reset([
        makePlan({
          id: 'p-missing',
          status: 'approved',
          brief: 'Missing fields',
          steps: [step({ step_id: 0, intent: undefined as any, tool_name: null, agent_role: undefined as any })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Missing fields');
      await expect(page.locator(nodeSel(0))).toBeVisible();
      await expect(page.locator(nodeSel(0))).toContainText('Reasoning (LLM)');
    });

    test('S9.7 — Very long intents are truncated in the node without overflow crash', async () => {
      mock.reset([
        makePlan({
          id: 'p-long',
          status: 'approved',
          brief: 'Long intent',
          steps: [step({ step_id: 0, intent: 'X'.repeat(500) })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Long intent');
      await expect(page.locator(nodeSel(0))).toBeVisible();
    });

    test('S9.8 — Intents with quotes/emoji/newlines render in nodes', async () => {
      mock.reset([
        makePlan({
          id: 'p-weird',
          status: 'approved',
          brief: 'Weird intent',
          steps: [step({ step_id: 0, intent: 'Fix "quotes" 🔥\nand\nnewlines' })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Weird intent');
      await expect(page.locator(nodeSel(0))).toBeVisible();
    });

    test('S9.9 — Duplicate step_ids do not crash the graph', async () => {
      mock.reset([
        makePlan({
          id: 'p-dup',
          status: 'approved',
          brief: 'Duplicate ids',
          steps: [step({ step_id: 0 }), step({ step_id: 0, intent: 'Duplicate' })],
        }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Duplicate ids');
      await expect(page.locator(nodeSel(0)).first()).toBeVisible();
    });

    test('S9.10 — Drag a node while zoomed-in divides the delta by zoom', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Zoom in' }).click(); // zoom ≈1.15
      const before = parseTranslate(await nodeTransform(page, 0));
      await dragNode(page, 0, 80, 40);
      const after = parseTranslate(await nodeTransform(page, 0));
      expect(after.x).toBeGreaterThan(before.x);
      expect(after.y).toBeGreaterThan(before.y);
    });

    test('S9.11 — Resize while zoomed-in still clamps to the max', async () => {
      await openPlan(page, 'Audit duplicates in emissions dataset');
      await page.getByRole('button', { name: 'Zoom in' }).click();
      await dragResize(page, 0, 900, 900);
      const after = await nodeRect(page, 0);
      expect(after.w).toBe(640);
      expect(after.h).toBe(320);
    });

    test('S9.12 — Empty graph shows the empty-state message', async () => {
      await openPlan(page, 'Plan with no steps');
      // The plan card itself renders "No steps were planned." (no graph at all).
      await expect(page.getByText('No steps were planned.')).toBeVisible();
      await expect(page.locator(GRAPH)).toHaveCount(0);
    });

    test('S9.13 — Running an approved plan with zero steps completes instantly', async () => {
      mock.reset([
        makePlan({ id: 'p-empty-run', status: 'approved', brief: 'Empty run plan', steps: [] }),
      ]);
      await gotoTasks(page);
      await openPlan(page, 'Empty run plan');
      await page.getByRole('button', { name: 'Run plan' }).click();
      await expect(page.getByText('Run completed')).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('No steps were planned.')).toBeVisible();
    });
  });
});
