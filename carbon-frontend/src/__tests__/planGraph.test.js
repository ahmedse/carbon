// src/__tests__/planGraph.test.js
// W3-F — pure helpers: plan → DAG (nodes=steps, edges=depends_on), outcome
// diff summaries, the Mermaid graph source, and the layered execution-graph
// layout (TensorFlow-style ranks + phase bands).
import { describe, it, expect } from 'vitest';
import {
  buildPlanGraph,
  summarizePlanDiff,
  planDagMermaid,
  layoutExecutionGraph,
} from '../utils/planGraph';

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
    expect(nodes[0]).toMatchObject({
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

  it('enriches from workflow_graph with gateway + guard edges', () => {
    const plan = {
      ...PLAN,
      workflow_graph: {
        version: '1',
        entry: 'c',
        nodes: [
          { id: 'c', node_type: 'choice', intent: 'Pick path', meta: {} },
          { id: 't0', node_type: 'task', intent: 'Search', meta: { step_id: 0 } },
          { id: 't1', node_type: 'task', intent: 'Create', meta: { step_id: 1 } },
        ],
        edges: [
          { source: 'c', target: 't0', guard: "status == 'ok'" },
          { source: 'c', target: 't1', is_default: true },
        ],
      },
    };
    const { nodes, edges } = buildPlanGraph(plan);
    expect(nodes.some((n) => n.node_type === 'choice' && n.is_gateway)).toBe(true);
    expect(edges.some((e) => e.guard === "status == 'ok'")).toBe(true);
  });

  it('annotates payroll board-pack choice: within-band chosen, escalate unchosen', () => {
    const plan = {
      id: 'board-pack',
      status: 'completed',
      steps: [
        { step_id: 0, intent: 'Fetch', tool_name: 'call_host_api', status: 'completed', depends_on: [], agent_role: 'domain_specialist' },
        { step_id: 1, intent: 'Variance', tool_name: 'call_host_api', status: 'completed', depends_on: [0], agent_role: 'domain_specialist' },
        { step_id: 2, intent: 'Summarize', tool_name: null, status: 'completed', depends_on: [1], agent_role: 'researcher' },
        { step_id: 3, intent: 'Critic', tool_name: null, status: 'completed', depends_on: [2], agent_role: 'critic' },
        { step_id: 4, intent: 'Export', tool_name: 'export_document', status: 'completed', depends_on: [3], agent_role: 'orchestrator' },
        { step_id: 5, intent: 'Escalate Finance', tool_name: null, status: 'skipped', depends_on: [1], agent_role: 'orchestrator' },
      ],
      workflow_graph: {
        version: '1',
        entry: 't0',
        nodes: [
          { id: 't0', node_type: 'task', meta: { step_id: 0 } },
          { id: 't1', node_type: 'task', meta: { step_id: 1 } },
          { id: 'choice_variance', node_type: 'choice', intent: 'Variance within policy band?' },
          { id: 't2', node_type: 'task', meta: { step_id: 2 } },
          { id: 't5', node_type: 'human', meta: { step_id: 5 } },
          { id: 't3', node_type: 'task', meta: { step_id: 3 } },
          { id: 'observe_repair', node_type: 'observe', intent: 'Repair critic findings' },
          { id: 't4', node_type: 'task', meta: { step_id: 4 } },
          { id: 'fail_block_export', node_type: 'fail', intent: 'Block export' },
        ],
        edges: [
          { source: 't0', target: 't1' },
          { source: 't1', target: 'choice_variance' },
          { source: 'choice_variance', target: 't2', guard: 'variance_pct <= 2.0', label: 'within band' },
          { source: 'choice_variance', target: 't5', is_default: true, label: 'escalate' },
          { source: 't2', target: 't3' },
          { source: 't3', target: 't4' },
          { source: 'observe_repair', target: 't4', guard: 'critic_healed == true' },
          { source: 'observe_repair', target: 'fail_block_export', is_default: true },
          { source: 't5', target: 'fail_block_export' },
        ],
      },
    };
    const { nodes, edges } = buildPlanGraph(plan);
    const choice = nodes.find((n) => n.id === 'choice_variance');
    expect(choice).toBeTruthy();
    expect(choice.is_gateway).toBe(true);
    expect(choice.status).toBe('completed');
    const within = edges.find((e) => e.source === 'choice_variance' && e.target === 2);
    const escalate = edges.find((e) => e.source === 'choice_variance' && e.target === 5);
    expect(within?.branch).toBe('chosen');
    expect(escalate?.branch).toBe('unchosen');
    expect(nodes.some((n) => n.id === 'observe_repair' && n.node_type === 'observe')).toBe(true);
  });

  it('keeps depends_on edges when workflow_graph is sparse', () => {
    const plan = {
      steps: [
        { step_id: 0, intent: 'a', status: 'completed', depends_on: [] },
        { step_id: 1, intent: 'b', status: 'completed', depends_on: [0] },
        { step_id: 2, intent: 'follow-up', status: 'pending', depends_on: [1] },
      ],
      workflow_graph: {
        version: '1',
        entry: 't0',
        nodes: [
          { id: 't0', node_type: 'task', intent: 'a', meta: { step_id: 0 } },
          { id: 't1', node_type: 'task', intent: 'b', meta: { step_id: 1 } },
        ],
        edges: [
          { source: 't0', target: 't1' },
        ],
      },
    };
    const { edges } = buildPlanGraph(plan);
    expect(edges.some((e) => e.source === 0 && e.target === 1)).toBe(true);
    expect(edges.some((e) => e.source === 1 && e.target === 2)).toBe(true);
  });

  it('annotates live choice branches from step status', () => {
    const plan = {
      steps: [
        { step_id: 0, intent: 'ok path', status: 'completed', depends_on: [] },
        { step_id: 1, intent: 'bad path', status: 'skipped', depends_on: [] },
      ],
      workflow_graph: {
        version: '1',
        entry: 'c',
        nodes: [
          { id: 'c', node_type: 'choice', intent: 'Pick', meta: {} },
          { id: 't0', node_type: 'task', intent: 'ok', meta: { step_id: 0 } },
          { id: 't1', node_type: 'task', intent: 'bad', meta: { step_id: 1 } },
        ],
        edges: [
          { source: 'c', target: 't0', guard: "status == 'ok'" },
          { source: 'c', target: 't1', is_default: true },
        ],
      },
    };
    const { nodes, edges } = buildPlanGraph(plan);
    const chosen = edges.find((e) => e.target === 0);
    const unchosen = edges.find((e) => e.target === 1);
    expect(chosen.branch).toBe('chosen');
    expect(unchosen.branch).toBe('unchosen');
    expect(nodes.find((n) => n.id === 'c')?.status).toBe('completed');
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

describe('layoutExecutionGraph', () => {
  it('stacks pure sequential plans top→bottom in the Pulse rail', () => {
    const { nodes, direction } = layoutExecutionGraph(PLAN);

    expect(nodes.filter((n) => !n.is_dummy)).toHaveLength(3);
    expect(direction).toBe('tb');
    const byId = Object.fromEntries(nodes.filter((n) => !n.is_dummy).map((n) => [n.id, n]));

    // step 0 is a source (rank 0); step 1 depends on 0 (rank 1);
    // step 2 depends on 0 AND 1 → longest path → rank 2.
    expect(byId[0].rank).toBe(0);
    expect(byId[1].rank).toBe(1);
    expect(byId[2].rank).toBe(2);

    // TB: deeper rank → strictly larger y; same column x.
    expect(byId[2].y).toBeGreaterThan(byId[1].y);
    expect(byId[1].y).toBeGreaterThan(byId[0].y);
    expect(byId[0].x).toBe(byId[2].x);
  });

  it('assigns phase ids and emits phase bands', () => {
    const plan = {
      ...PLAN,
      phases: [
        { phase_id: 1, name: 'Investigate', goal: '', strategy: 'sequential', step_ids: [0] },
        { phase_id: 2, name: 'Act', goal: '', strategy: 'parallel', step_ids: [1, 2] },
      ],
    };
    const { nodes, phaseBands, direction } = layoutExecutionGraph(plan);

    const byId = Object.fromEntries(nodes.filter((n) => !n.is_dummy).map((n) => [n.id, n]));
    expect(byId[0].phase_id).toBe(1);
    expect(byId[1].phase_id).toBe(2);

    expect(phaseBands.some((b) => b.name === 'Investigate')).toBe(true);
    expect(phaseBands.some((b) => b.name === 'Act' && b.strategy === 'parallel')).toBe(true);
    const act = phaseBands.find((b) => b.name === 'Act');
    if (direction === 'tb') {
      expect(act.y + act.height).toBeGreaterThanOrEqual(byId[2].y + byId[2].h - 1);
    } else {
      expect(act.x + act.width).toBeGreaterThanOrEqual(byId[2].x + 168);
    }
  });

  it('emits directed edges with flow-aligned anchor points', () => {
    const { edges, direction } = layoutExecutionGraph(PLAN);
    const real = edges.filter((e) => !String(e.source).startsWith('__d') && !String(e.target).startsWith('__d'));
    // Long-span 0→2 is split through a dummy — at least the adjacent links remain.
    expect(edges.length).toBeGreaterThanOrEqual(3);
    if (direction === 'tb') {
      edges.forEach((e) => {
        expect(e.targetY).toBeGreaterThanOrEqual(e.sourceY);
      });
    } else {
      real.forEach((e) => {
        expect(e.targetX).toBeGreaterThan(e.sourceX);
      });
    }
  });

  it('carries per-node width/height so nodes can be rendered and resized generically', () => {
    const { nodes } = layoutExecutionGraph(PLAN);
    nodes.filter((n) => !n.is_dummy).forEach((n) => {
      expect(n.w).toBeGreaterThan(0);
      expect(n.h).toBeGreaterThan(0);
    });
  });

  it('handles a plan with no steps', () => {
    const layout = layoutExecutionGraph({ id: 'x', steps: [] });
    expect(layout.nodes).toEqual([]);
    expect(layout.edges).toEqual([]);
    expect(layout.phaseBands).toEqual([]);
    expect(layout.width).toBeGreaterThan(0);
    expect(layout.height).toBeGreaterThan(0);
  });

  it('packs disconnected isolates after the main spine (not floating at rank 0)', () => {
    const plan = {
      id: 'iso',
      steps: [
        { step_id: 0, intent: 'Fetch', depends_on: [], status: 'pending' },
        { step_id: 1, intent: 'Compute', depends_on: [0], status: 'pending' },
        { step_id: 2, intent: 'Orphan validate', depends_on: [], status: 'pending' },
        { step_id: 3, intent: 'Orphan report', depends_on: [], status: 'pending' },
      ],
    };
    const { nodes, direction } = layoutExecutionGraph(plan, { direction: 'tb' });
    expect(direction).toBe('tb');
    const byId = Object.fromEntries(nodes.filter((n) => !n.is_dummy).map((n) => [n.id, n]));
    expect(byId[0].rank).toBe(0);
    expect(byId[1].rank).toBe(1);
    expect(byId[2].rank).toBeGreaterThan(byId[1].rank);
    expect(byId[3].rank).toBeGreaterThan(byId[2].rank);
    // Spine left-aligned — no mid-canvas float for the sequential chain.
    expect(byId[0].x).toBe(byId[1].x);
  });

  it('lays out branched board-pack as T→B flowchart with chosen path left of escalate', () => {
    const plan = {
      id: 'board-pack',
      status: 'completed',
      steps: [
        { step_id: 0, intent: 'Fetch', tool_name: 'call_host_api', status: 'completed', depends_on: [], agent_role: 'domain_specialist' },
        { step_id: 1, intent: 'Variance', tool_name: 'call_host_api', status: 'completed', depends_on: [0], agent_role: 'domain_specialist' },
        { step_id: 2, intent: 'Summarize', tool_name: null, status: 'completed', depends_on: [1], agent_role: 'researcher' },
        { step_id: 3, intent: 'Critic', tool_name: null, status: 'completed', depends_on: [2], agent_role: 'critic' },
        { step_id: 4, intent: 'Export', tool_name: 'export_document', status: 'completed', depends_on: [3], agent_role: 'orchestrator' },
        { step_id: 5, intent: 'Escalate Finance', tool_name: null, status: 'skipped', depends_on: [1], agent_role: 'orchestrator' },
      ],
      workflow_graph: {
        version: '1',
        entry: 't0',
        nodes: [
          { id: 't0', node_type: 'task', meta: { step_id: 0 } },
          { id: 't1', node_type: 'task', meta: { step_id: 1 } },
          { id: 'choice_variance', node_type: 'choice', intent: 'Variance within policy band?' },
          { id: 't2', node_type: 'task', meta: { step_id: 2 } },
          { id: 't5', node_type: 'human', meta: { step_id: 5 } },
          { id: 't3', node_type: 'task', meta: { step_id: 3 } },
          { id: 'observe_repair', node_type: 'observe', intent: 'Repair critic findings' },
          { id: 't4', node_type: 'task', meta: { step_id: 4 } },
          { id: 'fail_block_export', node_type: 'fail', intent: 'Block export' },
        ],
        edges: [
          { source: 't0', target: 't1' },
          { source: 't1', target: 'choice_variance' },
          { source: 'choice_variance', target: 't2', guard: 'variance_pct <= 2.0', label: 'within band' },
          { source: 'choice_variance', target: 't5', is_default: true, label: 'escalate' },
          { source: 't2', target: 't3' },
          { source: 't3', target: 't4' },
          { source: 'observe_repair', target: 't4', guard: 'critic_healed == true' },
          { source: 'observe_repair', target: 'fail_block_export', is_default: true },
          { source: 't5', target: 'fail_block_export' },
        ],
      },
    };
    const { nodes, direction } = layoutExecutionGraph(plan);
    expect(direction).toBe('tb');
    const visible = nodes.filter((n) => !n.is_dummy);
    const byId = Object.fromEntries(visible.map((n) => [n.id, n]));

    // Orphan observe must not sit at the entry rank (that caused full-width crossings).
    expect(byId.observe_repair.rank).toBeGreaterThan(0);
    expect(byId.observe_repair.rank).toBeLessThanOrEqual(byId[4].rank);

    // Branch siblings share a rank: chosen summarize left of escalate.
    expect(byId[2].rank).toBe(byId[5].rank);
    expect(byId[2].x).toBeLessThan(byId[5].x);

    // Flow top→bottom along the happy path.
    expect(byId[1].y).toBeGreaterThan(byId[0].y);
    expect(byId.choice_variance.y).toBeGreaterThan(byId[1].y);
    expect(byId[4].y).toBeGreaterThan(byId[3].y);
  });
});

describe('layoutExecutionGraph — disconnected components', () => {
  it('stacks a secondary chain under the primary spine (not a second column)', () => {
    const plan = {
      id: 'ugly-dual',
      status: 'pending_approval',
      steps: [
        { step_id: 0, intent: 'List employees', status: 'pending', depends_on: [] },
        { step_id: 1, intent: 'Fetch salaries', status: 'pending', depends_on: [0] },
        { step_id: 2, intent: 'Analyze distribution', status: 'pending', depends_on: [1] },
        // Disconnected second chain (no depends_on into the spine)
        { step_id: 3, intent: 'Generate tables', status: 'pending', depends_on: [] },
        { step_id: 4, intent: 'Generate charts', status: 'pending', depends_on: [3] },
      ],
    };
    const { nodes, direction } = layoutExecutionGraph(plan, { direction: 'tb' });
    expect(direction).toBe('tb');
    const byId = Object.fromEntries(nodes.filter((n) => !n.is_dummy).map((n) => [n.id, n]));
    // Primary spine then secondary — all share one x lane (left-aligned).
    expect(byId[0].x).toBe(byId[1].x);
    expect(byId[3].x).toBe(byId[0].x);
    // Secondary sits below primary, not beside rank 0.
    expect(byId[3].y).toBeGreaterThan(byId[2].y);
    expect(byId[4].y).toBeGreaterThan(byId[3].y);
  });
});
