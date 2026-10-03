import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import StationCard from '../StationCard';
import StationDetail from '../StationDetail';
import JourneyArc from '../JourneyArc';
import LessonStepTimeline from '../LessonStepTimeline';
import {
  deriveJourney, routeLabel,
} from '../journeyStages';
import {
  momentum, nextLesson, overallProgress, stationForLesson, stationProgress,
} from '../journeyProgress';
import { renderRtl } from '../../../test/renderRtl';

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

// Two stations closed, one started, one pending. Every number below is derived
// from these lesson states — nothing is clicked to done.
const JOURNEY = {
  title: 'Your journey',
  intro: 'A journey that is always open.',
  glossary: ['Campus intake'],
  stages: [
    {
      n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.',
      lessons: ['D1'], competencies: ['one_row'], lead: [], owner: ['D1'], pending: false,
    },
    {
      n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover or exclude.',
      lessons: ['D2'], competencies: ['cover_exclude'], lead: [], owner: ['D2'], pending: false,
    },
    {
      n: 3, key: 'data_entry', title: 'Data entry', what: 'Enter rows in Campus intake.',
      lessons: ['D7'], competencies: ['data_product'], lead: [], owner: ['D7'], pending: false,
    },
    {
      n: 4, key: 'report', title: 'Report and disclosure', what: 'Not wired yet.',
      lessons: [], competencies: [], lead: [], owner: [], pending: true,
    },
  ],
  competencies: [
    { key: 'one_row', title: 'Save one row', good: 'A saved row exists.', kind: 'host', probe: 'row_created', lesson: 'D1' },
    { key: 'cover_exclude', title: 'Cover or exclude', good: 'A stated reason.', kind: 'host', probe: 'status_decided', lesson: 'D2' },
    { key: 'data_product', title: 'Enter the rows', good: 'A real row exists.', kind: 'answer', probe: '', lesson: 'D7' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  journey: JOURNEY,
  lessons: [
    lesson('D1', 'done', {
      title: 'What I owe this period',
      steps: [{ title: 'Enter rows in Campus intake', do: 'Add a real reading.', route: '/carbon/onboarding/intake' }],
    }),
    lesson('D2', 'done', { title: 'Enter one activity row' }),
    lesson('D7', 'started', { title: 'Bring many rows', is_next: true, route: '/carbon/onboarding/intake' }),
  ],
};

const model = deriveJourney(LISTING, 'D');
const stationByN = (n) => model.stages.find((station) => station.n === n);

function mockReducedMotion(matches) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: query.includes('prefers-reduced-motion') ? matches : false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  delete window.matchMedia;
});

describe('journeyProgress (honest momentum)', () => {
  it('counts only completed stations and proven outcomes', () => {
    const progress = overallProgress(model);
    expect(progress.done).toBe(2);
    expect(progress.total).toBe(4);
    expect(progress.pct).toBe(50);
    expect(progress.outcomesProven).toBe(2);
    expect(progress.outcomesTotal).toBe(3);
    expect(progress.started).toBe(true);
    expect(progress.complete).toBe(false);
  });

  it('measures a streak of consecutive complete stations, never points', () => {
    expect(momentum(model)).toBe(2);
    const fresh = deriveJourney({ ...LISTING, lessons: [] }, 'D');
    expect(momentum(fresh)).toBe(0);
  });

  it('reports a station with no work as 0 of 0, not a fabricated figure', () => {
    expect(stationProgress(stationByN(4))).toEqual({ done: 0, total: 0, pct: 0 });
  });

  it('finds the engine next lesson and its owning station', () => {
    const next = nextLesson(LISTING);
    expect(next.id).toBe('D7');
    expect(stationForLesson(model, 'D7').n).toBe(3);
  });
});

