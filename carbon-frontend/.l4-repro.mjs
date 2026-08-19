// TEMP qa-validator evidence — reproduce engine-settings + learning-flywheel crashes w/ error capture
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5179';

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);

const out = {};

async function visit(route) {
  const consoleErrors = [];
  const pageErrors = [];
  const onC = (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); };
  const onP = (e) => pageErrors.push(String(e));
  page.on('console', onC);
  page.on('pageerror', onP);
  await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4500);
  const body = (await page.locator('body').innerText().catch(() => '')).replace(/\n+/g, ' | ').slice(0, 500);
  const title = await page.title().catch(() => '');
  page.off('console', onC);
  page.off('pageerror', onP);
  return { title, crashed: /Something went wrong/.test(body), body: body.slice(0, 300), consoleErrors: consoleErrors.slice(0, 6), pageErrors: pageErrors.slice(0, 4) };
}

// login admin
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await page.getByLabel('Username').fill('admin');
await page.getByLabel('Password').fill('admin123');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForTimeout(3000);

out.engine_settings = await visit('/admin/ai/engine-settings');
out.learning_flywheel = await visit('/admin/ai/learning-flywheel');

// workspace: breadcrumb detail + Pulse heading position
await page.goto(`${BASE}/admin/ai/workspace`, { waitUntil: 'domcontentloaded' });
await page.getByRole('button', { name: 'Sessions' }).click();
await page.getByRole('listbox', { name: 'Conversation sessions' }).waitFor({ timeout: 20000 });
await page.waitForTimeout(1500);

out.workspace = {
  crumbNav: await page.getByLabel('Breadcrumb navigation').innerText().catch(() => null),
  crumbElements: await page.evaluate(() =>
    Array.from(document.querySelectorAll('nav[aria-label="Breadcrumb navigation"] a, nav[aria-label="Breadcrumb navigation"] [aria-current]'))
      .map((el) => ({ text: el.textContent.trim(), current: el.getAttribute('aria-current') }))
  ),
  pulseHeadings: await page.evaluate(() =>
    Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map((h) => h.textContent.trim()).filter((t) => /pulse/i.test(t))
  ),
};

console.log(JSON.stringify(out, null, 2));
await browser.close();
