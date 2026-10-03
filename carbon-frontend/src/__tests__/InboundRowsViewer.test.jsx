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
// viewer's columns/states through a thin stand-in that still calls each column's
// renderCell/valueGetter, so the smoke-result and details cells are exercised.
vi.mock('../components/FilteredDataGrid', () => ({
  default: ({ rows, columns, loading, emptyMessage, rowCount }) => (
    <div>
      <div data-testid="loading">{loading ? 'loading' : 'idle'}</div>
      <div data-testid="rowcount">{String(rowCount)}</div>
      {rows.length === 0
        ? <div data-testid="empty">{emptyMessage}</div>
        : rows.map((row) => (
          <div key={row.__row} data-testid="row">
            {columns.map((col) => {
              const value = col.valueGetter ? col.valueGetter(row[col.field], row) : row[col.field];
              const content = col.renderCell
                ? col.renderCell({ row, value })
                : String(value ?? '');
              return (
                <span key={col.field} data-testid={`cell-${col.field}-${row.__row}`}>
                  {content}
                </span>
              );
            })}
          </div>
        ))}
    </div>
  ),
}));

import InboundRowsViewer from '../components/inbound/InboundRowsViewer';

const HEADERS = ['employee_no', 'full_name'];
const FIELDS = [
  { name: 'employee_no', label: 'Employee number' },
  { name: 'full_name', label: 'Full name' },
  { name: 'org_unit', label: 'Org unit code' },
];
const COLUMN_MAP = { 'Code': 'employee_no', 'Full name': 'full_name', 'Cost Center': 'org_unit' };

function renderViewer() {
  return render(
    <InboundRowsViewer
      token="t"
      batchId={7}
      headers={HEADERS}
      fields={FIELDS}
      columnMap={COLUMN_MAP}
    />,
  );
}

describe('InboundRowsViewer — read-only full-row states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a smoke result and action per row, including rows past the 20-row sample', async () => {
    mocks.fetchInboundRows.mockResolvedValue({
      results: [
        {
          row: 21,
          key: 'DMSDEV9021',
          verdict: 'insert',
          reason: '',
          issues: [],
          values: { employee_no: 'DMSDEV9021', full_name: 'Row 21' },
        },
        {
          row: 22,
          key: 'DMSDEV9022',
          verdict: 'reject',
          reason: 'org_unit unresolved',
          issues: [{
            field: 'org_unit',
            message: 'org_unit unresolved',
            fix: 'Use an existing org unit code.',
          }],
          values: { employee_no: 'DMSDEV9022', full_name: 'Row 22' },
        },
      ],
      headers: HEADERS,
      page: 1,
      page_size: 50,
      count: 45,
      max_page_size: 200,
      smoked: true,
    });
    renderViewer();

    expect(mocks.fetchInboundRows).toHaveBeenCalledWith('t', 7, { page: 1, pageSize: 50 });
    expect(await screen.findByText('45 rows in this file')).toBeInTheDocument();
    // Row 21+ is reachable, gets a friendly insert result and a no-action note.
    expect(screen.getByText('Ready to add')).toBeInTheDocument();
    expect(screen.getByText('No action needed — added on commit.')).toBeInTheDocument();
    // A reject is Blocked and exposes the raw reason in its row.
    expect(screen.getByText('Blocked')).toBeInTheDocument();
    expect(screen.getByText('org_unit unresolved')).toBeInTheDocument();
    expect(screen.getByTestId('rowcount')).toHaveTextContent('45');
  });

  it('expands a failing row into the offending column, reason and fix', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundRows.mockResolvedValue({
      results: [{
        row: 22,
        key: 'DMSDEV9022',
        verdict: 'reject',
        reason: 'org_unit unresolved',
        issues: [{
          field: 'org_unit',
          message: 'org_unit unresolved',
          fix: 'Use an existing org unit code.',
        }],
        values: { employee_no: 'DMSDEV9022', full_name: 'Row 22' },
      }],
      headers: HEADERS,
      page: 1,
      page_size: 50,
      count: 1,
      smoked: true,
    });
    renderViewer();

    await user.click(await screen.findByRole('button', { name: 'Details' }));

    expect(await screen.findByText('Row 22 · DMSDEV9022')).toBeInTheDocument();
    // The CSV column that maps to the failed target field, then the fix.
    expect(screen.getByText('Cost Center → Org unit code')).toBeInTheDocument();
    expect(screen.getByText(/Use an existing org unit code\./)).toBeInTheDocument();

    // Closing the panel is inline, never a second modal.
    await user.click(screen.getByRole('button', { name: 'Close details' }));
    await waitFor(() => {
      expect(screen.queryByText('Row 22 · DMSDEV9022')).not.toBeInTheDocument();
    });
  });

  it('shows the not-smoked state instead of a false pass', async () => {
    mocks.fetchInboundRows.mockResolvedValue({
      results: [{
        row: 1,
        key: 'DMSDEV9001',
        verdict: '',
        reason: '',
        issues: [],
        values: { employee_no: 'DMSDEV9001', full_name: 'Row 1' },
      }],
      headers: HEADERS,
      page: 1,
      page_size: 50,
      count: 1,
      smoked: false,
    });
    renderViewer();

    expect(await screen.findByText('Not smoked yet')).toBeInTheDocument();
    expect(screen.getByText(/has not been smoked yet/i)).toBeInTheDocument();
    expect(screen.queryByText('Ready to add')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Details' })).not.toBeInTheDocument();
  });

  it('shows the empty state with no rows in the file', async () => {
    mocks.fetchInboundRows.mockResolvedValue({
      results: [], headers: HEADERS, page: 1, page_size: 50, count: 0, smoked: false,
    });
    renderViewer();

    expect(await screen.findByText('No rows in this file')).toBeInTheDocument();
  });

  it('distinguishes a page with no rows from an empty file', async () => {
    mocks.fetchInboundRows.mockResolvedValue({
      results: [], headers: HEADERS, page: 9, page_size: 50, count: 5, smoked: true,
    });
    renderViewer();

    expect(await screen.findByText('No rows on this page')).toBeInTheDocument();
  });

  it('shows an error with retry', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundRows
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({
        results: [], headers: HEADERS, page: 1, page_size: 50, count: 0, smoked: false,
      });
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
