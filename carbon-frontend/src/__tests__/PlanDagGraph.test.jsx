// src/__tests__/PlanDagGraph.test.jsx
// W3-F — live plan DAG rendered as a layered DIRECTED execution graph:
// nodes = steps, edges = depends_on with arrowheads (marker), node color =
// step status via theme tokens, legend, live badge, empty state, a movable +
// resizable canvas (pan/zoom), a detailed inspection pane (docked, never
// floating), and an expand button that opens the graph in a full-screen modal
// (jsdom-safe, no d3).
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import PlanDagGraph, {
  planStepStatusColor,
  planStepStatusLabel,
  planStepStatusChipColor,
  parallelLaneGroups,
  laneAttentionLabel,
} from '../components/graph/PlanDagGraph';

const theme = createTheme();

// MUI Dialog/Modal rely on matchMedia in jsdom — provide a no-op polyfill.
const originalMatchMedia = window.matchMedia;
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
});
afterAll(() => {
  window.matchMedia = originalMatchMedia;
});

const PLAN = {
  id: 'plan-1',
  status: 'running',
  brief: 'Audit duplicates.',
  steps: [
    { step_id: 0, intent: 'Search for duplicate records', tool_name: 'search_entity', status: 'completed', depends_on: [] },
    { step_id: 1, intent: 'Create a rule to prevent duplicates', tool_name: 'create_dq_rule', status: 'running', depends_on: [0] },
    { step_id: 2, intent: 'Report the findings', tool_name: 'search_entity', status: 'pending', depends_on: [0, 1] },
  ],
};

const renderGraph = (props) =>
  render(
    <ThemeProvider theme={theme}>
      <PlanDagGraph {...props} />
    </ThemeProvider>,
  );

