import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const navigateMock = vi.fn();

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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

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
  confidence: 0.8,
  confidence_label: 'high',
  provenance: {
    sources: [
      { label: 'Live reading', detail: 'value=1250.0, metric=variance_amount' },
      { label: 'Recent alerts', detail: '1 related alert(s) in the last day' },
    ],
    basis: 'Based on live readings and recent alerts',
  },
  disposition: 'pending',
  created_at: new Date().toISOString(),
};

beforeEach(() => {
  vi.clearAllMocks();
  navigateMock.mockReset();
  apiFetchStream.mockResolvedValue({ body: stubStream() });
});

describe('InsightNotificationPanel', () => {
  it('renders the empty state when there are no insights', async () => {
    listInsights.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPanel();

    expect(await screen.findByText('No insights yet.')).toBeInTheDocument();
    expect(
      screen.getByText(/reviews your data nightly/i),
    ).toBeInTheDocument();
  });

  it('renders insights with a severity TEXT label (not color-only)', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    expect(await screen.findByText('Emissions threshold exceeded')).toBeInTheDocument();
    // Severity must carry text + icon — assert the TEXT label.
    expect(screen.getByText('Critical')).toBeInTheDocument();
    // Primary recommended action surfaces on the Act chip.
    expect(screen.getByText('Review the latest activity entries')).toBeInTheDocument();
  });

  it('surfaces backend confidence_label (never invents a signal)', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');
    expect(screen.getByRole('meter', { name: /Answer confidence: high/i })).toBeInTheDocument();
  });

  it('opens provenance from real backend sources only', async () => {
    const user = userEvent.setup();
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');
    await user.click(screen.getByRole('button', { name: /What went into this/i }));

    expect(await screen.findByText('Based on live readings and recent alerts')).toBeInTheDocument();
    expect(screen.getByText('Live reading')).toBeInTheDocument();
    expect(screen.getByText(/value=1250\.0/)).toBeInTheDocument();
  });

  it('marks read on row acknowledge without navigating', async () => {
    const user = userEvent.setup();
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    postDisposition.mockResolvedValue({ ...INSIGHT, disposition: 'read' });
    renderPanel();

    const row = await screen.findByRole('button', {
      name: /Emissions threshold exceeded/i,
    });
    await user.click(row);

    await waitFor(() => {
      expect(postDisposition).toHaveBeenCalledWith('test-token', 'insight-1', 'read', '');
    });
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('Act chip posts acted_on and navigates', async () => {
    const user = userEvent.setup();
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    postDisposition.mockResolvedValue({ ...INSIGHT, disposition: 'acted_on' });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');
    await user.click(screen.getByText('Review the latest activity entries'));

    await waitFor(() => {
      expect(postDisposition).toHaveBeenCalledWith('test-token', 'insight-1', 'acted_on', '');
    });
    expect(navigateMock).toHaveBeenCalledWith('/engines');
  });

  it('Dismiss posts dismissed disposition', async () => {
    const user = userEvent.setup();
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    postDisposition.mockResolvedValue({ ...INSIGHT, disposition: 'dismissed' });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');
    await user.click(screen.getByRole('button', { name: /^Dismiss$/i }));

    await waitFor(() => {
      expect(postDisposition).toHaveBeenCalledWith('test-token', 'insight-1', 'dismissed', '');
    });
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('never renders engine jargon (insight_type / trigger_id / instance_id / raw disposition)', async () => {
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [INSIGHT] });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');

    expect(screen.queryByText(/threshold_alert/)).not.toBeInTheDocument();
    expect(screen.queryByText(/trigger-123/)).not.toBeInTheDocument();
    expect(screen.queryByText(/instance-456/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\bpending\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/salience|witness|S2|trigger_id/i)).not.toBeInTheDocument();
  });

  it('does not invent confidence when the backend omits it', async () => {
    const bare = { ...INSIGHT, confidence: undefined, confidence_label: undefined, provenance: null };
    listInsights.mockResolvedValue({ count: 1, next: null, previous: null, results: [bare] });
    renderPanel();

    await screen.findByText('Emissions threshold exceeded');
    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /What went into this/i })).not.toBeInTheDocument();
  });
});
