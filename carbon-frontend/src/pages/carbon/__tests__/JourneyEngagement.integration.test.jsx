import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import JourneyPage from '../JourneyPage';
import { deriveJourney } from '../../../components/journey/journeyStages';

const hoisted = vi.hoisted(() => ({ value: null }));

vi.mock('../../../components/journey/useJourney', () => ({
  default: () => hoisted.value,
}));
vi.mock('../OnboardingPage', () => ({
  default: () => <div data-testid="readiness-view" />,
}));

const lesson = (id, state, extra = {}) => ({
  id,
  track: 'D',
  state,
  title: extra.title || id,
  minutes: extra.minutes ?? 2,
  is_next: false,
  blocker: null,
  route: '/carbon/my-data',
  steps: extra.steps || [],
  completion: extra.completion || 'answer',
  ...extra,
});

const JOURNEY = {
  title: 'Your carbon onboarding journey',
  intro: 'A journey that is always open.',
  glossary: ['Campus intake'],
  stages: [
    { n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.', lessons: ['D1'], competencies: ['one_row'], lead: [], owner: ['D1'], pending: false },
    { n: 2, key: 'data_entry', title: 'Data entry', what: 'Enter rows in Campus intake.', lessons: ['D7'], competencies: ['data_product'], lead: [], owner: ['D7'], pending: false },
  ],
  competencies: [
    { key: 'one_row', title: 'Save one row', good: 'A saved row exists.', kind: 'host', probe: 'row_created', lesson: 'D1' },
    { key: 'data_product', title: 'Use a data product', good: 'Upload, map, validate.', kind: 'answer', probe: '', lesson: 'D7' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  journey: JOURNEY,
  lessons: [
    lesson('D1', 'done', { title: 'What I owe this period' }),
    lesson('D7', 'started', { title: 'Bring many rows', is_next: true, route: '/carbon/onboarding/intake' }),
  ],
};

beforeEach(() => {
  hoisted.value = {
    phase: 'loaded',
    data: LISTING,
    journey: deriveJourney(LISTING, 'D'),
    period: { status: 'open', period: { id: 17, name: 'Calendar year 2026' }, openCount: 1 },
    closed: [],
    live: null,
    next: LISTING.lessons.find((row) => row.is_next),
    reload: vi.fn(),
    effectiveTrack: 'D',
  };
});

describe('Journey engagement wired into the page', () => {
  it('renders the scene spine and the honest progress arc together', () => {
    render(
      <MemoryRouter initialEntries={['/carbon/onboarding']}>
        <JourneyPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-arc')).toBeInTheDocument();
    expect(screen.getByTestId('journey-scenario-card')).toBeInTheDocument();
    expect(screen.getByTestId('journey-mission')).toHaveTextContent('Bring many rows');
  });

  it('asks a first-run seat once, then remembers it and stops asking', () => {
    render(
      <MemoryRouter initialEntries={['/carbon/onboarding']}>
        <JourneyPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-role-prompt')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('journey-role-L'));

    // The choice is persisted under its own personalization key.
    expect(localStorage.getItem('carbon-journey-role:anon:carbon')).toBe('L');
    // And the prompt is gone for this session.
    expect(screen.queryByTestId('journey-role-prompt')).not.toBeInTheDocument();
  });
});
