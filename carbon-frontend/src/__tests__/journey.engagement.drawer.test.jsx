import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { JourneyTabBody } from '../inspector/tabs/journeyTabs';
import { deriveJourney } from '../components/journey/journeyStages';

const hoisted = vi.hoisted(() => ({ value: null }));

vi.mock('../components/journey/useJourney', () => ({
  default: () => hoisted.value,
}));

const LISTING = {
  recommended_track: 'D',
  journey: {
    title: 'Your journey',
    intro: 'Always open.',
    glossary: ['Campus intake'],
    stages: [
      { n: 1, key: 'data_entry', title: 'Data entry', what: 'Enter rows in Campus intake.', lessons: ['D7'], competencies: ['data_product'], lead: [], owner: ['D7'], pending: false },
    ],
    competencies: [
      { key: 'data_product', title: 'Use a data product', good: 'Upload, map, validate.', kind: 'answer', probe: '', lesson: 'D7' },
    ],
  },
  lessons: [
    {
      id: 'D7',
      track: 'D',
      state: 'started',
      title: 'Bring many rows',
      minutes: 3,
      is_next: true,
      blocker: null,
      route: '/carbon/onboarding/intake',
      steps: [{ title: 'Start the import', do: 'Drop one file.', route: '/carbon/onboarding/intake' }],
      completion: 'answer',
    },
  ],
};

beforeEach(() => {
  hoisted.value = {
    phase: 'loaded',
    journey: deriveJourney(LISTING, 'D'),
    data: LISTING,
    reload: vi.fn(),
  };
});

describe('Journey drawer tab carries the new engagement', () => {
  it('shows the compact scene spine beside the station rail', () => {
    render(
      <MemoryRouter initialEntries={['/journey/carbon']}>
        <JourneyTabBody />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-tab')).toBeInTheDocument();
    const card = screen.getByTestId('journey-scenario-card');
    expect(card).toHaveAttribute('data-compact', 'true');
    expect(screen.getByTestId('journey-rail')).toBeInTheDocument();
    // The mission opens the reader inside the tab, not the main route.
    expect(screen.getByTestId('journey-mission-open')).toHaveTextContent('Start this lesson');
  });
});
