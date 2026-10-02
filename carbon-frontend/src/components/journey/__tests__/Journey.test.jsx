import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import StationRail from '../StationRail';
import StationDetail from '../StationDetail';
import LessonList from '../LessonList';
import LessonReader from '../LessonReader';
import LessonStepTimeline from '../LessonStepTimeline';
import MixedText from '../MixedText';
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
  ...extra,
});

const JOURNEY = {
  title: 'Your journey',
  intro: 'A journey that is always open.',
  glossary: ['emission factor'],
  stages: [
    {
      n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the open period.',
      lessons: ['D1'], competencies: ['one_row'], lead: [], owner: ['D1'], pending: false,
    },
    {
      n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover or exclude with a reason.',
      lessons: ['D2'], competencies: ['cover_exclude'], lead: [], owner: ['D2'], pending: false,
    },
    {
      n: 3, key: 'data_products', title: 'Data products', what: 'Not wired to the app yet.',
      lessons: [], competencies: [], lead: [], owner: [], pending: true,
    },
  ],
  competencies: [
    { key: 'one_row', title: 'Save one row', good: 'A saved row exists.', kind: 'host', probe: 'row_created', lesson: 'D1' },
    { key: 'cover_exclude', title: 'Cover or exclude', good: 'A stated reason.', kind: 'host', probe: 'status_decided', lesson: 'D2' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  journey: JOURNEY,
  lessons: [
    lesson('D1', 'done', { title: 'What I owe this period', steps: [{ title: 'Open My Data', do: 'Open My Data.', route: '/carbon/my-data' }] }),
    lesson('D2', 'started', {
      title: 'Enter one activity row',
      is_next: true,
      steps: [
        { title: 'Open My Data', do: 'Open My Data.', route: '/carbon/my-data' },
        { title: 'Save the row', do: 'Press Save.', route: '/carbon/my-data' },
      ],
    }),
  ],
};

const model = deriveJourney(LISTING, 'D');
const stationByN = (n) => model.stages.find((station) => station.n === n);

describe('StationRail', () => {
  const renderRail = (props = {}) => render(
    <MemoryRouter>
      <StationRail stations={model.stages} selectedN={3} onSelect={() => {}} {...props} />
    </MemoryRouter>,
  );

  it('renders a compact tile per station with a completion count and no gate labels', () => {
    renderRail();
    expect(screen.getAllByRole('tab')).toHaveLength(3);
    const pending = screen.getByTestId('journey-station-3');
    expect(pending).toHaveTextContent('Data products');
    expect(pending).toHaveTextContent('0 of 0 done');
    expect(screen.queryByText(/available/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^locked$/i)).not.toBeInTheDocument();
    // No pack-id pills in the rail.
    expect(within(pending).queryByText('D1')).not.toBeInTheDocument();
  });

  it('keeps every station clickable, including a pending one', () => {
    const onSelect = vi.fn();
    renderRail({ onSelect });
    fireEvent.click(screen.getByTestId('journey-station-3'));
    expect(onSelect).toHaveBeenCalledWith(3);
  });

  it('moves selection with the arrow keys from a focused tab', () => {
    const onSelect = vi.fn();
    renderRail({ onSelect });
    screen.getByTestId('journey-station-1').focus();
    fireEvent.keyDown(screen.getByTestId('journey-rail'), { key: 'ArrowRight' });
    expect(onSelect).toHaveBeenCalledWith(2);
  });
});

describe('StationDetail', () => {
  it('shows plain outcomes with what good looks like and a real-page action', () => {
    const onNavigate = vi.fn();
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(2)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={onNavigate}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText('Coverage targets')).toBeInTheDocument();
    expect(screen.getByText(/Cover or exclude with a reason/)).toBeInTheDocument();
    expect(screen.getByText('What good looks like:')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Go there' }));
    expect(onNavigate).toHaveBeenCalledWith('/carbon/my-data');
  });

  it('lists lessons as rows that open the reader, with no inline body', () => {
    const onOpenLesson = vi.fn();
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(2)}
          glossary={model.glossary}
          onOpenLesson={onOpenLesson}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    const row = screen.getByTestId('journey-lesson-D2');
    expect(row).toHaveTextContent('Enter one activity row');
    expect(row).toHaveTextContent('Steps: 2');
    expect(within(row).getByText('Cover or exclude')).toBeInTheDocument();
    expect(screen.queryByTestId('lesson-accordion')).not.toBeInTheDocument();
    expect(screen.queryByTestId('lesson-steps')).not.toBeInTheDocument();
    fireEvent.click(row);
    expect(onOpenLesson).toHaveBeenCalledWith('D2');
  });

  it('does not render a mentor panel or a stat strip', () => {
    render(
      <MemoryRouter>
        <StationDetail
          station={stationByN(1)}
          glossary={model.glossary}
          onOpenLesson={() => {}}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('journey-mentor')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-summary')).not.toBeInTheDocument();
  });
});

describe('LessonList', () => {
  it('shows title, step count, done indicator and one-line outcome', () => {
    const onOpen = vi.fn();
    render(
      <LessonList
        lessons={[LISTING.lessons[1]]}
        glossary={[]}
        outcomeByLesson={{ D2: 'Save one row' }}
        onOpen={onOpen}
      />,
    );
    const row = screen.getByTestId('journey-lesson-D2');
    expect(row).toHaveTextContent('Enter one activity row');
    expect(row).toHaveTextContent('Steps: 2');
    expect(row).toHaveTextContent('Save one row');
    expect(row).toHaveAttribute('data-state', 'started');
    fireEvent.click(row);
    expect(onOpen).toHaveBeenCalledWith('D2');
  });

  it('marks a done lesson without expanding any lesson body', () => {
    render(
      <LessonList lessons={[LISTING.lessons[0]]} glossary={[]} outcomeByLesson={{}} onOpen={() => {}} />,
    );
    const row = screen.getByTestId('journey-lesson-D1');
    expect(row).toHaveTextContent('Done');
    expect(row).toHaveAttribute('data-state', 'done');
    expect(screen.queryByTestId('lesson-steps')).not.toBeInTheDocument();
  });
});

describe('LessonReader', () => {
  const STATION = { n: 2, title: 'Coverage targets' };
  const renderReader = (props = {}) => render(
    <MemoryRouter>
      <LessonReader
        station={STATION}
        lesson={LISTING.lessons[1]}
        glossary={[]}
        onGo={() => {}}
        onBackToStation={() => {}}
        prevLesson={LISTING.lessons[0]}
        nextLesson={{ id: 'D7', title: 'Bring many rows' }}
        onNavigateLesson={() => {}}
        onStationSummary={() => {}}
        {...props}
      />
    </MemoryRouter>,
  );

  it('shows the station, lesson title, step k of n and Prev/Next, reusing the step timeline', () => {
    renderReader();
    expect(screen.getByTestId('lesson-reader-station')).toHaveTextContent('Coverage targets');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(screen.getByTestId('lesson-reader-stepcount')).toHaveTextContent('Step 1 of 2');
    expect(screen.getByTestId('lesson-reader-prev')).toBeEnabled();
    expect(screen.getByTestId('lesson-reader-next')).toHaveTextContent('Next lesson');
    // The reader body is the shared LessonStepTimeline, not a second timeline.
    expect(screen.getByTestId('lesson-steps')).toBeInTheDocument();
  });

  it('goes to the neighbouring lesson, and to the station summary at the last lesson', () => {
    const onNavigateLesson = vi.fn();
    const onStationSummary = vi.fn();
    const onBackToStation = vi.fn();
    const { rerender } = renderReader({ onNavigateLesson, onStationSummary, onBackToStation, prevLesson: null });
    expect(screen.getByTestId('lesson-reader-prev')).toBeDisabled();
    fireEvent.click(screen.getByTestId('lesson-reader-station'));
    expect(onBackToStation).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('lesson-reader-next'));
    expect(onNavigateLesson).toHaveBeenCalledWith('D7');

    rerender(
      <MemoryRouter>
        <LessonReader
          station={STATION}
          lesson={LISTING.lessons[1]}
          glossary={[]}
          onGo={() => {}}
          onBackToStation={onBackToStation}
          prevLesson={LISTING.lessons[0]}
          nextLesson={null}
          onNavigateLesson={onNavigateLesson}
          onStationSummary={onStationSummary}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('lesson-reader-next')).toHaveTextContent('Station summary');
    fireEvent.click(screen.getByTestId('lesson-reader-next'));
    expect(onStationSummary).toHaveBeenCalled();
  });

  it('moves the active step when a node marker is chosen', () => {
    renderReader();
    expect(screen.getByTestId('lesson-reader-stepcount')).toHaveTextContent('Step 1 of 2');
    fireEvent.click(screen.getByTestId('lesson-step-focus-1'));
    expect(screen.getByTestId('lesson-reader-stepcount')).toHaveTextContent('Step 2 of 2');
    expect(screen.getByTestId('lesson-step-1')).toHaveAttribute('data-active', 'true');
  });
});

describe('LessonStepTimeline', () => {
  it('renders one node per step with an imperative line and a real-page button', () => {
    const onGo = vi.fn();
    render(<LessonStepTimeline steps={LISTING.lessons[1].steps} glossary={[]} onGo={onGo} />);
    expect(screen.getAllByTestId(/lesson-step-/)).toHaveLength(2);
    expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Press Save.')).toBeInTheDocument();
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toHaveTextContent('Go to My data');
    fireEvent.click(buttons[0]);
    expect(onGo).toHaveBeenCalledWith('/carbon/my-data');
  });
});

describe('MixedText', () => {
  it('isolates an allowlisted English term with bdi dir=ltr in an RTL sentence', () => {
    render(<MixedText text="اضبط emission factor للنطاق نفسه." glossary={['emission factor']} />);
    const term = screen.getByText('emission factor');
    expect(term.tagName.toLowerCase()).toBe('bdi');
    expect(term).toHaveAttribute('dir', 'ltr');
  });

  it('leaves a sentence with no allowlisted term untouched', () => {
    render(<MixedText text="نص عربي فقط." glossary={['emission factor']} />);
    expect(screen.getByText('نص عربي فقط.')).toBeInTheDocument();
  });
});
