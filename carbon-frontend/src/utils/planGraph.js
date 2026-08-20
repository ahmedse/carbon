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
