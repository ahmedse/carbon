import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AssuranceRulesPanel from '../excellence/AssuranceRulesPanel';

const snapshot = {
  commit: 'board-test',
  ledger: 'docs/assurance/evidence/nibras-demo-2026-09-23.jsonl',
  blocking_not_passed: 1,
  rows: [
    {
      rule_id: 'NR-PAY-01',
      pack: 'nibras',
      journey: 'Payroll',
      meaning: 'Commit needs a different person',
      label: 'configured',
      reason: 'no evidence event for this rule',
      residual: 'Same actor is refused',
      blocks_release: true,
    },
    {
      rule_id: 'PL-SSE-01',
      pack: 'platform',
      journey: 'Live stream',
      meaning: 'Board has its own stream',
      label: 'configured',
      reason: 'no evidence event for this rule',
      residual: 'The stream does not launch tests',
      blocks_release: false,
    },
  ],
};

vi.mock('../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'staff-token' }),
}));

vi.mock('../../../api/api', () => ({
  apiFetch: vi.fn(async () => snapshot),
  apiFetchStream: vi.fn(async () => ({
    ok: true,
    body: {
      getReader() {
        let sent = false;
        return {
          async read() {
            if (sent) return { done: true, value: undefined };
            sent = true;
            return {
              done: false,
              value: new TextEncoder().encode(`data: ${JSON.stringify(snapshot)}\n\n`),
            };
          },
        };
      },
    },
  })),
}));

describe('AssuranceRulesPanel', () => {
  it('shows ledger rows and the residual for the selected rule', async () => {
    render(<AssuranceRulesPanel embedded />);
    expect(await screen.findByText('NR-PAY-01')).toBeTruthy();
    expect(screen.getByText('PL-SSE-01')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'View NR-PAY-01' }));
    expect(await screen.findByText(/Same actor is refused/)).toBeTruthy();
  });

  it('can hide rules that do not block release', async () => {
    render(<AssuranceRulesPanel embedded />);
    await screen.findByText('PL-SSE-01');
    fireEvent.click(screen.getByLabelText('Blocks release'));
    await waitFor(() => {
      expect(screen.queryByText('PL-SSE-01')).toBeNull();
    });
    expect(screen.getByText('NR-PAY-01')).toBeTruthy();
  });
});
