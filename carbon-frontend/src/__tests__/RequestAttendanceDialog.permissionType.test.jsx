// RequestAttendanceDialog — permission_type from governed ReferenceSet.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestAttendanceDialog from '../apps/my/components/RequestAttendanceDialog';

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: (setName) => {
    if (setName === 'permission_type') {
      return {
        options: [
          { value: 'personal', label: 'Personal' },
          { value: 'medical', label: 'Medical' },
        ],
        loading: false,
        error: null,
        refetch: vi.fn(),
      };
    }
    return { options: [], loading: false, error: null, refetch: vi.fn() };
  },
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/my', () => ({
  submitAttendancePermission: vi.fn(),
}));

describe('RequestAttendanceDialog permission_type governed', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists ReferenceSet options in SearchSelect', async () => {
    const user = userEvent.setup();
    render(
      <RequestAttendanceDialog
        open
        onClose={() => {}}
        profile={{ manager: { full_name: 'Boss' } }}
        onSubmitted={() => {}}
      />,
    );

    const field = await screen.findByLabelText(/permission type/i);
    await user.click(field);
    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('Personal')).toBeInTheDocument();
    expect(within(listbox).getByText('Medical')).toBeInTheDocument();
  });
});
