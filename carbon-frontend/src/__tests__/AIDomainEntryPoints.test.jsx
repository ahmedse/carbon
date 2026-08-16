// src/__tests__/AIDomainEntryPoints.test.jsx
// Phase 7C — manifest entry_points rendered on entity pages and dispatched
// with entity payload + explicit app_identifier.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const mocks = vi.hoisted(() => ({
  transferTask: vi.fn(),
  manifests: [],
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ transferTask: mocks.transferTask }),
}));

vi.mock('../hooks/useDomainManifests', () => ({
  useDomainManifests: () => ({ manifests: mocks.manifests }),
}));

import AIDomainEntryPoints from '../shell/AIDomainEntryPoints';

const EMISSIONS = {
  app_identifier: 'emissions',
  entry_points: [
    { label: 'Validate DQ', task_type: 'dq_validate', on_entity: 'table', icon: 'FactCheck' },
    { label: 'Draft Report', task_type: 'report_draft', on_entity: 'module', icon: 'Description' },
    { label: 'Ask about this', task_type: 'chat', on_entity: '*', icon: 'Chat' },
  ],
};

const TABLE = { id: 't1', name: 'Emissions Fuel', row_count: 100 };
const MODULE = { id: 'm1', name: 'Scope 2 Electricity' };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.manifests = [];
  mocks.transferTask.mockResolvedValue('conv-1');
});

describe('AIDomainEntryPoints (Phase 7C)', () => {
  it('filters entry points by entity type (table + "*", not module)', () => {
    mocks.manifests = [EMISSIONS];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    expect(screen.getByRole('button', { name: 'Validate DQ' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask about this' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Draft Report' })).not.toBeInTheDocument();
  });

  it('renders null when no entry points match', () => {
    mocks.manifests = [{ app_identifier: 'emissions', entry_points: [] }];
    const { container } = render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('dispatches table entry point with entity payload + explicit app_identifier', async () => {
    mocks.manifests = [EMISSIONS];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Validate DQ' }));

    await waitFor(() => expect(mocks.transferTask).toHaveBeenCalled());
    expect(mocks.transferTask).toHaveBeenCalledWith(
      'dq_validate',
      {
        table_id: 't1',
        table_name: 'Emissions Fuel',
        row_count: 100,
        module_id: null,
        module_name: null,
      },
      expect.objectContaining({
        app_identifier: 'emissions',
        source_page: 'catalog-schema-detail',
        title: 'Validate DQ: Emissions Fuel',
      }),
    );
  });

  it('dispatches module entry point with module payload', async () => {
    mocks.manifests = [EMISSIONS];
    render(
      <AIDomainEntryPoints entityType="module" entityId={MODULE.id} entity={MODULE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Draft Report' }));

    await waitFor(() => expect(mocks.transferTask).toHaveBeenCalled());
    expect(mocks.transferTask).toHaveBeenCalledWith(
      'report_draft',
      { module_id: 'm1', module_name: 'Scope 2 Electricity' },
      expect.objectContaining({
        app_identifier: 'emissions',
        source_page: 'catalog-data-product-detail',
      }),
    );
  });

  it('dispatches "*" chat entry point with explicit app_identifier', async () => {
    mocks.manifests = [EMISSIONS];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ask about this' }));

    await waitFor(() => expect(mocks.transferTask).toHaveBeenCalled());
    expect(mocks.transferTask).toHaveBeenCalledWith(
      'chat',
      expect.objectContaining({ table_id: 't1' }),
      expect.objectContaining({ app_identifier: 'emissions' }),
    );
  });
});