describe('PlanDagGraph', () => {
  it('renders the DAG with step/link counts and legend chips', () => {
    renderGraph({ plan: PLAN });

    expect(screen.getByTestId('plan-dag-graph')).toBeInTheDocument();
    expect(screen.getByText('Plan graph')).toBeInTheDocument();
    expect(screen.getByText('3 steps · 3 links')).toBeInTheDocument();
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0);
    expect(screen.getByText('Needs approval')).toBeInTheDocument();
    expect(screen.getAllByText('Finished').length).toBeGreaterThan(0);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders a directed SVG with arrowhead markers on edges', () => {
    const { container } = renderGraph({ plan: PLAN });

    const marker = container.querySelector('marker#plan-arrow');
    expect(marker).not.toBeNull();
    expect(marker.getAttribute('orient')).toBe('auto-start-reverse');

    // Long-span edges are split through invisible dummies, so path count may
    // exceed the logical link count shown in the header.
    const edgePaths = container.querySelectorAll('path[marker-end]');
    expect(edgePaths.length).toBeGreaterThanOrEqual(3);
    edgePaths.forEach((p) => expect(p.getAttribute('marker-end')).toBe('url(#plan-arrow)'));
  });

  it('lays sequential steps top-to-bottom by execution rank', () => {
    const { container } = renderGraph({ plan: PLAN });

    const step0 = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const step2 = container.querySelector('[role="button"][aria-label^="Step 2:"]');
    expect(step0).not.toBeNull();
    expect(step2).not.toBeNull();
    // Pure sequential plans stack TB in the Pulse rail.
    const y0 = Number(step0.getAttribute('transform').match(/translate\([\d.-]+,\s*([\d.-]+)/)[1]);
    const y2 = Number(step2.getAttribute('transform').match(/translate\([\d.-]+,\s*([\d.-]+)/)[1]);
    expect(y2).toBeGreaterThan(y0);
  });

  it('renders intent on DAG nodes without tool noise', () => {
    const multiAgentPlan = {
      id: 'plan-agents',
      status: 'completed',
      brief: 'Board pack',
      steps: [
        {
          step_id: 0,
          intent: 'Fetch headcount and payroll totals',
          tool_name: 'call_host_api',
          agent_role: 'domain_specialist',
          status: 'completed',
          depends_on: [],
        },
        {
          step_id: 1,
          intent: 'Critic review: flag compliance risks',
          tool_name: null,
          agent_role: 'critic',
          status: 'completed',
          depends_on: [0],
        },
        {
          step_id: 2,
          intent: 'Export board pack',
          tool_name: 'export_document',
          agent_role: 'orchestrator',
          status: 'completed',
          depends_on: [1],
        },
      ],
    };
    renderGraph({ plan: multiAgentPlan });

    expect(screen.getAllByText(/Fetch headcount/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/call_host_api/)).not.toBeInTheDocument();
    expect(screen.queryByText(/export_document/)).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Step 1:.*Critic/ }),
    ).toBeInTheDocument();
  });

  it('opens a light business inspection pane when a node is clicked', () => {
    renderGraph({ plan: PLAN });

    expect(screen.queryByTestId('plan-step-detail')).not.toBeInTheDocument();

    const step0 = screen.getByRole('button', { name: /Step 0:/ });
    fireEvent.click(step0);

    const pane = screen.getByTestId('plan-step-detail');
    expect(pane).toBeInTheDocument();
    expect(within(pane).getByText('Step details')).toBeInTheDocument();
    expect(within(pane).getByTestId('beat-detail-body')).toBeInTheDocument();
    expect(within(pane).getByText(/Next: Create a rule/)).toBeInTheDocument();
    expect(within(pane).queryByText('search_entity')).not.toBeInTheDocument();
    expect(within(pane).queryByText(/More detail/)).not.toBeInTheDocument();
    expect(within(pane).queryByText(/Show inputs/)).not.toBeInTheDocument();
    expect(within(pane).queryByText(/Show output/)).not.toBeInTheDocument();

    fireEvent.click(within(pane).getByRole('button', { name: /Close step details/ }));
    expect(screen.queryByTestId('plan-step-detail')).not.toBeInTheDocument();
  });

  it('shows the Live badge only while the run is live', () => {
    const { rerender } = renderGraph({ plan: PLAN, live: true });
    expect(screen.getByText('Live')).toBeInTheDocument();

    rerender(
      <ThemeProvider theme={theme}>
        <PlanDagGraph plan={PLAN} live={false} />
      </ThemeProvider>,
    );
    expect(screen.queryByText('Live')).not.toBeInTheDocument();
  });

  it('shows an empty state when the plan has no steps', () => {
    renderGraph({ plan: { id: 'plan-x', steps: [] } });
    expect(screen.getByText('This plan has no steps to graph yet.')).toBeInTheDocument();
  });

  it('offers a Reset view control (pan/zoom restored)', () => {
    renderGraph({ plan: PLAN });
    expect(screen.getByRole('button', { name: /Reset view/ })).toBeInTheDocument();
  });

  it('expands to a full-screen modal with its own zoomable canvas', async () => {
    const { container } = renderGraph({ plan: PLAN });

    fireEvent.click(screen.getByTestId('plan-graph-expand'));

    // Modal opens with the graph at full size + a unique marker id (no DOM id
    // collision with the inline canvas).
    await waitFor(() => expect(screen.getByText('Plan graph — full view')).toBeInTheDocument());
    expect(screen.getByTestId('plan-dag-graph-modal')).toBeInTheDocument();
    expect(container.querySelectorAll('marker#plan-arrow').length).toBe(1); // inline only
    expect(document.querySelector('marker#plan-arrow-modal')).not.toBeNull();

    // The docked detail pane still works inside the modal.
    const modalCanvas = screen.getByTestId('plan-dag-graph-modal');
    fireEvent.click(within(modalCanvas).getByRole('button', { name: /Step 0:/ }));
    expect(screen.getByTestId('plan-step-detail-modal')).toBeInTheDocument();

    // Close dismisses the modal again.
    fireEvent.click(screen.getByTestId('plan-graph-modal-close'));
    await waitFor(() =>
      expect(screen.queryByText('Plan graph — full view')).not.toBeInTheDocument(),
    );
  });

  it('structure mode: agent tasks are card boxes; gateways keep BPMN shapes', () => {
    const multi = {
      id: 'p-shapes',
      status: 'pending_approval',
      brief: 'Board pack',
      steps: [
        { step_id: 0, intent: 'Fetch totals', tool_name: 'call_host_api', agent_role: 'domain_specialist', status: 'pending', depends_on: [] },
        { step_id: 1, intent: 'Research notes', tool_name: null, agent_role: 'researcher', status: 'pending', depends_on: [0] },
        { step_id: 2, intent: 'Critic review', tool_name: null, agent_role: 'critic', status: 'pending', depends_on: [1] },
        { step_id: 3, intent: 'Export pack', tool_name: 'export_document', agent_role: 'orchestrator', status: 'pending', depends_on: [2] },
      ],
    };
    const { container } = renderGraph({ plan: multi, mode: 'structure' });
    expect(screen.getByTestId('plan-shape-legend')).toBeInTheDocument();
    const cards = container.querySelectorAll('[data-shape="roundedRect"]');
    expect(cards.length).toBeGreaterThanOrEqual(4);
  });

  it('structure mode: docked detail box collapsible', () => {
    renderGraph({
      plan: {
        ...PLAN,
        steps: PLAN.steps.map((s) => ({ ...s, status: 'completed' })),
      },
      mode: 'structure',
    });
    expect(screen.getByTestId('plan-structure-detail')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('plan-structure-collapse'));
    expect(screen.getByTestId('plan-structure-detail-collapsed')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('plan-structure-expand'));
    expect(screen.getByTestId('plan-structure-detail')).toBeInTheDocument();
  });
});

