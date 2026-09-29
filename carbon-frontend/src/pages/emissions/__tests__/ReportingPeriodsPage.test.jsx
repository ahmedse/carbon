import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReportingPeriodsPage from '../ReportingPeriodsPage';

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't', canManageAllModules: () => true }),
}));

vi.mock('../../../hooks/useDocumentTitle', () => ({
  default: () => {},
}));

const fetchReportingPeriods = vi.fn();
const lockPeriod = vi.fn();
const closePeriod = vi.fn();

vi.mock('../../../api/emissions-extended', () => ({
  fetchReportingPeriods: (...args) => fetchReportingPeriods(...args),
  lockPeriod: (...args) => lockPeriod(...args),
  closePeriod: (...args) => closePeriod(...args),
  createReportingPeriod: vi.fn(),
  updateReportingPeriod: vi.fn(),
  deleteReportingPeriod: vi.fn(),
  submitPeriod: vi.fn(),
  openPeriod: vi.fn(),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <ReportingPeriodsPage />
    </MemoryRouter>,
  );
}

const twoOpenFixture = [
  {
    id: 15,
    name: 'FY 2023-24',
    period_type: 'annual',
    start_date: '2023-07-01',
    end_date: '2024-06-30',
    status: 'open',
  },
  {
    id: 16,
    name: 'FY 2025-26',
    period_type: 'annual',
    start_date: '2025-07-01',
    end_date: '2026-06-30',
    status: 'open',
  },
];

beforeEach(() => {
  fetchReportingPeriods.mockReset();
  lockPeriod.mockReset();
  closePeriod.mockReset();
});

describe('ReportingPeriodsPage', () => {
  it('warns when more than one period is open (O1-USE-PERIODS)', async () => {
    fetchReportingPeriods.mockResolvedValue(twoOpenFixture);
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Close is not allowed from Open/);
    expect(alert).toHaveTextContent(/FY 2023-24/);
    expect(alert).toHaveTextContent(/FY 2025-26/);
    expect(screen.queryByText(/kg CO2e/)).toBeNull();
    expect(lockPeriod).not.toHaveBeenCalled();
    expect(closePeriod).not.toHaveBeenCalled();
  });

  it('does not show the multi-open warning when exactly one period is open', async () => {
    fetchReportingPeriods.mockResolvedValue([
      {
        id: 15,
        name: 'FY 2023-24',
        period_type: 'annual',
        start_date: '2023-07-01',
        end_date: '2024-06-30',
        status: 'open',
      },
      {
        id: 17,
        name: 'FY 2024-25',
        period_type: 'annual',
        start_date: '2024-07-01',
        end_date: '2025-06-30',
        status: 'locked',
      },
    ]);
    renderPage();
    expect(await screen.findByText(/FY 2023-24/)).toBeInTheDocument();
    expect(screen.queryByText(/Close is not allowed from Open/)).toBeNull();
  });
});
