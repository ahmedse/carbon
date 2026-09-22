// A17 — Employee EOSI tab smoke (provision + lineage / 409 conflict).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/people', () => ({
  fetchEmployeeEosi: vi.fn(),
}));

import { fetchEmployeeEosi } from '../api/people';
import EmployeeEosiTab from '../apps/people/tabs/EmployeeEosiTab';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('EmployeeEosiTab smoke (A17)', () => {
  it('renders provision amount and lineage', async () => {
    fetchEmployeeEosi.mockResolvedValue({
      value: '900.000',
      as_of: '2026-03-01',
      lineage: {
        rule_id: 'kw-eosi-test',
        rule_version: '2026.1',
        inputs: { basic_salary: '780.000', service_years: '1.997' },
      },
    });

    render(<EmployeeEosiTab entityData={{ empId: 42, id: 42 }} />);

    expect(await screen.findByText(/900/)).toBeInTheDocument();
    expect(screen.getByText(/kw-eosi-test/)).toBeInTheDocument();
    expect(screen.getByText(/2026\.1/)).toBeInTheDocument();
    await waitFor(() => expect(fetchEmployeeEosi).toHaveBeenCalled());
  });

  it('shows warning when no authoritative rule (409)', async () => {
    const err = new Error('No authoritative eosi rule');
    err.status = 409;
    fetchEmployeeEosi.mockRejectedValue(err);

    render(<EmployeeEosiTab entityData={{ empId: 7 }} />);

    expect(await screen.findByText(/No authoritative eosi rule/i)).toBeInTheDocument();
  });
});
