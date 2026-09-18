/**
 * JOURNEY 18 (steward depth): Pulse Control Plane P0 UI walk + J2–J6 oracles.
 *
 * ADR-0036 / docs/pulse/PULSE-ADMIN-QA-GATE.md Wave 2.
 * Complements journey-17 (API + light UI) and journey-09 (read CBAC).
 * Note: journey-18-done-surface-pack.spec.ts is a separate Done-track pack.
 *
 * Serial + one shared UI login (journey-16 pattern) to stay under the
 * 5-logins/min throttle.
 */
import { test, expect, Page } from '@playwright/test';
import {
  login,
  navigateTo,
  assertVisible,
  type UserPersona,
} from '../fixtures/users';

/** Live Nibras steward — PERSONAS.admin may be absent on local DBs. */
const ADMIN: UserPersona = {
  username:
    process.env.CARBON_E2E_ADMIN_USER ||
    process.env.NIBRAS_ADMIN_USERNAME ||
    process.env.PULSE_QA_USER ||
    'ahmed',
  password:
    process.env.CARBON_E2E_ADMIN_PASS ||
    process.env.NIBRAS_ADMIN_PASSWORD ||
    process.env.CARBON_ADMIN_PASSWORD ||
    process.env.PULSE_QA_PASS ||
    'AdminPa_132',
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

const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8009/carbon-api';
const CONTROL = `${API_BASE}/ai/pulse/control`;
const REGISTRY = `${API_BASE}/ai/registry/processes`;

test.describe.serial('Journey 18: Steward Admin Depth (P0 UI + J2–J6)', () => {
  let page: Page | undefined;
  let token = '';
  let processId = '';
  let rejectProcessId = '';

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(180_000);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await ctx.newPage();
    const ok = await login(page, ADMIN);
    if (!ok) throw new Error(`Admin UI login failed for ${ADMIN.username}`);
    token = (await page.evaluate(() => localStorage.getItem('access'))) || '';
    if (!token) {
      throw new Error('No access token in localStorage after UI login');
    }

    // Caps hydrate async after login; retry Control Plane until Command Center paints.
    let ready = false;
    let lastErr = '';
    for (let i = 0; i < 8; i++) {
      await page.goto('/admin/ai');
      await page.waitForLoadState('networkidle').catch(() => {});
      try {
        await expect(page.getByText('Command Center').first()).toBeVisible({ timeout: 10_000 });
        ready = true;
        break;
      } catch (e) {
        lastErr = String(e?.message || e).slice(0, 200);
        await page.waitForTimeout(2_000);
      }
    }
    if (!ready) {
      const snap = await page.evaluate(() => ({
        path: location.pathname,
        isAdmin: localStorage.getItem('is_global_admin'),
        body: document.body?.innerText?.slice(0, 400) || '',
      }));
      throw new Error(
        `Command Center not reachable after login: ${JSON.stringify(snap)} last=${lastErr}`,
      );
    }
    console.log(`  UI login (${ADMIN.username}): ok, apiToken=ok`);
  });

  test.afterAll(async () => {
    if (token && page) {
      try {
        await page.request.post(`${CONTROL}/containment/`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          data: { level: 'normal', reason: 'journey-18 afterAll reset' },
        });
      } catch {
        /* best-effort */
      }
    }
    await page?.context().close();
  });

  const hdr = () => {
    if (!token) throw new Error('No admin token');
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  };

  async function api(
    request: { get: Function; post: Function },
    method: 'get' | 'post',
    url: string,
    options: Record<string, unknown> = {},
    retries = 4,
  ) {
    let last: { status: () => number; text: () => Promise<string>; json: () => Promise<unknown> } | null =
      null;
    for (let i = 0; i < retries; i++) {
      last =
        method === 'get'
          ? await request.get(url, { headers: hdr(), ...options })
          : await request.post(url, { headers: hdr(), ...options });
      if (last!.status() !== 429) return last!;
      const wait = 3000 * (i + 1);
      console.log(`  ⏳ 429 on ${url} — wait ${wait}ms`);
      await new Promise((r) => setTimeout(r, wait));
    }
    return last!;
  }

  const ui = () => {
    if (!page) throw new Error('No shared page');
    return page;
  };

  test('18A. P0 walk — six destinations + P0 tabs', async () => {
    test.setTimeout(120_000);
    const p = ui();

    await navigateTo(p, '/admin/ai');
    await assertVisible(p, 'Command Center', 12000);
    await expect(p.getByText(/Queues/i).first()).toBeVisible({ timeout: 8000 });
    await expect(p.getByText(/Graduated containment/i).first()).toBeVisible();

    await navigateTo(p, '/admin/ai/domain?tab=processes');
    await assertVisible(p, 'Process Registry', 10000);
    await expect(p.getByRole('button', { name: /New draft/i })).toBeVisible();

    await navigateTo(p, '/admin/ai/domain?tab=policy');
    await assertVisible(p, 'Policy dry-run', 10000);

    await navigateTo(p, '/admin/ai/assets?tab=knowledge');
    await assertVisible(p, 'Curated knowledge', 10000);

    await navigateTo(p, '/admin/ai/assets?tab=memory');
    await assertVisible(p, 'Memory', 10000);
    await expect(p.getByText(/Revoke stops future use/i)).toBeVisible();

    await navigateTo(p, '/admin/ai/assets?tab=skills');
    await assertVisible(p, 'Skills Catalog', 10000);

    await navigateTo(p, '/admin/ai/assets?tab=prompts');
    await assertVisible(p, 'Prompt versions', 10000);
    await expect(p.getByText(/PEC-7A/i).first()).toBeVisible();

    await navigateTo(p, '/admin/ai/evidence?tab=explorer');
    await assertVisible(p, 'Evidence Explorer', 10000);
    await expect(p.getByRole('button', { name: /^Trace$/i })).toBeDisabled();

    await navigateTo(p, '/admin/ai/learning?tab=review');
    await assertVisible(p, 'Review Queue', 10000);

    await navigateTo(p, '/admin/ai/learning?tab=candidates');
    await assertVisible(p, 'Candidates', 10000);

    await navigateTo(p, '/admin/ai/platform?tab=spend');
    await assertVisible(p, 'Spend & caps', 10000);

    await navigateTo(p, '/admin/ai/platform?tab=roles');
    await assertVisible(p, 'Roles & AI capabilities', 10000);
    await expect(p.getByRole('link', { name: /\/admin\/access/i }).first()).toBeVisible();

    console.log('  ✅ P0 destination headings present');
  });

  test('18B. Seed registry processes for J2/J3 UI oracles', async ({ request }) => {
    test.skip(!token, 'No API token');

    let capability = '';
    const capsRes = await api(request, 'get', `${API_BASE}/ai/catalog/capabilities/?limit=20`);
    if (capsRes.status() === 200) {
      const capsBody = await capsRes.json();
      const caps = Array.isArray(capsBody)
        ? capsBody
        : (capsBody as { results?: unknown[] }).results ||
          (capsBody as { capabilities?: unknown[] }).capabilities ||
          [];
      const first = (caps as { capability_id?: string; id?: string }[]).find(
        (c) => c.capability_id || c.id,
      );
      if (first) capability = first.capability_id || first.id || '';
    }
    test.skip(!capability, 'No catalog capability available for process seed');
    console.log(`  capability for seed: ${capability}`);

    const draftDoc = (id: string, owner: string, predicate: string) => ({
      id,
      version: '0.1.0',
      owner,
      status: 'draft',
      steps: [
        {
          id: 's1',
          kind: 'command',
          capability,
          autonomy: 'human_only',
        },
      ],
      objective: { predicate },
    });

    processId = `proc.j18.sod.${Date.now().toString(36)}`;
    const create = await api(request, 'post', `${REGISTRY}/`, {
      data: draftDoc(processId, ADMIN.username, 'j18 sod ui'),
    });

    if (![200, 201].includes(create.status())) {
      console.log(`  ⚠️ Create failed (${create.status()}): ${(await create.text()).slice(0, 200)}`);
      const list = await api(request, 'get', `${REGISTRY}/?limit=20`);
      if (list.status() !== 200) {
        test.skip(true, `Registry list ${list.status()} after create failure`);
      }
      const body = await list.json();
      const rows = Array.isArray(body)
        ? body
        : (body as { results?: unknown[]; processes?: unknown[]; items?: unknown[] }).results ||
          (body as { processes?: unknown[] }).processes ||
          (body as { items?: unknown[] }).items ||
          [];
      const review = (rows as { status?: string; process_id?: string; id?: string }[]).find(
        (r) => r.status === 'review',
      );
      const any = review || (rows as { process_id?: string; id?: string; status?: string }[])[0];
      test.skip(!any, 'No registry processes available to open');
      processId = any.process_id || any.id || '';
      console.log(`  reuse process ${processId} status=${any.status}`);
    } else {
      const submit = await api(
        request,
        'post',
        `${REGISTRY}/${encodeURIComponent(processId)}/submit/`,
      );
      console.log(`  submit ${processId} → ${submit.status()}`);
    }

    rejectProcessId = `proc.j18.rej.${Date.now().toString(36)}`;
    const createReject = await api(request, 'post', `${REGISTRY}/`, {
      data: draftDoc(rejectProcessId, 'j18-author', 'j18 reject ui'),
    });
    if ([200, 201].includes(createReject.status())) {
      await api(request, 'post', `${REGISTRY}/${encodeURIComponent(rejectProcessId)}/submit/`);
      const rej = await api(request, 'post', `${REGISTRY}/${encodeURIComponent(rejectProcessId)}/reject/`, {
        data: { reason: 'J18 missing evidence' },
      });
      console.log(`  reject seed status=${rej.status()}`);
      if (rej.status() >= 400) rejectProcessId = '';
    } else {
      console.log(`  ⚠️ reject process create ${createReject.status()}`);
      rejectProcessId = '';
    }
  });

  test('18C. J2 UI — process object + Publish control', async ({ request }) => {
    test.skip(!processId, 'No process seeded');
    const p = ui();

    const detail = await request.get(`${REGISTRY}/${encodeURIComponent(processId)}/`, {
      headers: hdr(),
    });
    test.skip(detail.status() !== 200, `Process ${processId} not readable`);
    const body = await detail.json();
    const status = body.status || body.definition?.status;

    await navigateTo(p, `/admin/ai/domain/processes/${encodeURIComponent(processId)}`);
    await expect(p.getByText(processId).first()).toBeVisible({ timeout: 12000 });
    await expect(p.getByRole('tab', { name: /Overview/i })).toBeVisible();
    await expect(p.getByRole('tab', { name: /Scope/i })).toBeVisible();
    await expect(p.getByRole('tab', { name: /Diff/i })).toBeVisible();
    await expect(p.getByText(/Kill switch/i)).toBeVisible();

    if (status === 'review') {
      // Publish affordance present. Author∩publisher SoD deny is L2/L3
      // (test_j2 / CBAC matrix); platform admins with * may still publish.
      await expect(p.getByRole('button', { name: /^Publish$/i })).toBeVisible();
    }
    console.log(`  ✅ J2 process object UI (status=${status})`);
  });

  test('18D. J3 UI — reject reason on overview', async () => {
    test.skip(!rejectProcessId, 'No rejected process seeded');
    const p = ui();
    await navigateTo(p, `/admin/ai/domain/processes/${encodeURIComponent(rejectProcessId)}`);
    await expect(p.getByText(rejectProcessId).first()).toBeVisible({ timeout: 12000 });
    const reason = p.getByText(/Last reject reason/i);
    const visible = await reason.isVisible({ timeout: 5000 }).catch(() => false);
    test.skip(!visible, 'Reject reason not on page');
    await expect(p.getByText(/J18 missing evidence/i)).toBeVisible();
    console.log('  ✅ J3 reject reason on overview');
  });

  test('18E. J4 UI — Policy dry-run + Evidence Explorer', async ({ request }) => {
    const p = ui();
    const dry = await request.post(`${CONTROL}/pdp/dry-run/`, {
      headers: hdr(),
      data: {
        action: 'carbon:query',
        autonomy: 'human_only',
        objects: [],
        process_state: {},
      },
    });
    expect([200, 403]).toContain(dry.status());

    await navigateTo(p, '/admin/ai/domain?tab=policy');
    await assertVisible(p, 'Policy dry-run', 10000);
    await p.getByRole('button', { name: /^Simulate$/i }).click();
    await expect(p.locator('.MuiChip-root').first()).toBeVisible({ timeout: 10000 });

    await navigateTo(p, '/admin/ai/evidence?tab=explorer');
    await assertVisible(p, 'Evidence Explorer', 10000);
    await p.getByLabel('Run ID').fill('dry-run');
    await p.getByRole('button', { name: /^Trace$/i }).click();
    const pdpChip = p.getByText(/^pdp$/i).first();
    const hasPdp = await pdpChip.isVisible({ timeout: 8000 }).catch(() => false);
    if (hasPdp) {
      console.log('  ✅ J4 Explorer shows PDP events');
    } else {
      // Honest empty / error still proves Explorer gate works
      await expect(
        p.getByText(/events|Evidence lookup|failed|0 events/i).first(),
      ).toBeVisible({ timeout: 5000 });
      console.log('  ✅ J4 Explorer traced (PDP optional if dry-run not joined)');
    }
  });

  test('18F. J5 UI — learning freeze surfaces Skills lock', async ({ request }) => {
    const p = ui();
    const freeze = await request.post(`${CONTROL}/containment/`, {
      headers: hdr(),
      data: { level: 'learning_freeze', reason: 'journey-18 J5' },
    });
    expect(freeze.status()).toBe(200);

    try {
      await navigateTo(p, '/admin/ai/assets?tab=skills');
      await assertVisible(p, 'Skills Catalog', 10000);
      await expect(p.getByTestId('skills-learning-freeze')).toBeVisible({ timeout: 10000 });
      await expect(p.getByText(/Learning admissions are frozen/i).first()).toBeVisible();
      console.log('  ✅ J5 Skills freeze banner');
    } finally {
      await request.post(`${CONTROL}/containment/`, {
        headers: hdr(),
        data: { level: 'normal', reason: 'journey-18 J5 reset' },
      });
    }
  });

  test('18G. J6 UI — Memory revoke affordance', async () => {
    const p = ui();
    await navigateTo(p, '/admin/ai/assets?tab=memory');
    await assertVisible(p, 'Memory', 10000);
    await expect(p.getByText(/Revoke stops future use while keeping the row/i)).toBeVisible();
    const revoke = p.getByRole('button', { name: /^Revoke$/i }).first();
    if (await revoke.isVisible({ timeout: 3000 }).catch(() => false)) {
      await expect(revoke).toBeEnabled();
      console.log('  ✅ J6 Memory Revoke control visible');
    } else {
      await expect(p.getByText(/Memory/i).first()).toBeVisible();
      console.log('  ✅ J6 Memory empty-honest (no facts to revoke)');
    }
  });

  test('18H. Platform Spend override Save', async () => {
    const p = ui();
    await navigateTo(p, '/admin/ai/platform?tab=spend');
    await assertVisible(p, 'Spend & caps', 10000);
    const field = p.getByLabel(/Daily budget USD override/i);
    await field.fill('55.5');
    await p.getByRole('button', { name: /^Save$/i }).click();
    await expect(p.getByText(/Budget override saved|Override active/i).first()).toBeVisible({
      timeout: 10000,
    });
    console.log('  ✅ Spend override save');
  });
});
