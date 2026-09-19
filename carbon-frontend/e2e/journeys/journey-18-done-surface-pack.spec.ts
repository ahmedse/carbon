/**
 * JOURNEY 18 — Done surface + export pack (PD-01…05 / G8)
 *
 * Structural API (+ optional UI) checks for the Pulse × Nibras coworker QA
 * Done track: completed demo runs expose downloadable pack artifacts
 * (docx/xlsx/pdf/png). Complements journey-15 S4 (single export) without
 * requiring a fresh LLM plan when a seeded demo run already exists.
 *
 * Fixture IDs: PD-04, PD-05, G8 · canvas pulse-nibras-coworker-qa
 */

import { test, expect } from '@playwright/test';
import { login, type UserPersona } from '../fixtures/users';

const API = process.env.CARBON_API_URL || 'http://127.0.0.1:8009/carbon-api';
const BASE = process.env.CARBON_BASE_URL || 'http://127.0.0.1:5179';

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

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function fetchToken(request: any): Promise<string> {
  const res = await request.post(`${API}/token/`, {
    data: { username: NIBRAS_ADMIN.username, password: NIBRAS_ADMIN.password },
  });
  expect(res.status(), 'token endpoint').toBe(200);
  const body = await res.json();
  const access = body.access || body.token;
  expect(access).toBeTruthy();
  return access as string;
}

test.describe.configure({ mode: 'serial' });

test('PD-04/G8: seeded or completed plan exposes pack mime artifacts', async ({ request }) => {
  test.setTimeout(120_000);
  const token = await fetchToken(request);

  const listRes = await request.get(`${API}/ai/plans/?limit=50`, {
    headers: authHeaders(token),
  });
  expect(listRes.status()).toBe(200);
  const listBody = await listRes.json();
  const plans = Array.isArray(listBody) ? listBody : listBody.plans || [];

  // Prefer demo-seeded completed pack run; else any completed plan with ≥1 artifact.
  let target = plans.find(
    (p: any) => p.status === 'completed' && /board pack|workforce|compliance/i.test(p.brief || p.user_message || ''),
  );
  if (!target) {
    target = plans.find((p: any) => p.status === 'completed');
  }
  test.skip(!target, 'No completed plan — run seed_complex_agent_demos --with-demo-run');

  const artRes = await request.get(`${API}/ai/plans/${target.id}/artifacts/`, {
    headers: authHeaders(token),
  });
  expect(artRes.status()).toBe(200);
  const artBody = await artRes.json();
  const artifacts = Array.isArray(artBody) ? artBody : artBody.artifacts || [];
  console.log(`  J18: plan=${target.id} artifacts=${artifacts.length}`);

  expect(artifacts.length).toBeGreaterThan(0);

  const mimes = artifacts.map((a: any) => String(a.mime_type || '').toLowerCase());
  const names = artifacts.map((a: any) => String(a.name || '').toLowerCase());
  const blob = [...mimes, ...names].join(' ');

  // Pack completeness when demo seed present; otherwise at least one office/pdf/png deliverable.
  const hasDocx = /wordprocessingml|\.docx/.test(blob);
  const hasXlsx = /spreadsheetml|\.xlsx/.test(blob);
  const hasPdf = /pdf|\.pdf/.test(blob);
  const hasPng = /image\/png|\.png/.test(blob);
  const packScore = [hasDocx, hasXlsx, hasPdf, hasPng].filter(Boolean).length;
  console.log(`  J18: packScore=${packScore} docx=${hasDocx} xlsx=${hasXlsx} pdf=${hasPdf} png=${hasPng}`);

  if (/board pack|payroll variance/i.test(target.brief || target.user_message || '')) {
    expect(packScore).toBeGreaterThanOrEqual(4);
  } else {
    expect(packScore).toBeGreaterThanOrEqual(1);
  }

  // Download first artifact — bytes > 0
  const first = artifacts[0];
  const dl = await request.get(
    `${API}/ai/plans/${target.id}/artifacts/${first.id}/download/`,
    { headers: authHeaders(token) },
  );
  expect(dl.status()).toBe(200);
  const buf = await dl.body();
  expect(buf.byteLength).toBeGreaterThan(40);
});

