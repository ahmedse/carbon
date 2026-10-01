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
  fetchPolicyVersion: vi.fn(async (id) => {
    const authoritative = id === 8;
    return {
      id,
      policy: 'sample-policy',
      version: authoritative ? '2026.1' : '2026.2',
      state: authoritative ? 'authoritative' : 'in_review',
      citation: authoritative
        ? 'Kuwait Labour Law (Private Sector) Law No. 6 of 2010; GOFSCO HRMS Issues (Issues with Hard Task HRMS System.docx, 2026-07-28)'
        : 'cited text',
      examples: { passed: true, results: [{ index: 0, expected: '6.000', actual: '6.000', passed: true }] },
      floors: { passed: authoritative, results: [] },
      diff: authoritative ? [] : [{ field: 'citation', before: 'old', after: 'cited text' }],
      event: authoritative
        ? null
        : { action: 'submit', before: { lifecycle: 'draft' }, after: { lifecycle: 'in_review' } },
      preparer_id: 2,
      publisher_id: authoritative ? 3 : null,
    };
  }),
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

  it('opens an authoritative version from the eye and shows the full citation', async () => {
    const user = userEvent.setup();
    renderDesk();
    await screen.findAllByText('sample-policy');
    const viewButtons = screen.getAllByRole('button', { name: 'View' });
    expect(viewButtons).toHaveLength(2);
    await user.click(viewButtons[1]);
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Authoritative')).toBeInTheDocument();
    expect(within(dialog).getByText(/Issues with Hard Task HRMS System\.docx/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Examples:\s*Pass/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Floor:\s*Pass/)).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
    expect(catalogApi.fetchPolicyVersion).toHaveBeenCalledWith(8, 'test-token');
  });
});
