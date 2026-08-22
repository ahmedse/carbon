// e2e/helpers/plansApiMock.ts
// Deterministic in-browser mock of the Carbon plan endpoints for the Task/Run
// view (Sprint 23 W3-A/W3-C). Route-intercepts the real `/carbon-api/ai/plans`
// surface so the E2E spec can drive the actual React UI (login, workspace,
// composer, list, plan card, streamed run, graph) with 100% reproducible data —
// no LLM latency, no cost, no flakiness. This is the *presentation + interaction*
// layer under test; the real backend integration is covered by the live spec.
//
// The mock mirrors the real backend contracts exactly (see backend/ai/plans_*):
//   create (planning only) → approve/decline → run/resume (SSE) → per-step
//   confirm/decline → ledger; plus edit/pause/fork. SSE frames are serialized
//   as `data: {json}\n\n` and read by streamJsonPost's shared reader.

import type { Page, Route } from '@playwright/test';

// ── Fixture types ──────────────────────────────────────────────────────────

export interface PlanStep {
  step_id: number;
  intent: string;
  tool_name?: string | null;
  tool_args?: Record<string, unknown> | null;
  depends_on?: number[];
  instructions?: string | null;
  agent_role?: string;
  status?: string;
  draft_text?: string | null;
  critic_verdict?: string | null;
  error?: string | null;
  phase_id?: number | null;
}

export interface PlanPhase {
  phase_id: number;
  name: string;
  goal?: string;
  strategy?: 'sequential' | 'parallel';
  step_ids: number[];
}

export interface PlanFixture {
  id: string;
  status: string;
  brief: string;
  steps: PlanStep[];
  phases?: PlanPhase[];
  pattern?: string;
  source?: string;
  skill_name?: string | null;
  forked_from?: string | null;
  needs_confirmation?: boolean;
  conversation_id?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  final_response?: string | null;
}

export type Frame = Record<string, unknown>;

// ── Factories ──────────────────────────────────────────────────────────────

let autoStep = 0;
let autoPlan = 0;

export function step(over: Partial<PlanStep> = {}): PlanStep {
  const id = over.step_id ?? autoStep++;
  return {
    step_id: id,
    intent: over.intent ?? `Step ${id} action`,
    tool_name: over.tool_name ?? null,
    tool_args: over.tool_args ?? null,
    depends_on: over.depends_on ?? [],
    instructions: over.instructions ?? null,
    agent_role: over.agent_role ?? 'orchestrator',
    status: over.status ?? 'pending',
    draft_text: over.draft_text ?? null,
    critic_verdict: over.critic_verdict ?? null,
    error: over.error ?? null,
    phase_id: over.phase_id ?? null,
  };
}

export function makePlan(
  over: Partial<PlanFixture> & { stepCount?: number } = {},
): PlanFixture {
  const { stepCount, ...rest } = over as Partial<PlanFixture> & { stepCount?: number };
  const steps =
    rest.steps ??
    Array.from({ length: stepCount ?? 3 }, (_, i) => step({ step_id: i }));
  const now = '2026-01-15T09:30:00Z';
  return {
    id: rest.id ?? `plan-auto-${autoPlan++}`,
    status: rest.status ?? 'pending_approval',
    brief: rest.brief ?? 'Audit the emissions dataset for duplicates',
    steps,
    phases: rest.phases,
    pattern: rest.pattern,
    source: rest.source,
    skill_name: rest.skill_name,
    forked_from: rest.forked_from,
    needs_confirmation: rest.needs_confirmation,
    conversation_id: rest.conversation_id,
    created_at: rest.created_at ?? now,
    updated_at: rest.updated_at ?? now,
    completed_at: rest.completed_at ?? null,
    final_response: rest.final_response ?? null,
  };
}

const deep = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

// ── SSE ────────────────────────────────────────────────────────────────────

export function sse(frames: Frame[]): string {
  return frames.map((f) => `data: ${JSON.stringify(f)}\n\n`).join('');
}

// ── Run scripts (frame generators) ─────────────────────────────────────────

