// src/__tests__/AIDomainEntryPoints.test.jsx
// ONE simple "Ask AI" button that activates the Pulse with the current
// entity's context. No dropdowns, no per-domain action buttons.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  transferTask: vi.fn(),
}));

vi.mock('../shell/useAITaskTransfer', () => ({
  useAITaskTransfer: () => ({ transferTask: mocks.transferTask }),
}));

import AIDomainEntryPoints from '../shell/AIDomainEntryPoints';

const TABLE = { id: 't1', name: 'Emissions Fuel', row_count: 100 };
const MODULE = { id: 'm1', name: 'Scope 2 Electricity' };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transferTask.mockResolvedValue('conv-1');
});

describe('AIDomainEntryPoints', () => {
  it('renders exactly ONE "Ask AI" button — no dropdown, no extra actions', () => {
    render(
      <AIDomainEntryPoints entityType="table" entityId={TABLE.id} entity={TABLE} />,
    );

    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Ask AI' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'More AI actions' })).not.toBeInTheDocument();
  });

  it('activates Pulse with table context on click', async () => {
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

  it('activates Pulse with module context on click', async () => {
    render(
      <AIDomainEntryPoints entityType="module" entityId={MODULE.id} entity={MODULE} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ask AI' }));

    await waitFor(() => expect(mocks.transferTask).toHaveBeenCalled());
    expect(mocks.transferTask).toHaveBeenCalledWith(
      'chat',
      { module_id: 'm1', module_name: 'Scope 2 Electricity' },
      expect.objectContaining({
        source_page: 'catalog-data-product-detail',
        title: 'Ask about: Scope 2 Electricity',
        workspaceContext: expect.objectContaining({
          workspace: 'catalog',
          entity_type: 'module',
          entity_id: 'm1',
          intent_signal: 'chat',
        }),
      }),
    );
  });
});
