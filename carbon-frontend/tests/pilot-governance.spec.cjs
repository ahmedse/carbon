/**
 * P3-12 — Pilot end-to-end governance acceptance tests (Playwright).
 *
 * Complements backend/ai/tests/pilot/test_pilot_e2e.py. This spec drives the
 * HTTP surface of the governed `dq.rule.release` pilot loop end-to-end and then
 * smoke-checks the two governance UI routes.
 *
 * Mapping to the five pilot scenarios
 * (docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md §P3-12):
 *   1. Restart survival        → "a created draft survives fresh reads"
 *   2. Concurrent edit         → covered by the backend suite (ApprovalGrant
 *                                fail-closed on version/revision bump); the
 *                                HTTP-observable duplicate-submit guard is
 *                                asserted here.
 *   3. Duplicate submit        → "second submit is refused…"
 *   4. Revoked permission      → "deactivating ai:publisher blocks publish…"
 *   5. Self-approval refused   → "create → submit → self-publish 403…"
 *
 * Auth is JWT via {API_BASE}/token/. Users/groups/roles are self-provisioned
 * through the accounts API under the seeded superuser so the spec never depends
 * on pre-existing tenant data.
 *
 * Test isolation: `fullyParallel` is enabled in playwright.config.cjs, so each
 * test mints a UNIQUE process id (suffix) for the same pilot definition. The
 * registry is keyed by the document `id` (the `process_id` column), which keeps
 * every scenario hermetic even when tests run concurrently.
 *
 * Config (env overrides mirror CI .github/workflows/ci.yml e2e job):
 *   CARBON_API_URL    default http://localhost:8009/carbon-api
 *   CARBON_BASE_URL   default http://localhost:8009
 *   CARBON_ADMIN_USER default admin   (CI seed: admin/admin123)
 *   CARBON_ADMIN_PASS default admin123
 *
 * Run:  cd carbon-frontend && npx playwright test tests/pilot-governance.spec.cjs
 */

const { test, expect } = require('@playwright/test');

// ─── Configuration ───────────────────────────────────────────────────────────
const API_BASE = (process.env.CARBON_API_URL || 'http://localhost:8009/carbon-api').replace(/\/+$/, '');
const BASE_URL = (process.env.CARBON_BASE_URL || 'http://localhost:8009').replace(/\/+$/, '');
const ADMIN_USER = process.env.CARBON_ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.CARBON_ADMIN_PASS || 'admin123';

const REGISTRY = '/ai/registry/processes';
const OWNER_GROUP = 'ai_process_owner_group';
const PUBLISHER_GROUP = 'ai_publisher_group';
const USER_PASS = 'PilotPass_123!';

let adminToken = null;

/** Unique, test-scoped process id for the canonical pilot definition. */
function pilotProcessId(tag) {
  const suffix = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return `dq.rule.release.e2e.${tag}.${suffix}`;
}

/** Minimal, validation-passing pilot definition (mirrors
 *  domain_packs/carbon/processes/dq.rule.release.yaml). The registry `create`
 *  action overwrites `owner` and `status`, so only id/version/steps matter. */
function makePilotDocument(processId) {
  return {
    id: processId,
    version: '1.0',
    owner: 'ai',
    status: 'draft',
    steps: [
      { id: 'validate', kind: 'command', capability: 'dq.rule.validate', depends_on: [], autonomy: 'act_notify' },
      { id: 'review', kind: 'human_task', capability: 'dq.rule.review', depends_on: ['validate'], autonomy: 'human_only' },
      { id: 'publish', kind: 'command', capability: 'dq.rule.publish', depends_on: ['review'], autonomy: 'act_confirm' },
      { id: 'verify', kind: 'assertion', capability: 'dq.rule.active_revision_matches_approved_revision', depends_on: ['publish'], autonomy: 'observe' },
    ],
  };
}

// ─── Auth + HTTP helpers ─────────────────────────────────────────────────────

