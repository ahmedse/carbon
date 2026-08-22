// src/__tests__/AIDomainEntryPoints.test.jsx
// Phase 7C — the AI entry-point surface is ONE "Ask AI" button. Clicking the
// main button activates the Pulse with the entity context (generic chat); a
// split-button arrow reveals the entity-specific domain actions (deduped).
// Regression: multiple matching entry points never render more than one AI button.
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

const ADMIN = {
  app_identifier: 'admin',
  entry_points: [
    { label: 'Trace lineage', task_type: 'lineage', on_entity: 'table', icon: 'ManageSearch' },
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
  it('renders exactly ONE "Ask AI" button even with multiple matching entry points', () => {
    mocks.manifests = [EMISSIONS, ADMIN];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    expect(screen.getAllByRole('button', { name: 'Ask AI' })).toHaveLength(1);
    // Entry points are hidden behind the split-button arrow until opened.
    expect(screen.queryByRole('menuitem', { name: 'Validate DQ' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Trace lineage' })).not.toBeInTheDocument();
  });

  it('main button activates Pulse with entity context (chat)', async () => {
    mocks.manifests = [EMISSIONS];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }));

    await waitFor(() => expect(mocks.transferTask).toHaveBeenCalled());
    expect(mocks.transferTask).toHaveBeenCalledWith(
      'chat',
      {
        table_id: 't1',
        table_name: 'Emissions Fuel',
        row_count: 100,
        module_id: null,
        module_name: null,
      },
      expect.objectContaining({
        source_page: 'catalog-schema-detail',
        title: 'Ask about: Emissions Fuel',
        workspaceContext: expect.objectContaining({
          workspace: 'catalog',
          entity_type: 'table',
          entity_id: 't1',
          entity_name: 'Emissions Fuel',
          intent_signal: 'chat',
        }),
      }),
    );
  });

  it('lists only entity-specific actions (deduped) behind the arrow', () => {
    mocks.manifests = [EMISSIONS, ADMIN];
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'More AI actions' }));

    // Entity-specific actions from every matching domain app.
    expect(screen.getByRole('menuitem', { name: 'Validate DQ' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Trace lineage' })).toBeInTheDocument();
    // The generic chat is the main button; deduped, not repeated per app.
    expect(screen.queryByRole('menuitem', { name: 'Ask about this' })).not.toBeInTheDocument();
    // Module-only action is filtered out on a table page.
    expect(screen.queryByRole('menuitem', { name: 'Draft Report' })).not.toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: 'More AI actions' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Validate DQ' }));

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

    fireEvent.click(screen.getByRole('button', { name: 'More AI actions' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Draft Report' }));

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
});
