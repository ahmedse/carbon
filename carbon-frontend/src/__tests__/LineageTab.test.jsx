import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const mockGetTableLineage = vi.fn();
const mockGetTableImpact = vi.fn();
const mockCreateLineageEdge = vi.fn();

vi.mock('../api/lineage', () => ({
  getTableLineage: (...args) => mockGetTableLineage(...args),
  getTableImpact: (...args) => mockGetTableImpact(...args),
  createLineageEdge: (...args) => mockCreateLineageEdge(...args),
  deleteLineageEdge: vi.fn(),
}));

vi.mock('../api/dataschema', () => ({
  fetchDataSchemaTables: vi.fn(),
}));

const mockNotify = vi.fn();
const mockNotifyFromError = vi.fn();

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: mockNotify, notifyFromError: mockNotifyFromError }),
}));

import LineageTab from '../pages/catalog/tabs/LineageTab';
import { fetchDataSchemaTables } from '../api/dataschema';

beforeEach(() => {
  vi.clearAllMocks();
  fetchDataSchemaTables.mockResolvedValue([]);
});

describe('LineageTab', () => {
  it('renders graph view by default', async () => {
    mockGetTableLineage.mockResolvedValue({ upstream: [], downstream: [] });
    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: /graph/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /impact/i })).toBeInTheDocument();
    expect(await screen.findByText(/no lineage registered/i)).toBeInTheDocument();
  });

  it('toggles to impact view', async () => {
    mockGetTableImpact.mockResolvedValue({ levels: [], total_affected: 0 });
    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /impact/i }));

    expect(await screen.findByText(/no impact data available/i)).toBeInTheDocument();
    expect(mockGetTableImpact).toHaveBeenCalledWith('test-token', '42', 5);
  });

  it('renders empty state when no edges returned', async () => {
    mockGetTableLineage.mockResolvedValue({ upstream: [], downstream: [] });
    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/no lineage registered/i)).toBeInTheDocument();
  });

  it('shows upstream and downstream nodes in graph view', async () => {
    mockGetTableLineage.mockResolvedValue({
      upstream: [
        {
          id: 1,
          source_table: '41',
          target_table: '42',
          source_table_name: 'SourceTable',
          target_table_name: 'CurrentTable',
          source_field_name: 'src_field',
          target_field_name: 'tgt_field',
          edge_type: 'copy',
        },
      ],
      downstream: [
        {
          id: 2,
          source_table: '42',
          target_table: '43',
          source_table_name: 'CurrentTable',
          target_table_name: 'DownstreamTable',
          source_field_name: 'src_field',
          target_field_name: 'tgt_field',
          edge_type: 'transform',
        },
      ],
    });

    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/SourceTable/i)).toBeInTheDocument();
    expect(screen.getByText(/DownstreamTable/i)).toBeInTheDocument();
  });

  it('renders impact view level structure', async () => {
    mockGetTableImpact.mockResolvedValue({
      levels: [
        {
          depth: 1,
          tables: [
            { id: '41', name: 'ParentTable', module_name: 'Sales', edge_type: 'dependency' },
          ],
        },
        {
          depth: 2,
          tables: [
            { id: '40', name: 'GrandParentTable', module_name: 'Finance', edge_type: 'aggregate' },
          ],
        },
      ],
      total_affected: 2,
    });

    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: /impact/i }));

    expect(await screen.findByText(/Depth 1/i)).toBeInTheDocument();
    expect(screen.getByText('ParentTable')).toBeInTheDocument();
    expect(screen.getByText('Sales')).toBeInTheDocument();
    expect(screen.getByText('Dependency')).toBeInTheDocument();
    expect(screen.getByText(/Depth 2/i)).toBeInTheDocument();
    expect(screen.getByText('GrandParentTable')).toBeInTheDocument();
  });

  it('opens add edge dialog for admin and hides button for non-admin', async () => {
    mockGetTableLineage.mockResolvedValue({ upstream: [], downstream: [] });
    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={true} />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: /add edge/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    vi.clearAllMocks();
    render(
      <MemoryRouter>
        <LineageTab tableId="42" isAdmin={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /add edge/i })).not.toBeInTheDocument();
  });
});
