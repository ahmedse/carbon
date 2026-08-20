// src/__tests__/planGraph.test.js
// W3-F — pure helpers: plan → DAG (nodes=steps, edges=depends_on), outcome
// diff summaries, and the Mermaid graph source.
import { describe, it, expect } from 'vitest';
import { buildPlanGraph, summarizePlanDiff, planDagMermaid } from '../utils/planGraph';

const PLAN = {
  id: 'plan-1',
  status: 'pending_approval',
  brief: 'Audit duplicates.',
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', status: 'pending', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', status: 'completed', depends_on: [0] },
    { step_id: 2, intent: 'Report the findings', tool_name: 'search_entity', status: 'running', depends_on: [0, 1] },
  ],
};

describe('buildPlanGraph', () => {
  it('maps steps to nodes and depends_on to edges', () => {
    const { nodes, edges } = buildPlanGraph(PLAN);

    expect(nodes).toHaveLength(3);
    expect(nodes[0]).toEqual({
      id: 0,
      label: 'Search for duplicate records',
      status: 'pending',
      tool_name: 'search_entity',
    });
    expect(edges).toEqual([
      { source: 0, target: 1, label: 'depends on' },
      { source: 0, target: 2, label: 'depends on' },
      { source: 1, target: 2, label: 'depends on' },
    ]);
  });

  it('skips orphan dependency ids so malformed plans never crash', () => {
    const plan = {
      ...PLAN,
      steps: [
        { step_id: 0, intent: 'First', tool_name: null, status: 'pending', depends_on: [99] },
        { step_id: 1, intent: 'Second', tool_name: null, status: 'pending', depends_on: [0] },
      ],
    };
    const { nodes, edges } = buildPlanGraph(plan);
    expect(nodes).toHaveLength(2);
    expect(edges).toEqual([{ source: 0, target: 1, label: 'depends on' }]);
  });

  it('tolerates a plan with no steps', () => {
    const { nodes, edges } = buildPlanGraph({ id: 'x', steps: null });
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });
});

describe('summarizePlanDiff', () => {
  it('summarizes added/removed/changed in outcome terms', () => {
    const summary = summarizePlanDiff({
      added: [{ intent: 'Send a summary email' }],
      removed: [{ intent: 'Search for duplicate records' }],
      changed: [{ old: { intent: 'Create a rule' }, new: { intent: 'Create two rules' } }],
    });

    expect(summary.count).toBe(3);
    expect(summary.summary).toBe('1 step added, 1 step removed, 1 step changed.');
    expect(summary.added).toEqual(['Send a summary email']);
    expect(summary.removed).toEqual(['Search for duplicate records']);
    expect(summary.changed).toEqual([{ from: 'Create a rule', to: 'Create two rules' }]);
  });

  it('falls back to title and empty-intent safety', () => {
    const summary = summarizePlanDiff({
      added: [{ title: 'Titled step' }],
      removed: [{}],
      changed: [],
    });
    expect(summary.summary).toBe('1 step added, 1 step removed.');
    expect(summary.added).toEqual(['Titled step']);
  });

  it('reports no changes for an empty or missing diff', () => {
    expect(summarizePlanDiff(undefined).summary).toBe('No changes to the plan steps.');
    expect(summarizePlanDiff({ added: [], removed: [], changed: [] }).count).toBe(0);
  });
});

describe('planDagMermaid', () => {
  it('builds a graph LR definition from steps + depends_on', () => {
    const src = planDagMermaid(PLAN);
    expect(src.startsWith('graph LR')).toBe(true);
    expect(src).toContain('s0["Search for duplicate records"]');
    expect(src).toContain('s1["Create a rule to prevent duplicates"]');
    expect(src).toContain('s0 --> s1');
    expect(src).toContain('s1 --> s2');
  });

  it('escapes quotes in free-text intents', () => {
    const src = planDagMermaid({
      steps: [{ step_id: 0, intent: 'He said "hi"', status: 'pending' }],
    });
    expect(src).toContain(`s0["He said 'hi'"]`);
  });

  it('handles a plan with no steps', () => {
    expect(planDagMermaid({ steps: [] })).toContain('No steps yet');
  });
});
