// ComplianceRulesPanel — category/jurisdiction use governed ReferenceSets.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../hooks/useReferenceOptions', () => ({
  useReferenceOptions: (setName) => {
    if (setName === 'compliance_category') {
      return {
        options: [
          { value: 'leave', label: 'Leave' },
          { value: 'gosi', label: 'GOSI' },
        ],
        loading: false,
        error: null,
        refetch: vi.fn(),
      };
    }
    if (setName === 'jurisdiction') {
      return {
        options: [
          { value: 'KW', label: 'Kuwait' },
          { value: 'SA', label: 'Saudi Arabia' },
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

vi.mock('../api/people', () => ({
  fetchComplianceRules: vi.fn(async () => []),
  createComplianceRule: vi.fn(),
  updateComplianceRule: vi.fn(),
  deleteComplianceRule: vi.fn(),
}));

import ComplianceRulesPanel from '../apps/people/ComplianceRulesPanel';

describe('ComplianceRulesPanel governed pickers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('offers SearchSelect options for category and jurisdiction', async () => {
    const user = userEvent.setup();
    render(<ComplianceRulesPanel />);

    const addButtons = await screen.findAllByRole('button', { name: /add rule/i });
    await user.click(addButtons[0]);

    const category = await screen.findByLabelText(/^category|الفئة/i);
    await user.click(category);
    let listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('Leave')).toBeInTheDocument();
    expect(within(listbox).getByText('GOSI')).toBeInTheDocument();
    await user.keyboard('{Escape}');

    const jurisdiction = await screen.findByLabelText(/jurisdiction|الولاية/i);
    await user.click(jurisdiction);
    listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('Kuwait')).toBeInTheDocument();
    expect(within(listbox).getByText('Saudi Arabia')).toBeInTheDocument();
  });
});
