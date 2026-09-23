// Account Settings remake — Account tab, no Pulse, linked employee.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';

const authState = {
  user: { username: 'emp_1067', email: '', roles: [{ role: 'employee' }, { role: 'employee' }] },
  employee: null,
};

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('../api/api', () => ({
  apiFetch: vi.fn().mockResolvedValue({
    username: 'emp_1067',
    roles: [{ role: 'employee' }, { role: 'employee' }],
  }),
}));

vi.mock('../hooks/useDocumentTitle', () => ({
  default: () => {},
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({
    notify: vi.fn(),
    notifyFromError: vi.fn(),
  }),
}));

vi.mock('../i18n/useLanguage', () => ({
  useLanguage: () => ({ lang: 'en', setLanguage: vi.fn(), isRtl: false, ready: true }),
}));

vi.mock('../theme/useThemeMode', () => ({
  useThemeMode: () => ({ mode: 'light', toggle: vi.fn() }),
}));

import SettingsPage from '../pages/SettingsPage';
import { apiFetch } from '../api/api';

function renderAt(path) {
  return render(
    <ThemeProvider theme={createTheme()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('SettingsPage Account remake', () => {
  beforeEach(() => {
    authState.user = {
      username: 'emp_1067',
      email: '',
      roles: [{ role: 'employee' }, { role: 'employee' }],
    };
    authState.employee = {
      id: 1,
      full_name: 'Bilagot Panta Suerte',
      employee_no: '1067',
      org_unit_name: 'Coiled Tubing',
      job_title: 'Heavy Duty Driver',
    };
    localStorage.setItem('access', 'tok');
    vi.clearAllMocks();
    apiFetch.mockResolvedValue({
      username: 'emp_1067',
      roles: [{ role: 'employee' }, { role: 'employee' }],
    });
  });

  it('shows Account tab (not Profile) and no Pulse AI tab', async () => {
    renderAt('/settings?tab=account');
    expect(await screen.findByRole('tab', { name: /Account/i })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Pulse/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /^Profile$/i })).not.toBeInTheDocument();
  });

  it('shows Linked employee and dedupes roles', async () => {
    renderAt('/settings?tab=account');
    expect(await screen.findByText('Linked employee')).toBeInTheDocument();
    expect(screen.getByText('Bilagot Panta Suerte')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open in My/i })).toBeInTheDocument();
    await waitFor(() => {
      const chips = screen.getAllByText(/^employee$/i);
      expect(chips.length).toBe(1);
    });
  });

  it('Preferences exposes language and theme (not coming soon)', async () => {
    renderAt('/settings?tab=preferences');
    expect(await screen.findByLabelText(/Language/i)).toBeInTheDocument();
    expect(screen.getByText(/Light theme|Dark theme/i)).toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it('aliases legacy ?tab=profile to Account content', async () => {
    renderAt('/settings?tab=profile');
    expect(await screen.findByText('Linked employee')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Account/i })).toHaveAttribute('aria-selected', 'true');
  });
});
