import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  fetchInboundTemplateExamples: vi.fn(),
  downloadInboundTemplateExample: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../api/inbound', () => ({
  fetchInboundTemplateExamples: mocks.fetchInboundTemplateExamples,
  downloadInboundTemplateExample: mocks.downloadInboundTemplateExample,
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: mocks.notifyFromError }),
}));

import InboundExampleTemplates from '../components/inbound/InboundExampleTemplates';

describe('InboundExampleTemplates — downloadable example files', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    URL.createObjectURL = vi.fn(() => 'blob:example');
    URL.revokeObjectURL = vi.fn();
  });

  it('lists the shipped example CSVs and downloads one', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundTemplateExamples.mockResolvedValue([
      {
        slug: 'people-employee-snapshot',
        filename: 'people-employee-snapshot.template.csv',
        name: 'people employee snapshot',
        columns: ['employee_no', 'full_name'],
      },
    ]);
    mocks.downloadInboundTemplateExample.mockResolvedValue(new Blob(['employee_no\n']));

    render(<InboundExampleTemplates token="t" />);
    await user.click(screen.getByRole('button', { name: /Example templates/i }));

    expect(
      await screen.findByText('people-employee-snapshot.template.csv · 2 columns'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Download CSV/i }));
    await waitFor(() =>
      expect(mocks.downloadInboundTemplateExample).toHaveBeenCalledWith('t', 'people-employee-snapshot'),
    );
  });

  it('shows the empty state when no example ships', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundTemplateExamples.mockResolvedValue([]);
    render(<InboundExampleTemplates token="t" />);
    await user.click(screen.getByRole('button', { name: /Example templates/i }));
    expect(await screen.findByText('No example templates are available.')).toBeInTheDocument();
  });

  it('shows an error when the index fails', async () => {
    const user = userEvent.setup();
    mocks.fetchInboundTemplateExamples.mockRejectedValue(new Error('nope'));
    render(<InboundExampleTemplates token="t" />);
    await user.click(screen.getByRole('button', { name: /Example templates/i }));
    expect(await screen.findByText('nope')).toBeInTheDocument();
  });
});
