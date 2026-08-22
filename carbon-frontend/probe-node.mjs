import { chromium } from '@playwright/test';

const BASE = 'http://127.0.0.1:5179';
const browser = await chromium.launch({ args: ['--disable-web-security'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/login`);
await page.getByLabel('Username').fill('admin');
await page.getByLabel('Password').fill('admin123');
await page.getByRole('button', { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith('/login'));
await page.waitForTimeout(1500);

await page.route(/\/ai\/plans/, (route) => {
  const url = new URL(route.request().url());
  const path = url.pathname;
  if (path.endsWith('/ai/plans/')) {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ plans: [
      { id: 'p1', status: 'approved', brief: 'Audit duplicates in emissions dataset', pattern: 'audit-dq', source: 'pulse', skill_name: 'dq-audit', needs_confirmation: true, created_at: '2024-01-01T00:00:00Z',
        steps: [
          { step_id: 0, intent: 'Scan the dataset for duplicate rows', tool_name: 'dq_scan', tool_args: { table: 'emissions' }, depends_on: [], agent_role: 'orchestrator', status: 'pending' },
          { step_id: 1, intent: 'Deduplicate the rows', tool_name: 'dq_dedupe', tool_args: { table: 'emissions', mode: 'safe' }, depends_on: [0], agent_role: 'data_engineer', status: 'pending' },
          { step_id: 2, intent: 'Create a rule to prevent duplicates', tool_name: 'dq_rule', tool_args: { rule: 'unique' }, depends_on: [0, 1], agent_role: 'data_engineer', status: 'pending' },
        ] },
    ], count: 1 }) });
  }
  if (/\/ai\/plans\/[^/]+$/.test(path)) {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'p1', status: 'approved', brief: 'Audit duplicates in emissions dataset', steps: [
      { step_id: 0, intent: 'Scan the dataset for duplicate rows', tool_name: 'dq_scan', tool_args: { table: 'emissions' }, depends_on: [], agent_role: 'orchestrator', status: 'pending' },
      { step_id: 1, intent: 'Deduplicate the rows', tool_name: 'dq_dedupe', tool_args: { table: 'emissions', mode: 'safe' }, depends_on: [0], agent_role: 'data_engineer', status: 'pending' },
      { step_id: 2, intent: 'Create a rule to prevent duplicates', tool_name: 'dq_rule', tool_args: { rule: 'unique' }, depends_on: [0, 1], agent_role: 'data_engineer', status: 'pending' },
    ] }) });
  }
  return route.continue();
});

await page.goto(`${BASE}/admin/ai/workspace`);
await page.locator('[aria-label="Tasks"]').first().click();
await page.getByRole('tab', { name: 'Tasks' }).click();
await page.getByText('Audit duplicates in emissions dataset').first().click();
await page.getByText('Task plan').waitFor();

const sel = `[data-testid="plan-dag-graph"] [role="button"][aria-label^="Step 0:"]`;
const el = page.locator(sel).first();
await el.waitFor({ state: 'visible' });
const b = await el.boundingBox();
console.log('boundingBox:', JSON.stringify(b));

const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
console.log('center:', cx, cy);
const hit = await page.evaluate(([x, y]) => {
  const el = document.elementFromPoint(x, y);
  if (!el) return 'null';
  const g = el.closest('[role="button"]');
  return { tag: el.tagName, testid: el.getAttribute('data-testid'), nodeAria: g && g.getAttribute('aria-label') };
}, [cx, cy]);
console.log('elementFromPoint at center:', JSON.stringify(hit));

await page.mouse.click(cx, cy);
await page.waitForTimeout(500);
const pane = await page.locator('[data-testid="plan-step-detail"]').count();
console.log('pane count after mouse.click:', pane);

await browser.close();
