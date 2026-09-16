// src/__tests__/SkillsPanel.test.jsx
// PEC-6B — Skills Catalog promote/reject: list rendering, CBAC gating,
// promote call, and retire dialog with optional reason.
//
// CarbonDataGrid only mounts once its container has width > 0, so we stub
// getBoundingClientRect + ResizeObserver (jsdom has neither by default).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import SkillsPanel, { statusLabel } from '../pages/admin/ai/SkillsPanel';

const state = vi.hoisted(() => ({ capabilities: [] }));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: state.capabilities }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const listSkills = vi.fn();
const promoteSkill = vi.fn();
const rejectSkill = vi.fn();

vi.mock('../api/aiCatalog', () => ({
  listSkills: (...a) => listSkills(...a),
  promoteSkill: (...a) => promoteSkill(...a),
  rejectSkill: (...a) => rejectSkill(...a),
}));

const ROWS = [
  {
    id: 'skill-1',
    name: 'payroll_variance_check',
    kind: 'procedure',
    status: 'draft',
    description: 'Check payroll variance',
    usage_count: 0,
    success_rate: null,
    avg_latency_ms: null,
    signature: {},
    admission: null,
  },
  {
    id: 'skill-2',
    name: 'leave_balance_lookup',
    kind: 'procedure',
    status: 'instance_promoted',
    description: 'Look up leave balance',
    usage_count: 3,
    success_rate: 1,
    avg_latency_ms: 120,
    signature: {},
    admission: {
      verdict: 'admitted',
      structural_passed: true,
      harmlessness_passed: true,
      consistency_passed: true,
      marginal_gain_passed: true,
      admitted_by: 'admin:alice',
      created_at: '2026-09-01T10:00:00Z',
    },
  },
];

class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;

beforeEach(() => {
  vi.clearAllMocks();
  state.capabilities = [];
  listSkills.mockResolvedValue(ROWS);
  promoteSkill.mockResolvedValue({
    decision: 'promote',
    verdict: 'admitted',
    skill: { ...ROWS[0], status: 'instance_promoted' },
  });
  rejectSkill.mockResolvedValue({
    decision: 'reject',
    verdict: 'rejected',
    skill: { ...ROWS[0], status: 'deprecated' },
  });
  global.ResizeObserver = FakeResizeObserver;
  Element.prototype.getBoundingClientRect = () => ({
    width: 960,
    height: 600,
    top: 0,
    left: 0,
    right: 960,
    bottom: 600,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
});

afterEach(() => {
  delete global.ResizeObserver;
  Element.prototype.getBoundingClientRect = originalGetBoundingClientRect;
});

describe('statusLabel', () => {
  it('maps engine statuses to outcome labels', () => {
    expect(statusLabel('instance_promoted')).toBe('Promoted');
    expect(statusLabel('deprecated')).toBe('Retired');
    expect(statusLabel('draft')).toBe('Draft');
  });
});

describe('SkillsPanel', () => {
  it('renders the skill catalog list', async () => {
    render(<SkillsPanel />);
    expect(await screen.findByText('payroll_variance_check')).toBeInTheDocument();
    expect(screen.getByText('leave_balance_lookup')).toBeInTheDocument();
  });

  it('disables Promote without ai:publisher / ai:process_owner', async () => {
    render(<SkillsPanel />);
    await screen.findByText('payroll_variance_check');
    fireEvent.click(screen.getByText('payroll_variance_check'));

    const promote = await screen.findByTestId('skill-promote');
    expect(promote).toBeDisabled();
  });

  it('enables Promote with ai:publisher and calls promoteSkill', async () => {
    state.capabilities = ['ai:publisher'];
    render(<SkillsPanel />);
    await screen.findByText('payroll_variance_check');
    fireEvent.click(screen.getByText('payroll_variance_check'));

    const promote = await screen.findByTestId('skill-promote');
    expect(promote).not.toBeDisabled();
    fireEvent.click(promote);

    await waitFor(() =>
      expect(promoteSkill).toHaveBeenCalledWith('test-token', 'skill-1'),
    );
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success' }),
    );
  });

  it('enables Retire with ai:process_owner and posts reason', async () => {
    state.capabilities = ['ai:process_owner'];
    render(<SkillsPanel />);
    await screen.findByText('payroll_variance_check');
    fireEvent.click(screen.getByText('payroll_variance_check'));

    fireEvent.click(await screen.findByTestId('skill-reject'));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByTestId('skill-reject-reason'), {
      target: { value: 'Not ready for production' },
    });
    fireEvent.click(within(dialog).getByTestId('skill-reject-confirm'));

    await waitFor(() =>
      expect(rejectSkill).toHaveBeenCalledWith(
        'test-token',
        'skill-1',
        'Not ready for production',
      ),
    );
  });

  it('disables Promote for already-promoted skills', async () => {
    state.capabilities = ['ai:publisher'];
    render(<SkillsPanel />);
    await screen.findByText('leave_balance_lookup');
    fireEvent.click(screen.getByText('leave_balance_lookup'));

    const promote = await screen.findByTestId('skill-promote');
    expect(promote).toBeDisabled();
    expect(screen.getByTestId('skill-reject')).not.toBeDisabled();
  });
});
