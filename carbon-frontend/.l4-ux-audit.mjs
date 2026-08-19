// TEMP qa-validator evidence script — Layer 4 UX audit v2 (headless Playwright)
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5179';
const API = 'http://127.0.0.1:8009/carbon-api';

const results = {};
const consoleErrors = [];
const pageErrors = [];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.setDefaultTimeout(25000);

page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => pageErrors.push(String(e)));

const log = (k, v) => { results[k] = v; };

// ---------- login ----------
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await page.getByLabel('Username').fill('ahmed');
await page.getByLabel('Password').fill('AdminPa_132');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForTimeout(3000);

// ---------- workspace: open sessions drawer ----------
await page.goto(`${BASE}/admin/ai/workspace`, { waitUntil: 'domcontentloaded' });
await page.getByRole('button', { name: 'Sessions' }).click();
await page.getByRole('listbox', { name: 'Conversation sessions' }).waitFor({ timeout: 20000 });
await page.waitForTimeout(1500);

log('W7_title', await page.title());
log('W6_breadcrumb_nav_text', await page.getByLabel('Breadcrumb navigation').innerText().catch(() => null));
log('W1_console_errors_workspace', consoleErrors.slice(0, 10));

// ---------- UX-W5 dark mode ----------
try {
  const toggle = page.getByRole('button', { name: 'Light mode' }).or(page.getByRole('button', { name: 'Dark mode' }));
  const labelBefore = await toggle.getAttribute('aria-label');
  const bgBefore = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await toggle.click();
  await page.waitForTimeout(900);
  const labelAfter = await toggle.getAttribute('aria-label');
  const bgAfter = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  log('W5_dark_mode', { labelBefore, labelAfter, bgBefore, bgAfter, works: labelBefore !== labelAfter });
  await toggle.click();
  await page.waitForTimeout(500);
} catch (e) { log('W5_dark_mode', { error: String(e) }); }

// ---------- UX-W8 responsive 768 ----------
await page.setViewportSize({ width: 768, height: 1024 });
await page.waitForTimeout(1500);
const m768 = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
log('W8_responsive_768', { ...m768, overflow: m768.sw > m768.iw });

// ---------- UX-12 zoom 150% ----------
await page.setViewportSize({ width: 1440, height: 900 });
await page.evaluate(() => { document.body.style.zoom = '1.5'; });
await page.waitForTimeout(1200);
const mz = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
await page.evaluate(() => { document.body.style.zoom = ''; });
log('UX12_zoom150', { ...mz, overflow: mz.sw > mz.iw });

// ---------- UX-W9 keyboard focus ----------
await page.mouse.click(5, 5);
const focusChain = [];
for (let i = 0; i < 5; i++) {
  await page.keyboard.press('Tab');
  focusChain.push(await page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return null;
    const cs = getComputedStyle(el);
    return { tag: el.tagName, aria: el.getAttribute('aria-label') || '', fv: el.matches(':focus-visible'), outline: cs.outlineStyle + ' ' + cs.outlineWidth };
  }));
}
log('W9_keyboard_focus', focusChain);

