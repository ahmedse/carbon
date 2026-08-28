import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SchemaStructureTab from '../pages/catalog/tabs/SchemaStructureTab';

const updateFieldMaskingStrategy = vi.fn();

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { is_superuser: false }, context: {} }),
}));

const notify = vi.fn();

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError: vi.fn(), showFeedback: vi.fn() }),
}));

vi.mock('../api/dataschema', () => ({
  createDataSchemaField: vi.fn(),
  deleteDataSchemaField: vi.fn(),
  deleteDataSchemaTable: vi.fn(),
  updateDataSchemaField: vi.fn(),
  updateDataSchemaFieldOrder: vi.fn(),
}));

vi.mock('../api/fieldPolicies', () => ({
  updateFieldMaskingStrategy: (...args) => updateFieldMaskingStrategy(...args),
  getFieldPolicies: vi.fn(),
  createFieldPolicy: vi.fn(),
  deleteFieldPolicy: vi.fn(),
  fetchAllFields: vi.fn(),
}));

const baseTable = {
  id: 5,
  title: 'Customers',
  description: 'Customer records',
  row_count: 0,
  module: null,
};

function renderTab({ fields = [], isAdmin = false, onChanged = vi.fn() } = {}) {
  return render(
    <MemoryRouter initialEntries={['/catalog/tables/5']}>
      <SchemaStructureTab
        _entityData={null}
        tableId={5}
        table={baseTable}
        fields={fields}
        onChanged={onChanged}
        isAdmin={isAdmin}
        onEditMetadata={vi.fn()}
      />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('SchemaStructureTab — field visibility & masking', () => {
  it('renders LockIcon + "(Access Restricted)" for an access_denied field and hides edit/reorder actions', () => {
    renderTab({ fields: [{ id: 1, name: 'ssn', label: 'SSN', type: 'string', access_denied: true }], isAdmin: true });

    expect(screen.getByText('(Access Restricted)')).toBeInTheDocument();
    expect(screen.getByTestId('LockIcon')).toBeInTheDocument();
    // Denied rows get no edit/reorder buttons even for admins
    expect(screen.queryByTestId('EditIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('DeleteIcon')).not.toBeInTheDocument();
  });

  it('renders VisibilityOffIcon + "Masked" chip for an is_masked field', () => {
    renderTab({
      fields: [{ id: 2, name: 'email', label: 'Email', type: 'string', masking_strategy: 'redact', is_masked: true }],
    });

    expect(screen.getByTestId('VisibilityOffIcon')).toBeInTheDocument();
    expect(screen.getByText('Masked')).toBeInTheDocument();
    // Not access-denied — no lock indicator
    expect(screen.queryByTestId('LockIcon')).not.toBeInTheDocument();
  });

  it('renders a normal field without any access icons', () => {
    renderTab({ fields: [{ id: 3, name: 'first_name', label: 'First Name', type: 'string', masking_strategy: 'none' }] });

    expect(screen.getByText('first_name')).toBeInTheDocument();
    expect(screen.queryByTestId('LockIcon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('VisibilityOffIcon')).not.toBeInTheDocument();
  });

  it('shows the masking-strategy Select for admins and updates the strategy on change', async () => {
    updateFieldMaskingStrategy.mockResolvedValue({});
    const onChanged = vi.fn();
    renderTab({
      fields: [{ id: 7, name: 'phone', label: 'Phone', type: 'string', masking_strategy: 'none' }],
      isAdmin: true,
      onChanged,
    });

    const comboboxes = screen.getAllByRole('combobox');
    expect(comboboxes).toHaveLength(1);

    fireEvent.mouseDown(comboboxes[0]);
    const redact = await screen.findByRole('option', { name: 'Redact' });
    fireEvent.click(redact);

    await waitFor(() => {
      expect(updateFieldMaskingStrategy).toHaveBeenCalledWith('test-token', 7, 'redact');
    });
    await waitFor(() => {
      expect(onChanged).toHaveBeenCalled();
    });
  });

  it('hides the masking-strategy Select for non-admins', () => {
    renderTab({
      fields: [{ id: 7, name: 'phone', label: 'Phone', type: 'string', masking_strategy: 'none' }],
      isAdmin: false,
    });

    expect(screen.queryAllByRole('combobox')).toHaveLength(0);
    // Type chip still renders as before
    expect(screen.getByText('string')).toBeInTheDocument();
  });
});
