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
 * When ``plan.workflow_graph`` is present (ADR-0034), task nodes are enriched
 * with ``node_type`` and edges may carry ``guard`` / ``is_default``; choice /
 * parallel gateways are added as synthetic nodes (string ids).
 *
 * @param {object} plan - plan payload from GET /ai/plans/{id}/
 * @returns {{nodes: Array<object>, edges: Array<object>}}
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
      node_type: 'task',
      is_gateway: false,
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

  const wg = plan?.workflow_graph;
  if (wg && Array.isArray(wg.nodes) && wg.nodes.length) {
    const wgToStep = new Map();
    wg.nodes.forEach((wn) => {
      const sid = wn?.meta?.step_id;
      // task + human (and any typed node pinned to a plan step)
      if (sid !== undefined && sid !== null && ['task', 'human'].includes(wn?.node_type)) {
        wgToStep.set(wn.id, sid);
      }
    });
    nodes.forEach((n) => {
      const wn = wg.nodes.find((x) => x?.meta?.step_id === n.id);
      if (wn?.node_type) n.node_type = wn.node_type;
    });
    // Synthetic gateways (choice / parallel / observe / map / loop / wait / fail)
    wg.nodes.forEach((wn) => {
      if (!wn || !['choice', 'parallel', 'observe', 'map', 'loop', 'wait', 'fail', 'succeed'].includes(wn.node_type)) {
        return;
      }
      if (ids.has(wn.id)) return;
      // Skip if this gateway is already bound to a step id via meta.
      if (wn.meta?.step_id !== undefined && wn.meta?.step_id !== null) return;
      nodes.push({
        id: wn.id,
        label: wn.intent || wn.node_type,
        status: 'pending',
        tool_name: null,
        agent_role: 'orchestrator',
        phase_id: wn.meta?.phase_id ?? null,
        node_type: wn.node_type,
        is_gateway: true,
      });
      ids.add(wn.id);
    });
    // Prefer workflow edges when they resolve to known node ids
    const resolved = [];
    (wg.edges || []).forEach((we) => {
      const source = wgToStep.has(we.source) ? wgToStep.get(we.source) : we.source;
      const target = wgToStep.has(we.target) ? wgToStep.get(we.target) : we.target;
      if (!ids.has(source) || !ids.has(target)) return;
      const label = we.guard
        ? `if ${we.guard}`
        : (we.is_default ? 'default' : (we.label || 'next'));
      resolved.push({
        source,
        target,
        label,
        guard: we.guard || null,
        is_default: Boolean(we.is_default),
      });
    });
    if (resolved.length) {
      // Prefer workflow_graph edges, but KEEP depends_on edges that the
      // compiled graph does not cover (runtime follow-ups, heal inserts).
      // Replacing wholesale caused "7 steps · 1 link" orphan graphs.
      const keyOf = (e) => `${e.source}->${e.target}`;
      const seen = new Set(resolved.map(keyOf));
      const merged = [...resolved];
      edges.forEach((e) => {
        const k = keyOf(e);
        if (seen.has(k)) return;
        seen.add(k);
        merged.push(e);
      });
      edges.length = 0;
      edges.push(...merged);
    }
  }

  annotateChoiceBranches(nodes, edges);

  // Deterministic ordering (source, then target) for stable renders + tests.
  edges.sort((a, b) => String(a.source).localeCompare(String(b.source), undefined, { numeric: true })
    || String(a.target).localeCompare(String(b.target), undefined, { numeric: true }));
  return { nodes, edges };
}

const _ACTIVE = new Set(['completed', 'running', 'awaiting_approval', 'failed']);

/**
 * Mark outgoing edges from ``choice`` gateways as chosen / unchosen / pending
 * using live step statuses (skipped ⇒ unchosen; active ⇒ chosen).
 * Also flips the choice gateway status to ``completed`` once a branch is taken.
 *
 * @param {Array<object>} nodes
 * @param {Array<object>} edges
 */
