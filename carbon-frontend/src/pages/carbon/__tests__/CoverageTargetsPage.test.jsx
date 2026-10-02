import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
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
    counts: { required: 9, entered: 3, excluded: 1, awaiting_factor: 1, missing: 4 },
    measured_pct: '44.44',
    measured_kg: null,
    state: 'short',
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

  it('renders the target grid with the measured ratio labelled not-claimed', async () => {
    renderPage();
    expect(await screen.findByText('South Valley')).toBeInTheDocument();
    expect(screen.getByText('South Valley 1+2')).toBeInTheDocument();
    expect(screen.getByText('Measured, not claimed')).toBeInTheDocument();
    expect(screen.getByText(/streams settled/)).toBeInTheDocument();
    // The open period is editable, so no read-only history banner.
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();
  });

  it('makes no read-only claim while the board is still loading', async () => {
    const pending = deferred();
    fetchCoverageTargetBoard.mockReturnValueOnce(pending.promise);

    renderPage();

    // LoadingSkeleton (toolkit loading state) is on screen, not a closed-period
    // sentence with a blank cycle name.
    await waitFor(() => expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy());
    expect(screen.queryByText(/This cycle is/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No coverage targets yet/)).not.toBeInTheDocument();

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
    expect(screen.queryByText(/No coverage targets yet/)).not.toBeInTheDocument();
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

  it('renders domain terms isolated for an RTL (Arabic) surface', async () => {
    document.documentElement.setAttribute('dir', 'rtl');
    renderPage();
    const scope = await screen.findByText('Scope 1+2');
    expect(scope.tagName.toLowerCase()).toBe('bdi');
    expect(scope).toHaveAttribute('dir', 'ltr');
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
});

function queryColumnHeader(name) {
  return screen.queryByRole('columnheader', { name });
}
