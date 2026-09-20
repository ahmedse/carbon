/**
 * ADR-0041 / ADR-0043 — merge live plan/run truth into a Job Map artifact.
 *
 * The durable AIArtifact board can lag (create-time Planned seed, conversation
 * upsert clobber). The Operator Canvas must never show Planned 0/1 when the
 * cockpit header already shows Completed N/N — overlay the live journey.
 */

const TERMINAL = new Set(['completed', 'failed', 'skipped']);

/**
 * @param {object|null} artifact — AIArtifact job_map row
 * @param {object|null} journey — { status, brief, steps, finalResponse, artifacts }
 * @returns {object|null} artifact-shaped object with merged content_json
 */
export function mergeCanvasJourney(artifact, journey) {
  if (!journey || typeof journey !== 'object') return artifact;

  const stepsIn = Array.isArray(journey.steps) ? journey.steps : [];
  const mapped = stepsIn.map((s, i) => ({
    id: String(s.step_id ?? s.step_index ?? s.id ?? i),
    title: String(s.intent || s.title || s.tool_name || s.tool || `Step ${i + 1}`).slice(0, 200),
    tool: String(s.tool_name || s.tool || ''),
    status: String(s.status || 'pending'),
    deps: Array.isArray(s.depends_on) ? s.depends_on : (s.deps || []),
  }));

  const settled = mapped.filter((s) => TERMINAL.has(s.status)).length;
  const total = mapped.length || 1;
  let progress = mapped.length ? Math.round((100 * settled) / total) : 0;

  const runStatus = String(journey.status || '').toLowerCase();
  const awaiting = mapped.find((s) => s.status === 'awaiting_approval');
  let liveStatus = 'planned';
  if (awaiting) liveStatus = 'blocked';
  else if (runStatus === 'completed_with_gaps') liveStatus = 'partial';
  else if (runStatus === 'completed' || (mapped.length && settled === mapped.length && !mapped.some((s) => s.status === 'failed'))) {
    liveStatus = mapped.some((s) => s.status === 'failed') ? 'failed' : 'completed';
    progress = 100;
  } else if (runStatus === 'failed' || mapped.some((s) => s.status === 'failed' && settled === mapped.length)) {
    liveStatus = 'failed';
  } else if (settled > 0 || runStatus === 'running' || runStatus === 'paused') {
    liveStatus = runStatus === 'paused' ? 'blocked' : 'running';
  }

  const base = artifact && typeof artifact === 'object'
    ? { ...artifact, content_json: { ...(artifact.content_json || {}) } }
    : {
      title: (journey.brief || 'Agent Job Map').slice(0, 80),
      artifact_type: 'job_map',
      content_json: {
        kind: 'job_map',
        mode: 'agent',
        title: (journey.brief || 'Agent Job Map').slice(0, 80),
        plan_id: journey.planId || null,
      },
    };

  const content = { ...(base.content_json || {}), kind: 'job_map', mode: 'agent' };
  if (journey.planId) content.plan_id = journey.planId;
  const layers = { ...(content.layers || {}) };

  const intent = { ...(layers.intent || {}) };
  if (journey.brief && !intent.ask) intent.ask = journey.brief;
  layers.intent = intent;

  if (mapped.length) {
    layers.job_map = {
      ...(layers.job_map || {}),
      steps: mapped,
      tools: [...new Set(mapped.map((s) => s.tool).filter(Boolean))].sort(),
    };
  }

  layers.live_run = {
    ...(layers.live_run || {}),
    progress_pct: progress,
    status: liveStatus,
    blockers: awaiting
      ? [`Consent required: step ${awaiting.id} — ${awaiting.title}`]
      : (layers.live_run?.blockers || []),
    pending_consent: awaiting
      ? { step_id: awaiting.id, tool: awaiting.tool, intent: awaiting.title }
      : null,
  };

  const evidence = { ...(layers.evidence || {}) };
  const arts = Array.isArray(journey.artifacts) ? journey.artifacts : [];
  if (arts.length) {
    const other = (evidence.tables || []).filter((t) => t?.title !== 'Deliverables');
    evidence.tables = [
      {
        title: 'Deliverables',
        columns: ['File'],
        rows: arts.map((a) => [a.name || a.filename || String(a.id || '')]),
      },
      ...other,
    ];
  }
  const finalText = (journey.finalResponse || '').trim();
  if (finalText) {
    evidence.prose = finalText.slice(0, 2000);
    if (!evidence.headline && (liveStatus === 'completed' || liveStatus === 'partial')) {
      evidence.headline = `Run finished · ${settled}/${total} steps`;
    }
  }
  layers.evidence = evidence;

  if (finalText || liveStatus === 'completed' || liveStatus === 'partial' || liveStatus === 'failed') {
    layers.outcome = {
      ...(layers.outcome || {}),
      summary: finalText
        ? finalText.slice(0, 800)
        : (layers.outcome?.summary || `Journey ${liveStatus} · ${settled}/${total} steps.`),
    };
  }

  content.layers = layers;
  base.content_json = content;
  if (!base.title && journey.brief) base.title = journey.brief.slice(0, 80);
  return base;
}

export default mergeCanvasJourney;
