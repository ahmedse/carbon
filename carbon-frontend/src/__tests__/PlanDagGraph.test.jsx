// src/__tests__/PlanDagGraph.test.jsx
// W3-F — live plan DAG rendered as a layered DIRECTED execution graph:
// nodes = steps, edges = depends_on with arrowheads (marker), node color =
// step status via theme tokens, legend, live badge, empty state, a movable +
// resizable canvas (pan/zoom), a detailed inspection pane (docked, never
// floating), and an expand button that opens the graph in a full-screen modal
// (jsdom-safe, no d3).
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import PlanDagGraph, { planStepStatusColor, planStepStatusLabel } from '../components/graph/PlanDagGraph';

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
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Needs approval')).toBeInTheDocument();
    expect(screen.getByText('Finished')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders a directed SVG with arrowhead markers on edges', () => {
    const { container } = renderGraph({ plan: PLAN });

    const marker = container.querySelector('marker#plan-arrow');
    expect(marker).not.toBeNull();
    expect(marker.getAttribute('orient')).toBe('auto-start-reverse');

    const edgePaths = container.querySelectorAll('path[marker-end]');
    expect(edgePaths.length).toBe(3);
    edgePaths.forEach((p) => expect(p.getAttribute('marker-end')).toBe('url(#plan-arrow)'));
  });

  it('lays steps out left-to-right by execution rank', () => {
    const { container } = renderGraph({ plan: PLAN });

    const step0 = container.querySelector('[role="button"][aria-label^="Step 0:"]');
    const step2 = container.querySelector('[role="button"][aria-label^="Step 2:"]');
    expect(step0).not.toBeNull();
    expect(step2).not.toBeNull();
    // Longest-path layering: step 2 (depends on 0 AND 1) sits at a deeper rank
    // than step 0, so its x coordinate must be strictly greater.
    const x0 = Number(step0.getAttribute('transform').match(/translate\(([\d.-]+)/)[1]);
    const x2 = Number(step2.getAttribute('transform').match(/translate\(([\d.-]+)/)[1]);
    expect(x2).toBeGreaterThan(x0);
  });

  it('opens a detailed inspection pane when a node is clicked', () => {
    renderGraph({ plan: PLAN });

    expect(screen.queryByTestId('plan-step-detail')).not.toBeInTheDocument();

    // Step 0 is a source (no depends_on) → "Nothing — starts the workflow".
    const step0 = screen.getByRole('button', { name: /Step 0:/ });
    fireEvent.click(step0);

    const pane = screen.getByTestId('plan-step-detail');
    expect(pane).toBeInTheDocument();
    expect(screen.getByText('Step 0')).toBeInTheDocument();
    expect(screen.getByText('Search for duplicate records')).toBeInTheDocument();
    expect(within(pane).getByText('search_entity')).toBeInTheDocument();
    expect(within(pane).getByText(/Nothing — starts the workflow/)).toBeInTheDocument();
    expect(within(pane).getByText(/Create a rule to prevent duplicates/)).toBeInTheDocument(); // feeds into

    // Closing the pane hides it again.
    fireEvent.click(screen.getByRole('button', { name: /Close/ }));
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
    const nodeRect = container.querySelector('[role="button"][aria-label^="Step 0:"] > rect');
    const beforeW = Number(nodeRect.getAttribute('width'));

    fireEvent.mouseDown(handle, { button: 0, clientX: 200, clientY: 200 });
    fireEvent.mouseMove(handle, { clientX: 240, clientY: 220 });
    fireEvent.mouseUp(handle, { clientX: 240, clientY: 220 });

    expect(Number(nodeRect.getAttribute('width'))).toBeGreaterThan(beforeW);
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
    const nodeRect = node.querySelector('rect');
    const beforeW = Number(nodeRect.getAttribute('width'));

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

    const w = Number(nodeRect.getAttribute('width'));
    const h = Number(nodeRect.getAttribute('height'));
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

  it('shows a status pill on each node', () => {
    const { container } = renderGraph({ plan: PLAN });

    expect(container.querySelector('[role="button"][aria-label^="Step 1:"]').textContent).toContain('RUNNING');
    expect(container.querySelector('[role="button"][aria-label^="Step 0:"]').textContent).toContain('FINISHED');
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
    expect(planStepStatusLabel('running')).toBe('Running');
    expect(planStepStatusLabel('awaiting_approval')).toBe('Needs approval');
    expect(planStepStatusLabel('failed')).toBe('Failed');
    expect(planStepStatusLabel('skipped')).toBe('Skipped');
    expect(planStepStatusLabel('pending')).toBe('Pending');
  });
});
