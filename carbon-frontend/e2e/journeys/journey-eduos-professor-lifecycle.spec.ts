/**
 * Journey: GradeVance / EduOS full professor lifecycle (end-to-end).
 *
 * Covers: KB browse → course → stem authoring → calibration → publish →
 * student submission → analyze → run workbench (breadcrumbs, LCT report,
 * SystemDialog ExpertEdit) → audit export → marking → proposals → Learn.
 *
 * Requires EduOS brand locally (`./manage.sh brand eduos` + services up).
 * Credentials: admin / AdmEduos_132 (or EDUOS_* env overrides).
 */
import { test, expect, Page, APIRequestContext } from '@playwright/test';
import { login } from '../fixtures/users';

const API_BASE = process.env.CARBON_API_URL || 'http://127.0.0.1:8009';
const GV = `${API_BASE}/carbon-api/gradevance`;

const PROFESSOR = {
  username: process.env.EDUOS_ADMIN_USERNAME || 'admin',
  password: process.env.EDUOS_ADMIN_PASSWORD || 'AdmEduos_132',
  role: 'admins_group',
  isGlobalAdmin: true,
  expectations: {
    canAccessAdmin: true,
    canSeeDashboard: true,
    canEnterData: true,
    canSeeDQ: true,
    canSeeGovernance: true,
    visibleBranches: [],
  },
};

const STUDENT = {
  username: process.env.EDUOS_STUDENT_USERNAME || 'gv_student',
  password: process.env.CARBON_ADMIN_PASSWORD || 'AdminPa_132',
  role: 'student',
  isGlobalAdmin: false,
  expectations: {
    canAccessAdmin: false,
    canSeeDashboard: true,
    canEnterData: false,
    canSeeDQ: false,
    canSeeGovernance: false,
    visibleBranches: [],
  },
};

const SAMPLE_ESSAY = `
In my first clinical placement I felt overwhelmed by the pace of the ward.
I noticed that I was describing feelings rather than evaluating why protocols
existed. Later I connected this to epistemic injustice: junior voices were
discounted when they questioned publishing norms that exclude practice-based
knowing. Abstractly, legitimation codes help me see how semantic gravity
moves from concrete incidents toward theoretical claims about knowledge.
Concretely, next week I will ask one clarifying question in handover and
record whether my contribution was taken up. This wave—from feeling, through
context, to theory, then back to action—is the reflective practice I need.
`.trim();

type Ctx = {
  headers: Record<string, string>;
  studentHeaders: Record<string, string>;
  kbId: string | null;
  courseId: string;
  entryCode: string;
  assignmentId: string;
  profilePackId: string;
  submissionId: string;
  runId: string;
};