export function annotateChoiceBranches(nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const outBySource = new Map();
  edges.forEach((e) => {
    if (!outBySource.has(e.source)) outBySource.set(e.source, []);
    outBySource.get(e.source).push(e);
  });

  nodes.forEach((n) => {
    if (n.node_type !== 'choice') return;
    const outs = outBySource.get(n.id) || [];
    let anyChosen = false;
    outs.forEach((e) => {
      const target = byId.get(e.target);
      const st = target?.status || 'pending';
      if (st === 'skipped') {
        e.branch = 'unchosen';
      } else if (_ACTIVE.has(st)) {
        e.branch = 'chosen';
        anyChosen = true;
      } else {
        e.branch = 'pending';
      }
    });
    if (anyChosen) {
      n.status = 'completed';
      // Remaining pending siblings are still waiting on the engine to skip them;
      // treat as unchosen visually once a winner exists.
      outs.forEach((e) => {
        if (e.branch === 'pending') e.branch = 'unchosen';
      });
    }
  });
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
    const safeId = String(n.id).replace(/[^a-zA-Z0-9_]/g, '_');
    const prefix = n.is_gateway || ['choice', 'parallel', 'observe', 'map', 'loop'].includes(n.node_type)
      ? (n.node_type === 'choice' ? '{' : '[')
      : '[';
    const suffix = prefix === '{' ? '}' : ']';
    const label = String(n.label || `Step ${n.id}`).replace(/"/g, "'");
    lines.push(`  s${safeId}${prefix}"${label}"${suffix}`);
  });
  edges.forEach((e) => {
    const s = String(e.source).replace(/[^a-zA-Z0-9_]/g, '_');
    const t = String(e.target).replace(/[^a-zA-Z0-9_]/g, '_');
    const edgeLabel = e.guard ? `|${String(e.guard).replace(/\|/g, '/')}|` : '';
    lines.push(`  s${s} -->${edgeLabel} s${t}`);
  });  return lines.join('\n');
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

// ── Execution-graph layout (Sugiyama-style flowchart) ─────────────────────
// Longest-path ranks + barycentric within-rank order so edges flow cleanly
// L→R (branched) or T→B (pure sequential). Orphan mid-flow gateways (e.g. an
// observe node with no inbound edge) are pulled ALAP beside their successors
// instead of sitting at rank 0 and shooting long crossing edges.

export const EXEC_LAYOUT = {
  nodeW: 300,
  nodeH: 68,
  colGap: 48,
  rowGap: 36,
  padX: 24,
  padTop: 32,
  padBottom: 24,
};

const STATUS_LANE = {
  completed: 0,
  running: 1,
  awaiting_approval: 2,
  pending: 3,
  skipped: 4,
  failed: 5,
};

function idKey(id) {
  return String(id);
}

