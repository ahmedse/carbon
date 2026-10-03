import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import JourneyTrail from '../JourneyTrail';
import JourneyScenario from '../JourneyScenario';
import StationDetail from '../StationDetail';
import { deriveJourney } from '../journeyStages';

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
  know: extra.know || '',
  dont: extra.dont || '',
  ...extra,
});

// Four camps: one proven, one current, one open, one with no work owed. Every
// state below comes from the engine's lesson states, never from a click.
const LISTING = {
  recommended_track: 'D',
  journey: {
    title: 'Your journey',
    intro: 'A journey that is always open.',
    glossary: ['emission factor'],
    stages: [
      {
        n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.', voice: 'Two open periods means every total has two meanings.', lessons: ['D1'], competencies: ['one_row'], lead: [], owner: ['D1'], pending: false,
      },
      {
        n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover or exclude with a reason.', voice: 'An exclusion is a decision. An omission is a mistake.', lessons: ['D2'], competencies: ['cover_exclude'], lead: [], owner: ['D2'], pending: false,
      },
      {
        n: 3, key: 'lock', title: 'Lock and close', what: 'Name the transition.', voice: 'Open goes to locked.', lessons: ['D3'], competencies: ['legal_transition'], lead: [], owner: ['D3'], pending: false,
      },
      {
        n: 4, key: 'report', title: 'Report and disclosure', what: 'Not wired yet.', voice: 'What does this add up to?', lessons: [], competencies: [], lead: [], owner: [], pending: true,
      },
    ],
    competencies: [
      { key: 'one_row', title: 'Save one row', good: 'A saved row exists.', kind: 'host', probe: 'row_created', lesson: 'D1' },
      { key: 'cover_exclude', title: 'Cover or exclude', good: 'A stated reason.', kind: 'host', probe: 'status_decided', lesson: 'D2' },
      { key: 'legal_transition', title: 'Name the transition', good: 'Open to locked.', kind: 'answer', probe: '', lesson: 'D3' },
    ],
  },
  lessons: [
    lesson('D1', 'done', {
      title: 'What I owe this period',
      know: 'Data Entry lists the data products you own for the open period.',
      dont: 'Do not enter data for a source you do not own.',
    }),
    lesson('D2', 'started', {
      title: 'Enter one activity row',
      is_next: true,
      know: 'A row is one activity, written in the unit the factor expects.',
      dont: 'Do not round or convert to another unit to look tidy.',
    }),
    lesson('D3', 'offered', {
      title: 'Name the next legal transition',
      know: 'A period moves open, locked, submitted, then verified.',
      dont: 'Do not close a period straight from open.',
    }),
  ],
};

const model = deriveJourney(LISTING, 'D');
const stationByN = (n) => model.stages.find((station) => station.n === n);

describe('JourneyTrail — camps on one path', () => {
  const renderTrail = (props = {}) => render(
    <MemoryRouter>
      <JourneyTrail stations={model.stages} selectedN={2} onSelect={() => {}} {...props} />
    </MemoryRouter>,
  );

  it('keeps the tablist contract and draws the trail label', () => {
    renderTrail();
    expect(screen.getByTestId('journey-trail')).toBeInTheDocument();
    expect(screen.getByTestId('journey-rail')).toBeInTheDocument();
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getByTestId('journey-trail')).toHaveTextContent('The trail');
  });

  it('marks each camp by proven state, never a lock', () => {
    renderTrail();
    expect(screen.getByTestId('journey-station-marker-1')).toHaveAttribute('data-marker', 'done');
    expect(screen.getByTestId('journey-station-marker-2')).toHaveAttribute('data-marker', 'current');
    expect(screen.getByTestId('journey-station-marker-3')).toHaveAttribute('data-marker', 'open');
    expect(screen.getByTestId('journey-station-marker-4')).toHaveAttribute('data-marker', 'interlude');
    expect(screen.queryByText(/^locked$/i)).not.toBeInTheDocument();
  });

  it('keeps every camp clickable and walks the path with arrow keys', () => {
    const onSelect = vi.fn();
    renderTrail({ onSelect });
    fireEvent.click(screen.getByTestId('journey-station-4'));
    expect(onSelect).toHaveBeenCalledWith(4);
    screen.getByTestId('journey-station-2').focus();
    fireEvent.keyDown(screen.getByTestId('journey-rail'), { key: 'ArrowRight' });
    expect(onSelect).toHaveBeenCalledWith(3);
  });
});

describe('Camp briefing — the pack voice reaches the page', () => {
  const renderBriefing = (props = {}) => render(
    <MemoryRouter>
      <JourneyScenario
        journey={model}
        station={stationByN(2)}
        role={model.path}
        onOpenLesson={() => {}}
        {...props}
      />
    </MemoryRouter>,
  );

  it('shows the camp voice line beside the scene and mission', () => {
    renderBriefing();
    const card = screen.getByTestId('journey-scenario-card');
    expect(card).toHaveTextContent('Camp 2 of 4');
    expect(within(card).getByTestId('journey-voice'))
      .toHaveTextContent('An exclusion is a decision. An omission is a mistake.');
    expect(within(card).getByTestId('journey-mission')).toHaveTextContent('Enter one activity row');
  });

  it('keeps the compact drawer briefing tight, without the voice paragraph', () => {
    renderBriefing({ compact: true });
    expect(screen.queryByTestId('journey-voice')).not.toBeInTheDocument();
    expect(screen.getByTestId('journey-mission')).toBeInTheDocument();
  });
});

describe('Camp drama — the station panel plays the scene', () => {
  const DRAMA_STATION = {
    ...stationByN(1),
    scenarioBeat: 0,
    scenario: {
      beats: [{
        id: 'keep_one_open',
        cast: 'Carbon Lead',
        line: 'Two doors, one record.',
        question: 'What do you do first?',
        choices: ['Lock the old period.', 'Open one more, to be safe.'],
        explain: 'Exactly one period may be open at a time.',
      }],
    },
  };

  it('plays the pack drama inside the station panel when the surface can write', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={DRAMA_STATION}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
          onScenarioAnswer={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-drama')).toHaveTextContent('Camp 1 drama');
    expect(screen.getByTestId('journey-drama-question')).toHaveTextContent('What do you do first?');
  });

  it('stays out of a read-only surface that cannot write', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={DRAMA_STATION}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('journey-drama')).not.toBeInTheDocument();
  });
});
