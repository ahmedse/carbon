// src/__tests__/CapabilitiesPanel.test.jsx
// PEC-R2 — Capabilities registry: loading / empty / success (mock listCapabilities).
//
// CarbonDataGrid only mounts once its container has width > 0, so we stub
// getBoundingClientRect + ResizeObserver (jsdom has neither by default).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CapabilitiesPanel, { kindLabel } from '../pages/admin/ai/CapabilitiesPanel';

const state = vi.hoisted(() => ({ capabilities: ['ai:view_console'] }));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: state.capabilities }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({
    notify: vi.fn(),
    notifyFromError: vi.fn(),
    showFeedback: vi.fn(),
  }),
}));

const listCapabilities = vi.fn();

vi.mock('../api/aiCatalog', () => ({
  listCapabilities: (...a) => listCapabilities(...a),
}));

const ROWS = [
  {
    capability_id: 'dq.rule.validate',
    business_name: 'Validate DQ rule',
    purpose: 'Validate a draft DQ rule before publish',
    kind: 'read_only',
    host_action: 'dq.validate_rule',
    owner: 'dq',
    version: '1.0',
    permissions: { read: ['ai:view_console'] },
    requires_confirmation: false,
  },
  {
    capability_id: 'payroll.run.publish',
    business_name: 'Publish payroll run',
    purpose: 'Publish a reviewed payroll run',
    kind: 'mutation',
    host_action: 'payroll.publish_run',
    owner: 'people',
    version: '2.1',
    permissions: { write: ['ai:manage_console'] },
    requires_confirmation: true,
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
  state.capabilities = ['ai:view_console'];
  listCapabilities.mockResolvedValue(ROWS);
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

describe('kindLabel', () => {
  it('maps kinds to outcome labels', () => {
    expect(kindLabel('read_only')).toBe('Look up');
    expect(kindLabel('mutation')).toBe('Changes data');
    expect(kindLabel('human_task')).toBe('Needs a person');
    expect(kindLabel('assertion')).toBe('Verify');
  });
});

describe('CapabilitiesPanel', () => {
  it('shows loading then the capability list', async () => {
    let resolveList;
    listCapabilities.mockReturnValue(
      new Promise((resolve) => {
        resolveList = resolve;
      }),
    );

    render(<CapabilitiesPanel />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    resolveList(ROWS);
    expect(await screen.findByText('Validate DQ rule')).toBeInTheDocument();
    expect(screen.getByText('Publish payroll run')).toBeInTheDocument();
    expect(listCapabilities).toHaveBeenCalledWith('test-token');
  });

  it('shows empty state when the registry has no rows', async () => {
    listCapabilities.mockResolvedValue([]);
    render(<CapabilitiesPanel />);
    expect(
      await screen.findByText('No capabilities in the registry yet.'),
    ).toBeInTheDocument();
  });

  it('shows offline state when listCapabilities rejects', async () => {
    listCapabilities.mockRejectedValue(new Error('network'));
    render(<CapabilitiesPanel />);
    expect(
      await screen.findByText('Capability registry unavailable'),
    ).toBeInTheDocument();
  });

  it('opens detail drawer with host_action as technical id', async () => {
    render(<CapabilitiesPanel />);
    await screen.findByText('Validate DQ rule');
    fireEvent.click(screen.getByText('Validate DQ rule'));

    expect(await screen.findByTestId('capability-host-action')).toHaveTextContent(
      'dq.validate_rule',
    );
    expect(screen.getByText('No confirmation')).toBeInTheDocument();
  });

  it('gates the panel without ai:view_console', async () => {
    state.capabilities = [];
    render(<CapabilitiesPanel />);
    expect(
      await screen.findByText(/requires ai:view_console/i),
    ).toBeInTheDocument();
    expect(listCapabilities).not.toHaveBeenCalled();
  });

  it('shows success rows after load settles', async () => {
    render(<CapabilitiesPanel />);
    await waitFor(() => {
      expect(screen.getByText('Validate DQ rule')).toBeInTheDocument();
    });
    expect(screen.getByText('Look up')).toBeInTheDocument();
    expect(screen.getByText('Changes data')).toBeInTheDocument();
  });
});
