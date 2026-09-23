import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ user: { token: 'test-token' } }),
}));

vi.mock('../api/orgUnits', () => ({
  fetchOrgUnits: vi.fn(),
  createOrgUnit: vi.fn(),
  updateOrgUnit: vi.fn(),
  deleteOrgUnit: vi.fn(),
}));

import { fetchOrgUnits } from '../api/orgUnits';
import OrgUnitsPage from '../pages/admin/OrgUnitsPage';

const UNITS = [
  { id: 1, name: 'GOFSCO', org_type: 'company', parent: null, code: 'GOFSCO', full_path: 'GOFSCO' },
  {
    id: 2,
    name: 'Administration - Cleaner',
    org_type: 'cost_center',
    parent: 1,
    code: 'administration-cleaner',
    full_path: 'GOFSCO / Administration - Cleaner',
  },
  {
    id: 3,
    name: 'Drilling',
    org_type: 'cost_center',
    parent: 1,
    code: 'drilling',
    full_path: 'GOFSCO / Drilling',
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  fetchOrgUnits.mockResolvedValue(UNITS);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <OrgUnitsPage />
    </MemoryRouter>,
  );
}

function nameColumn() {
  return screen.getAllByRole('gridcell')
    .filter((el) => el.getAttribute('data-field') === 'name')
    .map((el) => el.textContent);
}

describe('OrgUnitsPage list chrome', () => {
  it('searches by name and hides rows that do not match', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Drilling');
    expect(nameColumn()).toEqual(expect.arrayContaining(['Drilling', 'Administration - Cleaner', 'GOFSCO']));

    await user.type(screen.getByPlaceholderText(/Search by name, code, or path/i), 'drill');

    expect(nameColumn()).toEqual(['Drilling']);
    expect(screen.getByText('1 of 3')).toBeInTheDocument();
  });

  it('filters by type', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('Administration - Cleaner');
    await user.click(screen.getByRole('button', { name: /Filters/i }));

    await user.click(screen.getByLabelText('Type'));
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('Company'));

    await waitFor(() => {
      expect(nameColumn()).toEqual(['GOFSCO']);
    });
    expect(screen.getByText('1 of 3')).toBeInTheDocument();
  });
});