function avg(nums) {
  if (!nums.length) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

/**
 * Pull source-less mid-flow nodes (observe/fail side paths) to sit just before
 * their successors so they do not occupy rank 0 and cross the whole DAG.
 */
function tightenOrphanSources(rankOf, preds, succs) {
  let changed = true;
  let guard = 0;
  while (changed && guard < 32) {
    changed = false;
    guard += 1;
    rankOf.forEach((r, id) => {
      const ps = preds.get(id) || [];
      if (ps.length) return;
      const outs = succs.get(id) || [];
      if (!outs.length) return;
      const succRanks = outs.map((s) => rankOf.get(s)).filter((v) => v != null);
      if (!succRanks.length) return;
      const next = Math.max(0, Math.min(...succRanks) - 1);
      if (next !== r) {
        rankOf.set(id, next);
        changed = true;
      }
    });
  }
}

/**
 * True isolates (no in/out edges) used to pile onto rank 0 and float as a
 * disconnected strip above the main spine. Stack them after the connected
 * component so the primary flow stays compact and readable.
 */
function packIsolates(rankOf, preds, succs) {
  let maxConnected = -1;
  rankOf.forEach((r, id) => {
    const ps = preds.get(id) || [];
    const outs = succs.get(id) || [];
    if (ps.length || outs.length) {
      maxConnected = Math.max(maxConnected, r);
    }
  });
  const isolates = [];
  rankOf.forEach((_r, id) => {
    const ps = preds.get(id) || [];
    const outs = succs.get(id) || [];
    if (!ps.length && !outs.length) isolates.push(id);
  });
  if (!isolates.length) return;
  const base = maxConnected < 0 ? 0 : maxConnected + 1;
  isolates.forEach((id, i) => {
    rankOf.set(id, base + i);
  });
}

/**
 * Weakly connected components (undirected over the DAG edges).
 * Largest first — that is the primary journey spine.
 */
function weaklyConnectedComponents(nodes, edges) {
  const parent = new Map(nodes.map((n) => [n.id, n.id]));
  const find = (x) => {
    let r = x;
    while (parent.get(r) !== r) r = parent.get(r);
    let c = x;
    while (c !== r) {
      const n = parent.get(c);
      parent.set(c, r);
      c = n;
    }
    return r;
  };
  const unite = (a, b) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent.set(ra, rb);
  };
  edges.forEach((e) => {
    if (parent.has(e.source) && parent.has(e.target)) unite(e.source, e.target);
  });
  const groups = new Map();
  nodes.forEach((n) => {
    const r = find(n.id);
    if (!groups.has(r)) groups.set(r, []);
    groups.get(r).push(n.id);
  });
  return [...groups.values()].sort((a, b) => b.length - a.length);
}

/**
 * Stack secondary components UNDER the primary spine instead of parking them
 * as a second column (ugly dual vertical strips with empty space between).
 */
function stackDisconnectedComponents(rankOf, nodes, edges) {
  const comps = weaklyConnectedComponents(nodes, edges);
  if (comps.length <= 1) return;
  let globalMax = -1;
  (comps[0] || []).forEach((id) => {
    globalMax = Math.max(globalMax, rankOf.get(id) ?? 0);
  });
  for (let c = 1; c < comps.length; c += 1) {
    const ids = comps[c];
    let localMin = Infinity;
    ids.forEach((id) => {
      localMin = Math.min(localMin, rankOf.get(id) ?? 0);
    });
    if (!Number.isFinite(localMin)) continue;
    const shift = globalMax + 1 - localMin;
    ids.forEach((id) => {
      rankOf.set(id, (rankOf.get(id) ?? 0) + shift);
    });
    ids.forEach((id) => {
      globalMax = Math.max(globalMax, rankOf.get(id) ?? 0);
    });
  }
}

/**
 * Compact ranks to 0..max after orphan tightening (gaps from pulls).
 */
function compressRanks(rankOf) {
  const used = [...new Set(rankOf.values())].sort((a, b) => a - b);
  const map = new Map(used.map((r, i) => [r, i]));
  rankOf.forEach((r, id) => rankOf.set(id, map.get(r)));
}

/**
 * Split long-span edges with invisible dummy nodes so barycenter ordering and
 * edge routing stay local to adjacent ranks (classic Sugiyama).
 */
function insertRankDummies(nodes, edges, rankOf) {
  const outNodes = [...nodes];
  const outEdges = [];
  let seq = 0;
  edges.forEach((e) => {
    const rs = rankOf.get(e.source);
    const rt = rankOf.get(e.target);
    if (rs == null || rt == null || rt <= rs + 1) {
      outEdges.push(e);
      return;
    }
    let prev = e.source;
    for (let r = rs + 1; r < rt; r += 1) {
      const id = `__d${seq++}`;
      outNodes.push({
        id,
        label: '',
        status: 'pending',
        tool_name: null,
        agent_role: null,
        phase_id: null,
        node_type: 'dummy',
        is_gateway: false,
        is_dummy: true,
      });
      rankOf.set(id, r);
      outEdges.push({
        source: prev,
        target: id,
        label: null,
        guard: null,
        is_default: false,
        branch: e.branch || null,
      });
      prev = id;
    }
    outEdges.push({
      source: prev,
      target: e.target,
      label: e.label || null,
      guard: e.guard || null,
      is_default: Boolean(e.is_default),
      branch: e.branch || null,
    });
  });
  return { nodes: outNodes, edges: outEdges };
}

