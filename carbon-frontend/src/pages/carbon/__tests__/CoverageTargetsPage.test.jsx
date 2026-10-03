import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CoverageTargetsPage from '../CoverageTargetsPage';

vi.mock('../../../hooks/useDocumentTitle', () => ({ default: () => {} }));

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 'test-token',
    user: { is_staff: true, is_superuser: true },
    availablePerspectives: ['carbon-admin'],
  }),
}));

vi.mock('../../../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

const fetchCoverageTargetBoard = vi.fn();
const fetchCoverageTargets = vi.fn();
const createCoverageTarget = vi.fn();
const fetchCoverageCampusOptions = vi.fn();
const fetchCoverageOrgUnitOptions = vi.fn();
const fetchCoverageOwnerOptions = vi.fn();

vi.mock('../../../api/emissions-extended', () => ({
  fetchCoverageTargetBoard: (...args) => fetchCoverageTargetBoard(...args),
  fetchCoverageTargets: (...args) => fetchCoverageTargets(...args),
  createCoverageTarget: (...args) => createCoverageTarget(...args),
  fetchCoverageCampusOptions: (...args) => fetchCoverageCampusOptions(...args),
  fetchCoverageOrgUnitOptions: (...args) => fetchCoverageOrgUnitOptions(...args),
  fetchCoverageOwnerOptions: (...args) => fetchCoverageOwnerOptions(...args),
}));

// Real lookup payloads — campuses, one campus's descendants, real people.
const campusOption = { id: 2, name: 'South Valley Campus', code: 'SV' };
const orgUnitRows = [
  { id: 2, name: 'South Valley Campus', code: 'SV', is_campus: true },
  { id: 3, name: 'South Valley Lab', code: '', is_campus: false },
];
const ownerRow = { id: 9, username: 'lead', full_name: 'Lead Person', label: 'Lead Person (lead)' };

const targetFixture = {
  id: 5,
  name: 'South Valley 1+2',
  campus: 2,
  campus_name: 'South Valley Campus',
  org_unit: 3,
  org_unit_name: 'South Valley',
  reporting_period: 17,
  reporting_period_name: 'Calendar year 2026',
  scope: '1+2',
  scope_display: 'Scope 1+2',
  scope3_category: null,
  goal_kind: 'percent',
  goal_value: '80.0000',
  goal_unit: '',
  min_quality_tier: 2,
  due_date: '2026-12-31',
  owner: 9,
  owner_username: 'lead',
  status: 'active',
  notes: '',
  progress: {
    counts: {
      required: 9,
      entered: 3,
      excluded: 1,
      awaiting_factor: 1,
      missing: 4,
      measured: 3,
      settled: 4,
      settled_at_target: 2,
      below_floor: 0,
      tier_unknown: 0,
    },
    measured_pct: '44.44',
    excluded_pct: '11.11',
    settled_pct: '44.44',
    settled_at_target_pct: '22.22',
    measured_kg: null,
    measured_kg_at_target: null,
    measured_value: null,
    measured_unit: null,
    metric: 'coverage_percent',
    goal_concept: 'coverage_kpi',
    goal_kind: 'percent',
    state: 'short',
    findings: [],
    basis: 'streams_with_a_real_row_on_the_target_period',
    claim: 'measured_not_claimed',
    coverage_complete: false,
    streams: [],
  },
};

const boardFixture = {
  product: 'Carbon on AASTMT',
  coverage_complete: false,
  period_default: 17,
  open_period: { id: 17, name: 'Calendar year 2026', status: 'open' },
  periods: [
    { id: 17, name: 'Calendar year 2026', status: 'open' },
    { id: 16, name: 'FY 2025-26', status: 'closed' },
    { id: 15, name: 'FY 2023-24', status: 'closed' },
  ],
  targets: [targetFixture],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <CoverageTargetsPage />
    </MemoryRouter>,
  );
}