describe('StationCard sense of place', () => {
  const renderCard = (n) => render(
    <MemoryRouter>
      <StationCard station={stationByN(n)} active={n === 3} onSelect={() => {}} />
    </MemoryRouter>,
  );

  it('renders a numbered pip, a check only when done, and no lock', () => {
    render(
      <MemoryRouter>
        <StationCard station={stationByN(1)} active={false} onSelect={() => {}} />
        <StationCard station={stationByN(3)} active onSelect={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-station-done-1')).toBeInTheDocument();
    expect(screen.queryByTestId('journey-station-done-3')).not.toBeInTheDocument();
    // A done camp is a filled check; an open one keeps its number.
    expect(screen.getByTestId('journey-station-marker-1')).toHaveAttribute('data-marker', 'done');
    expect(screen.getByTestId('journey-station-marker-3')).toHaveAttribute('data-marker', 'current');
    expect(screen.getByTestId('journey-station-3')).toHaveTextContent('Data entry');
    expect(screen.queryByText(/^locked$/i)).not.toBeInTheDocument();
  });

  it('marks the current station "Here" without a lock icon', () => {
    renderCard(3);
    expect(screen.getByTestId('journey-station-here-3')).toBeInTheDocument();
    expect(screen.getByTestId('journey-station-3')).toHaveAttribute('aria-current', 'step');
  });

  it('opts out of motion when the OS prefers reduced motion', () => {
    mockReducedMotion(true);
    renderCard(3);
    expect(screen.getByTestId('journey-station-3')).toHaveAttribute('data-motion', 'reduced');
  });

  it('animates when motion is allowed', () => {
    mockReducedMotion(false);
    renderCard(3);
    expect(screen.getByTestId('journey-station-3')).toHaveAttribute('data-motion', 'full');
  });
});

describe('StationDetail completion summary', () => {
  it('closes the loop in plain language only for a station proven done', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(2)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    const summary = screen.getByTestId('journey-station-done');
    expect(summary).toHaveTextContent('You closed the loop on');
    expect(summary).toHaveTextContent('1 of 1 outcomes proven by the app');
  });

  it('renders no completion summary for a station that is still open', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(3)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('journey-station-done')).not.toBeInTheDocument();
  });

  it('shows a mastery badge only on a proven outcome, never on a pending one', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(2)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-mastery-cover_exclude')).toHaveTextContent('Mastered');

    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(3)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('journey-mastery-data_product')).not.toBeInTheDocument();
    expect(screen.getByTestId('journey-outcome-data_product')).toHaveAttribute('data-status', 'inProgress');
  });
});

describe('JourneyArc momentum panel', () => {
  it('shows the honest arc, the streak and the one next action to the real page', () => {
    const onGo = vi.fn();
    render(
      <MemoryRouter>
        <JourneyArc journey={model} listing={LISTING} role={model.path} onGo={onGo} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-arc-count')).toHaveTextContent('2 of 4 stations complete');
    expect(screen.getByTestId('journey-arc-outcomes')).toHaveTextContent('2 of 3 outcomes proven');
    expect(screen.getByTestId('journey-streak')).toHaveTextContent('2 stations done in a row');
    expect(screen.getByTestId('journey-here')).toHaveTextContent('Data entry');
    fireEvent.click(screen.getByRole('button', { name: /Go to Campus intake/ }));
    expect(onGo).toHaveBeenCalledWith('/carbon/onboarding/intake');
  });

  it('frames a fresh journey in one sentence and names the role scenario', () => {
    const fresh = deriveJourney({ ...LISTING, lessons: [] }, 'D');
    render(
      <MemoryRouter>
        <JourneyArc journey={fresh} listing={{ ...LISTING, lessons: [] }} role="owner" onGo={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-start')).toBeInTheDocument();
    expect(screen.getByTestId('journey-scenario')).toHaveTextContent('enter this period\'s activity rows');
    expect(screen.queryByTestId('journey-streak')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-next')).not.toBeInTheDocument();
  });
});

describe('Campus intake is named and reachable', () => {
  it('labels the intake route and sends the step button to the intake page', () => {
    expect(routeLabel('/carbon/onboarding/intake')).toBe('Campus intake');
    const onGo = vi.fn();
    render(
      <MemoryRouter>
        <LessonStepTimeline
          steps={[{ title: 'Enter rows', do: 'Add a real reading.', route: '/carbon/onboarding/intake' }]}
          glossary={model.glossary}
          onGo={onGo}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Go to Campus intake' }));
    expect(onGo).toHaveBeenCalledWith('/carbon/onboarding/intake');
  });
});

describe('Journey momentum renders in RTL', () => {
  it('renders the arc with an Arabic theme direction', () => {
    renderRtl(
      <MemoryRouter>
        <JourneyArc journey={model} listing={LISTING} role={model.path} onGo={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-arc')).toBeInTheDocument();
  });
});