/** Full completion: every step runs to `completed`, then `done(completed)`. */
export function completeRunScript(plan: PlanFixture): Frame[] {
  const frames: Frame[] = [
    { type: 'plan_start', plan_id: plan.id, status: 'running' },
  ];
  for (const s of plan.steps) {
    frames.push({ type: 'step_start', plan_id: plan.id, step_id: s.step_id, intent: s.intent });
    frames.push({
      type: 'step_result',
      plan_id: plan.id,
      step_id: s.step_id,
      intent: s.intent,
      status: 'completed',
      verdict: 'ok',
      draft_text: 'draft output',
      tool_output: { rows: 1 },
      error: null,
    });
    frames.push({ type: 'step_end', plan_id: plan.id, step_id: s.step_id, status: 'completed' });
  }
  frames.push({
    type: 'done',
    plan_id: plan.id,
    status: 'completed',
    final_response: 'All steps completed.',
  });
  return frames;
}

/**
 * Consent-gate run: complete `beforeSteps`, then pause at `consentStepId`
 * with a `step_confirm` frame and a terminal `done(status: paused)`.
 */
export function consentRunScript(
  plan: PlanFixture,
  consentStepId: number,
  beforeSteps: number[] = [],
): Frame[] {
  const frames: Frame[] = [
    { type: 'plan_start', plan_id: plan.id, status: 'running' },
  ];
  for (const id of beforeSteps) {
    const s = plan.steps.find((x) => x.step_id === id);
    if (!s) continue;
    frames.push({ type: 'step_start', plan_id: plan.id, step_id: id, intent: s.intent });
    frames.push({
      type: 'step_result',
      plan_id: plan.id,
      step_id: id,
      intent: s.intent,
      status: 'completed',
      verdict: 'ok',
      draft_text: 'draft',
      tool_output: { rows: 1 },
      error: null,
    });
    frames.push({ type: 'step_end', plan_id: plan.id, step_id: id, status: 'completed' });
  }
  const target = plan.steps.find((x) => x.step_id === consentStepId);
  frames.push({
    type: 'step_confirm',
    plan_id: plan.id,
    step_id: consentStepId,
    intent: target?.intent ?? `Step ${consentStepId}`,
    message: 'This action writes to Carbon.',
  });
  frames.push({ type: 'done', plan_id: plan.id, status: 'paused' });
  return frames;
}

/** Resume after a consent pause: run `consentStepId` to completion, then done. */
export function resumeAfterConsentScript(plan: PlanFixture, consentStepId: number): Frame[] {
  const s = plan.steps.find((x) => x.step_id === consentStepId);
  const frames: Frame[] = [
    { type: 'plan_start', plan_id: plan.id, status: 'running' },
    { type: 'step_start', plan_id: plan.id, step_id: consentStepId, intent: s?.intent ?? `Step ${consentStepId}` },
    {
      type: 'step_result',
      plan_id: plan.id,
      step_id: consentStepId,
      intent: s?.intent ?? `Step ${consentStepId}`,
      status: 'completed',
      verdict: 'ok',
      draft_text: 'draft',
      tool_output: { rows: 1 },
      error: null,
    },
    { type: 'step_end', plan_id: plan.id, step_id: consentStepId, status: 'completed' },
    { type: 'done', plan_id: plan.id, status: 'completed', final_response: 'Consent granted and step executed.' },
  ];
  return frames;
}

/** Terminal failure via a `done(status: failed)` frame. */
export function failedRunScript(plan: PlanFixture): Frame[] {
  const first = plan.steps[0];
  return [
    { type: 'plan_start', plan_id: plan.id, status: 'running' },
    ...(first
      ? [{ type: 'step_start', plan_id: plan.id, step_id: first.step_id, intent: first.intent }]
      : []),
    ...(first
      ? [
          {
            type: 'step_result',
            plan_id: plan.id,
            step_id: first.step_id,
            intent: first.intent,
            status: 'failed',
            verdict: 'veto',
            draft_text: null,
            tool_output: null,
            error: 'Boom: insufficient history',
          },
          { type: 'step_end', plan_id: plan.id, step_id: first.step_id, status: 'failed' },
        ]
      : []),
    { type: 'done', plan_id: plan.id, status: 'failed' },
  ];
}

/** Terminal failure via a raw `error` frame (onError path). */
export function errorFrameRunScript(_plan: PlanFixture): Frame[] {
  return [
    { type: 'plan_start', status: 'running' },
    { type: 'error', error: 'The plan engine exploded.' },
  ];
}

