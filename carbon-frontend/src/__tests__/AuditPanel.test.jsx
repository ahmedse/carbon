// src/__tests__/AuditPanel.test.jsx — H2-F Audit viewer (filters + CSV export).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock the AI pulse API layer (getAuditTrail is the only export used).
vi.mock('../api/aiPulse', () => ({
  getAuditTrail: vi.fn(),
}));

// Mock AuthContext — useAuth returns a mutable token + capabilities.
let authMock = { token: 't', userCapabilities: ['ai:manage_console'] };
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => authMock,
}));

// Mock the document-title hook to a no-op.
vi.mock('../hooks/useDocumentTitle', () => ({
  default: () => {},
}));

import AuditPanel from '../pages/admin/ai/AuditPanel';
import { getAuditTrail } from '../api/aiPulse';

const ROW = {
  id: 1,
  timestamp: '2026-09-02T18:00:00Z',
  actor: '42',
  action: 'ai.tool_call',
  target: 'create_dq_rule',
  detail: { tool_id: 'x' },
};

beforeEach(() => {
  vi.clearAllMocks();
  authMock = { token: 't', userCapabilities: ['ai:manage_console'] };
  getAuditTrail.mockResolvedValue({ count: 1, page: 1, page_size: 50, results: [ROW] });
  // Browser APIs jsdom does not implement.
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
});

function renderPanel() {
  return render(
    <MemoryRouter>
      <AuditPanel />
    </MemoryRouter>
  );
}

describe('AuditPanel — audit viewer', () => {
  it('renders rows from getAuditTrail', async () => {
    renderPanel();
    expect(await screen.findByText('ai.tool_call')).toBeInTheDocument();
    expect(screen.getByText('create_dq_rule')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows empty state when there are no rows', async () => {
    getAuditTrail.mockResolvedValue({ count: 0, page: 1, page_size: 50, results: [] });
    renderPanel();
    expect(await screen.findByText('No audit entries match the current filters.')).toBeInTheDocument();
  });

  it('shows offline state when getAuditTrail rejects', async () => {
    getAuditTrail.mockRejectedValue(new Error('Network error'));
    renderPanel();
    expect(await screen.findByText('Data unavailable')).toBeInTheDocument();
  });

  it('downloads CSV on export click', async () => {
    renderPanel();
    await screen.findByText('ai.tool_call');
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
  });

  it('toggles the detail JSON view when a row is clicked', async () => {
    renderPanel();
    await screen.findByText('ai.tool_call');

    expect(screen.queryByText(/tool_id/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('create_dq_rule'));
    expect(await screen.findByText(/tool_id/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('create_dq_rule'));
    await waitFor(() => expect(screen.queryByText(/tool_id/)).not.toBeInTheDocument());
  });

  it('passes actor filter to getAuditTrail on Apply', async () => {
    getAuditTrail.mockResolvedValue({ count: 0, page: 1, page_size: 50, results: [] });
    renderPanel();
    await screen.findByText('No audit entries match the current filters.');

    fireEvent.change(screen.getByPlaceholderText('Actor'), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(getAuditTrail).toHaveBeenLastCalledWith('t', expect.objectContaining({ actor: '42' }));
    });
  });

  it('non-admin sees the manage-console message and does not fetch', async () => {
    authMock.userCapabilities = ['ai:view_console'];
    renderPanel();

    expect(
      await screen.findByText(/requires the AI manage console capability/i)
    ).toBeInTheDocument();
    expect(getAuditTrail).not.toHaveBeenCalled();
  });

  it('renders TablePagination with the correct count', async () => {
    getAuditTrail.mockResolvedValue({
      count: 123,
      page: 1,
      page_size: 50,
      results: [ROW],
    });
    renderPanel();
    await screen.findByText('ai.tool_call');
    expect(screen.getByText(/of 123/)).toBeInTheDocument();
  });
});
