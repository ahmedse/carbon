// TeamRequestDetail — act UX smoke (SystemDialog + comment gate).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const navigateMock = vi.fn();
const notifyMock = vi.fn();
const authState = vi.hoisted(() => ({ id: 7 }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => ({ id: '42' }),
  };
});

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: authState.id } }),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: notifyMock }),
}));

vi.mock('../api/team', () => ({
  fetchCorrespondenceDetail: vi.fn(),
  approveCorrespondence: vi.fn(),
  acknowledgeCorrespondence: vi.fn(),
  reviewCorrespondence: vi.fn(),
  rejectCorrespondence: vi.fn(),
  sendBackCorrespondence: vi.fn(),
}));

import {
  fetchCorrespondenceDetail,
  approveCorrespondence,
  rejectCorrespondence,
} from '../api/team';
import TeamRequestDetail from '../apps/team/TeamRequestDetail';

const baseItem = {
  id: 42,
  reference_no: 'CRS-2026-0099',
  title: 'Annual leave',
  status: 'submitted',
  current_approver_ids: [7],
  current_step: 0,
  approver_chain: [{ order: 1, role: 'manager', intent: 'approve', user_ids: [7] }],
  events: [],
  corr_type_code: 'leave_request',
  requester_name: 'Alice',
};

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockClear();
  notifyMock.mockClear();
  authState.id = 7;
});

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/team/42']}>
      <Routes>
        <Route path="/team/:id" element={<TeamRequestDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TeamRequestDetail act UX', () => {
  it('opens SystemDialog for approve and submits optional comment', async () => {
    const user = userEvent.setup();
    fetchCorrespondenceDetail.mockResolvedValue(baseItem);
    approveCorrespondence.mockResolvedValue({ ...baseItem, status: 'approved' });

    renderDetail();
    expect(await screen.findByRole('button', { name: /^Approve$/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Approve$/i }));
    expect(await screen.findByLabelText(/Comment/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Approve$/i }));
    await waitFor(() => expect(approveCorrespondence).toHaveBeenCalled());
    expect(navigateMock).toHaveBeenCalledWith('/team');
  });

  it('requires comment before reject confirm', async () => {
    const user = userEvent.setup();
    fetchCorrespondenceDetail.mockResolvedValue(baseItem);

    renderDetail();
    await screen.findByRole('button', { name: /^Reject$/i });
    await user.click(screen.getByRole('button', { name: /^Reject$/i }));

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: /^Reject$/i }));
    const field = within(dialog).getByLabelText(/Comment/i);
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(rejectCorrespondence).not.toHaveBeenCalled();
  });

  it('hides decide buttons when the viewer is not the current approver', async () => {
    authState.id = 99;
    fetchCorrespondenceDetail.mockResolvedValue(baseItem);
    renderDetail();
    expect(await screen.findByText(/belongs to the current approver/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Reject$/i })).not.toBeInTheDocument();
  });

  it('hides act buttons when status is terminal', async () => {
    fetchCorrespondenceDetail.mockResolvedValue({
      ...baseItem,
      status: 'approved',
    });
    renderDetail();
    expect(await screen.findByText(/No actions available/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Archive$/i })).not.toBeInTheDocument();
  });
});