async function getAdminToken(request) {
  if (adminToken) return adminToken;
  const res = await request.post(`${API_BASE}/token/`, {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  expect(res.status(), `admin login for ${ADMIN_USER} failed`).toBe(200);
  const body = await res.json();
  adminToken = body.access;
  return adminToken;
}

async function getToken(request, username, password) {
  const res = await request.post(`${API_BASE}/token/`, {
    data: { username, password },
  });
  expect(res.status(), `login for ${username} failed`).toBe(200);
  const body = await res.json();
  return body.access;
}

const auth = (token) => ({ Authorization: `Bearer ${token}` });

const httpGet = (request, path, token) =>
  request.get(`${API_BASE}${path}`, { headers: auth(token) });
const httpPost = (request, path, token, data = null) =>
  request.post(`${API_BASE}${path}`, { headers: auth(token), data });
const httpPatch = (request, path, token, data = {}) =>
  request.patch(`${API_BASE}${path}`, { headers: auth(token), data });

/** List endpoint bodies are either a raw array (registry) or a paginated
 *  `{results: [...]}` envelope (DRF viewsets). Return the array either way. */
async function listAll(request, token, path) {
  const res = await httpGet(request, path, token);
  expect(res.status()).toBe(200);
  const body = await res.json();
  return Array.isArray(body) ? body : (body.results ?? []);
}

// ─── Provisioning helpers (idempotent) ───────────────────────────────────────

async function ensureGroup(request, admin, name) {
  const found = (await listAll(request, admin, '/accounts/groups/?page_size=200'))
    .find((g) => g.name === name);
  if (found) return found.id;

  const res = await httpPost(request, '/accounts/groups/', admin, { name });
  if (res.status() === 201) return (await res.json()).id;

  // Race fallback: another worker created it.
  const again = (await listAll(request, admin, '/accounts/groups/?page_size=200'))
    .find((g) => g.name === name);
  expect(again, `group ${name} should exist`).toBeTruthy();
  return again.id;
}

async function ensureUser(request, admin, username, password) {
  const res = await httpPost(request, '/accounts/users/', admin, {
    username, password, is_active: true,
  });
  if (res.status() === 201) return (await res.json()).id;

  // Race fallback: user already provisioned.
  const found = (await listAll(request, admin, '/accounts/users/?page_size=200'))
    .find((u) => u.username === username);
  expect(found, `user ${username} should exist`).toBeTruthy();
  return found.id;
}

async function assignGlobalRole(request, admin, userId, groupId) {
  const res = await httpPost(request, '/accounts/scoped-roles/', admin, {
    user: userId, group: groupId, org_unit: null, module: null, is_active: true,
  });
  expect(res.status(), 'assign global role').toBe(201);
}

/** Deactivate a user's global scoped role (revoke the capability). */
async function deactivateRole(request, admin, username, groupName) {
  const role = (await listAll(request, admin, '/accounts/scoped-roles/?page_size=200'))
    .find((r) => r.user === username && r.group === groupName && r.is_active === true);
  expect(role, `active scoped role ${groupName} for ${username}`).toBeTruthy();
  const res = await httpPatch(request, `/accounts/scoped-roles/${role.id}/`, admin, { is_active: false });
  expect(res.status()).toBe(200);
}

// ─── Registry actions ────────────────────────────────────────────────────────

async function createDraft(request, token, processId) {
  const res = await httpPost(request, `${REGISTRY}/`, token, makePilotDocument(processId));
  expect(res.status(), 'create draft').toBe(201);
  return res.json();
}

async function latest(request, token, processId) {
  const res = await httpGet(request, `${REGISTRY}/${processId}/`, token);
  expect(res.status()).toBe(200);
  return res.json();
}

// ─── Scenario 1 — restart survival (HTTP) ────────────────────────────────────

test.describe('P3-12 · scenario 1 — restart survival', () => {
  test('a created draft survives independent fresh reads', async ({ request }) => {
    const admin = await getAdminToken(request);
    const processId = pilotProcessId('restart');

    const draft = await createDraft(request, admin, processId);
    expect(draft.status).toBe('draft');
    expect(draft.process_id).toBe(processId);
    expect(draft.owner).toBe(ADMIN_USER);

    // Two reads over two fresh requests — no shared client state, which is the
    // HTTP-level analogue of a service restart (the row lives in the DB).
    const read1 = await latest(request, admin, processId);
    const read2 = await latest(request, admin, processId);
    expect(read1.status).toBe('draft');
    expect(read2.status).toBe('draft');
    expect(read1.version).toBe(read2.version);
    expect(read1.process_id).toBe(processId);
    expect(read1.owner).toBe(ADMIN_USER);
  });
});

// ─── Scenario 5 + loop — self-approval refused; publish by a different user ──

test.describe('P3-12 · scenario 5 — self-approval refused (and publish by another)', () => {
  test('create draft → submit → self-publish 403 → publish by different user → deprecate', async ({ request }) => {
    const admin = await getAdminToken(request);
    const processId = pilotProcessId('loop');
    const authorUser = `gov_author_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const publisherUser = `gov_pub_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

    const authorId = await ensureUser(request, admin, authorUser, USER_PASS);
    const publisherId = await ensureUser(request, admin, publisherUser, USER_PASS);
    const ownerGroup = await ensureGroup(request, admin, OWNER_GROUP);
    const pubGroup = await ensureGroup(request, admin, PUBLISHER_GROUP);

    // The author holds BOTH capabilities. That clears the publisher capability
    // gate yet is still refused on separation-of-duties grounds — the point of
    // the self-approval scenario.
    await assignGlobalRole(request, admin, authorId, ownerGroup);
    await assignGlobalRole(request, admin, authorId, pubGroup);
    await assignGlobalRole(request, admin, publisherId, pubGroup);

    const authorTok = await getToken(request, authorUser, USER_PASS);
    const publisherTok = await getToken(request, publisherUser, USER_PASS);

    const draft = await createDraft(request, authorTok, processId);
    expect(draft.owner).toBe(authorUser);

    const submitRes = await httpPost(request, `${REGISTRY}/${processId}/submit/`, authorTok);
    expect(submitRes.status()).toBe(200);
    expect((await submitRes.json()).status).toBe('review');

    const selfPub = await httpPost(request, `${REGISTRY}/${processId}/publish/`, authorTok);
    expect(selfPub.status()).toBe(403);
    expect((await selfPub.json()).error).toBe('forbidden');

    const pubRes = await httpPost(request, `${REGISTRY}/${processId}/publish/`, publisherTok);
    expect(pubRes.status()).toBe(200);
    expect((await pubRes.json()).status).toBe('active');

    const depRes = await httpPost(request, `${REGISTRY}/${processId}/deprecate/`, authorTok);
    expect(depRes.status()).toBe(200);
    expect((await depRes.json()).status).toBe('deprecated');
  });
});

// ─── Scenario 3 — duplicate submit has no duplicate effect ───────────────────

test.describe('P3-12 · scenario 3 — duplicate submit has no duplicate effect', () => {
  test('second submit is refused and the document stays in review once', async ({ request }) => {
    const admin = await getAdminToken(request);
    const processId = pilotProcessId('dup');

    await createDraft(request, admin, processId);

    const submit1 = await httpPost(request, `${REGISTRY}/${processId}/submit/`, admin);
    expect(submit1.status()).toBe(200);
    expect((await submit1.json()).status).toBe('review');

    // Duplicate submit → illegal transition; no new row, no state change.
    const submit2 = await httpPost(request, `${REGISTRY}/${processId}/submit/`, admin);
    expect(submit2.status()).toBe(400);
    expect((await submit2.json()).error).toBe('invalid');

    const current = await latest(request, admin, processId);
    expect(current.status).toBe('review');
    expect(current.process_id).toBe(processId);

    // The registry list collapses versions to one entry per process id.
    const list = await listAll(request, admin, `${REGISTRY}/`);
    expect(list.filter((r) => r.process_id === processId)).toHaveLength(1);
  });
});

// ─── Scenario 4 — revoked permission blocks publish ──────────────────────────

test.describe('P3-12 · scenario 4 — revoked permission blocks publish', () => {
  test('deactivating ai:publisher blocks publish and keeps the document in review', async ({ request }) => {
    const admin = await getAdminToken(request);
    const processId = pilotProcessId('revoke');
    const authorUser = `gov_author_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const publisherUser = `gov_pub_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

    const authorId = await ensureUser(request, admin, authorUser, USER_PASS);
    const publisherId = await ensureUser(request, admin, publisherUser, USER_PASS);
    const ownerGroup = await ensureGroup(request, admin, OWNER_GROUP);
    const pubGroup = await ensureGroup(request, admin, PUBLISHER_GROUP);

    await assignGlobalRole(request, admin, authorId, ownerGroup);
    await assignGlobalRole(request, admin, publisherId, pubGroup);

    const authorTok = await getToken(request, authorUser, USER_PASS);
    const publisherTok = await getToken(request, publisherUser, USER_PASS);

    // Baseline: publisher CAN publish a review the author created.
    await createDraft(request, authorTok, processId);
    await httpPost(request, `${REGISTRY}/${processId}/submit/`, authorTok);
    const pub1 = await httpPost(request, `${REGISTRY}/${processId}/publish/`, publisherTok);
    expect(pub1.status()).toBe(200);
    expect((await pub1.json()).status).toBe('active');

    // New draft + submit → review.
    const draft2 = await createDraft(request, authorTok, processId);
    expect(draft2.status).toBe('draft');
    await httpPost(request, `${REGISTRY}/${processId}/submit/`, authorTok);

    // Revoke the publisher's global role.
    await deactivateRole(request, admin, publisherUser, PUBLISHER_GROUP);

    // Publish now fails with 403.
    const pub2 = await httpPost(request, `${REGISTRY}/${processId}/publish/`, publisherTok);
    expect(pub2.status()).toBe(403);

    // Document remains in review (no partial publish).
    const current = await latest(request, authorTok, processId);
    expect(current.status).toBe('review');
  });
});

// ─── UI smoke — governance routes render ─────────────────────────────────────

test.describe('P3-12 · UI smoke — governance routes render', () => {
  test('Process Registry and Review Queue render their headings', async ({ page, request }) => {
    const token = await getAdminToken(request);

    // Seed a logged-in superuser session before the app boots. `is_global_admin`
    // short-circuits the AdminRoute capability gate; `available_perspectives`
    // is a fallback if the app's async me/context refresh rewrites the flag.
    await page.addInitScript(([t, u]) => {
      localStorage.setItem('user', JSON.stringify({ id: null, username: u, token: t, refresh: t, roles: [] }));
      localStorage.setItem('access', t);
      localStorage.setItem('refresh', t);
      localStorage.setItem('is_global_admin', '1');
      localStorage.setItem('user_capabilities', JSON.stringify(['*']));
      localStorage.setItem('available_perspectives', JSON.stringify(['admin']));
    }, [token, ADMIN_USER]);

    await page.goto(`${BASE_URL}/admin/ai/registry`);
    await expect(page.getByRole('heading', { name: 'Process Registry' })).toBeVisible();

    await page.goto(`${BASE_URL}/admin/ai/review-queue`);
    await expect(page.getByRole('heading', { name: 'Review Queue' })).toBeVisible();
  });
});