// ── Ledger default ─────────────────────────────────────────────────────────

function defaultLedger(plan: PlanFixture): Record<string, unknown> {
  return {
    plan_id: plan.id,
    status: plan.status,
    actor: { user_id: 'admin', display_name: 'Admin' },
    provenance: {
      pattern: plan.pattern || 'audit',
      source: plan.source || 'pulse',
      skill_name: plan.skill_name ?? null,
      needs_confirmation: !!plan.needs_confirmation,
    },
    usage: { total_latency_ms: 1234, total_llm_calls: 3, total_tokens: 4567 },
    steps: plan.steps.map((s) => ({
      step_id: s.step_id,
      intent: s.intent,
      status: s.status === 'skipped' ? 'skipped' : 'completed',
      confirmed: s.status !== 'skipped',
      latency_ms: 100,
      skipped: s.status === 'skipped',
    })),
    confirmations: plan.steps.slice(0, 1).map((s) => ({ step_id: s.step_id, status: 'confirmed' })),
    replans: 0,
    final_response: plan.final_response || 'All steps completed.',
  };
}

// ── Route-intercepted mock ─────────────────────────────────────────────────

export class PlansApiMock {
  plans: PlanFixture[] = [];
  runScript: (plan: PlanFixture) => Frame[] = completeRunScript;
  resumeScript: (plan: PlanFixture) => Frame[] = completeRunScript;
  requests: Array<{ method: string; path: string; body: unknown }> = [];
  ledgers: Record<string, Record<string, unknown>> = {};

  constructor(plans: PlanFixture[] = []) {
    this.reset(plans);
  }

  reset(plans: PlanFixture[] = []): void {
    this.plans = deep(plans);
    this.runScript = completeRunScript;
    this.resumeScript = completeRunScript;
    this.requests = [];
    this.ledgers = {};
  }

  clearRequests(): void {
    this.requests = [];
  }

  private get(id: string): PlanFixture | undefined {
    return this.plans.find((p) => p.id === id);
  }

