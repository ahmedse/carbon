// Shell identity helpers + header menu (person-first vs Account).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';

import { resolveDisplayName, resolveInitials } from '../auth/shellIdentity';

describe('resolveDisplayName', () => {
  it('prefers employee.full_name over username', () => {
    expect(
      resolveDisplayName(
        { username: 'emp_1067', full_name: 'emp_1067' },
        { full_name: 'Bilagot Panta Suerte' },
      ),
    ).toBe('Bilagot Panta Suerte');
  });

  it('falls back to username when no employee', () => {
    expect(resolveDisplayName({ username: 'ahmed' }, null)).toBe('ahmed');
  });

  it('uses Django full_name when employee is absent', () => {
    expect(
      resolveDisplayName({ username: 'ahmed', full_name: 'Ahmed Ali' }, null),
    ).toBe('Ahmed Ali');
  });
});

describe('resolveInitials', () => {
  it('uses word starts for multi-part names', () => {
    expect(resolveInitials('Bilagot Panta Suerte')).toBe('BP');
  });

  it('does not take EM from emp_ username style', () => {
    expect(resolveInitials('emp_1067')).toBe('EM');
    expect(resolveInitials(resolveDisplayName(
      { username: 'emp_1067' },
      { full_name: 'Bilagot Panta Suerte' },
    ))).toBe('BP');
  });
});

const authState = {
  user: { username: 'emp_1067', token: 't' },
  employee: null,
  availablePerspectives: [],
  logout: vi.fn(),
};

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authState,
}));

vi.mock('../hooks/useNotifications', () => ({
  useNotifications: () => ({ unreadCount: 0 }),
}));

vi.mock('../hooks/useInsightStream', () => ({
  useInsightStream: () => ({ unreadCount: 0 }),
}));

vi.mock('../theme/useThemeMode', () => ({
  useThemeMode: () => ({ mode: 'light', toggle: vi.fn() }),
}));

vi.mock('../i18n/useLanguage', () => ({
  useLanguage: () => ({ lang: 'en', setLanguage: vi.fn() }),
}));

vi.mock('../components/notifications/NotificationCenter', () => ({
  NotificationCenter: () => null,
}));

vi.mock('../components/notifications/InsightNotificationPanel', () => ({
  InsightNotificationPanel: () => null,
}));

vi.mock('../config/branding', () => ({
  INSTANCE_LOGO: '',
  PLATFORM_TITLE: 'Carbon',
}));

import HeaderEnhanced from '../components/HeaderEnhanced';

function renderHeader() {
  return render(
    <ThemeProvider theme={createTheme()}>
      <MemoryRouter>
        <HeaderEnhanced />
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('HeaderEnhanced shell identity', () => {
  beforeEach(() => {
    authState.user = { username: 'emp_1067', token: 't' };
    authState.employee = null;
    authState.availablePerspectives = [];
  });

  it('shows username when no employee is linked', () => {
    authState.user = { username: 'ahmed', token: 't' };
    renderHeader();
    expect(screen.getByText('ahmed')).toBeInTheDocument();
    fireEvent.click(screen.getByText('ahmed'));
    expect(screen.getByText('Account')).toBeInTheDocument();
    expect(screen.queryByText('My Profile')).not.toBeInTheDocument();
  });

  it('shows employee name and My Profile when linked', () => {
    authState.employee = {
      id: 1,
      full_name: 'Bilagot Panta Suerte',
      employee_no: '1067',
      job_title: 'Coiled Tubing',
    };
    renderHeader();
    expect(screen.getAllByText('Bilagot Panta Suerte').length).toBeGreaterThan(0);
    expect(screen.getByText('BP')).toBeInTheDocument();
    fireEvent.click(screen.getAllByText('Bilagot Panta Suerte')[0]);
    expect(screen.getByText('My Profile')).toBeInTheDocument();
    expect(screen.getByText('Account')).toBeInTheDocument();
  });
});