describe('EnterpriseGraph interactions (movable/resizable nodes, live status, toolbar)', () => {
  it('offers the full enterprise toolbar (zoom/fit/reset/redraw/export/maximize)', () => {
    renderGraph({ plan: PLAN });

    expect(screen.getByRole('button', { name: 'Zoom in' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Zoom out' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Zoom to fit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reset view' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Redraw layout' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export as PNG' })).toBeInTheDocument();
    expect(screen.getByTestId('plan-graph-expand')).toBeInTheDocument();
  });

  it('zooms the canvas when the zoom-in control is clicked', () => {
    const { container } = renderGraph({ plan: PLAN });
    const transformG = container.querySelector('svg > g[transform]');
    const before = transformG.getAttribute('transform');

    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));

    expect(transformG.getAttribute('transform')).not.toBe(before);
  });

  it('lets a node be dragged to a new position (nodes themselves are movable)', () => {
    const { container } = renderGraph({ plan: PLAN });
    const node = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const before = node.getAttribute('transform');

    fireEvent.mouseDown(node, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(node, { clientX: 140, clientY: 130 });
    fireEvent.mouseUp(node, { clientX: 140, clientY: 130 });

    expect(node.getAttribute('transform')).not.toBe(before);
  });

  it('lets a node be resized via its bottom-right handle', () => {
    const { container } = renderGraph({ plan: PLAN });
    const handle = container.querySelector('[data-testid="plan-dag-graph-resize-0"]');
    const node = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const frame = node.querySelector('path');
    const beforeD = frame.getAttribute('d');

    fireEvent.mouseDown(handle, { button: 0, clientX: 200, clientY: 200 });
    fireEvent.mouseMove(handle, { clientX: 240, clientY: 220 });
    fireEvent.mouseUp(handle, { clientX: 240, clientY: 220 });

    expect(frame.getAttribute('d')).not.toBe(beforeD);
  });

  it('keeps a correct position when dragging after a resize (no NaN origin)', () => {
    const { container } = renderGraph({ plan: PLAN });
    const node = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const before = node.getAttribute('transform');

    // Resize first — the drag origin must come from the EFFECTIVE (post-resize)
    // geometry, not a stale raw-layout position (W5-E).
    const handle = container.querySelector('[data-testid="plan-dag-graph-resize-0"]');
    fireEvent.mouseDown(handle, { button: 0, clientX: 200, clientY: 200 });
    fireEvent.mouseMove(handle, { clientX: 240, clientY: 220 });
    fireEvent.mouseUp(handle, { clientX: 240, clientY: 220 });

    // Then drag the node by (+40, +30) px.
    fireEvent.mouseDown(node, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(node, { clientX: 140, clientY: 130 });
    fireEvent.mouseUp(node, { clientX: 140, clientY: 130 });

    const after = node.getAttribute('transform');
    expect(after).not.toContain('NaN');
    const parse = (t) => t.match(/translate\(([\d.]+), ([\d.]+)\)/);
    const b = parse(before);
    const a = parse(after);
    expect(a).not.toBeNull();
    expect(Number(a[1]) - Number(b[1])).toBeCloseTo(40, 5);
    expect(Number(a[2]) - Number(b[2])).toBeCloseTo(30, 5);
  });

  it('keeps correct dimensions when resizing after a drag (no NaN size)', () => {
    const { container } = renderGraph({ plan: PLAN });
    const node = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const beforeW = Number(node.getAttribute('data-node-w'));

    // Drag the node first.
    fireEvent.mouseDown(node, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(node, { clientX: 140, clientY: 130 });
    fireEvent.mouseUp(node, { clientX: 140, clientY: 130 });

    // Then resize by (+40, +20) px — dimensions must stay finite and the
    // dragged x/y must be preserved (W5-E).
    const handle = container.querySelector('[data-testid="plan-dag-graph-resize-0"]');
    fireEvent.mouseDown(handle, { button: 0, clientX: 200, clientY: 200 });
    fireEvent.mouseMove(handle, { clientX: 240, clientY: 220 });
    fireEvent.mouseUp(handle, { clientX: 240, clientY: 220 });

    const w = Number(node.getAttribute('data-node-w'));
    const h = Number(node.getAttribute('data-node-h'));
    expect(Number.isFinite(w)).toBe(true);
    expect(Number.isFinite(h)).toBe(true);
    expect(w).toBeCloseTo(beforeW + 40, 5);
    expect(node.getAttribute('transform')).not.toContain('NaN');
  });

  it('redraw drops node position overrides and resets the view', () => {
    const { container } = renderGraph({ plan: PLAN });
    const node = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const original = node.getAttribute('transform');

    fireEvent.mouseDown(node, { button: 0, clientX: 100, clientY: 100 });
    fireEvent.mouseMove(node, { clientX: 200, clientY: 200 });
    fireEvent.mouseUp(node, { clientX: 200, clientY: 200 });
    expect(node.getAttribute('transform')).not.toBe(original);

    fireEvent.click(screen.getByRole('button', { name: 'Redraw layout' }));
    expect(node.getAttribute('transform')).toBe(original);
  });

  it('pulses running nodes with an animated outline (live status)', () => {
    const { container } = renderGraph({ plan: PLAN });

    // Step 1 is "running" → an <animate> drives its pulsing outline.
    const runningNode = container.querySelector('[role="button"][aria-label^="Step 1:"]');
    expect(runningNode.querySelector('animate')).not.toBeNull();

    // Step 0 is "completed" → no pulse.
    const doneNode = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    expect(doneNode.querySelector('animate')).toBeNull();
  });

  it('keeps a full title instead of clipping the first glyphs', () => {
    const { container } = renderGraph({
      plan: {
        ...PLAN,
        steps: [
          { step_id: 0, intent: 'Submitting the leave request', status: 'running', depends_on: [] },
          { step_id: 1, intent: 'تقديم الطلب حتى 2026-07-01', status: 'pending', depends_on: [0] },
        ],
      },
    });
    const arabic = container.querySelector('foreignObject[data-title*="تقديم"]');
    expect(arabic).not.toBeNull();
    expect(arabic.getAttribute('data-dir')).toBe('rtl');
    expect(arabic.textContent).toContain('تقديم الطلب');
    expect(arabic.textContent).toContain('2026-07-01');
    const date = [...arabic.querySelectorAll('[dir="ltr"]')].find((el) => el.textContent.includes('2026-07-01'));
    expect(date).toBeTruthy();
    const english = container.querySelector('foreignObject[data-title="Submitting the leave request"]');
    expect(english?.getAttribute('data-dir')).toBe('ltr');
    expect(arabic.textContent).not.toContain(':7-02-01');
    expect(container.textContent).not.toContain('bmiting');
  });

  it('shows a status pill on each node', () => {
    const { container } = renderGraph({ plan: PLAN });

    expect(container.querySelector('[role="button"][aria-label^="Step 1:"]').textContent).toContain('Running');
    expect(container.querySelector('[role="button"][aria-label^="Step 0:"]').textContent).toContain('Finished');
  });
});

describe('planStepStatusColor', () => {
  it('maps step statuses to theme tokens (never raw hex)', () => {
    expect(planStepStatusColor('completed', theme)).toBe(theme.palette.success.main);
    expect(planStepStatusColor('running', theme)).toBe(theme.palette.primary.main);
    expect(planStepStatusColor('awaiting_approval', theme)).toBe(theme.palette.warning.main);
    expect(planStepStatusColor('failed', theme)).toBe(theme.palette.error.main);
    expect(planStepStatusColor('skipped', theme)).toBe(theme.palette.text.disabled);
    expect(planStepStatusColor('pending', theme)).toBe(theme.palette.text.disabled);
    expect(planStepStatusColor('unknown-status', theme)).toBe(theme.palette.text.disabled);
  });
});

describe('planStepStatusLabel', () => {
  it('labels statuses in outcome terms (RULE_23)', () => {
    expect(planStepStatusLabel('completed')).toBe('Finished');
    expect(planStepStatusLabel('running')).toBe('Running…');
    expect(planStepStatusLabel('awaiting_approval')).toBe('Needs approval');
    expect(planStepStatusLabel('failed')).toBe('Failed');
    expect(planStepStatusLabel('skipped')).toBe('Skipped');
    expect(planStepStatusLabel('pending')).toBe('Pending');
  });
});

describe('planStepStatusChipColor', () => {
  it('maps statuses to MUI chip color tokens (RULE_5 chip + label)', () => {
    expect(planStepStatusChipColor('completed')).toBe('success');
    expect(planStepStatusChipColor('running')).toBe('primary');
    expect(planStepStatusChipColor('awaiting_approval')).toBe('warning');
    expect(planStepStatusChipColor('failed')).toBe('error');
    expect(planStepStatusChipColor('skipped')).toBe('default');
    expect(planStepStatusChipColor('pending')).toBe('default');
  });
});

describe('parallelLaneGroups', () => {
  it('groups only parallel steps sharing a non-null parallel_group, ascending', () => {
    const steps = [
      { step_id: 0, strategy: 'parallel', parallel_group: 2 },
      { step_id: 1, strategy: 'parallel', parallel_group: 1 },
      { step_id: 2, strategy: 'sequential', parallel_group: 1 },
      { step_id: 3, strategy: 'parallel', parallel_group: null },
      { step_id: 4, strategy: 'parallel', parallel_group: 1 },
    ];
    const lanes = parallelLaneGroups(steps);
    expect(lanes.map((l) => l.groupId)).toEqual([1, 2]);
    expect(lanes[0].steps.map((s) => s.step_id)).toEqual([1, 4]);
    expect(lanes[1].steps.map((s) => s.step_id)).toEqual([0]);
  });

  it('returns an empty list when nothing is parallel', () => {
    expect(parallelLaneGroups([])).toEqual([]);
    expect(parallelLaneGroups([{ step_id: 0, strategy: 'sequential', parallel_group: 0 }])).toEqual([]);
  });
});

describe('laneAttentionLabel', () => {
  it('is null when no sibling failed', () => {
    expect(laneAttentionLabel([{ status: 'completed' }, { status: 'pending' }])).toBeNull();
  });

  it('uses precise partial copy — never a blanket "failed" (RULE_23)', () => {
    expect(laneAttentionLabel([{ status: 'failed' }, { status: 'completed' }, { status: 'completed' }])).toBe(
      '1 of 3 steps needs attention',
    );
    expect(laneAttentionLabel([{ status: 'failed' }, { status: 'failed' }, { status: 'completed' }])).toBe(
      '2 of 3 steps need attention',
    );
    expect(laneAttentionLabel([{ status: 'failed' }])).toBe('1 of 1 step needs attention');
  });
});

describe('F-26 — parallel lane band rendering', () => {
  const PARALLEL_PLAN = {
    id: 'plan-par',
    status: 'running',
    brief: 'Match and merge entities in parallel.',
    phases: [{ phase_id: 0, name: 'Ingest & match', goal: '', strategy: 'parallel', step_ids: [0, 1, 2] }],
    steps: [
      { step_id: 0, intent: 'Match records', tool_name: 'search_entity', status: 'failed', error: 'No matches found', strategy: 'parallel', parallel_group: 0, depends_on: [] },
      { step_id: 1, intent: 'Merge duplicates', tool_name: 'merge_entity', status: 'awaiting_approval', strategy: 'parallel', parallel_group: 0, depends_on: [] },
      { step_id: 2, intent: 'Normalize names', tool_name: 'search_entity', status: 'completed', strategy: 'parallel', parallel_group: 0, depends_on: [] },
    ],
  };

  it('renders a collapsible lane with the phase name + "Runs together" chip', () => {
    renderGraph({ plan: PARALLEL_PLAN });

    expect(screen.getByTestId('parallel-lanes')).toBeInTheDocument();
    expect(screen.getByTestId('parallel-lane-0')).toBeInTheDocument();
    expect(screen.getByText('Ingest & match')).toBeInTheDocument();
    expect(screen.getByText('Runs together')).toBeInTheDocument();
  });

  it('keeps each step its own status chip (RULE_5)', () => {
    renderGraph({ plan: PARALLEL_PLAN });

    // All three steps are visible inside the expanded lane with their chips.
    // Scope to the lane band so the same intent labels in the SVG DAG don't
    // make the query ambiguous.
    const lane = screen.getByTestId('parallel-lanes');
    expect(within(lane).getByText('Match records')).toBeInTheDocument();
    expect(within(lane).getByText('Merge duplicates')).toBeInTheDocument();
    expect(within(lane).getByText('Normalize names')).toBeInTheDocument();
    // Chips: failed step + completed step + awaiting-approval step.
    expect(within(lane).getByText('Failed')).toBeInTheDocument();
    expect(within(lane).getByText('Finished')).toBeInTheDocument();
    expect(within(lane).getByText('Needs approval')).toBeInTheDocument();
  });

  it('shows precise attention copy (1 of 3) instead of blanket "failed"', () => {
    renderGraph({ plan: PARALLEL_PLAN });
    // Lane header chip carries the partial-attention signal…
    expect(screen.getByText('1 of 3 steps needs attention')).toBeInTheDocument();
    // …and the graph header summary appends the same precise copy (no blanket
    // "failed" rollup when only one sibling failed).
    expect(screen.getByText('3 steps · 0 links · 1 of 3 steps needs attention')).toBeInTheDocument();
  });

  it('renders Approve/Decline for the awaiting-approval step inside the lane', () => {
    const onConfirmStep = vi.fn();
    const onDeclineStep = vi.fn();
    renderGraph({ plan: PARALLEL_PLAN, onConfirmStep, onDeclineStep });

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    expect(onConfirmStep).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByRole('button', { name: 'Decline' }));
    expect(onDeclineStep).toHaveBeenCalledWith(1);
  });

  it('keeps a persistent failed chip + Retry affordance for a failed sibling', () => {
    const onRetryStep = vi.fn();
    renderGraph({ plan: PARALLEL_PLAN, onRetryStep });

    expect(screen.getByText('No matches found')).toBeInTheDocument(); // error preserved
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetryStep).toHaveBeenCalledWith(0);
  });

  it('collapses and expands the lane band', () => {
    renderGraph({ plan: PARALLEL_PLAN });
    const lane = screen.getByTestId('parallel-lane-0');
    const toggle = () =>
      within(lane).getByRole('button', { name: 'Toggle parallel lane Ingest & match' });

    // Expanded by default (ExpandMore icon shown).
    expect(within(lane).getByTestId('ExpandMoreIcon')).toBeInTheDocument();

    fireEvent.click(toggle());
    // Collapsed: chevron-right icon replaces the expand-more icon.
    expect(within(lane).queryByTestId('ExpandMoreIcon')).not.toBeInTheDocument();
    expect(within(lane).getByTestId('ChevronRightIcon')).toBeInTheDocument();

    fireEvent.click(toggle());
    expect(within(lane).getByTestId('ExpandMoreIcon')).toBeInTheDocument();
  });
});
