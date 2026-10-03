import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  fetchInboundRows: vi.fn(),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundRows: mocks.fetchInboundRows,
}));

// The shared grid virtualizes by viewport, which jsdom measures as 0. Assert the
// viewer's props/states through a thin stand-in for FilteredDataGrid instead.
vi.mock('../components/FilteredDataGrid', () => ({
  default: ({ rows, loading, emptyMessage, rowCount }) => (
    <div>
      <div data-testid="loading">{loading ? 'loading' : 'idle'}</div>
      <div data-testid="rowcount">{String(rowCount)}</div>
      {rows.length === 0
        ? <div data-testid="empty">{emptyMessage}</div>
        : rows.map((row) => (
          <div key={row.__row} data-testid="row">
            {`${row.__row}|${row.__key}|${row.__verdict}|${row.__reason}`}
          </div>
        ))}
    </div>
  ),
}));

import InboundRowsViewer from '../components/inbound/InboundRowsViewer';

const HEADERS = ['employee_no', 'full_name'];

function renderViewer() {
  return render(<InboundRowsViewer token="t" batchId={7} headers={HEADERS} />);
}

describe('InboundRowsViewer — read-only full-row states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders every row from the endpoint, including rows past the 20-row sample', async () => {
    mocks.fetchInboundRows.mockResolvedValue({
      results: [
        { row: 21, key: 'DMSDEV9021', verdict: 'insert', reason: '', values: { employee_no: 'DMSDEV9021', full_name: 'Row 21' } },
        { row: 22, key: 'DMSDEV9022', verdict: 'reject', reason: 'org_unit unresolved', values: { employee_no: 'DMSDEV9022', full_name: 'Row 22' } },
      ],
      headers: HEADERS,
      page: 1,
      page_size: 50,
      count: 45,
      max_page_size: 200,
    });
    renderViewer();

    expect(mocks.fetchInboundRows).toHaveBeenCalledWith('t', 7, { page: 1, pageSize: 50 });
    expect(await screen.findByText('45 rows in this file')).toBeInTheDocument();
    // Row 21+ is now reachable (the old ≤20 grid could never show it), a clean
    // insert keeps an empty reason, and a reject keeps its reason.
    expect(screen.getByText('21|DMSDEV9021|insert|')).toBeInTheDocument();
    expect(screen.getByText('22|DMSDEV9022|reject|org_unit unresolved')).toBeInTheDocument();
    expect(screen.getByTestId('rowcount')).toHaveTextContent('45');
  });

  it('shows the empty state with no rows in the file', async () => {
    mocks.fetchInboundRows.mockResolvedValue({ results: [], headers: HEADERS, page: 1, page_size: 50, count: 0 });
    renderViewer();

    expect(await screen.findByText('No rows in this file')).toBeInTheDocument();
  });

  it('distinguishes a page with no rows from an empty file', async () => {
    mocks.fetchInboundRows.mockResolvedValue({ results: [], headers: HEADERS, page: 9, page_size: 50, count: 5 });
    renderViewer();

    expect(await screen.findByText('No rows on this page')).toBeInTheDocument();
  });

  it('shows an error with retry', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundRows
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({ results: [], headers: HEADERS, page: 1, page_size: 50, count: 0 });
    renderViewer();

    expect(await screen.findByText('boom')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(mocks.fetchInboundRows).toHaveBeenCalledTimes(2));
  });

  it('shows the forbidden state without a retry', async () => {
    const err = Object.assign(new Error('forbidden'), { status: 403 });
    mocks.fetchInboundRows.mockRejectedValue(err);
    renderViewer();

    expect(await screen.findByText(/do not have permission to open People Import/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });
});
