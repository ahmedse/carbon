// My New Request — loan_type uses governed SearchSelect (NSR-7 residual).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NewRequestDialog from '../apps/my/components/NewRequestDialog';

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: (setName) => {
    if (setName === 'loan_type') {
      return {
        options: [
          { value: 'housing', label: 'Housing' },
          { value: 'personal', label: 'Personal' },
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
  submitLeaveRequest: vi.fn(),
  submitLoanRequest: vi.fn(),
  submitProfileChange: vi.fn(),
  submitGenericCorrespondence: vi.fn(),
}));

vi.mock('../api/orgUnits', () => ({
  fetchOrgUnits: vi.fn(async () => []),
}));

describe('NewRequestDialog loan_type governed', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('offers SearchSelect options from loan_type ReferenceSet', async () => {
    const user = userEvent.setup();
    render(
      <NewRequestDialog open onClose={() => {}} profile={{ id: 1, org_unit: { id: 1 } }} />,
    );

    const typeSelect = screen.getByLabelText(/request type|نوع الطلب/i);
    await user.click(typeSelect);
    const loanOption = await screen.findByRole('option', { name: /loan|قرض/i });
    await user.click(loanOption);

    const loanType = await screen.findByLabelText(/loan type|نوع القرض/i);
    await user.click(loanType);
    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('Housing')).toBeInTheDocument();
    expect(within(listbox).getByText('Personal')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/e\.g\. Personal/i)).not.toBeInTheDocument();
  });
});
