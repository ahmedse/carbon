import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    token: 't',
    isGlobalAdminFlag: false,
    userCapabilities: ['my:access'],
  }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundBatches: vi.fn(),
  fetchInboundTargets: vi.fn(),
  createInboundBatch: vi.fn(),
}));

import ImportListPage from '../apps/people/ImportListPage';

describe('People Import list', () => {
  it('shows forbidden copy when the user lacks inbound caps', () => {
    render(
      <MemoryRouter>
        <ImportListPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/do not have permission to open People Import/i)).toBeInTheDocument();
  });
});