/**
 * Rebuild adjacency after dummy insertion.
 */
function buildAdj(nodes, edges) {
  const preds = new Map(nodes.map((n) => [n.id, []]));
  const succs = new Map(nodes.map((n) => [n.id, []]));
  edges.forEach((e) => {
    if (preds.has(e.target)) preds.get(e.target).push(e.source);
    if (succs.has(e.source)) succs.get(e.source).push(e.target);
  });
  return { preds, succs };
}

/**
 * Barycentric crossing reduction (forward + backward sweeps) with stable
 * tie-breaks: chosen/happy path above escalate/skipped/fail lanes.
 */
function orderRanksBarycenter(byRank, ranks, preds, succs, edges, nodesById) {
  const branchBias = new Map();
  edges.forEach((e) => {
    if (e.branch === 'chosen') branchBias.set(e.target, Math.min(branchBias.get(e.target) ?? 9, 0));
    else if (e.branch === 'unchosen') branchBias.set(e.target, Math.min(branchBias.get(e.target) ?? 9, 2));
  });

  const tieBreak = (a, b) => {
    const ba = branchBias.get(a.id) ?? 1;
    const bb = branchBias.get(b.id) ?? 1;
    if (ba !== bb) return ba - bb;
    const sa = STATUS_LANE[a.status] ?? 3;
    const sb = STATUS_LANE[b.status] ?? 3;
    if (sa !== sb) return sa - sb;
    // Gateways (choice) stay centered relative to plain tasks of same bias.
    const ga = a.is_gateway ? 0 : 1;
    const gb = b.is_gateway ? 0 : 1;
    if (ga !== gb) return ga - gb;
    return idKey(a.id).localeCompare(idKey(b.id), undefined, { numeric: true });
  };

  ranks.forEach((r) => byRank.get(r).sort(tieBreak));

  const positionOf = () => {
    const pos = new Map();
    ranks.forEach((r) => {
      byRank.get(r).forEach((n, i) => pos.set(n.id, i));
    });
    return pos;
  };

  const sortByNeighborAvg = (r, neighborFn) => {
    const pos = positionOf();
    const group = byRank.get(r);
    const scored = group.map((n, idx) => {
      const nbrs = neighborFn(n.id);
      const bary = avg(nbrs.map((id) => pos.get(id)).filter((v) => v != null));
      return { n, bary: bary == null ? idx : bary, idx };
    });
    scored.sort((a, b) => {
      if (a.bary !== b.bary) return a.bary - b.bary;
      return tieBreak(a.n, b.n) || a.idx - b.idx;
    });
    byRank.set(r, scored.map((s) => s.n));
  };

  for (let iter = 0; iter < 16; iter += 1) {
    for (let i = 1; i < ranks.length; i += 1) {
      sortByNeighborAvg(ranks[i], (id) => preds.get(id) || []);
    }
    for (let i = ranks.length - 2; i >= 0; i -= 1) {
      sortByNeighborAvg(ranks[i], (id) => succs.get(id) || []);
    }
  }

  // Final pass: keep chosen-path / completed nodes toward the top lane so the
  // happy path reads as a straight flowchart spine.
  ranks.forEach((r) => {
    const group = byRank.get(r);
    if (group.length < 2) return;
    group.sort(tieBreak);
    // Re-apply one bary pull so tie-break does not undo neighbor alignment.
    sortByNeighborAvg(r, (id) => {
      const ps = preds.get(id) || [];
      return ps.length ? ps : (succs.get(id) || []);
    });
  });

  // Silence unused in case of empty graph tooling.
  void nodesById;
}

