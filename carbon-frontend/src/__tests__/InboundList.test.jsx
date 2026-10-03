import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  fetchInboundBatches: vi.fn(),
  fetchInboundTargets: vi.fn(),
  createInboundBatch: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 't',
    isGlobalAdminFlag: false,
    user: { username: 'prep' },
    userCapabilities: ['inbound:prepare'],
  }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundBatches: mocks.fetchInboundBatches,
  fetchInboundTargets: mocks.fetchInboundTargets,
  createInboundBatch: mocks.createInboundBatch,
}));

vi.mock('../components/inbound/InboundExampleTemplates', () => ({ default: () => null }));

// The shared grid virtualizes by viewport (jsdom measures 0), so stand in for it
// and surface the server-paging props/state the list wires up.
vi.mock('../components/FilteredDataGrid', () => ({
  default: (props) => (
    <div>
      <div data-testid="mode">{props.paginationMode}</div>
      <div data-testid="rowcount">{String(props.rowCount)}</div>
      <div data-testid="search" onClick={() => props.onSearchChange('alpha')}>type-search</div>
      <div data-testid="filter" onClick={() => props.onFilterChange('status', 'committed')}>apply-filter</div>
      <div data-testid="nextpage" onClick={() => props.onPaginationModelChange({ page: 1, pageSize: 25 })}>next</div>
      {props.rows.map((row) => <div key={row.id} data-testid="row">{row.original_filename}</div>)}
      {props.rows.map((row) => (
        <div key={`updated-${row.id}`} data-testid="updated">
          {props.columns.find((c) => c.field === 'updated_at')?.valueGetter(row.updated_at, row)}
        </div>
      ))}
    </div>
  ),
}));

import i18n from '../i18n';
import { formatDisplayDateTime } from '../utils/dateUtils';
import InboundList from '../components/inbound/InboundList';

function renderList() {
  return render(
    <MemoryRouter>
      <InboundList kind="typed_object" listPath="/people/import" />
    </MemoryRouter>,
  );
}

describe('People Import list — server-side paging (Defect 1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchInboundTargets.mockResolvedValue([]);
  });

  it('asks the API for page 1 with a page size and shows the server total', async () => {
    mocks.fetchInboundBatches.mockResolvedValue({
      count: 137,
      results: [{ id: 1, original_filename: 'alpha.csv', status: 'draft' }],
    });
    renderList();

    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenCalled());
    expect(mocks.fetchInboundBatches).toHaveBeenCalledWith('t', expect.objectContaining({
      kind: 'typed_object',
      page: 1,
      page_size: 25,
    }));
    // The count comes from the API, so rows past the first page are not lost.
    expect(await screen.findByTestId('rowcount')).toHaveTextContent('137');
    expect(screen.getByTestId('mode')).toHaveTextContent('server');
    expect(screen.getByText('alpha.csv')).toBeInTheDocument();
  });

  it('sends the debounced q to the API and resets to page 1', async () => {
    mocks.fetchInboundBatches.mockResolvedValue({ count: 1, results: [{ id: 1, original_filename: 'alpha.csv', status: 'draft' }] });
    renderList();
    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId('search'));

    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenLastCalledWith('t', expect.objectContaining({
      q: 'alpha',
      page: 1,
    })));
  });

  it('sends an active filter to the API and pages the server', async () => {
    mocks.fetchInboundBatches.mockResolvedValue({ count: 60, results: [] });
    renderList();
    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId('filter'));
    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenLastCalledWith('t', expect.objectContaining({
      status: 'committed',
      page: 1,
    })));

    fireEvent.click(screen.getByTestId('nextpage'));
    await waitFor(() => expect(mocks.fetchInboundBatches).toHaveBeenLastCalledWith('t', expect.objectContaining({
      page: 2,
    })));
  });

  it('formats updated_at with the shared locale-aware date util, not inline Date', async () => {
    const updatedAt = '2026-10-03T13:07:00Z';
    mocks.fetchInboundBatches.mockResolvedValue({
      count: 1,
      results: [{ id: 1, original_filename: 'alpha.csv', status: 'draft', updated_at: updatedAt }],
    });
    renderList();

    // The cell text is exactly the util's output (inline toLocaleString would
    // include seconds and a different format), so the util is the single source.
    const cell = await screen.findByTestId('updated');
    expect(cell.textContent).toBe(formatDisplayDateTime(updatedAt, i18n.language));
  });
});