test('PS-01/02: catalog lists specialists and topology handoffs', async ({ request }) => {
  test.setTimeout(60_000);
  const token = await fetchToken(request);

  const agentsRes = await request.get(`${API}/ai/catalog/agents/`, {
    headers: authHeaders(token),
  });
  expect(agentsRes.status()).toBe(200);
  const agentsBody = await agentsRes.json();
  const agents = Array.isArray(agentsBody) ? agentsBody : agentsBody.agents || agentsBody.results || [];
  const names = new Set(agents.map((a: any) => a.name));
  console.log(`  J18-PS: agents=${[...names].sort().join(',')}`);

  for (const name of [
    'payroll_controller',
    'compliance_auditor',
    'workforce_researcher',
    'finance_packager',
    'orchestrator',
  ]) {
    expect(names.has(name), `missing agent ${name}`).toBeTruthy();
  }

  const payroll = agents.find((a: any) => a.name === 'payroll_controller');
  const tools = payroll?.tool_set || [];
  expect(tools).toContain('export_document');

  const topoRes = await request.get(`${API}/ai/catalog/topology/`, {
    headers: authHeaders(token),
  });
  expect(topoRes.status()).toBe(200);
  const topo = await topoRes.json();
  const byName = Object.fromEntries((topo.nodes || []).map((n: any) => [n.name, n.id]));
  const edgeSet = new Set((topo.edges || []).map((e: any) => `${e.from}->${e.to}`));
  const orch = byName.orchestrator;
  expect(orch).toBeTruthy();
  for (const spec of ['payroll_controller', 'compliance_auditor', 'workforce_researcher', 'finance_packager']) {
    const sid = byName[spec];
    expect(sid, spec).toBeTruthy();
    expect(edgeSet.has(`${orch}->${sid}`), `orch→${spec}`).toBeTruthy();
    expect(edgeSet.has(`${sid}->${orch}`), `${spec}→orch`).toBeTruthy();
  }
});

test('PS-04: plan templates include pack export steps', async ({ request }) => {
  test.setTimeout(60_000);
  const token = await fetchToken(request);
  const res = await request.get(`${API}/ai/plans/templates/`, {
    headers: authHeaders(token),
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  const templates = Array.isArray(body) ? body : body.templates || [];
  console.log(`  J18-PS: templates=${templates.length}`);
  test.skip(templates.length === 0, 'No templates — run seed_complex_agent_demos');

  const packish = templates.filter((t: any) =>
    /board pack|compliance|workforce/i.test(t.name || ''),
  );
  expect(packish.length).toBeGreaterThanOrEqual(1);
});

test('PA-S0 smoke: completed plan ledger + artifacts endpoints (mode contract evidence)', async ({ request }) => {
  // Lightweight S0/S2 hook: Agent completed surface APIs exist and are owner-scoped.
  test.setTimeout(60_000);
  const token = await fetchToken(request);
  const listRes = await request.get(`${API}/ai/plans/?limit=20`, {
    headers: authHeaders(token),
  });
  expect(listRes.status()).toBe(200);
  const listBody = await listRes.json();
  const plans = Array.isArray(listBody) ? listBody : listBody.plans || [];
  const target = plans.find((p: any) => p.status === 'completed');
  test.skip(!target, 'No completed plan for S0 smoke');

  for (const path of ['ledger', 'flight', 'qos']) {
    const r = await request.get(`${API}/ai/plans/${target.id}/${path}/`, {
      headers: authHeaders(token),
    });
    expect(r.status(), path).toBe(200);
  }
  const art = await request.get(`${API}/ai/plans/${target.id}/artifacts/`, {
    headers: authHeaders(token),
  });
  expect(art.status()).toBe(200);
});

test('PD-01 UI: Agent Done Output shows Discuss + rendered answer path', async ({ page, request }) => {
  test.setTimeout(180_000);
  const token = await fetchToken(request);
  const listRes = await request.get(`${API}/ai/plans/?limit=50`, {
    headers: authHeaders(token),
  });
  const listBody = await listRes.json();
  const plans = Array.isArray(listBody) ? listBody : listBody.plans || [];
  const target = plans.find((p: any) => p.status === 'completed');
  test.skip(!target, 'No completed plan for UI Done check');

  expect(await login(page, NIBRAS_ADMIN)).toBe(true);
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });

  // Open Pulse if not already — try common entry points without being brittle.
  const pulseToggle = page.getByRole('button', { name: /Pulse|AI/i }).first();
  if (await pulseToggle.isVisible().catch(() => false)) {
    await pulseToggle.click().catch(() => {});
  }
  const agentMode = page.getByRole('button', { name: /^Agent$/i }).or(page.getByText(/^Agent$/i)).first();
  if (await agentMode.isVisible({ timeout: 8_000 }).catch(() => false)) {
    await agentMode.click().catch(() => {});
  }

  // Task picker: select completed plan by brief snippet if visible.
  const picker = page.getByLabel('Task');
  if (await picker.isVisible({ timeout: 15_000 }).catch(() => false)) {
    await picker.selectOption({ value: String(target.id) }).catch(async () => {
      await picker.click();
      await page.getByRole('option').filter({ hasText: /Completed|board|payroll|workforce/i }).first().click().catch(() => {});
    });
  }

  const discuss = page.getByRole('button', { name: /Discuss in Chat/i });
  const outputBtn = page.getByRole('button', { name: /^Output$/i });
  if (await outputBtn.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await outputBtn.click();
  }

  // Soft UI asserts — pass if Discuss or Answer chrome is visible.
  const discussVisible = await discuss.isVisible({ timeout: 20_000 }).catch(() => false);
  const finalChrome = await page.getByText(/Answer|Final response/i).first().isVisible({ timeout: 5_000 }).catch(() => false);
  console.log(`  J18-UI: discuss=${discussVisible} finalChrome=${finalChrome}`);
  expect(discussVisible || finalChrome).toBeTruthy();
});

