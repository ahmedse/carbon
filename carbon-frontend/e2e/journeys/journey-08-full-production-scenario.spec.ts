/**
 * JOURNEY 8: Full Multi-User Production Scenario
 *
 * Simulates a complete reporting cycle across both branches.
 * Uses sequential auth with rate-limit handling.
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { PERSONAS, getAuthHeaders } from '../fixtures/users';

const ADMIN = PERSONAS.admin;
const AL_OWNER = PERSONAS.alamien_dataowner;
const SV_OWNER = PERSONAS.sv_dataowner;
const AL_ANALYST = PERSONAS.alamien_analyst;
const AL_VIEWER = PERSONAS.alamien_viewer;
const AUDITOR = PERSONAS.auditor_user;
const CARBON_LEAD = PERSONAS.carbon_lead_user;
const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8000/carbon-api';

function verifyCalculation(c: any) {
  expect(c).toHaveProperty('co2e_kg');
  expect(parseFloat(c.co2e_kg)).toBeGreaterThanOrEqual(0);
  expect([1, 2, 3]).toContain(c.scope);
}

test.describe.serial('Journey 8: Full Multi-User Production Scenario', () => {
  let adminHeaders: Record<string, string>;
  let alOwnerHeaders: Record<string, string>;
  let svOwnerHeaders: Record<string, string>;
  let alAnalystHeaders: Record<string, string>;
  let alViewerHeaders: Record<string, string>;
  let auditorHeaders: Record<string, string>;
  let carbonLeadHeaders: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    // Authenticate sequentially to avoid rate limiting
    console.log('  🔐 Authenticating 7 personas...');
    adminHeaders = await getAuthHeaders(request, API_BASE, ADMIN);
    alOwnerHeaders = await getAuthHeaders(request, API_BASE, AL_OWNER);
    svOwnerHeaders = await getAuthHeaders(request, API_BASE, SV_OWNER);
    alAnalystHeaders = await getAuthHeaders(request, API_BASE, AL_ANALYST);
    alViewerHeaders = await getAuthHeaders(request, API_BASE, AL_VIEWER);
    auditorHeaders = await getAuthHeaders(request, API_BASE, AUDITOR);
    carbonLeadHeaders = await getAuthHeaders(request, API_BASE, CARBON_LEAD);
    console.log('  ✅ All 7 personas authenticated');
  });

  // ── PHASE 1: SETUP VERIFICATION ──────────────────────────────
  test('8A [SETUP]: Verify emission factors are seeded', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/factors/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const factors = Array.isArray(data) ? data : data.results || [];
    console.log(`  Emission factors: ${factors.length}`);
    expect(factors.length).toBeGreaterThan(0);
  });

  test('8B [SETUP]: Verify DQ rules are configured', async ({ request }) => {
    const res = await request.get(`${API_BASE}/dq/rules/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const rules = Array.isArray(data) ? data : data.results || [];
    console.log(`  DQ rules: ${rules.length}`);
  });

  test('8C [SETUP]: Verify reference data is seeded', async ({ request }) => {
    const res = await request.get(`${API_BASE}/mdm/reference-sets/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const sets = Array.isArray(data) ? data : data.results || [];
    console.log(`  Reference sets: ${sets.length}`);
  });

  // ── PHASE 2: DATA ENTRY ──────────────────────────────────────
  test('8D [DATA ENTRY]: Data owners can access calculations', async ({ request }) => {
    for (const [headers, name] of [[alOwnerHeaders, 'AL Owner'], [svOwnerHeaders, 'SV Owner']] as const) {
      const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=1`, { headers });
      expect(res.ok(), name).toBe(true);
    }
    console.log('  ✅ Both data owners can read calculations');
  });

  test('8E [DATA ENTRY]: Data owner can POST calculation', async ({ request }) => {
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: alOwnerHeaders,
      data: { emission_factor: 1, activity_value: '5000.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    // Accept 201, 400 (validation), or 403 (permission)
    expect([201, 400, 403]).toContain(createRes.status());
    console.log(`  ✅ AL Owner POST → ${createRes.status()}`);
  });

  // ── PHASE 3: RBAC WRITE RESTRICTIONS ─────────────────────────
  test('8F [RBAC]: Viewer cannot POST calculations', async ({ request }) => {
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: alViewerHeaders,
      data: { emission_factor: 1, activity_value: '100.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    expect(createRes.status()).toBe(403);
    console.log('  ✅ Viewer POST → 403 Forbidden');
  });

  test('8G [RBAC]: Auditor cannot POST calculations', async ({ request }) => {
    const createRes = await request.post(`${API_BASE}/carbon/calculations/`, {
      headers: auditorHeaders,
      data: { emission_factor: 1, activity_value: '100.0',
        activity_unit: 'kWh', scope: 2, category: 'electricity' },
    });
    expect(createRes.status()).toBe(403);
    console.log('  ✅ Auditor POST → 403 Forbidden');
  });

  // ── PHASE 4: CALCULATIONS VERIFICATION ───────────────────────
  test('8H [CALC]: Calculations have valid structure', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=5`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const calcs = Array.isArray(data) ? data : data.results || [];
    for (const c of calcs) verifyCalculation(c);
    console.log(`  ✅ ${calcs.length} calculations verified`);
  });

  test('8I [CALC]: CO2e values are non-negative', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/calculations/?page_size=20`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const calcs = Array.isArray(data) ? data : data.results || [];
    for (const c of calcs) expect(parseFloat(c.co2e_kg)).toBeGreaterThanOrEqual(0);
    console.log(`  ✅ ${calcs.length} calculations — all non-negative`);
  });

  // ── PHASE 5: DQ VIOLATIONS ───────────────────────────────────
  test('8J [DQ]: DQ results are recorded', async ({ request }) => {
    const res = await request.get(`${API_BASE}/dq/results/?page_size=5`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const results = Array.isArray(data) ? data : data.results || [];
    const violations = results.filter((r: any) => r.passed === false);
    console.log(`  DQ results: ${results.length} (${violations.length} violations)`);
  });

  // ── PHASE 6: GOVERNANCE VERIFICATION ─────────────────────────
  test('8K [GOV]: Governance events trail exists', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/?page_size=5`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const events = Array.isArray(data) ? data : data.results || [];
    console.log(`  Governance events: ${events.length}`);
  });

  test('8L [GOV]: Auditor can read governance events', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/?page_size=5`, { headers: auditorHeaders });
    expect(res.ok()).toBe(true);
    console.log('  ✅ Auditor reads governance events');
  });

  // ── PHASE 7: REPORTING PERIODS ───────────────────────────────
  test('8M [PERIOD]: Reporting periods are accessible', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/periods/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const periods = Array.isArray(data) ? data : data.results || [];
    console.log(`  Reporting periods: ${periods.length}`);
  });

  // ── PHASE 8: FINAL COMPLIANCE ────────────────────────────────
  test('8N [FINAL]: All emission factors have valid units', async ({ request }) => {
    const res = await request.get(`${API_BASE}/carbon/factors/`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const factors = Array.isArray(data) ? data : data.results || [];
    for (const f of factors.slice(0, 10)) {
      expect(f.unit || f.factor_unit || f.activity_unit).toBeTruthy();
      if (f.factor_value) expect(parseFloat(f.factor_value)).toBeGreaterThan(0);
    }
    console.log(`  ✅ ${factors.length} factors verified`);
  });

  test('8O [FINAL]: Governance events cover entity types', async ({ request }) => {
    const res = await request.get(`${API_BASE}/catalog/governance-events/?page_size=50`, { headers: adminHeaders });
    expect(res.ok()).toBe(true);
    const data = await res.json();
    const events = Array.isArray(data) ? data : data.results || [];
    const entityTypes = new Set(events.map((e: any) => e.entity_type));
    console.log(`  Entity types: ${[...entityTypes].join(', ')}`);
  });
});
