/**
 * Records one Pulse how-to. Scene holds come from a JSON file so the
 * Arabic narration fits. No password is stored in this file.
 *
 *   node scripts/pulse-howto-record.mjs employee /tmp/holds-employee.json
 */
import { chromium } from '@playwright/test';
import fs from 'node:fs';

const persona = process.argv[2];
const holdsPath = process.argv[3];
const outDir = process.argv[4] || '/tmp/pulse-howto-raw';
const BASE = 'http://127.0.0.1:5179';
const holds = JSON.parse(fs.readFileSync(holdsPath, 'utf8'));
const user = process.env.HOWTO_USER;
const pass = process.env.HOWTO_PASS;
if (!user || !pass) throw new Error('HOWTO_USER and HOWTO_PASS are required');

const HOME = {
  employee: '/my',
  hr: '/people',
}[persona];
if (!HOME) throw new Error(`unknown persona ${persona}`);

fs.mkdirSync(outDir, { recursive: true });

async function pause(page, ms) {
  await page.waitForTimeout(ms);
}

async function tidy(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.MuiAlert-root').forEach((el) => {
      el.style.display = 'none';
    });
    document.querySelectorAll('[data-testid="pulse-expanded-dock-banner"]').forEach((el) => {
      el.style.display = 'none';
    });
    document.querySelectorAll('p, span, div, button, h6').forEach((el) => {
      const own = [...el.childNodes]
        .filter((n) => n.nodeType === 3)
        .map((n) => n.textContent)
        .join('')
        .trim();
      if (/^Thought for|^Considered:/.test(own)) {
        const block = el.parentElement || el;
        block.style.display = 'none';
      }
    });
  }).catch(() => {});
}

async function hold(page, id) {
  await tidy(page);
  const ms = Number(holds[id] || 8000);
  await pause(page, ms);
}

async function sendAsk(page, text) {
  const ask = page.getByTestId('pulse-process-switch').getByRole('button', { name: /^ask$/i });
  if (await ask.count()) await ask.click().catch(() => {});
  const box = page.getByPlaceholder(/ask a question|describe the outcome/i);
  await box.waitFor({ state: 'visible', timeout: 15000 });
  await box.click();
  await box.fill(text);
  await pause(page, 700);
  await page.getByRole('button', { name: /send message/i }).click();
  const thinking = page.getByText(/AI is thinking/i);
  const started = await thinking.waitFor({ state: 'visible', timeout: 8000 }).then(() => true).catch(() => false);
  if (started) {
    await thinking.waitFor({ state: 'hidden', timeout: 50000 }).catch(() => {});
  } else {
    await pause(page, 6000);
  }
  await pause(page, 800);
  await tidy(page);
}

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const setup = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const login = await setup.newPage();
await login.goto(`${BASE}/login`);
await login.getByLabel('Username').fill(user);
await login.getByLabel('Password').fill(pass);
await login.getByRole('button', { name: /sign in/i }).click();
await login.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20000 });
await login.evaluate(() => {
  localStorage.setItem('carbon-copilot-visible', '0');
  localStorage.setItem('carbon-copilot-expanded', '0');
});
const state = `${outDir}/storage.json`;
await setup.storageState({ path: state });
await setup.close();

const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  storageState: state,
  recordVideo: { dir: outDir, size: { width: 1440, height: 900 } },
});
await context.addInitScript(() => {
  if (sessionStorage.getItem('howto-expand') === '1') {
    localStorage.setItem('carbon-copilot-visible', 'true');
    localStorage.setItem('carbon-copilot-expanded', 'true');
  }
  const hide = () => {
    document.querySelectorAll('.MuiChip-label').forEach((el) => {
      if (/early preview/i.test(el.textContent || '')) {
        const chip = el.closest('.MuiChip-root');
        if (chip) chip.style.display = 'none';
      }
    });
    document.querySelectorAll('.MuiAlert-root').forEach((el) => {
      el.style.display = 'none';
    });
  };
  const start = () => {
    hide();
    new MutationObserver(hide).observe(document.documentElement, { childList: true, subtree: true });
  };
  if (document.documentElement) start();
  else document.addEventListener('DOMContentLoaded', start);
});
const page = await context.newPage();
const marks = [];
const origin = Date.now();
const mark = async (id, fn) => {
  await fn();
  const start = (Date.now() - origin) / 1000;
  await hold(page, id);
  const end = (Date.now() - origin) / 1000;
  marks.push({ id, start, end });
};

await page.goto(`${BASE}${HOME}`);
await page.waitForLoadState('domcontentloaded');
await pause(page, 1200);
if (persona === 'hr' && page.url().includes('/login')) {
  throw new Error('HR login did not stick');
}
if (persona === 'hr' && /403|not found|permission/i.test(await page.locator('body').innerText().catch(() => ''))) {
  await page.goto(`${BASE}/my`);
}

await mark('home', async () => { await tidy(page); });

await mark('open', async () => {
  await page.evaluate(() => sessionStorage.setItem('howto-expand', '1'));
  await page.reload();
  await page.getByTestId('composer-process').waitFor({ state: 'visible', timeout: 20000 });
  await pause(page, 600);
  const fresh = page.getByRole('button', { name: /new chat/i });
  if (await fresh.count()) await fresh.first().click().catch(() => {});
  await pause(page, 600);
});

const questions = persona === 'hr'
  ? [
      ['askHeadcount', 'How many active employees are there, by job title? Answer as a short list.'],
      ['askLeave', 'Which leave requests are waiting for approval?'],
      ['askMine', 'What is my own leave balance?'],
    ]
  : [
      ['askLeave', 'What is my leave balance?'],
      ['askPay', 'What is my latest payslip?'],
      ['askRequests', 'Do I have any requests still waiting?'],
      ['askAttendance', 'Summarize my attendance for this month.'],
    ];

for (const [id, text] of questions) {
  await mark(id, async () => { await sendAsk(page, text); });
}

await mark('plan', async () => {
  const plan = page.getByTestId('pulse-process-switch').getByRole('button', { name: /^plan$/i });
  await plan.click();
  await pause(page, 900);
  const box = page.getByPlaceholder(/describe the outcome/i);
  await box.waitFor({ state: 'visible', timeout: 10000 });
  const draft = persona === 'hr'
    ? 'Draft a summary of leave requests waiting for approval. Do not approve or reject anything.'
    : 'I want one day of annual leave next week. Draft it only. Do not submit it.';
  await box.fill(draft);
  await pause(page, 600);
});

await mark('tasks', async () => {
  const tasks = page.getByTestId('pulse-workspace-switch').getByRole('button', { name: /^tasks$/i });
  await tasks.click();
  await pause(page, 1200);
});

await mark('close', async () => {
  const chat = page.getByTestId('pulse-workspace-switch').getByRole('button', { name: /^chat$/i });
  if (await chat.count()) await chat.click().catch(() => {});
  await pause(page, 400);
});

const video = page.video();
await context.close();
await browser.close();
const src = await video.path();
const dest = `${outDir}/${persona}.webm`;
fs.copyFileSync(src, dest);
fs.writeFileSync(`${outDir}/${persona}-marks.json`, JSON.stringify(marks, null, 2));
console.log(dest);