// Route-aware render so a test can prove row click does NOT navigate while the
// explicit Open target action DOES (RULE 14 / M1).
function renderWithRoutes() {
  return render(
    <MemoryRouter initialEntries={['/carbon/admin/coverage-targets']}>
      <Routes>
        <Route path="/carbon/admin/coverage-targets" element={<CoverageTargetsPage />} />
        <Route path="/carbon/admin/coverage-targets/:targetId" element={<div>target-detail</div>} />
        <Route path="/carbon/onboarding/intake" element={<div>intake-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  fetchCoverageTargetBoard.mockReset();
  fetchCoverageTargets.mockReset();
  createCoverageTarget.mockReset();
  fetchCoverageCampusOptions.mockReset();
  fetchCoverageOrgUnitOptions.mockReset();
  fetchCoverageOwnerOptions.mockReset();
  fetchCoverageTargetBoard.mockResolvedValue(boardFixture);
  fetchCoverageTargets.mockResolvedValue([]);
  createCoverageTarget.mockResolvedValue({ id: 9 });
  fetchCoverageCampusOptions.mockResolvedValue({ count: 1, results: [campusOption] });
  fetchCoverageOrgUnitOptions.mockResolvedValue({ campus: campusOption, count: 2, results: orgUnitRows });
  fetchCoverageOwnerOptions.mockResolvedValue({ count: 1, page: 1, page_size: 200, results: [ownerRow] });
});

afterEach(() => {
  document.documentElement.removeAttribute('dir');
});

describe('CoverageTargetsPage — cycle, grid, honesty', () => {
  it('defaults the cycle dropdown to the single open period', async () => {
    renderPage();
    await screen.findByDisplayValue('Calendar year 2026 · Open');
    expect(screen.getByRole('combobox')).toHaveValue('Calendar year 2026 · Open');
    // The board already carries the open period's targets — no list refetch.
    expect(fetchCoverageTargets).not.toHaveBeenCalled();
  });

  it('renders ONE compact progress signal per row — measured figure + one status, breakdown in the tooltip', async () => {
    const user = userEvent.setup();
    renderPage();
    const name = await screen.findByText('South Valley 1+2');
    const row = name.closest('.MuiDataGrid-row');

    // A single measured figure and a single status chip in the cell …
    expect(within(row).getByText('44.44%')).toBeInTheDocument();
    expect(within(row).getByText('Short of goal')).toBeInTheDocument();
    // … and NONE of the old chip pile-up or per-row CTAs. The only action in the
    // row is the deliberate `Open target`.
    expect(within(row).queryByText('Measured (with kg)')).not.toBeInTheDocument();
    expect(within(row).queryByText('Excluded share')).not.toBeInTheDocument();
    expect(within(row).queryByText('Measured, not claimed')).not.toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Open target' })).toBeInTheDocument();

    // The breakdown (excluded share + the honesty marker) is behind ONE tooltip.
    await user.hover(within(row).getByText('44.44%'));
    const tip = await screen.findByRole('tooltip');
    expect(within(tip).getByText(/Measured \(with kg\)/)).toBeInTheDocument();
    expect(within(tip).getByText(/Excluded share/)).toBeInTheDocument();
    expect(within(tip).getByText('11.11%')).toBeInTheDocument();
    expect(within(tip).getByText('Measured, not claimed')).toBeInTheDocument();

    // Numbers go through the shared formatter — the raw 4-decimal API string
    // ("80.0000") must never reach the screen.
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.queryByText('80.0000%')).not.toBeInTheDocument();
    // The open period is editable, so no read-only history banner.
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();
  });

  it('shows a fully-excluded target as measured 0% / excluded 100% and NOT met', async () => {
    const user = userEvent.setup();
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 7,
          name: 'Fully excluded',
          progress: {
            ...targetFixture.progress,
            counts: {
              required: 4,
              measured: 0,
              settled: 4,
              settled_at_target: 0,
              below_floor: 0,
              tier_unknown: 0,
              excluded: 4,
              awaiting_factor: 0,
              missing: 0,
            },
            measured_pct: '0.00',
            excluded_pct: '100.00',
            settled_pct: '100.00',
            settled_at_target_pct: '0.00',
            state: 'short',
          },
        },
      ],
    });
    renderPage();
    const name = await screen.findByText('Fully excluded');
    const row = name.closest('.MuiDataGrid-row');
    expect(within(row).getByText('0%')).toBeInTheDocument();
    expect(within(row).getByText('Short of goal')).toBeInTheDocument();
    expect(screen.queryByText('Goal met (measured)')).not.toBeInTheDocument();
    // 100% excluded is a separate figure in the tooltip, never inline as measured.
    expect(screen.queryByText('100%')).not.toBeInTheDocument();
    await user.hover(within(row).getByText('0%'));
    const tip = await screen.findByRole('tooltip');
    expect(within(tip).getByText('100%')).toBeInTheDocument();
    // Non-negotiable: exclusions never read as measured coverage.
    expect(screen.queryByText(/100% measured/)).not.toBeInTheDocument();
  });

  it('surfaces below-floor and tier-unknown counts distinctly (not as settled-at-target)', async () => {
    const user = userEvent.setup();
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 8,
          name: 'Floor gap',
          progress: {
            ...targetFixture.progress,
            counts: {
              ...targetFixture.progress.counts,
              measured: 5,
              below_floor: 2,
              tier_unknown: 1,
            },
          },
        },
      ],
    });
    renderPage();
    const name = await screen.findByText('Floor gap');
    const row = name.closest('.MuiDataGrid-row');
    // The quality-floor detail lives in the compact cell's tooltip, not inline.
    expect(screen.queryByText('2 below the quality floor')).not.toBeInTheDocument();
    await user.hover(within(row).getByText('44.44%'));
    const tip = await screen.findByRole('tooltip');
    expect(within(tip).getByText('2 below the quality floor')).toBeInTheDocument();
    expect(within(tip).getByText('1 tier unknown')).toBeInTheDocument();
  });

  it('makes no read-only claim while the board is still loading', async () => {
    const pending = deferred();
    fetchCoverageTargetBoard.mockReturnValueOnce(pending.promise);

    renderPage();

    // LoadingSkeleton (toolkit loading state) is on screen, not a closed-period
    // sentence with a blank cycle name.
    await waitFor(() => expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy());
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No data completeness targets yet/)).not.toBeInTheDocument();

    pending.resolve(boardFixture);
    await screen.findByText('South Valley 1+2');
  });

  it('names the coverage targets source on failure and offers Retry, with no read-only claim', async () => {
    fetchCoverageTargetBoard.mockRejectedValueOnce(
      Object.assign(new Error('The requested resource was not found.'), { status: 404 }),
    );

    renderPage();

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/coverage targets source returned an error/i)).toBeInTheDocument();
    expect(within(alert).getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    // A failed load must not masquerade as closed history or an empty board.
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No data completeness targets yet/)).not.toBeInTheDocument();
  });

  it('is not a second Missing / Entered / Excluded reporter', async () => {
    renderPage();
    await screen.findByText('South Valley 1+2');
    // Those states belong to the Coverage streams page only; the targets grid
    // must not re-label them as its own.
    expect(screen.queryByText('Missing')).not.toBeInTheDocument();
    expect(screen.queryByText('Entered')).not.toBeInTheDocument();
    expect(screen.queryByText('Excluded')).not.toBeInTheDocument();
    expect(queryColumnHeader('Missing')).toBeNull();
    expect(queryColumnHeader('Entered')).toBeNull();
    expect(queryColumnHeader('Excluded')).toBeNull();
  });

  it('makes a closed period read-only history', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByDisplayValue('Calendar year 2026 · Open');

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByText('FY 2025-26 · Closed'));

    await waitFor(() => expect(fetchCoverageTargets).toHaveBeenCalledWith({ reporting_period: '16' }, 'test-token'));
    expect(await screen.findByText(/This cycle is Closed/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add target/ })).toBeDisabled();
  });

  it('shows the read-only banner only after the closed period has loaded', async () => {
    const user = userEvent.setup();
    const pending = deferred();
    fetchCoverageTargets.mockReturnValueOnce(pending.promise);

    renderPage();
    await screen.findByDisplayValue('Calendar year 2026 · Open');

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByText('FY 2025-26 · Closed'));

    // The closed period's targets are still in flight: claim nothing yet.
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();

    pending.resolve([]);
    expect(await screen.findByText(/This cycle is Closed/)).toBeInTheDocument();
  });

  it('adds a target through searchable campus, campus-driven org unit and owner', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('South Valley 1+2');

    await user.click(screen.getByRole('button', { name: /Add target/ }));
    const dialog = await screen.findByRole('dialog');

    await user.type(within(dialog).getByLabelText(/Target name/i), 'New goal');

    // Campus is a REAL searchable lookup, not a numeric id field.
    // Campus is a REAL searchable lookup, not a numeric id field.
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Campus/i));
    fireEvent.click(await screen.findByText(/South Valley Campus · SV/));

    // Org unit options come from the selected campus's descendants.
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Org unit/i));
    fireEvent.click(await screen.findByText('South Valley Lab'));

    // Owner is a REAL searchable people lookup.
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Owner/i));
    fireEvent.click(await screen.findByText(/Lead Person \(lead\)/));

    await user.type(within(dialog).getByLabelText(/Goal value/i), '50');
    await user.click(within(dialog).getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createCoverageTarget).toHaveBeenCalledTimes(1));
    expect(fetchCoverageOrgUnitOptions).toHaveBeenCalledWith({ campus: '2' }, 'test-token');
    expect(createCoverageTarget.mock.calls[0][0]).toMatchObject({
      name: 'New goal',
      campus: 2,
      org_unit: 3,
      owner: 9,
      scope: '1+2',
      goal_kind: 'percent',
      goal_value: 50,
      reporting_period: 17,
      status: 'draft',
    });
  });

  it('refreshes and clears the org unit when the campus changes', async () => {
    fetchCoverageCampusOptions.mockResolvedValue({
      count: 2,
      results: [campusOption, { id: 4, name: 'Abu Qir Campus', code: 'AQ' }],
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('South Valley 1+2');

    await user.click(screen.getByRole('button', { name: /Add target/ }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.mouseDown(within(dialog).getByLabelText(/^Campus/i));
    fireEvent.click(await screen.findByText(/South Valley Campus · SV/));
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Org unit/i));
    fireEvent.click(await screen.findByText('South Valley Lab'));
    expect(within(dialog).getByLabelText(/^Org unit/i)).toHaveValue('South Valley Lab');

    fetchCoverageOrgUnitOptions.mockResolvedValueOnce({
      campus: { id: 4, name: 'Abu Qir Campus' },
      count: 2,
      results: [
        { id: 4, name: 'Abu Qir Campus', is_campus: true },
        { id: 6, name: 'Abu Qir Plant', is_campus: false },
      ],
    });
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Campus/i));
    fireEvent.click(await screen.findByText(/Abu Qir Campus · AQ/));

    await waitFor(() => expect(fetchCoverageOrgUnitOptions).toHaveBeenLastCalledWith({ campus: '4' }, 'test-token'));
    // The stale child selection is gone until the new campus's units are picked.
    expect(within(dialog).getByLabelText(/^Org unit/i)).toHaveValue('');
  });

  it('shows an honest no-sub-units message when a campus has no descendants', async () => {
    fetchCoverageCampusOptions.mockResolvedValue({
      count: 1,
      results: [{ id: 4, name: 'Abu Qir Campus', code: 'AQ' }],
    });
    fetchCoverageOrgUnitOptions.mockResolvedValue({
      campus: { id: 4, name: 'Abu Qir Campus' },
      count: 1,
      results: [{ id: 4, name: 'Abu Qir Campus', is_campus: true }],
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('South Valley 1+2');

    await user.click(screen.getByRole('button', { name: /Add target/ }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Campus/i));
    fireEvent.click(await screen.findByText(/Abu Qir Campus · AQ/));

    expect(await within(dialog).findByText(/no sub-units/i)).toBeInTheDocument();
  });

  it('surfaces a real error (with Retry) when the campus lookup fails — no fake options', async () => {
    fetchCoverageCampusOptions.mockRejectedValue(new Error('boom'));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('South Valley 1+2');

    await user.click(screen.getByRole('button', { name: /Add target/ }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.mouseDown(within(dialog).getByLabelText(/^Campus/i));

    expect(await screen.findByText(/Couldn't load campuses/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });

  it('renders the localized scope word with only the Latin code bdi-isolated (M4)', async () => {
    document.documentElement.setAttribute('dir', 'rtl');
    renderPage();
    const row = (await screen.findByText('South Valley 1+2')).closest('.MuiDataGrid-row');
    // The translatable word stays in the sentence; only the GHG code is isolated.
    expect(within(row).getByText('Scope')).toBeInTheDocument();
    const code = within(row).getByText('1+2');
    expect(code.tagName.toLowerCase()).toBe('bdi');
    expect(code).toHaveAttribute('dir', 'ltr');
  });

  it('keeps per-row next-action CTAs OUT of the grid — they live on the detail page', async () => {
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 11,
          name: 'Gap with action',
          progress: {
            ...targetFixture.progress,
            next_actions: [
              {
                code: 'missing',
                count: 1,
                verb: 'enter_stream',
                moves: ['entered', 'measured'],
                streams: [
                  {
                    inventory_source_id: 42,
                    source_name: 'Smart Village electricity',
                    org_unit_id: 3,
                    scope: 2,
                  },
                ],
              },
            ],
          },
        },
      ],
    });
    renderWithRoutes();
    await screen.findByText('Gap with action');
    // No per-row action buttons and no gap chip in a data cell.
    expect(screen.queryByRole('button', { name: /Open Smart Village electricity/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Open coverage streams/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Missing entry · 1')).not.toBeInTheDocument();
    // The deliberate row action is still the only action in the row.
    expect(screen.getByRole('button', { name: 'Open target' })).toBeInTheDocument();
  });

  it('feeds the Owner picker only from the eligibility lookup (no client list)', async () => {
    const user = userEvent.setup();
    // The server decides eligibility: whatever this endpoint returns is what
    // the picker offers, and nothing is added or filtered client-side.
    fetchCoverageOwnerOptions.mockResolvedValue({
      count: 2,
      page: 1,
      page_size: 200,
      results: [
        { id: 9, username: 'lead', full_name: 'Lead Person', label: 'Lead Person (lead)' },
        {
          id: 12,
          username: 'data.smartvillage',
          full_name: 'Smart Village Data owner',
          label: 'Smart Village Data owner (data.smartvillage)',
        },
      ],
    });
    renderPage();
    await screen.findByText('South Valley 1+2');

    await user.click(screen.getByRole('button', { name: /Add target/ }));
    const dialog = await screen.findByRole('dialog');

    expect(fetchCoverageOwnerOptions).toHaveBeenCalledWith({ q: '', pageSize: 200 }, 'test-token');

    fireEvent.mouseDown(within(dialog).getByLabelText(/^Owner/i));
    expect(await screen.findByText(/Lead Person \(lead\)/)).toBeInTheDocument();
    expect(screen.getByText(/Smart Village Data owner \(data\.smartvillage\)/)).toBeInTheDocument();
  });

  it('keeps Owner + Notes reachable with the footer as a distinct scroll region', async () => {
    const originalHeight = window.innerHeight;
    // Short viewport where the raw 640px window used to push its footer off
    // screen (and over the last fields).
    Object.defineProperty(window, 'innerHeight', { configurable: true, writable: true, value: 700 });
    try {
      const user = userEvent.setup();
      renderPage();
      await screen.findByText('South Valley 1+2');

      await user.click(screen.getByRole('button', { name: /Add target/ }));
      const dialog = await screen.findByRole('dialog');
      const paper = dialog;

      const content = paper.querySelector('.MuiDialogContent-root');
      const footer = paper.querySelector('.MuiDialogActions-root');
      expect(content).toBeTruthy();
      expect(footer).toBeTruthy();

      // The footer is a sibling region, never nested in the scrolling content.
      expect(content.contains(footer)).toBe(false);
      expect(footer.contains(content)).toBe(false);

      // Window is a flex column: title/footer are flexShrink 0, content scrolls.
      expect(paper.style.display).toBe('flex');
      expect(paper.style.flexDirection).toBe('column');
      expect(paper.style.overflow).toBe('hidden');
      // Desktop keeps the draggable/resizable absolute window.
      expect(paper.style.position).toBe('absolute');

      // The window is fitted inside the viewport, so the footer stays visible.
      const top = Number.parseFloat(paper.style.top);
      const height = Number.parseFloat(paper.style.height);
      expect(top).toBeGreaterThanOrEqual(0);
      expect(top + height).toBeLessThanOrEqual(window.innerHeight);

      // Last fields (Owner, Notes) are inside the scrolling content region.
      expect(within(content).getByLabelText(/^Owner/i)).toBeInTheDocument();
      expect(within(content).getByLabelText(/Notes/i)).toBeInTheDocument();
    } finally {
      Object.defineProperty(window, 'innerHeight', {
        configurable: true,
        writable: true,
        value: originalHeight,
      });
      window.dispatchEvent(new Event('resize'));
    }
  });

  it('renders the footer as a distinct region in a mobile full-screen sheet', async () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = (query) => ({
      matches: /max-width/.test(query),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    });
    try {
      const user = userEvent.setup();
      renderPage();
      await screen.findByText('South Valley 1+2');

      await user.click(screen.getByRole('button', { name: /Add target/ }));
      const dialog = await screen.findByRole('dialog');
      const content = dialog.querySelector('.MuiDialogContent-root');
      const footer = dialog.querySelector('.MuiDialogActions-root');
      expect(content).toBeTruthy();
      expect(footer).toBeTruthy();
      expect(content.contains(footer)).toBe(false);
      // Mobile is a full-screen sheet, not the absolute desktop window.
      expect(dialog.style.position).not.toBe('absolute');
      expect(within(content).getByLabelText(/^Owner/i)).toBeInTheDocument();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('presents Data completeness in ONE line, with the honesty note behind an info affordance', async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText('Data completeness')).toBeInTheDocument();
    // A single short line of context — not the old two-sentence paragraph.
    expect(screen.getByText(/Measured fill-rate and quality/i)).toBeInTheDocument();
    // The NOT-GHG clarification is NOT stacked inline in the header …
    expect(screen.queryByText(/NOT the GHG completeness assertion/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Coverage streams remain the only reporter of Missing \/ Entered \/ Excluded/i),
    ).not.toBeInTheDocument();
    // … it lives in a compact info affordance.
    await user.hover(screen.getByRole('button', { name: /About data completeness/i }));
    const tip = await screen.findByRole('tooltip');
    expect(within(tip).getByText(/NOT the GHG completeness assertion/i)).toBeInTheDocument();
    expect(
      within(tip).getByText(/Coverage streams remain the only reporter of Missing \/ Entered \/ Excluded/i),
    ).toBeInTheDocument();
  });

  it('highlights a row on click without navigating; the explicit Open target action navigates (RULE 14)', async () => {
    const user = userEvent.setup();
    renderWithRoutes();
    await screen.findByText('South Valley 1+2');

    // Clicking the row (a data cell) must only highlight — never route away.
    await user.click(screen.getByText('South Valley 1+2'));
    expect(screen.queryByText('target-detail')).not.toBeInTheDocument();

    // The deliberate Open target action is what navigates.
    await user.click(screen.getByRole('button', { name: 'Open target' }));
    expect(await screen.findByText('target-detail')).toBeInTheDocument();
  });

  it('exposes grid search plus scope/status filters (no hideSearch)', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('South Valley 1+2');

    expect(screen.getByPlaceholderText(/Search by target, campus, org unit or owner/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Filters/i }));
    expect(await screen.findByLabelText('Scope')).toBeInTheDocument();
    expect(screen.getByLabelText('Status')).toBeInTheDocument();
  });

  it('labels an absolute goal as an emissions value target and renders the measured value in the goal unit', async () => {
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 6,
          name: 'Campus CO2e',
          goal_kind: 'absolute',
          goal_value: '500000.0000',
          goal_unit: 'kgCO2e',
          progress: {
            ...targetFixture.progress,
            metric: 'absolute_emissions',
            goal_concept: 'emissions_value',
            goal_kind: 'absolute',
            measured_value: '1250.5000',
            measured_unit: 'tCO2e',
            state: 'short',
          },
        },
      ],
    });
    renderPage();
    const name = await screen.findByText('Campus CO2e');
    const row = name.closest('.MuiDataGrid-row');
    expect(within(row).getByText('Emissions value target')).toBeInTheDocument();
    // Value rendered in the GOAL's unit, not a conflation.
    expect(within(row).getByText('1,250.5 tCO2e')).toBeInTheDocument();
  });

  it('renders an absent measured value as an em dash, never as 0', async () => {
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 9,
          name: 'No value yet',
          goal_kind: 'absolute',
          goal_value: '100.0000',
          goal_unit: 'tCO2e',
          progress: {
            ...targetFixture.progress,
            metric: 'absolute_emissions',
            goal_concept: 'emissions_value',
            goal_kind: 'absolute',
            measured_kg: null,
            measured_value: null,
            measured_unit: null,
            state: 'short',
          },
        },
      ],
    });
    renderPage();
    const name = await screen.findByText('No value yet');
    const row = name.closest('.MuiDataGrid-row');
    // Absent, not zero.
    expect(within(row).getByText('—')).toBeInTheDocument();
    expect(within(row).queryByText('0 tCO2e')).not.toBeInTheDocument();
  });

  it('renders no_declared_sources as an explicit headlined finding, not a blank or "no active streams"', async () => {
    fetchCoverageTargetBoard.mockResolvedValue({
      ...boardFixture,
      targets: [
        {
          ...targetFixture,
          id: 10,
          name: 'Empty boundary',
          progress: {
            ...targetFixture.progress,
            counts: {
              required: 0, measured: 0, settled: 0, settled_at_target: 0,
              below_floor: 0, tier_unknown: 0, excluded: 0, awaiting_factor: 0, missing: 0,
            },
            measured_pct: null,
            excluded_pct: null,
            settled_pct: null,
            settled_at_target_pct: null,
            state: 'empty',
            findings: [{ code: 'no_declared_sources', detail: 'No declared sources.' }],
          },
        },
      ],
    });
    renderPage();
    expect(await screen.findByText('Empty boundary')).toBeInTheDocument();
    expect(screen.getByText('No declared sources')).toBeInTheDocument();
    // The generic empty line must not be the finding's stand-in.
    expect(screen.queryByText(/No active streams in this target's scope yet/)).not.toBeInTheDocument();
  });
});

function queryColumnHeader(name) {
  return screen.queryByRole('columnheader', { name });
}
