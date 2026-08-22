// src/utils/planGraph.js
// W3-F — pure helpers that turn a plan payload into graph data (nodes =
// steps, edges = depends_on) and outcome-terms diff summaries (RULE_23).
// Kept framework-free so unit tests run fast and deterministic.

/**
 * Build DAG nodes + edges from a plan payload.
 * Nodes = steps (id = step_id, label = intent); edges = depends_on
 * (a step listing dependency D gets an edge D → step). Orphan dependency
 * ids (not present in the step list) are skipped so a malformed plan never
 * crashes the graph.
 *
 * @param {object} plan - plan payload from GET /ai/plans/{id}/
 * @returns {{nodes: Array<{id:number,label:string,status:string,tool_name:string|null}>, edges: Array<{source:number,target:number,label:string}>}}
 */
export function buildPlanGraph(plan) {
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const nodes = steps
    .filter((s) => s && s.step_id !== undefined)
    .map((s) => ({
      id: s.step_id,
      label: s.intent || `Step ${s.step_id}`,
      status: s.status || 'pending',
      tool_name: s.tool_name || null,
      agent_role: s.agent_role || 'orchestrator',
      phase_id: s.phase_id ?? null,
    }));

  const ids = new Set(nodes.map((n) => n.id));
  const edges = [];
  steps.forEach((s) => {
    const deps = Array.isArray(s.depends_on) ? s.depends_on : [];
    deps.forEach((dep) => {
      if (!ids.has(dep)) return; // orphan dep — skip silently
      edges.push({ source: dep, target: s.step_id, label: 'depends on' });
    });
  });
  // Deterministic ordering (source, then target) for stable renders + tests.
  edges.sort((a, b) => a.source - b.source || a.target - b.target);
  return { nodes, edges };
}

/**
 * Human-readable (outcome-terms) summary of a plan diff.
 * @param {object} diff - { added: [step], removed: [step], changed: [{old,new}] }
 * @returns {{added:Array<string>, removed:Array<string>, changed:Array<{from:string,to:string}>, count:number, summary:string}}
 */
export function summarizePlanDiff(diff) {
  const added = Array.isArray(diff?.added) ? diff.added : [];
  const removed = Array.isArray(diff?.removed) ? diff.removed : [];
  const changed = Array.isArray(diff?.changed) ? diff.changed : [];

  const intentOf = (s) => {
    if (!s) return 'a step';
    return s.intent || s.title || `Step ${s.step_id ?? ''}`.trim() || 'a step';
  };

  const addedSteps = added.map(intentOf);
  const removedSteps = removed.map(intentOf);
  const changedSteps = changed.map((c) => ({
    from: intentOf(c?.old),
    to: intentOf(c?.new),
  }));

  const parts = [];
  if (addedSteps.length) {
    parts.push(`${addedSteps.length} step${addedSteps.length > 1 ? 's' : ''} added`);
  }
  if (removedSteps.length) {
    parts.push(`${removedSteps.length} step${removedSteps.length > 1 ? 's' : ''} removed`);
  }
  if (changedSteps.length) {
    parts.push(`${changedSteps.length} step${changedSteps.length > 1 ? 's' : ''} changed`);
  }
  const summary = parts.length
    ? `${parts.join(', ')}.`
    : 'No changes to the plan steps.';

  return {
    added: addedSteps,
    removed: removedSteps,
    changed: changedSteps,
    count: added.length + removed.length + changed.length,
    summary,
  };
}

/**
 * Mermaid `graph LR` definition for a plan DAG — used by the static diagram
 * preview in the review card. Node labels are quoted + escaped so free-text
 * intents never break the diagram.
 *
 * @param {object} plan
 * @returns {string} mermaid source
 */
