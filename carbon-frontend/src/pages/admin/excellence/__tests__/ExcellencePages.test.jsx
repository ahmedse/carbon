import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { apiFetch } from '../../../../api/api';
import ExcellenceConsolePage from '../ExcellenceConsolePage';

const overview = {
  head: 'abc1234def',
  contexts: [
    {
      id: 'pulse', title: 'Pulse', owner: 'pulse-master', app_count: 1, median: 0, floor: 0, unmanaged: 1,
      histogram: {},
      apps: [{ id: 'pulse', title: 'Pulse', tier: 'pulse', kind: 'app', level: 0, level_name: 'Unmanaged', distance: 9 }],
    },
    {
      id: 'nibras', title: 'Nibras', owner: 'nibras-master', app_count: 1, median: 2, floor: 2, unmanaged: 0,
      histogram: {},
      apps: [{ id: 'nibras.module.people', title: 'people', tier: 'nibras', kind: 'module', level: 2, level_name: 'Specified', distance: 3 }],
    },
  ],
};

const pulseApp = {
  id: 'pulse', title: 'Pulse', tier: 'pulse', head: 'abc1234def', level: 0, level_name: 'Unmanaged',
  dimensions: { secure: 0 }, weakest: 'secure', distance: 1, freshness: 0, tracks: [{ id: 'chat', title: 'Chat' }],
  cells: [
    { dimension: 'secure', level: 1, state: 'open', rung: 'Data class declared', evidence_floor: 'configured', checks: [] },
    { dimension: 'governed', level: 1, state: 'passed', rung: 'Owner named', evidence_floor: 'configured', checks: [] },
  ],
  next: [{ dimension: 'secure', level: 1, state: 'open', rung: 'Data class declared' }],
};

vi.mock('../../../../auth/AuthContext', () => ({ useAuth: () => ({ token: 'staff-token' }) }));
vi.mock('../../../../components/NotificationProvider', () => ({ useNotification: () => ({ notify: vi.fn() }) }));
vi.mock('../../../../api/api', () => ({ apiFetch: vi.fn(), apiFetchStream: vi.fn() }));

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation((url) => {
    if (url.startsWith('excellence/apps/')) return Promise.resolve(pulseApp);
    if (url.startsWith('excellence/overview')) return Promise.resolve(overview);
    return Promise.resolve({ version: 1, rungs: [] });
  });
});

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/excellence" element={<ExcellenceConsolePage />} />
        <Route path="/admin/excellence/:context" element={<ExcellenceConsolePage />} />
        <Route path="/admin/excellence/:context/:app" element={<ExcellenceConsolePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Excellence console', () => {
  it('opens as a window on the framework', async () => {
    renderAt('/admin/excellence');
    expect(await screen.findByText(/quality framework/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'View Pulse' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'View Nibras' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'View Read the standard' })).toBeTruthy();
  });

  it('opens Pulse ladder with open cell and weakest-aspect copy', async () => {
    renderAt('/admin/excellence/pulse/pulse');
    expect(await screen.findByLabelText('Secure Declared open')).toBeTruthy();
    expect(screen.getByText(/The level is the weakest aspect/i)).toBeTruthy();
    expect(screen.getByText(/Weakest: Secure/i)).toBeTruthy();
  });

  it('opens the Pulse product page with coverage before coworker maturity', async () => {
    const user = userEvent.setup();
    renderAt('/admin/excellence');
    await screen.findByRole('button', { name: 'View Pulse' });
    await user.click(screen.getByRole('button', { name: 'View Pulse' }));
    expect(await screen.findByText(/weakest of nine aspects/i)).toBeTruthy();
    expect(screen.getByText(/Pulse coworker maturity/i)).toBeTruthy();
    expect(screen.getByText('Understands · not mapped')).toBeTruthy();
  });
});
