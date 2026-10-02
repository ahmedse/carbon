import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import InventoryCoveragePage from '../InventoryCoveragePage';

vi.mock('../../../hooks/useDocumentTitle', () => ({
  default: () => {},
}));

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 'test-token',
    user: { is_staff: true, is_superuser: true },
    availablePerspectives: ['carbon-admin'],
  }),
}));

// The real NotificationProvider exposes `notify` / `notifyFromError` as
// useCallback-stable identities for the provider's lifetime. An inline object
// literal here returned brand-new functions on every render, which changed
// `loadAll`'s useCallback identity and re-ran the mount effect on every commit.
// That produced an artificial refetch storm (~90 full board reloads / 2s) that
// starved the page under full-suite parallel load and made the multi-stage
// async assertions miss RTL's default 1s timeout. Mirror the real contract with
// one stable reference so the page loads exactly as it does in production.
const notificationMock = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../../../components/NotificationProvider', () => ({
  useNotification: () => notificationMock,
}));

const fetchReportingPeriods = vi.fn();
const fetchInventorySources = vi.fn();
const fetchCoverageGoals = vi.fn();
const fetchCoverageActions = vi.fn();
const fetchInventorySourceStatuses = vi.fn();
const fetchCoverage = vi.fn();
const fetchCampusIntake = vi.fn();
const createCoverageGoal = vi.fn();
const fetchCoverageReconciliation = vi.fn();
const setCoverageRowExclusion = vi.fn();

vi.mock('../../../api/emissions-extended', () => ({
  fetchReportingPeriods: (...args) => fetchReportingPeriods(...args),
  fetchInventorySources: (...args) => fetchInventorySources(...args),
  fetchCoverageGoals: (...args) => fetchCoverageGoals(...args),
  fetchCoverageActions: (...args) => fetchCoverageActions(...args),
  fetchInventorySourceStatuses: (...args) => fetchInventorySourceStatuses(...args),
  fetchCoverage: (...args) => fetchCoverage(...args),
  fetchCampusIntake: (...args) => fetchCampusIntake(...args),
  fetchCoverageReconciliation: (...args) => fetchCoverageReconciliation(...args),
  setCoverageRowExclusion: (...args) => setCoverageRowExclusion(...args),
  createInventorySource: vi.fn(),
  updateInventorySource: vi.fn(),
  deleteInventorySource: vi.fn(),
  createCoverageGoal: (...args) => createCoverageGoal(...args),
  updateCoverageGoal: vi.fn(),
  deleteCoverageGoal: vi.fn(),
  createCoverageAction: vi.fn(),
  updateCoverageAction: vi.fn(),
  deleteCoverageAction: vi.fn(),
}));

const coverageFixture = { pct: 40, covered: 1, total: 2, gaps_count: 1 };

// The board settles through a two-stage async load (periods → period-scoped
// coverage), so every network-driven query below can legitimately take longer
// than RTL's 1s default when the full suite runs in parallel. This is a retry
// budget on the real condition, not a sleep, and stays well inside the 15s
// per-test timeout.
const SETTLE = { timeout: 5000 };

function renderPage() {
  return render(
    <MemoryRouter>
      <InventoryCoveragePage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchReportingPeriods.mockReset();
  fetchInventorySources.mockReset();
  fetchCoverageGoals.mockReset();
  fetchCoverageActions.mockReset();
  fetchInventorySourceStatuses.mockReset();
  fetchCoverage.mockReset();
  fetchCampusIntake.mockReset();
  createCoverageGoal.mockReset();
  fetchCoverageReconciliation.mockReset();
  setCoverageRowExclusion.mockReset();
  setCoverageRowExclusion.mockResolvedValue({ written: true, excluded: true });

  fetchReportingPeriods.mockResolvedValue([{ id: 1, name: 'FY 2025' }]);
  fetchInventorySources.mockResolvedValue([]);
  fetchCoverageGoals.mockResolvedValue([]);
  fetchCoverageActions.mockResolvedValue([]);
  fetchInventorySourceStatuses.mockResolvedValue([]);
  fetchCoverage.mockResolvedValue(coverageFixture);
  fetchCoverageReconciliation.mockResolvedValue({
    coverage_complete: false,
    open_period: { id: 1, name: 'Calendar year 2026' },
    counts: { required: 9, entered: 1, excluded: 0, missing: 8, awaiting_factor: 0 },
    goals: [
      {
        goal_id: 1,
        name: 'South Valley 1+2',
        scope: '1+2',
        org_unit_name: 'South Valley',
        required: 2,
        entered: 0,
        excluded: 0,
        missing: 2,
        target_coverage_pct: '80.00',
      },
    ],
  });
  fetchCampusIntake.mockResolvedValue({
    coverage_complete: false,
    streams: [
      {
        id: 'O1:Smart Village electricity',
        campus: 'Smart Village',
        source_name: 'Smart Village electricity',
        scope: 2,
        status: 'entered',
        inventory_kg: null,
      },
      {
        id: 'O2:South Valley electricity',
        campus: 'South Valley',
        source_name: 'South Valley electricity',
        scope: 2,
        status: 'missing',
        reason: null,
        inventory_kg: null,
        inventory_source_id: 5,
      },
    ],
  });
});