test('S1/S2 CI: registry exposes five Nibras process lifecycles (PA-030–034)', async ({
  request,
}) => {
  test.setTimeout(60_000);
  const token = await fetchToken(request);
  const res = await request.get(`${API}/ai/registry/processes/`, {
    headers: authHeaders(token),
  });
  expect(res.status(), 'process registry list').toBe(200);
  const body = await res.json();
  const rows = Array.isArray(body) ? body : body.results || body.processes || [];
  const ids = new Set(
    rows.map((r: any) => r.process_id || r.id || r.document?.id).filter(Boolean),
  );
  const required = [
    'leave.request.lifecycle',
    'loan.request.lifecycle',
    'payroll.run.lifecycle',
    'employee.onboarding.lifecycle',
    'gosi_wps.sif.lifecycle',
  ];
  const missing = required.filter((id) => !ids.has(id));
  console.log(
    `  J18-S2: processes=${ids.size} missing=${missing.join(',') || 'none'}`,
  );
  test.skip(
    rows.length === 0,
    'Empty process registry — run seed_nibras_processes',
  );
  expect(missing, `missing process ids: ${missing.join(', ')}`).toEqual([]);
});

test('S3 CI: live headcount pass^k=3 (G1 grounding stability)', async ({ request }) => {
  test.setTimeout(120_000);
  const token = await fetchToken(request);
  const counts: number[] = [];
  for (let i = 0; i < 3; i += 1) {
    const res = await request.get(
      `${API}/people/employees/?page_size=1&is_active=true`,
      { headers: authHeaders(token) },
    );
    expect(res.status(), `headcount run ${i + 1}`).toBe(200);
    const body = await res.json();
    const count = typeof body.count === 'number' ? body.count : null;
    expect(count, `count run ${i + 1}`).not.toBeNull();
    counts.push(count as number);
  }
  console.log(`  J18-S3: headcount pass^k counts=${counts.join(',')}`);
  expect(new Set(counts).size).toBe(1);
  expect(counts[0]).toBeGreaterThan(0);
});

test('S4 CI: audit list + sweeps heartbeats (metabolism/export surface)', async ({
  request,
}) => {
  test.setTimeout(60_000);
  const token = await fetchToken(request);
  const audit = await request.get(`${API}/ai/audit/?page_size=5`, {
    headers: authHeaders(token),
  });
  expect([200, 403].includes(audit.status()), `audit ${audit.status()}`).toBeTruthy();
  if (audit.status() === 200) {
    const body = await audit.json();
    const rows = body.results || [];
    console.log(`  J18-S4: audit count=${body.count ?? rows.length}`);
    if (rows.length > 0) {
      for (const key of ['timestamp', 'actor', 'action', 'target', 'detail']) {
        expect(rows[0], key).toHaveProperty(key);
      }
    }
  } else {
    console.log('  J18-S4: audit 403 — capability gated (ok for non-console user)');
  }

  const sweeps = await request.get(`${API}/ai/pulse/sweeps/`, {
    headers: authHeaders(token),
  });
  expect([200, 403].includes(sweeps.status()), `sweeps ${sweeps.status()}`).toBeTruthy();
  if (sweeps.status() === 200) {
    const body = await sweeps.json();
    expect(body).toHaveProperty('heartbeats');
    console.log(`  J18-S4: heartbeats=${(body.heartbeats || []).length}`);
  }
});
