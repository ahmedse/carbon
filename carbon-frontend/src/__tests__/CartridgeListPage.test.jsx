import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const fetchInboundCartridges = vi.fn();

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 't', isGlobalAdminFlag: true, userCapabilities: [] }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundCartridges: (...args) => fetchInboundCartridges(...args),
  createInboundCartridge: vi.fn(),
}));

import CartridgeListPage from '../pages/admin/migration/CartridgeListPage';

describe('Cartridge definitions', () => {
  it('shows the key and opens only from the eye', async () => {
    fetchInboundCartridges.mockResolvedValue([
      {
        id: 7,
        key: 'people.leave_history',
        owner_app: 'people',
        label: 'Leave history',
        bound: true,
        enabled: true,
        batch_count: 1,
        last_status: 'committed',
      },
    ]);
    render(
      <MemoryRouter>
        <CartridgeListPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('people.leave_history')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open cartridge' })).toBeInTheDocument();
  });

  it('shows the forbidden state when define is refused', async () => {
    const err = new Error('no');
    err.status = 403;
    fetchInboundCartridges.mockRejectedValue(err);
    render(
      <MemoryRouter>
        <CartridgeListPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/cannot define cartridges/i)).toBeInTheDocument();
  });
});