// ---------- UX-13 long title truncation ----------
try {
  const token = await page.evaluate(() => localStorage.getItem('access'));
  const longTitle = 'L'.repeat(200);
  const res = await fetch(`${API}/ai/workspace/conversations/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ title: longTitle }),
  });
  const conv = await res.json().catch(() => null);
  log('UX13_created', { status: res.status, id: conv?.id });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Sessions' }).click();
  await page.getByRole('listbox', { name: 'Conversation sessions' }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(2000);
  const tab = page.locator('[role="option"]', { hasText: longTitle }).first();
  const count = await tab.count();
  let trunc = null;
  if (count) {
    trunc = await tab.locator('p').first().evaluate((el) => {
      const cs = getComputedStyle(el);
      return { textOverflow: cs.textOverflow, overflow: cs.overflow, scrollW: el.scrollWidth, clientW: el.clientWidth, truncated: el.scrollWidth > el.clientWidth };
    }).catch((e) => ({ err: String(e) }));
  }
  log('UX13_long_title', { found: !!count, trunc });
} catch (e) { log('UX13_long_title', { error: String(e) }); }

// ---------- UX-14 rapid tab switching ----------
try {
  const token = await page.evaluate(() => localStorage.getItem('access'));
  const ids = [];
  for (let i = 0; i < 10; i++) {
    const r = await fetch(`${API}/ai/workspace/conversations/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ title: `Rapid ${i}` }),
    });
    const j = await r.json().catch(() => null);
    if (j?.id) ids.push(j.id);
  }
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Sessions' }).click();
  await page.getByRole('listbox', { name: 'Conversation sessions' }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(2000);
  const before = consoleErrors.length;
  const opts = page.locator('[role="option"]');
  const n = await opts.count();
  const clicks = Math.min(n, 12);
  for (let i = 0; i < clicks; i++) {
    await opts.nth(i).click().catch(() => {});
    await page.waitForTimeout(90);
  }
  await page.waitForTimeout(1500);
  const newErrs = consoleErrors.slice(before);
  log('UX14_rapid_tabs', { created: ids.length, clicked: clicks, newConsoleErrors: newErrs.length, muiRelated: newErrs.filter((e) => /invalid|index|value|tabs/i.test(e)).slice(0, 5), sample: newErrs.slice(0, 3) });
} catch (e) { log('UX14_rapid_tabs', { error: String(e) }); }

// ---------- UX-15 refresh mid-stream ----------
try {
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Sessions' }).click();
  await page.getByRole('listbox', { name: 'Conversation sessions' }).waitFor({ timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.locator('[role="option"]').first().click();
  await page.waitForTimeout(2000);
  const composer = page.getByLabel('Message input');
  const hasC = await composer.count();
  if (!hasC) {
    log('UX15_refresh_midstream', { error: 'composer not found' });
  } else {
    await composer.fill('What is the capital of Madagascar?');
    await composer.press('Enter');
    await page.waitForTimeout(2500);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4500);
    const sessions = await page.getByRole('button', { name: 'Sessions' }).count();
    const body = (await page.locator('body').innerText().catch(() => '')).slice(0, 400);
    log('UX15_refresh_midstream', {
      reloaded: true,
      pageFunctional: sessions > 0,
      bodySnippet: body.replace(/\n+/g, ' | '),
      pageErrorsAfter: pageErrors.slice(-5),
      consoleErrorsAfter: consoleErrors.slice(-8),
    });
  }
} catch (e) { log('UX15_refresh_midstream', { error: String(e) }); }

// ---------- UX-W10 route sweep with per-route console attribution ----------
try {
  const routes = [
    '/admin/ai', '/admin/ai/workspace', '/admin/ai/conversations', '/admin/ai/knowledge',
    '/admin/ai/memory', '/admin/ai/graph', '/admin/ai/agents', '/admin/ai/mcp', '/admin/ai/tools',
    '/admin/ai/skills', '/admin/ai/archetypes', '/admin/ai/budget-usage', '/admin/ai/engine-settings',
    '/admin/ai/prompts', '/admin/ai/feedback', '/admin/ai/learning', '/admin/ai/learning-flywheel',
    '/admin/ai/monitoring', '/admin/ai/audit', '/admin/ai/logs',
  ];
  const sweep = [];
  for (const r of routes) {
    const before = consoleErrors.length;
    const beforePE = pageErrors.length;
    try {
      await page.goto(`${BASE}${r}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2200);
      const body = await page.locator('body').innerText().catch(() => '');
      const crashed = /Something went wrong/.test(body);
      const title = await page.title().catch(() => '');
      const errs = consoleErrors.slice(before).filter((e) => !/favicon|vite|websocket|\.map/i.test(e));
      const pes = pageErrors.slice(beforePE);
      sweep.push({ route: r, title, crashed, consoleErrors: errs.slice(0, 3), pageErrors: pes.slice(0, 2) });
    } catch (e) {
      sweep.push({ route: r, error: String(e).slice(0, 120) });
    }
  }
  log('W10_route_sweep', sweep);
} catch (e) { log('W10_route_sweep', { error: String(e) }); }

console.log(JSON.stringify(results, null, 2));
console.log('TOTAL console errors:', consoleErrors.length);
console.log('TOTAL page errors:', pageErrors.length);
await browser.close();