/**
 * Layered execution-graph layout for a plan.
 *
 * @param {object} plan - plan payload from GET /ai/plans/{id}/
 * @param {object} [options]
 * @param {'auto'|'tb'|'lr'} [options.direction='auto']
 *   - auto: TB for pure chains; LR when a rank has parallel siblings
 *   - tb / lr: force flow (Plan structure uses tb so parallel fans use width + height)
 * @param {object} [options.layout] - partial override of EXEC_LAYOUT
 * @returns {{nodes: Array<object>, edges: Array<object>, width:number, height:number, phaseBands: Array<object>, direction:'lr'|'tb'}}
 */
export function layoutExecutionGraph(plan, options = {}) {
  const { nodes, edges } = buildPlanGraph(plan);
  const { phases, stepPhase } = buildPlanPhases(plan);

  const preds = new Map(nodes.map((n) => [n.id, []]));
  const succs = new Map(nodes.map((n) => [n.id, []]));
  edges.forEach((e) => {
    if (preds.has(e.target)) preds.get(e.target).push(e.source);
    if (succs.has(e.source)) succs.get(e.source).push(e.target);
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
  tightenOrphanSources(rankOf, preds, succs);
  packIsolates(rankOf, preds, succs);
  stackDisconnectedComponents(rankOf, nodes, edges);
  compressRanks(rankOf);

  const withDummies = insertRankDummies(nodes, edges, rankOf);
  const layoutNodes = withDummies.nodes;
  const layoutEdges = withDummies.edges;
  const adj = buildAdj(layoutNodes, layoutEdges);

  const byRank = new Map();
  layoutNodes.forEach((n) => {
    const r = rankOf.get(n.id) ?? 0;
    if (!byRank.has(r)) byRank.set(r, []);
    byRank.get(r).push(n);
  });
  const ranks = [...byRank.keys()].sort((a, b) => a - b);
  const nodesById = new Map(layoutNodes.map((n) => [n.id, n]));
  orderRanksBarycenter(byRank, ranks, adj.preds, adj.succs, layoutEdges, nodesById);

  const L = { ...EXEC_LAYOUT, ...(options.layout || {}) };
  const maxRank = ranks.length ? ranks[ranks.length - 1] : 0;
  // Lane count ignores invisible dummies so height matches visible flowchart.
  const maxInRank = ranks.length
    ? Math.max(...ranks.map((r) => byRank.get(r).filter((n) => !n.is_dummy).length || 1))
    : 0;
  const prefer = options.direction || 'auto';
  const direction = prefer === 'tb' || prefer === 'lr'
    ? prefer
    : (maxInRank <= 1 && nodes.length >= 3 ? 'tb' : 'lr');

  let width;
  let height;
  if (direction === 'tb') {
    // Parallel siblings share a rank → sit side-by-side; use full lane width.
    width = L.padX * 2 + maxInRank * L.nodeW + Math.max(0, maxInRank - 1) * L.colGap;
    height = L.padTop + (maxRank + 1) * L.nodeH + maxRank * L.rowGap + L.padBottom;
  } else {
    width = L.padX * 2 + (maxRank + 1) * L.nodeW + maxRank * L.colGap;
    height = L.padTop + maxInRank * L.nodeH + Math.max(0, maxInRank - 1) * L.rowGap + L.padBottom;
  }

  const laid = [];
  ranks.forEach((r) => {
    const group = byRank.get(r);
    // Place visible nodes on the lane grid; dummies sit on the same y as the
    // barycentric slot so long edges track the lane without drawing a card.
    const visible = group.filter((n) => !n.is_dummy);
    const visibleIndex = new Map(visible.map((n, i) => [n.id, i]));
    if (direction === 'tb') {
      // Left-align ranks on a spine — centering skinny ranks in a wide canvas
      // left a sea of empty whitespace (Plan "fill" complaint).
      const startX = L.padX;
      const y = L.padTop + r * (L.nodeH + L.rowGap);
      group.forEach((n, i) => {
        const lane = visibleIndex.has(n.id) ? visibleIndex.get(n.id) : i;
        const x = startX + lane * (L.nodeW + L.colGap);
        if (n.is_dummy) {
          laid.push({
            ...n,
            x: x + L.nodeW / 2,
            y: y + L.nodeH / 2,
            w: 0,
            h: 0,
            rank: r,
            phase_id: null,
          });
        } else {
          laid.push({
            ...n,
            x,
            y,
            w: L.nodeW,
            h: L.nodeH,
            rank: r,
            phase_id: stepPhase[n.id] ?? null,
          });
        }
      });
    } else {
      // Top-align lanes on the spine (same reason as TB left-align).
      const startY = L.padTop;
      const x = L.padX + r * (L.nodeW + L.colGap);
      group.forEach((n, i) => {
        const lane = visibleIndex.has(n.id) ? visibleIndex.get(n.id) : Math.min(i, Math.max(visible.length - 1, 0));
        const y = startY + lane * (L.nodeH + L.rowGap);
        if (n.is_dummy) {
          laid.push({
            ...n,
            x: x + L.nodeW / 2,
            y: y + L.nodeH / 2,
            w: 0,
            h: 0,
            rank: r,
            phase_id: null,
          });
        } else {
          laid.push({
            ...n,
            x,
            y,
            w: L.nodeW,
            h: L.nodeH,
            rank: r,
            phase_id: stepPhase[n.id] ?? null,
          });
        }
      });
    }
  });

  const laidById = new Map(laid.map((n) => [n.id, n]));
  const laidEdges = layoutEdges
    .map((e) => {
      const s = laidById.get(e.source);
      const t = laidById.get(e.target);
      if (!s || !t) return null;
      const sDummy = Boolean(s.is_dummy);
      const tDummy = Boolean(t.is_dummy);
      if (direction === 'tb') {
        return {
          source: e.source,
          target: e.target,
          label: sDummy || tDummy ? null : e.label || null,
          guard: e.guard || null,
          is_default: Boolean(e.is_default),
          branch: e.branch || null,
          sourceX: sDummy ? s.x : s.x + L.nodeW / 2,
          sourceY: sDummy ? s.y : s.y + L.nodeH,
          targetX: tDummy ? t.x : t.x + L.nodeW / 2,
          targetY: tDummy ? t.y : t.y,
        };
      }
      return {
        source: e.source,
        target: e.target,
        label: sDummy || tDummy ? null : e.label || null,
        guard: e.guard || null,
        is_default: Boolean(e.is_default),
        branch: e.branch || null,
        sourceX: sDummy ? s.x : s.x + L.nodeW,
        sourceY: sDummy ? s.y : s.y + L.nodeH / 2,
        targetX: tDummy ? t.x : t.x,
        targetY: tDummy ? t.y : t.y + L.nodeH / 2,
      };
    })
    .filter(Boolean);

  const phaseBands = phases
    .map((p) => {
      const owned = p.step_ids
        .map((id) => laidById.get(id))
        .filter(Boolean);
      if (!owned.length) return null;
      if (direction === 'tb') {
        const ys = owned.map((n) => n.y);
        const xs = owned.map((n) => n.x);
        return {
          phase_id: p.phase_id,
          name: p.name,
          strategy: p.strategy,
          x: Math.min(...xs),
          width: Math.max(...xs) + L.nodeW - Math.min(...xs),
          y: Math.min(...ys),
          height: Math.max(...ys) + L.nodeH - Math.min(...ys),
        };
      }
      const xs = owned.map((n) => n.x);
      return {
        phase_id: p.phase_id,
        name: p.name,
        strategy: p.strategy,
        x: Math.min(...xs),
        width: Math.max(...xs) + L.nodeW - Math.min(...xs),
      };
    })
    .filter(Boolean);

  return {
    nodes: laid,
    edges: laidEdges,
    width,
    height,
    phaseBands,
    direction,
  };
}
