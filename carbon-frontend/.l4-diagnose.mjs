// TEMP diagnostic — dump workspace page state
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:5179';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);

const errs = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 300)); });
page.on('pageerror', (e) => errs.push('PAGEERROR: ' + String(e).slice(0, 500)));

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
await page.getByLabel('Username').fill('ahmed');
await page.getByLabel('Password').fill('AdminPa_132');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForTimeout(3000);

await page.goto(`${BASE}/admin/ai/workspace`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(8000);

const body = await page.locator('body').innerText().catch(() => '(no body)');
console.log('=== BODY TEXT (first 2500 chars) ===');
console.log(body.slice(0, 2500));
console.log('=== CONSOLE/PAGE ERRORS ===');
console.log(errs.slice(0, 15).join('\n---\n'));

await browser.close();
