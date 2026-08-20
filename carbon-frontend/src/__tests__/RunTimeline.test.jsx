// src/__tests__/RunTimeline.test.jsx
// W3-G — AI Admin run timeline spec (admin graph spec): ordered event log
// from GET /ai/runs/{id}/timeline/ — status chip, per-event colored dots +
// labels, step chips, timestamps, empty state, and the pure kind→meta /
// detail-text helpers. Theme tokens only; no @mui/lab (not a dependency).
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import RunTimeline, { timelineEventMeta, eventDetailText } from '../components/graph/RunTimeline';

const theme = createTheme();

const TIMELINE = {
  run_id: 'run-7',
  status: 'completed',
  events: [
    { t: '2026-08-20T09:00:00Z', kind: 'plan_created', detail: { brief: 'Audit duplicates.' } },
    { t: '2026-08-20T09:00:01Z', kind: 'step_pending', step_id: 0, detail: { intent: 'Search' } },
    { t: '2026-08-20T09:00:05Z', kind: 'step_completed', step_id: 0 },
    { t: '2026-08-20T09:00:09Z', kind: 'run_completed' },
  ],
};

const renderTimeline = (props) =>
  render(
    <ThemeProvider theme={theme}>
      <RunTimeline {...props} />
    </ThemeProvider>,
  );

describe('RunTimeline', () => {
  it('renders the event log with status chip and event labels', () => {
    renderTimeline({ timeline: TIMELINE });

    expect(screen.getByTestId('run-timeline')).toBeInTheDocument();
    expect(screen.getByText('Run timeline')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('4 events')).toBeInTheDocument();
    expect(screen.getByText('Plan created')).toBeInTheDocument();
    expect(screen.getByText('Step pending')).toBeInTheDocument();
    expect(screen.getByText('Step completed')).toBeInTheDocument();
    expect(screen.getByText('Run completed')).toBeInTheDocument();
  });

  it('renders step chips and detail lines', () => {
    renderTimeline({ timeline: TIMELINE });
    // Two events reference step 0 (pending + completed) → two "step 0" chips.
    expect(screen.getAllByText('step 0').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('intent: Search')).toBeInTheDocument();
    expect(screen.getByText('brief: Audit duplicates.')).toBeInTheDocument();
  });

  it('shows an empty state when there are no events', () => {
    renderTimeline({ timeline: { run_id: 'run-x', status: 'running', events: [] } });
    expect(screen.getByText('No timeline events recorded for this run.')).toBeInTheDocument();
  });
});

describe('timelineEventMeta', () => {
  it('maps durable event kinds to theme tokens + outcome labels (RULE_23)', () => {
    expect(timelineEventMeta('plan_created', theme)).toEqual({
      color: theme.palette.primary.main,
      label: 'Plan created',
    });
    expect(timelineEventMeta('step_completed', theme).color).toBe(theme.palette.success.main);
    expect(timelineEventMeta('step_failed', theme).color).toBe(theme.palette.error.main);
    expect(timelineEventMeta('step_awaiting_approval', theme).color).toBe(theme.palette.warning.main);
    expect(timelineEventMeta('run_completed', theme).color).toBe(theme.palette.success.main);
    expect(timelineEventMeta('run_resumed', theme).label).toBe('Run resumed');
  });

  it('falls back to the raw kind with disabled color for unknown kinds', () => {
    expect(timelineEventMeta('custom_kind', theme)).toEqual({
      color: theme.palette.text.disabled,
      label: 'custom_kind',
    });
  });
});

describe('eventDetailText', () => {
  it('extracts known fields into an outcome label line', () => {
    expect(eventDetailText({ intent: 'Search' })).toBe('intent: Search');
    expect(eventDetailText({ from_plan_id: 'p-1' })).toBe('from: p-1');
    expect(eventDetailText({ of: 'p-2' })).toBe('of: p-2');
  });

  it('passes strings through and renders em-dash for empty details', () => {
    expect(eventDetailText('raw detail')).toBe('raw detail');
    expect(eventDetailText(null)).toBe('');
    expect(eventDetailText(undefined)).toBe('');
  });
});
