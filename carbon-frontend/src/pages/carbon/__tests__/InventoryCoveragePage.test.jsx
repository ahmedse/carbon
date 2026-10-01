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

vi.mock('../../../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

const fetchReportingPeriods = vi.fn();
const fetchInventorySources = vi.fn();
const fetchCoverageGoals = vi.fn();
const fetchCoverageActions = vi.fn();
const fetchInventorySourceStatuses = vi.fn();
const fetchCoverage = vi.fn();
const fetchCampusIntake = vi.fn();
const createCoverageGoal = vi.fn();

vi.mock('../../../api/emissions-extended', () => ({
  fetchReportingPeriods: (...args) => fetchReportingPeriods(...args),
  fetchInventorySources: (...args) => fetchInventorySources(...args),
  fetchCoverageGoals: (...args) => fetchCoverageGoals(...args),
  fetchCoverageActions: (...args) => fetchCoverageActions(...args),
  fetchInventorySourceStatuses: (...args) => fetchInventorySourceStatuses(...args),
  fetchCoverage: (...args) => fetchCoverage(...args),
  fetchCampusIntake: (...args) => fetchCampusIntake(...args),
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

  fetchReportingPeriods.mockResolvedValue([{ id: 1, name: 'FY 2025' }]);
  fetchInventorySources.mockResolvedValue([]);
  fetchCoverageGoals.mockResolvedValue([]);
  fetchCoverageActions.mockResolvedValue([]);
  fetchInventorySourceStatuses.mockResolvedValue([]);
  fetchCoverage.mockResolvedValue(coverageFixture);
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
        inventory_kg: null,
      },
    ],
  });
});

describe('Inventory coverage O1 quote honesty', () => {
  it('warns that figures are not O1 and links to onboarding (O1-USE-QUOTE)', async () => {
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/are not the O1/);
    expect(screen.getByRole('button', { name: 'Inventory onboarding' })).toBeInTheDocument();
    expect(createCoverageGoal).not.toHaveBeenCalled();
  });

  it('defaults new goal scope to 1+2 with empty target coverage', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole('alert');

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
    expect(await screen.findByText(/FY 2023-24/)).toBeInTheDocument();
    expect(screen.getByText(/FY 2025-26/)).toBeInTheDocument();
    expect(screen.getAllByText('Missing').length).toBeGreaterThan(0);
    expect(screen.getByText('Entered')).toBeInTheDocument();
    expect(screen.getAllByText('Absent').length).toBeGreaterThan(0);
    expect(screen.queryByText(/^0 kg$/)).not.toBeInTheDocument();
  });
});
