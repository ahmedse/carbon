// Policy desk grid. Evidence is this component test, not a browser session.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { username: 'admin' } }),
}));

const versions = [
  {
    id: 7,
    policy: 'sample-policy',
    version: '2026.2',
    name: 'Sample',
    state: 'in_review',
    citation: 'cited text',
    effective_date: '2026-06-01',
    preparer_id: 2,
    publisher_id: null,
  },
  {
    id: 8,
    policy: 'sample-policy',
    version: '2026.1',
    name: 'Older',
    state: 'authoritative',
    citation: 'cited text',
    effective_date: '2026-01-01',
    preparer_id: 1,
    publisher_id: 3,
  },
];

vi.mock('../api/catalog', () => ({
  fetchPolicyVersions: vi.fn(async () => ({ count: versions.length, results: versions })),
  fetchPolicyVersion: vi.fn(async () => ({
    id: 7,
    policy: 'sample-policy',
    version: '2026.2',
    state: 'in_review',
    citation: 'cited text',
    examples: { passed: true, results: [] },
    floors: { passed: false, results: [] },
    diff: [{ field: 'citation', before: 'old', after: 'cited text' }],
    event: { action: 'submit', before: { lifecycle: 'draft' }, after: { lifecycle: 'in_review' } },
    preparer_id: 2,
    publisher_id: null,
  })),
  publishPolicyVersion: vi.fn(),
  submitPolicyVersion: vi.fn(),
}));

import * as catalogApi from '../api/catalog';
import PolicyDeskPage from '../pages/catalog/PolicyDeskPage';

function renderDesk() {
  return render(
    <MemoryRouter>
      <PolicyDeskPage />
    </MemoryRouter>,
  );
}

describe('policy desk', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    catalogApi.fetchPolicyVersions.mockResolvedValue({ count: versions.length, results: versions });
  });

  it('lists a policy version and does not publish on row click', async () => {
    const user = userEvent.setup();
    renderDesk();
    expect((await screen.findAllByText('sample-policy')).length).toBeGreaterThan(0);
    expect(screen.getByText('2026.2')).toBeInTheDocument();
    expect(screen.getByText('In review')).toBeInTheDocument();
    expect(screen.getByText('Authoritative')).toBeInTheDocument();
    const label = screen.getByText('2026.2');
    await user.click(label);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(label.closest('.MuiDataGrid-row')).toHaveClass('highlighted-row');
  });

  it('opens publish with the diff, the floor, and refuses the same actor', async () => {
    const user = userEvent.setup();
    catalogApi.publishPolicyVersion.mockRejectedValue(new Error('The preparer cannot publish this version.'));
    renderDesk();
    await screen.findAllByText('sample-policy');
    await user.click(screen.getByRole('button', { name: 'Publish' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('citation')).toBeInTheDocument();
    expect(within(dialog).getByText(/Floor:\s*Fail/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Examples:\s*Pass/)).toBeInTheDocument();
    expect(within(dialog).getByText(/submit: draft → in_review/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Publish' }));
    expect(await within(dialog).findByText('The preparer cannot publish this version.')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await waitFor(() => {
      expect(catalogApi.publishPolicyVersion).toHaveBeenCalledWith(7, 'test-token');
    });
  });
});
