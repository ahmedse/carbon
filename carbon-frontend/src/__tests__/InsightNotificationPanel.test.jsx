import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/insights', () => ({
  listInsights: vi.fn(),
  postDisposition: vi.fn(),
}));

vi.mock('../api/api', () => ({
  apiFetchStream: vi.fn(),
}));

import { listInsights, postDisposition } from '../api/insights';
import { apiFetchStream } from '../api/api';
import { InsightNotificationPanel } from '../components/notifications/InsightNotificationPanel';

// Stub SSE body: a ReadableStream that closes immediately (no real network).
function stubStream() {
  return new ReadableStream({
    start(controller) {
      controller.close();
    },
  });
}

function renderPanel() {
  const anchorEl = document.createElement('div');
  document.body.appendChild(anchorEl);
  return render(
    <MemoryRouter>
      <InsightNotificationPanel anchorEl={anchorEl} onClose={() => {}} />
    </MemoryRouter>,
  );
}

const INSIGHT = {
  id: 'insight-1',
  title: 'Emissions threshold exceeded',
  narrative: 'Scope 1 emissions are trending above the configured threshold.',
  severity: 'critical',
  insight_type: 'threshold_alert',
  trigger_id: 'trigger-123',
  instance_id: 'instance-456',
  recommended_actions: ['Review the latest activity entries', 'Re-run the calculation job'],
  context: {},
  disposition: 'pending',
  created_at: new Date().toISOString(),
};

beforeEach(() => {
  vi.clearAllMocks();
  apiFetchStream.mockResolvedValue({ body: stubStream() });
});

describe('InsightNotificationPanel', () => {
  it('renders the empty state when there are no insights', async () => {
    listInsights.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPanel();

    expect(await screen.findByText('No insights yet…')).toBeInTheDocument();
  });

  it('renders insights with a severity TEXT label (not color-only)', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    expect(await screen.findByText('Emissions threshold exceeded')).toBeInTheDocument();
    // Severity must carry text + icon — assert the TEXT label.
    expect(screen.getByText('Critical')).toBeInTheDocument();
    // Recommended actions (first 2) surface as plain text.
    expect(screen.getByText('Review the latest activity entries')).toBeInTheDocument();
    expect(screen.getByText('Re-run the calculation job')).toBeInTheDocument();
  });

  it('calls postDisposition when an insight row is clicked', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    postDisposition.mockResolvedValue({ ...INSIGHT, disposition: 'read' });
    renderPanel();

    const row = await screen.findByText('Emissions threshold exceeded');
    row.click();

    await waitFor(() => {
      expect(postDisposition).toHaveBeenCalledWith('test-token', 'insight-1', 'read', '');
    });
  });

  it('never renders engine jargon (insight_type / trigger_id / instance_id / disposition)', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');

    expect(screen.queryByText(/threshold_alert/)).not.toBeInTheDocument();
    expect(screen.queryByText(/trigger-123/)).not.toBeInTheDocument();
    expect(screen.queryByText(/instance-456/)).not.toBeInTheDocument();
    expect(screen.queryByText(/pending/)).not.toBeInTheDocument();
  });
});