export function planDagMermaid(plan) {
  const { nodes, edges } = buildPlanGraph(plan);
  if (nodes.length === 0) {
    return 'graph LR\n  empty["No steps yet"]';
  }
  const lines = ['graph LR'];
  nodes.forEach((n) => {
    const label = String(n.label || `Step ${n.id}`).replace(/"/g, "'");
    lines.push(`  s${n.id}["${label}"]`);
  });
  edges.forEach((e) => {
    lines.push(`  s${e.source} --> s${e.target}`);
  });
  return lines.join('\n');
}

/**
 * Build a phase-aware view of a plan: phases (workflow stages) each carrying
 * their steps, plus a map of step_id → phase. Phases come from the plan
 * payload (plan.phases); steps not claimed by any phase land in an implicit
 * "Remaining" phase so the workflow view never drops a step.
 *
 * @param {object} plan - plan payload from GET /ai/plans/{id}/
 * @returns {{phases: Array<{phase_id:number,name:string,goal:string,strategy:string,step_ids:number[],steps:Array<object>}>, stepPhase: Record<number,number>}}
 */
export function buildPlanPhases(plan) {
  const steps = Array.isArray(plan?.steps) ? plan.steps : [];
  const stepById = new Map(steps.filter((s) => s && s.step_id !== undefined).map((s) => [s.step_id, s]));

  const rawPhases = Array.isArray(plan?.phases) ? plan.phases : [];
  const phases = [];
  const claimed = new Set();

  rawPhases.forEach((p, i) => {
    const stepIds = Array.isArray(p?.step_ids)
      ? p.step_ids.filter((id) => stepById.has(id))
      : [];
    stepIds.forEach((id) => claimed.add(id));
    phases.push({
      phase_id: p?.phase_id ?? i,
      name: p?.name || `Phase ${i + 1}`,
      goal: p?.goal || '',
      strategy: p?.strategy === 'parallel' ? 'parallel' : 'sequential',
      step_ids: stepIds,
      steps: stepIds.map((id) => stepById.get(id)),
    });
  });

  const unclaimedIds = steps
    .filter((s) => !claimed.has(s.step_id))
    .map((s) => s.step_id);

  if (phases.length === 0 && unclaimedIds.length > 0) {
    phases.push({
      phase_id: 0,
      name: 'All steps',
      goal: '',
      strategy: 'sequential',
      step_ids: unclaimedIds,
      steps: unclaimedIds.map((id) => stepById.get(id)),
    });
  } else if (unclaimedIds.length > 0) {
    phases.push({
      phase_id: phases.length,
      name: 'Remaining',
      goal: '',
      strategy: 'sequential',
      step_ids: unclaimedIds,
      steps: unclaimedIds.map((id) => stepById.get(id)),
    });
  }

  const stepPhase = {};
  phases.forEach((p) => {
    p.step_ids.forEach((id) => {
      stepPhase[id] = p.phase_id;
    });
  });

  return { phases, stepPhase };
}

// ── Execution-graph layout (TensorFlow-style) ─────────────────────────────
// The plan DAG is rendered as a LAYERED DIRECTED execution graph: ranks come
// from longest-path layering (sources at rank 0, sinks at the max rank), so
// edges always flow left→right with arrowheads — dependency is execution
// order, exactly like a computation graph. Within a rank, steps are stacked
// top→bottom by step_id. Phase bands (vertical columns) group the ranks a
// phase spans so the workflow stages read as execution lanes.

export const EXEC_LAYOUT = {
  nodeW: 176,
  nodeH: 44,
  colGap: 48,
  rowGap: 28,
  padX: 24,
  padTop: 36,
  padBottom: 20,
};

/**
 * Layered execution-graph layout for a plan.
 *
 * @param {object} plan - plan payload from GET /ai/plans/{id}/
 * @returns {{nodes: Array<{id:number,label:string,status:string,tool_name:string|null,x:number,y:number,rank:number,phase_id:number|null}>, edges: Array<{source:number,target:number,sourceX:number,sourceY:number,targetX:number,targetY:number}>, width:number, height:number, phaseBands: Array<{phase_id:number,name:string,x:number,width:number,strategy:string}>}}
 */
export function layoutExecutionGraph(plan) {
  const { nodes, edges } = buildPlanGraph(plan);
  const { phases, stepPhase } = buildPlanPhases(plan);

  // Longest-path layering measured FROM SOURCES (Sugiyama):
  // rank(node) = 0 for sources, else 1 + max(rank of its predecessors).
  // Ranks grow left→right, so every dependency edge flows left→right.
  const preds = new Map(nodes.map((n) => [n.id, []]));
  edges.forEach((e) => {
    if (preds.has(e.target)) preds.get(e.target).push(e.source);
  });

  const rankOf = new Map();
  const memo = new Map();
  const visit = (id) => {
    if (memo.has(id)) return memo.get(id);
    const ps = preds.get(id) || [];
    const r = ps.length ? 1 + Math.max(...ps.map(visit)) : 0;
    memo.set(id, r);
    return r;
  };
  nodes.forEach((n) => rankOf.set(n.id, visit(n.id)));

  const maxRank = nodes.length ? Math.max(...rankOf.values()) : 0;
  const byRank = new Map();
  nodes.forEach((n) => {
    const r = rankOf.get(n.id) ?? 0;
    if (!byRank.has(r)) byRank.set(r, []);
    byRank.get(r).push(n);
  });
  const ranks = [...byRank.keys()].sort((a, b) => a - b);
  ranks.forEach((r) => byRank.get(r).sort((a, b) => a.id - b.id));

  const L = EXEC_LAYOUT;
  const width = L.padX * 2 + (maxRank + 1) * L.nodeW + maxRank * L.colGap;
  const maxInRank = ranks.length ? Math.max(...ranks.map((r) => byRank.get(r).length)) : 0;
  const height = L.padTop + maxInRank * L.nodeH + (maxInRank - 1) * L.rowGap + L.padBottom;

  const laid = [];
  ranks.forEach((r) => {
    const group = byRank.get(r);
    const groupH = group.length * L.nodeH + (group.length - 1) * L.rowGap;
    const startY = L.padTop + (height - L.padTop - L.padBottom - groupH) / 2;
    const x = L.padX + r * (L.nodeW + L.colGap);
    group.forEach((n, i) => {
      laid.push({
        ...n,
        x,
        y: startY + i * (L.nodeH + L.rowGap),
        // Node dimensions ride along so the enterprise graph can render and
        // (re)size nodes generically without re-deriving the layout constants.
        w: L.nodeW,
        h: L.nodeH,
        rank: r,
        phase_id: stepPhase[n.id] ?? null,
      });
    });
  });

  const laidEdges = edges
    .map((e) => {
      const s = laid.find((n) => n.id === e.source);
      const t = laid.find((n) => n.id === e.target);
      if (!s || !t) return null;
      return {
        source: e.source,
        target: e.target,
        sourceX: s.x + L.nodeW,
        sourceY: s.y + L.nodeH / 2,
        targetX: t.x,
        targetY: t.y + L.nodeH / 2,
      };
    })
    .filter(Boolean);

  // Phase bands — the x-span each phase covers across its step ranks.
  const phaseBands = phases
    .map((p) => {
      const xs = p.step_ids
        .map((id) => laid.find((n) => n.id === id))
        .filter(Boolean)
        .map((n) => n.x);
      if (!xs.length) return null;
      return {
        phase_id: p.phase_id,
        name: p.name,
        strategy: p.strategy,
        x: Math.min(...xs),
        width: Math.max(...xs) + L.nodeW - Math.min(...xs),
      };
    })
    .filter(Boolean);

  return { nodes: laid, edges: laidEdges, width, height, phaseBands };
}
