import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import JourneyPage from '../JourneyPage';
import { deriveJourney } from '../../../components/journey/journeyStages';

const hoisted = vi.hoisted(() => ({ value: null }));

vi.mock('../../../components/journey/useJourney', () => ({
  default: () => hoisted.value,
}));
vi.mock('../OnboardingPage', () => ({
  default: () => <div data-testid="readiness-view">O1 readiness checklist</div>,
}));

const lesson = (id, state, extra = {}) => ({
  id,
  track: 'D',
  state,
  title: extra.title || id,
  minutes: 2,
  is_next: false,
  blocker: null,
  route: '/carbon/my-data',
  steps: extra.steps || [],
  completion: 'answer',
  ...extra,
});

const JOURNEY = {
  title: 'Your carbon onboarding journey',
  intro: 'A journey that is always open, with nothing locked.',
  glossary: ['emission factor'],
  stages: [
    { n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.', lessons: ['D1'], competencies: ['one_row'], lead: [], owner: ['D1'], pending: false },
    { n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover or exclude.', lessons: ['D2'], competencies: ['cover_exclude'], lead: [], owner: ['D2'], pending: false },
    { n: 3, key: 'data_entry', title: 'Data entry', what: 'Save rows.', lessons: ['D7'], competencies: ['data_product'], lead: [], owner: ['D7'], pending: false },
    { n: 4, key: 'report', title: 'Report and disclosure', what: 'State the scope.', lessons: ['D5'], competencies: ['quote_scope'], lead: [], owner: ['D5'], pending: false },
  ],
  competencies: [
    { key: 'one_row', title: 'Save one row', good: 'A saved row.', kind: 'host', probe: 'row_created', lesson: 'D1' },
    { key: 'cover_exclude', title: 'Cover or exclude', good: 'A reason.', kind: 'host', probe: 'status_decided', lesson: 'D2' },
    { key: 'data_product', title: 'Use a data product', good: 'Upload, map, validate.', kind: 'answer', probe: '', lesson: 'D7' },
    { key: 'quote_scope', title: 'State the scope', good: 'Say what it sums.', kind: 'answer', probe: '', lesson: 'D5' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  journey: JOURNEY,
  lessons: [
    lesson('D1', 'done', { title: 'What I owe this period' }),
    lesson('D2', 'started', { title: 'Enter one activity row', is_next: true }),
    lesson('D7', 'offered', { title: 'Bring many rows' }),
    lesson('D5', 'offered', { title: 'Locked or rejected' }),
  ],
};

const CLOSED = [
  { id: 15, status: 'closed', name: 'FY 2023-24', start_date: '2023-07-01', end_date: '2024-06-30' },
  { id: 16, status: 'closed', name: 'FY 2025-26', start_date: '2025-07-01', end_date: '2026-06-30' },
];

function renderJourney(entry = '/carbon/onboarding') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <JourneyPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  const model = deriveJourney(LISTING, 'D');
  hoisted.value = {
    phase: 'loaded',
    data: LISTING,
    journey: model,
    period: { status: 'open', period: { id: 17, name: 'Calendar year 2026' }, openCount: 1 },
    closed: CLOSED,
    live: null,
    next: LISTING.lessons.find((row) => row.is_next),
    reload: vi.fn(),
    effectiveTrack: 'D',
  };
});

describe('Journey route', () => {
  it('renders the redesigned Journey at /carbon/onboarding by default', () => {
    renderJourney();
    expect(screen.getByRole('heading', { name: 'Journey' })).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Journey stations' })).toBeInTheDocument();
    expect(screen.getByTestId('journey-intro')).toHaveTextContent(/always open/);
    expect(screen.queryByTestId('readiness-view')).not.toBeInTheDocument();
  });

  it('renders the readiness checklist from ?view=readiness instead of a 404', () => {
    renderJourney('/carbon/onboarding?view=readiness');
    expect(screen.getByTestId('readiness-view')).toBeInTheDocument();
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  });

  it('removes the mentor panel and the four-stat strip', () => {
    renderJourney();
    expect(screen.queryByTestId('journey-mentor')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-honesty')).not.toBeInTheDocument();
  });

  it('keeps closed history read-only and separate from the open period', () => {
    renderJourney();
    fireEvent.click(screen.getByTestId('journey-station-4'));
    const closed = screen.getByTestId('journey-closed-history');
    expect(closed).toHaveTextContent('FY 2023-24');
    expect(closed).toHaveTextContent('FY 2025-26');
    expect(closed).toHaveTextContent(/Not summed into the open period/);
  });

  it('opens the station named by ?station=', () => {
    renderJourney('/carbon/onboarding?station=2');
    expect(screen.getByTestId('journey-station-panel-2')).toBeInTheDocument();
  });

  it('shows the open period and no kilogram figure', () => {
    renderJourney();
    expect(screen.getAllByText(/Calendar year 2026/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/kg co2e|tco2e|tonnes/i);
  });

  it('renders the journey for a wildcard caller with every role\'s lessons', () => {
    // Station 1 splits D1 (owner) and D2 (lead): a wildcard reader sees both.
    const suJourney = {
      ...JOURNEY,
      stages: [
        {
          n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.',
          lessons: ['D1', 'D2'], competencies: ['one_row', 'cover_exclude'],
          lead: ['D2'], owner: ['D1'], pending: false,
        },
        ...JOURNEY.stages.slice(1),
      ],
    };
    const suListing = {
      ...LISTING, all_tracks: true, recommended_track: null, journey: suJourney,
    };
    hoisted.value = {
      ...hoisted.value,
      data: suListing,
      journey: deriveJourney(suListing, 'D'),
    };
    renderJourney('/carbon/onboarding?station=1');
    expect(screen.queryByText('Journey is not open to you')).not.toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Journey stations' })).toBeInTheDocument();
    // Both the owner and the lead lesson of station 1 are shown.
    expect(screen.getByTestId('journey-lesson-D1')).toBeInTheDocument();
    expect(screen.getByTestId('journey-lesson-D2')).toBeInTheDocument();
  });

  it('keeps the honest no-work empty state when the caller has no lessons', () => {
    const emptyListing = { recommended_track: null, journey: JOURNEY, lessons: [] };
    hoisted.value = {
      ...hoisted.value,
      data: emptyListing,
      journey: deriveJourney(emptyListing, 'D'),
    };
    renderJourney();
    expect(screen.getByText('Journey is not open to you')).toBeInTheDocument();
    expect(screen.queryByRole('tablist', { name: 'Journey stations' })).not.toBeInTheDocument();
  });
});

describe('Generic Journey route', () => {
  it('renders /journey/:appId without the carbon readiness view', () => {
    render(
      <MemoryRouter initialEntries={['/journey/carbon']}>
        <JourneyPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Journey' })).toBeInTheDocument();
    expect(screen.queryByTestId('readiness-view')).not.toBeInTheDocument();
  });
});

function renderRouted(entry) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/journey/:appId" element={<JourneyPage />} />
        <Route path="/journey/:appId/:lessonId" element={<JourneyPage />} />
        <Route path="/carbon/onboarding" element={<JourneyPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Lesson reader route', () => {
  it('deep-links /journey/carbon/D2 to the reader and survives a remount (refresh)', () => {
    const first = renderRouted('/journey/carbon/D2');
    expect(screen.getByTestId('lesson-reader')).toBeInTheDocument();
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(screen.getByTestId('lesson-reader-station')).toHaveTextContent('Coverage targets');
    expect(screen.getByTestId('lesson-reader-stepcount')).toHaveTextContent('Step 0 of 0');
    first.unmount();

    renderRouted('/journey/carbon/D2');
    expect(screen.getByTestId('lesson-reader')).toBeInTheDocument();
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
  });

  it('opens the reader from a station lesson row and removes the inline accordion', () => {
    renderRouted('/carbon/onboarding');
    expect(screen.queryByTestId('lesson-accordion')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('journey-lesson-D2'));
    expect(screen.getByTestId('lesson-reader')).toBeInTheDocument();
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
  });

  it('falls back to an honest empty state for a lesson not on the path', () => {
    renderRouted('/journey/carbon/L5');
    expect(screen.getByText('Lesson not found')).toBeInTheDocument();
    expect(screen.queryByTestId('lesson-reader')).not.toBeInTheDocument();
  });
});
