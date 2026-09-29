import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

const fetchInboundCartridge = vi.fn();

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't', isGlobalAdminFlag: true, userCapabilities: [] }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundCartridge: (...args) => fetchInboundCartridge(...args),
  updateInboundCartridge: vi.fn(),
  deleteInboundCartridge: vi.fn(),
}));

import CartridgeDetailPage from '../pages/admin/migration/CartridgeDetailPage';

function At() {
  const location = useLocation();
  return <div data-testid="at">{location.pathname}</div>;
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/admin/migration/cartridges/4']}>
      <At />
      <Routes>
        <Route path="/admin/migration/cartridges/:id" element={<CartridgeDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Cartridge detail observe', () => {
  it('lists the batch and opens the People door from the eye', async () => {
    fetchInboundCartridge.mockResolvedValue({
      id: 4,
      key: 'people.leave_history',
      owner_app: 'people',
      label: 'Leave history',
      kind: 'typed_object',
      bound: true,
      enabled: true,
      batch_count: 1,
      last_status: 'committed',
      fields: [{ name: 'employee_no', label: 'Employee', required: true }],
      recent_batches: [{
        id: 6,
        kind: 'typed_object',
        status: 'committed',
        original_filename: 'history.csv',
        reject: 0,
      }],
    });
    const user = userEvent.setup();
    renderDetail();
    expect(await screen.findByText('history.csv')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete declaration' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Open batch' }));
    expect(screen.getByTestId('at')).toHaveTextContent('/people/import/6');
  });

  it('keeps a batch without a door on the declaration', async () => {
    fetchInboundCartridge.mockResolvedValue({
      id: 9,
      key: 'eduos.room',
      owner_app: 'eduos',
      label: 'Room',
      kind: 'typed_object',
      bound: false,
      enabled: true,
      batch_count: 1,
      last_status: 'draft',
      fields: [{ name: 'code', label: 'Code', required: true }],
      recent_batches: [{
        id: 3,
        kind: 'typed_object',
        status: 'draft',
        original_filename: 'rooms.csv',
        reject: null,
      }],
    });
    const user = userEvent.setup();
    renderDetail();
    expect(await screen.findByText('rooms.csv')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Open batch' }));
    expect(screen.getByTestId('at')).toHaveTextContent('/admin/migration/cartridges/4');
    expect(screen.getByText(/no door yet/i)).toBeInTheDocument();
  });
});