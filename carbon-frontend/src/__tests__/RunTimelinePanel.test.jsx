// src/__tests__/RunTimelinePanel.test.jsx
// W3-G — AI Admin run timeline panel spec: manual run-id entry → GET
// timeline; RULE_21 consent gates — resume/replay dialogs do NOT call the
// API until the admin confirms; replay stages via the wrapper (confirm:true
// is asserted in aiCatalog.test.js). No run-list API exists, so the id is
// entered manually (recorded assumption in TASK-RESULTS W3-G).
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RunTimelinePanel from '../pages/admin/ai/RunTimelinePanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', userCapabilities: [], isGlobalAdminFlag: false }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError, showFeedback: vi.fn() }),
}));

const getRunTimeline = vi.fn();
const resumeRun = vi.fn();
const replayRun = vi.fn();

vi.mock('../api/aiCatalog', () => ({
  getRunTimeline: (...args) => getRunTimeline(...args),
  resumeRun: (...args) => resumeRun(...args),
  replayRun: (...args) => replayRun(...args),
}));

const TIMELINE = {
  run_id: 'run-7',
  status: 'paused',
  events: [
    { t: '2026-08-20T09:00:00Z', kind: 'plan_created' },
    { t: '2026-08-20T09:00:05Z', kind: 'run_paused' },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  getRunTimeline.mockResolvedValue(TIMELINE);
  resumeRun.mockResolvedValue({ ok: true });
  replayRun.mockResolvedValue({ ok: true });
});

describe('RunTimelinePanel', () => {
  it('loads a timeline by manually entered run id (no run-list API)', async () => {
    render(<RunTimelinePanel />);

    fireEvent.change(screen.getByLabelText('Run / plan id'), { target: { value: 'run-7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load timeline' }));

    await waitFor(() => expect(getRunTimeline).toHaveBeenCalledWith('test-token', 'run-7'));
    expect(await screen.findByText('Run timeline')).toBeInTheDocument();
    expect(screen.getByText('Plan created')).toBeInTheDocument();
    expect(screen.getByText('paused')).toBeInTheDocument();
  });

  it('resume is consent-gated: API is NOT called until the dialog is confirmed', async () => {
    render(<RunTimelinePanel />);

    fireEvent.change(screen.getByLabelText('Run / plan id'), { target: { value: 'run-7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load timeline' }));
    await screen.findByText('Plan created');

    fireEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(screen.getByText('Confirm resume')).toBeInTheDocument();
    // Consent gate: nothing hit the API yet.
    expect(resumeRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Resume run' }));
    await waitFor(() => expect(resumeRun).toHaveBeenCalledWith('test-token', 'run-7'));
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'success' }),
    );
  });

  it('replay is consent-gated and describes the read-only outcome (RULE_23)', async () => {
    render(<RunTimelinePanel />);

    fireEvent.change(screen.getByLabelText('Run / plan id'), { target: { value: 'run-7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load timeline' }));
    await screen.findByText('Plan created');

    fireEvent.click(screen.getByRole('button', { name: 'Replay' }));
    expect(screen.getByText('Confirm replay staging')).toBeInTheDocument();
    expect(
      screen.getByText(/never re-executes/),
    ).toBeInTheDocument();
    expect(replayRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Stage replay' }));
    await waitFor(() => expect(replayRun).toHaveBeenCalledWith('test-token', 'run-7'));
  });

  it('surfaces the offline state for an unknown run id', async () => {
    getRunTimeline.mockRejectedValue(new Error('404'));
    render(<RunTimelinePanel />);

    fireEvent.change(screen.getByLabelText('Run / plan id'), { target: { value: 'nope' } });
    fireEvent.click(screen.getByRole('button', { name: 'Load timeline' }));

    expect(await screen.findByText('Timeline unavailable')).toBeInTheDocument();
  });
});