describe('Inventory coverage O1 quote honesty', () => {
  it('warns that figures are not O1 and links to onboarding (O1-USE-QUOTE)', async () => {
    renderPage();
    const alert = await screen.findByRole('alert', undefined, SETTLE);
    expect(alert).toHaveTextContent(/are not the O1/);
    expect(screen.getByRole('button', { name: 'Inventory onboarding' })).toBeInTheDocument();
    expect(createCoverageGoal).not.toHaveBeenCalled();
  });

  it('defaults new goal scope to 1+2 with empty target coverage', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole('alert', undefined, SETTLE);

    await user.click(screen.getByRole('tab', { name: 'Goals' }));
    await user.click(screen.getByRole('button', { name: 'New Goal' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText(/^Scope$/i)).toHaveTextContent('Scope 1+2');
    const targetPct = within(dialog).getByLabelText(/Target Coverage/i);
    expect(targetPct.value ?? '').toBe('');
    expect(createCoverageGoal).not.toHaveBeenCalled();
  });

  it('lists the open period and the locked year without a zero kilogram', async () => {
    fetchCampusIntake.mockResolvedValue({
      coverage_complete: false,
      streams: [],
      periods: [
        {
          id: 15,
          name: 'FY 2023-24',
          role: 'open',
          status: 'open',
          streams: [
            {
              id: 'open-sv',
              campus: 'South Valley',
              source_name: 'South Valley electricity',
              scope: 2,
              status: 'missing',
              inventory_kg: null,
            },
          ],
        },
        {
          id: 16,
          name: 'FY 2025-26',
          role: 'locked',
          status: 'locked',
          streams: [
            {
              id: 'locked-sv',
              campus: 'South Valley',
              source_name: 'South Valley electricity',
              scope: 2,
              status: 'entered',
              inventory_kg: null,
            },
            {
              id: 'locked-na',
              campus: 'New Alamein',
              source_name: 'New Alamein electricity',
              scope: 2,
              status: 'missing',
              inventory_kg: null,
            },
          ],
        },
      ],
    });
    renderPage();
    expect(await screen.findByText(/FY 2023-24/, undefined, SETTLE)).toBeInTheDocument();
    expect(screen.getByText(/FY 2025-26/)).toBeInTheDocument();
    expect(screen.getAllByText('Missing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Entered').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Absent').length).toBeGreaterThan(0);
    expect(screen.queryByText(/^0 kg$/)).not.toBeInTheDocument();
  });

  it('is the single surface that reports Missing / Entered / Excluded and offers a row entry', async () => {
    renderPage();
    expect(await screen.findByText('Reconciliation', undefined, SETTLE)).toBeInTheDocument();
    expect(screen.getAllByText('Missing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Entered').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Enter' })).toBeInTheDocument();
    expect(screen.getByText('Declared target')).toBeInTheDocument();
  });

  it('declares an exclusion on ONE coverage row with a vocabulary reason', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Reconciliation', undefined, SETTLE);

    await user.click(screen.getByRole('button', { name: 'Exclude' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/South Valley electricity/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Exclude' }));

    expect(setCoverageRowExclusion).toHaveBeenCalledTimes(1);
    const [sourceId, payload] = setCoverageRowExclusion.mock.calls[0];
    expect(sourceId).toBe(5);
    expect(payload.excluded).toBe(true);
    expect(payload.reason).toBe('insufficient_data');
  });
});
