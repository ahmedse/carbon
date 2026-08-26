// src/__tests__/TableProfileTab.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockGetTableProfile = vi.fn();
const mockRunTableProfile = vi.fn();

vi.mock('../api/profiling', () => ({
  getTableProfile: (...args) => mockGetTableProfile(...args),
  runTableProfile: (...args) => mockRunTableProfile(...args),
  getTableScorecard: vi.fn(),
  getTableFreshness: vi.fn(),
  saveFreshnessPolicy: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const mockNotify = vi.fn();

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify }),
}));

import TableProfileTab from '../pages/catalog/tabs/TableProfileTab';

// jsdom has no ResizeObserver — MUI DataGrid needs a stub.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;

const PROFILE_RESPONSE = {
  profile: {
    id: 1,
    data_table: 42,
    table_name: 'customers',
    row_count: 100,
    completeness_pct: 95.0,
    null_counts: {},
    distinct_counts: {},
    min_values: {},
    max_values: {},
    mean_values: {},
    profiled_at: '2026-08-26T10:00:00Z',
  },
  fields: [
    {
      id: 11,
      data_field: 101,
      field_name: 'customer_id',
      row_count: 100,
      null_count: 0,
      distinct_count: 100,
      completeness_pct: 100,
      uniqueness_pct: 100,
      min_value: '1',
      max_value: '100',
      mean_value: null,
      top_values: [{ value: '1', count: 1 }],
      profiled_at: '2026-08-26T10:00:00Z',
    },
    {
      id: 12,
      data_field: 102,
      field_name: 'email',
      row_count: 100,
      null_count: 25,
      distinct_count: 80,
      completeness_pct: 75,
      uniqueness_pct: 80,
      min_value: null,
      max_value: null,
      mean_value: null,
      top_values: [],
      profiled_at: '2026-08-26T10:00:00Z',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  global.ResizeObserver = FakeResizeObserver;
  Element.prototype.getBoundingClientRect = () => ({
    width: 960,
    height: 600,
    top: 0,
    left: 0,
    right: 960,
    bottom: 600,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
});

afterEach(() => {
  delete global.ResizeObserver;
  Element.prototype.getBoundingClientRect = originalGetBoundingClientRect;
});

describe('TableProfileTab', () => {
  it('renders the fields table after loading', async () => {
    mockGetTableProfile.mockResolvedValue(PROFILE_RESPONSE);

    render(
      <MemoryRouter>
        <TableProfileTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    expect(await screen.findByText('customer_id')).toBeInTheDocument();
    expect(screen.getByText('email')).toBeInTheDocument();
    expect(screen.getByText('25.0%')).toBeInTheDocument();
    expect(mockGetTableProfile).toHaveBeenCalledWith('42', 'test-token');
  });

  it('renders the "no profile yet" info state on 404', async () => {
    const notFound = new Error('No profile yet for this table.');
    notFound.status = 404;
    notFound.data = { detail: 'No profile yet for this table.' };
    mockGetTableProfile.mockRejectedValue(notFound);

    render(
      <MemoryRouter>
        <TableProfileTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('No profile yet — click Run Profile to compute one.'),
    ).toBeInTheDocument();
    expect(mockNotify).not.toHaveBeenCalled();
  });

  it('hides Run Profile when isAdmin is false', async () => {
    mockGetTableProfile.mockResolvedValue(PROFILE_RESPONSE);

    render(
      <MemoryRouter>
        <TableProfileTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    await screen.findByText('customer_id');
    expect(screen.queryByRole('button', { name: 'Run Profile' })).not.toBeInTheDocument();
  });

  it('shows Run Profile when isAdmin is true', async () => {
    mockGetTableProfile.mockResolvedValue(PROFILE_RESPONSE);

    render(
      <MemoryRouter>
        <TableProfileTab tableId="42" isAdmin />
      </MemoryRouter>,
    );

    await screen.findByText('customer_id');
    expect(screen.getByRole('button', { name: 'Run Profile' })).toBeInTheDocument();
  });
});