  private static ok(route: Route, data: unknown, status = 200): Promise<void> {
    return route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(data),
    });
  }

  private static fail(route: Route, status: number, message: string): Promise<void> {
    return route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ error: message }),
    });
  }

  /** Apply a run's frames back to the plan so a follow-up getPlan reflects them. */
  private applyFrames(plan: PlanFixture, frames: Frame[]): void {
    for (const f of frames) {
      if (f.type === 'step_end' || f.type === 'step_confirm' || f.type === 'step_result') {
        const s = plan.steps.find((x) => x.step_id === f.step_id);
        if (!s) continue;
        if (f.type === 'step_confirm') s.status = 'awaiting_approval';
        else s.status = String(f.status || 'pending');
      } else if (f.type === 'done') {
        const st = String(f.status || 'completed');
        plan.status = st === 'paused' ? 'paused' : st === 'stopped' ? 'cancelled' : st === 'failed' ? 'failed' : 'completed';
        if (typeof f.final_response === 'string') plan.final_response = f.final_response;
      } else if (f.type === 'error') {
        plan.status = 'failed';
      }
    }
  }

  async install(page: Page): Promise<void> {
    await page.route(/\/ai\/plans/, (route) => this.handle(route));
  }

  private async handle(route: Route): Promise<void> {
    const req = route.request();
    const method = req.method();
    const pathname = new URL(req.url()).pathname.replace(/\/+$/, '');
    const m = pathname.match(/\/ai\/plans\/?(.*)$/);
    const rest = m ? m[1] : '';
    const segs = rest.split('/').filter(Boolean);
    let body: any = {};
    if (method !== 'GET') {
      try {
        body = JSON.parse(req.postData() || '{}');
      } catch {
        body = {};
      }
    }
    this.requests.push({ method, path: rest, body });

    // GET/POST /ai/plans/  → list / create
    if (segs.length === 0) {
      if (method === 'GET') {
        return PlansApiMock.ok(route, { plans: this.plans, count: this.plans.length });
      }
      if (method === 'POST') {
        const created = makePlan({
          id: `plan-created-${this.requests.length}`,
          status: 'pending_approval',
          brief: String(body?.brief ?? '').trim(),
          stepCount: 2,
        });
        this.plans.unshift(created);
        return PlansApiMock.ok(route, created, 201);
      }
    }

    const id = segs[0];
    const plan = this.get(id);
    if (!plan) return PlansApiMock.fail(route, 404, 'Not found.');

    // GET /ai/plans/{id}/  → detail
    if (segs.length === 1) {
      if (method === 'GET') return PlansApiMock.ok(route, plan);
      if (method === 'PATCH') {
        // editPlan — returns plan + diff (replan gate)
        if (body?.brief !== undefined) plan.brief = String(body.brief).trim();
        plan.status = 'pending_approval';
        return PlansApiMock.ok(route, {
          ...plan,
          diff: {
            added: [],
            removed: [],
            changed: [{ old: { intent: plan.steps[0]?.intent || 'a step' }, new: { intent: plan.brief } }],
          },
        });
      }
    }

    const action = segs[1];
    // GET /ai/plans/{id}/ledger/
    if (action === 'ledger' && method === 'GET') {
      return PlansApiMock.ok(route, this.ledgers[id] || defaultLedger(plan));
    }

    // POST lifecycle actions
    if (segs.length === 2 && method === 'POST') {
      if (action === 'approve') {
        plan.status = 'approved';
        return PlansApiMock.ok(route, plan);
      }
      if (action === 'decline') {
        plan.status = 'cancelled';
        return PlansApiMock.ok(route, plan);
      }
      if (action === 'pause') {
        plan.status = 'paused';
        return PlansApiMock.ok(route, plan);
      }
      if (action === 'stop') {
        plan.status = 'cancelled';
        plan.steps.forEach((s) => {
          if (s.status === 'pending' || s.status === 'running') s.status = 'skipped';
        });
        return PlansApiMock.ok(route, plan);
      }
      if (action === 'fork') {
        const forked = makePlan({
          id: `plan-fork-${this.requests.length}`,
          status: 'pending_approval',
          brief: plan.brief,
          steps: plan.steps,
          phases: plan.phases,
          pattern: plan.pattern,
          source: plan.source,
          skill_name: plan.skill_name,
          forked_from: plan.id,
          needs_confirmation: plan.needs_confirmation,
        });
        this.plans.unshift(forked);
        return PlansApiMock.ok(route, forked, 201);
      }
      if (action === 'run' || action === 'resume') {
        const frames = action === 'run' ? this.runScript(plan) : this.resumeScript(plan);
        this.applyFrames(plan, frames);
        return route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: sse(frames),
        });
      }
    }

    // POST /ai/plans/{id}/steps/confirm|decline/
    if (segs.length === 3 && segs[1] === 'steps' && method === 'POST') {
      const stepId = body?.step_id;
      const s = plan.steps.find((x) => x.step_id === stepId);
      if (!s) return PlansApiMock.fail(route, 404, 'Step not found.');
      if (segs[2] === 'confirm') {
        s.status = 'completed';
        return PlansApiMock.ok(route, { status: 'confirmed', plan_id: plan.id, step_id: stepId });
      }
      if (segs[2] === 'decline') {
        s.status = 'skipped';
        return PlansApiMock.ok(route, { status: 'declined', plan_id: plan.id, step_id: stepId });
      }
    }

    // PATCH /ai/plans/{id}/steps/{stepId}/  → editStep
    if (segs.length === 3 && segs[1] === 'steps' && method === 'PATCH') {
      const stepId = Number(segs[2]);
      const s = plan.steps.find((x) => x.step_id === stepId);
      if (!s) return PlansApiMock.fail(route, 404, 'Step not found.');
      const oldIntent = s.intent;
      if (body?.title !== undefined) s.intent = String(body.title).trim();
      if (body?.instructions !== undefined) s.instructions = String(body.instructions);
      if (body?.depends_on !== undefined) s.depends_on = Array.isArray(body.depends_on) ? body.depends_on.map(Number) : [];
      plan.status = 'pending_approval';
      return PlansApiMock.ok(route, {
        ...plan,
        diff: {
          added: [],
          removed: [],
          changed: [{ old: { intent: oldIntent }, new: { intent: s.intent } }],
        },
      });
    }

    return PlansApiMock.fail(route, 405, `Unhandled: ${method} ${rest}`);
  }
}
