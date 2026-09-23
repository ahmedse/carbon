import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../api/api', () => ({
  apiFetch: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { apiFetch } from '../api/api';
import {
  fetchEmployeeBenefits,
  fetchLoans,
  fetchCertifications,
  fetchLeaveEntitlements,
} from '../api/people';

beforeEach(() => {
  vi.clearAllMocks();
  apiFetch.mockResolvedValue({ count: 0, results: [] });
});

describe('Employee 360 list helpers', () => {
  it('pass an employee query so 360 does not walk the full roster', async () => {
    await fetchEmployeeBenefits('tok', { employee: 42 });
    await fetchLoans('tok', { employee: 42 });
    await fetchCertifications('tok', { employee: 42 });
    expect(apiFetch.mock.calls[0][0]).toContain('employee=42');
    expect(apiFetch.mock.calls[1][0]).toContain('loans/?employee=42');
    expect(apiFetch.mock.calls[2][0]).toContain('certifications/?employee=42');
  });

  it('leave entitlements keep the employee filter on every page', async () => {
    await fetchLeaveEntitlements('tok', { employee: 42, year: 2026 });
    expect(apiFetch).toHaveBeenCalled();
    const url = String(apiFetch.mock.calls[0][0]);
    expect(url).toContain('employee=42');
    expect(url).toContain('year=2026');
  });
});