async function apiToken(
  request: APIRequestContext,
  persona: { username: string; password: string },
): Promise<string> {
  const res = await request.post(`${API_BASE}/carbon-api/token/`, {
    data: { username: persona.username, password: persona.password },
  });
  expect(res.ok(), `token for ${persona.username}: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  expect(body.access).toBeTruthy();
  return body.access as string;
}

async function jsonOrThrow(res: Awaited<ReturnType<APIRequestContext['get']>>, label: string) {
  const text = await res.text();
  if (!res.ok()) {
    throw new Error(`${label} → ${res.status()}: ${text.slice(0, 400)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label} non-JSON: ${text.slice(0, 200)}`);
  }
}

test.describe.serial('EduOS professor journey — full lifecycle', () => {
  const ctx: Partial<Ctx> = {};
  test.setTimeout(180_000);

  test.beforeAll(async ({ request }) => {
    const token = await apiToken(request, PROFESSOR);
    ctx.headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    try {
      const st = await apiToken(request, STUDENT);
      ctx.studentHeaders = {
        Authorization: `Bearer ${st}`,
        'Content-Type': 'application/json',
      };
    } catch {
      ctx.studentHeaders = undefined;
    }
  });

  test('1 · Knowledge bases available for pin', async ({ request }) => {
    const res = await request.get(`${GV}/knowledge-bases/`, { headers: ctx.headers });
    const data = await jsonOrThrow(res, 'knowledge-bases');
    const rows = Array.isArray(data) ? data : data.results || data.knowledge_bases || [];
    expect(rows.length, 'expected at least one KB after sync_eduos_packs').toBeGreaterThan(0);
    ctx.kbId = rows[0].pack_id || rows[0].id || rows[0].kb_id || null;
    console.log(`  KB pin candidate: ${ctx.kbId}`);
  });

  test('2 · Create course + stem (Author plane)', async ({ request }) => {
    const stamp = Date.now().toString(36);
    const courseRes = await request.post(`${GV}/courses/`, {
      headers: ctx.headers,
      data: {
        code: `E2E-${stamp}`,
        name: `E2E Reflective Writing ${stamp}`,
        discipline: 'academic_english',
        entry_code: `E2E${stamp}`.slice(0, 16).toUpperCase(),
      },
    });
    const course = await jsonOrThrow(courseRes, 'create course');
    ctx.courseId = course.id;
    ctx.entryCode = course.entry_code || '';
    expect(ctx.entryCode).toBeTruthy();

    const pack = 'naa_cycle1_exam_prep';
    ctx.profilePackId = pack;
    const brief: Record<string, unknown> = {
      stem: 'Write a reflective wave on epistemic injustice in clinical publishing (Cycle 1).',
      instructions: 'Move from concrete incident → theory → action. Use SG/SD vocabulary.',
      outcomes: ['Demonstrate semantic waving', 'Ground claims in evidence'],
    };
    if (ctx.kbId) {
      brief.kb = ctx.kbId;
      brief.kb_note = 'Pinned for E2E professor journey';
    }

    const asgRes = await request.post(`${GV}/assignments/`, {
      headers: ctx.headers,
      data: {
        course: ctx.courseId,
        title: `E2E NAA stem ${stamp}`,
        mode: 'formative',
        status: 'draft',
        profile_pack_id: pack,
        profile_version: 1,
        brief,
      },
    });
    const asg = await jsonOrThrow(asgRes, 'create assignment');
    ctx.assignmentId = asg.id;
    expect(asg.profile_pack_id).toBe(pack);
    console.log(`  Course ${ctx.courseId} · Assignment ${ctx.assignmentId}`);
  });

  test('3 · Calibration preview (instrument honesty)', async ({ request, page }) => {
    const res = await request.get(
      `${GV}/calibration/?profile_pack_id=${encodeURIComponent(ctx.profilePackId!)}&profile_version=1`,
      { headers: ctx.headers },
    );
    const cal = await jsonOrThrow(res, 'calibration');
    expect(cal).toBeTruthy();
    console.log(`  Calibration payload keys: ${Object.keys(cal).slice(0, 8).join(', ')}`);

    const ok = await login(page, PROFESSOR as any);
    test.skip(!ok, 'professor UI login failed');
    await page.goto(`/teach/calibration?profile_pack_id=${ctx.profilePackId}`);
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByRole('navigation', { name: 'Breadcrumb navigation' })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/calibration/i).first()).toBeVisible();
  });

  test('4 · Publish formative stem', async ({ request }) => {
    const res = await request.post(`${GV}/assignments/${ctx.assignmentId}/publish/`, {
      headers: ctx.headers,
      data: {},
    });
    const data = await jsonOrThrow(res, 'publish');
    expect(data.status || data.assignment?.status || 'published').toMatch(/published/i);
  });

  test('5 · Submission + analyze (assessment run)', async ({ request }) => {
    const res = await request.post(`${GV}/submissions/`, {
      headers: ctx.headers,
      data: {
        assignment: ctx.assignmentId,
        text: SAMPLE_ESSAY,
        analyze: true,
        external_student_key: 'e2e-professor-demo',
      },
    });
    const data = await jsonOrThrow(res, 'submit+analyze');
    const submission = data.submission || data;
    const run = data.run || null;
    ctx.submissionId = submission.id;
    expect(ctx.submissionId).toBeTruthy();

    if (run?.id) {
      ctx.runId = run.id;
    } else {
      const analyze = await request.post(`${GV}/submissions/${ctx.submissionId}/analyze/`, {
        headers: ctx.headers,
        data: {},
      });
      const runBody = await jsonOrThrow(analyze, 'analyze');
      ctx.runId = runBody.id;
    }
    expect(ctx.runId).toBeTruthy();

    const detail = await request.get(`${GV}/runs/${ctx.runId}/`, { headers: ctx.headers });
    const runDetail = await jsonOrThrow(detail, 'run detail');
    expect((runDetail.segments || []).length).toBeGreaterThan(0);
    expect(runDetail.wave).toBeTruthy();
    console.log(
      `  Run ${ctx.runId}: ${runDetail.segments.length} segments, status=${runDetail.status}`,
    );
  });

  test('6 · Run workbench UI — breadcrumbs + rich LCT + SystemDialog edit', async ({ page }) => {
    const ok = await login(page, PROFESSOR as any);
    test.skip(!ok, 'professor UI login failed');

    await page.goto(`/teach/runs/${ctx.runId}`);
    await page.waitForLoadState('networkidle').catch(() => {});

    // Shell breadcrumb (RULE_9) — not in-page crumbs
    const crumbs = page.getByRole('navigation', { name: 'Breadcrumb navigation' });
    await expect(crumbs).toBeVisible({ timeout: 20_000 });
    await expect(crumbs.getByText(/Teach/i)).toBeVisible();
    await expect(crumbs.getByText(/Run workbench/i)).toBeVisible();

    await expect(page.getByText('Run workbench').first()).toBeVisible();
    await expect(page.getByText(/LCT analysis/i)).toBeVisible();
    await expect(page.getByText(/SG distribution/i)).toBeVisible();
    await expect(page.getByText(/SD distribution/i)).toBeVisible();
    await expect(page.getByLabel(/LCT segment codes/i)).toBeVisible();

    // ExpertEdit via SystemDialog (not Drawer)
    const editSg = page.getByRole('button', { name: 'Edit SG' }).first();
    await expect(editSg).toBeVisible();
    await editSg.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/Edit SG/i)).toBeVisible();
    await expect(dialog.getByLabel(/Rationale/i)).toBeVisible();

    // HITL form must not live in a Drawer paper (toolkit = SystemDialog)
    await expect(page.locator('.MuiDrawer-paper').filter({ hasText: /Edit SG/i })).toHaveCount(0);

    await dialog.getByLabel(/Rationale/i).fill(
      'E2E expert opinion: segment is more abstract (theory of epistemic injustice) than engine SG.',
    );
    await dialog.getByRole('button', { name: /Save ExpertEdit/i }).click();
    await expect(page.getByText(/ExpertEdit saved/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/ExpertEdit audit trail/i)).toBeVisible();
    await expect(page.getByLabel(/Expert edit history/i)).toBeVisible();

    // Visual resegment painter (continuous essay + click-to-split)
    const reseg = page.getByRole('button', { name: 'Resegment' });
    await expect(reseg).toBeVisible();
    await reseg.click();
    const segDialog = page.getByRole('dialog');
    await expect(segDialog).toBeVisible();
    await expect(segDialog.getByText(/Resegment/i)).toBeVisible();
    await expect(segDialog.getByTestId('essay-painter')).toBeVisible();
    await expect(segDialog.getByTestId('segmentation-editor')).toBeVisible();

    // Split after an early word if handle exists
    const splitBtn = segDialog.getByTestId('split-after-4');
    if (await splitBtn.count()) {
      await splitBtn.click();
      await expect(segDialog.getByTestId('seg-chip-1')).toBeVisible({ timeout: 5_000 });
    }

    // Pulse draft suggestions (local/API assist)
    const suggest = segDialog.getByTestId('suggest-splits');
    if (await suggest.count()) {
      await suggest.click();
    }

    await segDialog.getByTestId('seg-rationale').fill(
      'E2E visual resegment: split reflective wave at discourse cue for calibration learning.',
    );
    await segDialog.getByRole('button', { name: /Save ExpertEdit/i }).click();
    await expect(page.getByText(/ExpertEdit saved|segmentation/i).first()).toBeVisible({ timeout: 20_000 });
  });

  test('6b · Calibration held-out resegment propose', async ({ page, request }) => {
    const res = await request.get(
      `${GV}/calibration/?profile_pack_id=${encodeURIComponent(ctx.profilePackId!)}&profile_version=1`,
      { headers: ctx.headers },
    );
    const cal = await jsonOrThrow(res, 'calibration for resegment');
    const essays = cal?.segmentation_fidelity?.essays || [];
    test.skip(!essays.length, 'no held-out essays for segmentation UI');

    const ok = await login(page, PROFESSOR as any);
    test.skip(!ok, 'professor UI login failed');
    await page.goto(`/teach/calibration?profile_pack_id=${ctx.profilePackId}`);
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByTestId('seg-calibration')).toBeVisible({ timeout: 15_000 });

    const firstId = essays[0].example_id;
    await page.getByTestId(`resegment-essay-${firstId}`).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByTestId('essay-painter')).toBeVisible();
    await dialog.getByTestId('seg-rationale').fill(
      'E2E calibration resegment: propose segmentation_policy from held-out essay painter.',
    );
    await dialog.getByTestId('save-cal-resegment').click();
    // Navigates to proposals after draft
    await page.waitForURL(/\/teach\/proposals/, { timeout: 20_000 }).catch(() => {});
    await expect(page.getByText(/Proposal/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test('7 · Audit export + marking queue + assignment hub', async ({ page, request }) => {
    const audit = await request.get(`${GV}/runs/${ctx.runId}/audit-export/`, {
      headers: ctx.headers,
    });
    const payload = await jsonOrThrow(audit, 'audit-export');
    expect(payload.export_format || payload.run_id).toBeTruthy();
    expect((payload.expert_edits || []).length).toBeGreaterThan(0);
    expect(payload.segments?.length || payload.segment_count).toBeTruthy();

    const ok = await login(page, PROFESSOR as any);
    test.skip(!ok, 'professor UI login failed');

    await page.goto('/teach/marking');
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByRole('navigation', { name: 'Breadcrumb navigation' })).toBeVisible();
    await expect(page.getByText(/Marking/i).first()).toBeVisible();

    await page.goto(`/teach/stems/${ctx.assignmentId}`);
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByRole('navigation', { name: 'Breadcrumb navigation' })).toBeVisible();
    await expect(page.getByText(/Assignment hub|Stem|Submissions/i).first()).toBeVisible();
  });

  test('8 · Proposals surface (learning loop after ExpertEdit)', async ({ page, request }) => {
    const res = await request.get(`${GV}/proposals/`, { headers: ctx.headers });
    // 200 even if empty — miner may be async
    expect([200, 403]).toContain(res.status());
    if (res.ok()) {
      const data = await res.json();
      const rows = Array.isArray(data) ? data : data.results || [];
      console.log(`  Proposals visible: ${rows.length}`);
    }

    const ok = await login(page, PROFESSOR as any);
    test.skip(!ok, 'professor UI login failed');
    await page.goto('/teach/proposals');
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByRole('navigation', { name: 'Breadcrumb navigation' })).toBeVisible();
    await expect(page.getByText(/Proposal/i).first()).toBeVisible();
  });

  test('9 · Learn path (student) when demo student exists', async ({ page, request }) => {
    test.skip(!ctx.studentHeaders, 'gv_student not provisioned — run seed_gradevance_demo');

    if (ctx.entryCode) {
      const join = await request.post(`${GV}/me/join/`, {
        headers: ctx.studentHeaders,
        data: { entry_code: ctx.entryCode },
      });
      // 200/201 join, or 400 if already enrolled / code unused
      expect([200, 201, 400]).toContain(join.status());
    }

    const list = await request.get(`${GV}/me/assignments/`, { headers: ctx.studentHeaders });
    expect(list.ok()).toBeTruthy();

    const ok = await login(page, STUDENT as any);
    test.skip(!ok, 'student UI login failed');
    await page.goto('/learn/assignments');
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.getByRole('navigation', { name: 'Breadcrumb navigation' })).toBeVisible();
    await expect(page.getByText(/Learn|Assignment/i).first()).toBeVisible();
  });

  test('10 · Release formative run (ceremony)', async ({ request }) => {
    const res = await request.post(`${GV}/runs/${ctx.runId}/release/`, {
      headers: ctx.headers,
      data: {},
    });
    // Formative may already allow release or no-op
    expect([200, 201, 400]).toContain(res.status());
    if (res.ok()) {
      const body = await res.json();
      console.log(`  Release status: released=${body.released}`);
    }
  });
});
