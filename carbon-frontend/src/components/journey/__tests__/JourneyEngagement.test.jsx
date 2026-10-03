import React from 'react';
import {
  describe, it, expect, vi, beforeEach, afterEach,
} from 'vitest';
import {
  render, screen, fireEvent, renderHook, act, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import JourneyScenario from '../JourneyScenario';
import JourneyCelebration from '../JourneyCelebration';
import JourneyRecall from '../JourneyRecall';
import useJourneyRole, { readJourneyRole } from '../useJourneyRole';
import useJourneyCelebration from '../useJourneyCelebration';
import {
  lessonsMinutes, missionLesson, provenOutcomes, recallLesson, sceneOf,
} from '../journeyVoice';
import { deriveJourney } from '../journeyStages';
import { renderRtl } from '../../../test/renderRtl';

const guideApi = vi.hoisted(() => ({ fetchGuideLesson: vi.fn(), postGuideEvent: vi.fn() }));
vi.mock('../../../api/guide', () => ({
  fetchGuideLesson: (...args) => guideApi.fetchGuideLesson(...args),
  postGuideEvent: (...args) => guideApi.postGuideEvent(...args),
}));

const lesson = (id, state, extra = {}) => ({
  id,
  track: 'D',
  state,
  title: extra.title || id,
  minutes: extra.minutes ?? 2,
  is_next: false,
  blocker: null,
  route: extra.route || '/carbon/my-data',
  steps: extra.steps || [],
  completion: extra.completion || 'answer',
  ...extra,
});

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
    { key: 'cover_exclude', title: 'Cover or exclude', good: 'A stated reason exists.', kind: 'host', probe: 'status_decided', lesson: 'D2' },
    { key: 'data_product', title: 'Use a data product', good: 'Upload, map, validate.', kind: 'answer', probe: '', lesson: 'D7' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  journey: JOURNEY,
  lessons: [
    lesson('D1', 'done', { title: 'What I owe this period' }),
    lesson('D2', 'done', { title: 'Enter one activity row' }),
    lesson('D7', 'started', {
      title: 'Bring many rows',
      is_next: true,
      minutes: 4,
      route: '/carbon/onboarding/intake',
      steps: [{ title: 'Start the import', do: 'Drop one file up to 10 MB.', route: '/carbon/onboarding/intake' }],
    }),
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

beforeEach(() => {
  guideApi.fetchGuideLesson.mockReset();
  guideApi.postGuideEvent.mockReset();
});

afterEach(() => {
  delete window.matchMedia;
});

describe('journeyVoice — everything derives from real state', () => {
  it('positions a station as a scene with the real total', () => {
    expect(sceneOf(model, stationByN(3))).toEqual({ n: 3, total: 4 });
  });

  it('picks the engine next lesson as the station mission, or the first open one', () => {
    expect(missionLesson(stationByN(3)).id).toBe('D7');
    expect(missionLesson(stationByN(4))).toBeNull();
  });

  it('sums only the engine minutes that exist', () => {
    expect(lessonsMinutes(stationByN(3).lessons)).toBe(4);
    expect(lessonsMinutes([])).toBe(0);
  });

  it('returns only proven outcomes for the consequence list', () => {
    expect(provenOutcomes(stationByN(2)).map((row) => row.key)).toEqual(['cover_exclude']);
    expect(provenOutcomes(stationByN(3))).toEqual([]);
  });

  it('maps a review to an earlier finished, choice-graded lesson only', () => {
    // On station 3 the earlier finished answer lessons are D1 then D2.
    expect(recallLesson(model, stationByN(3)).id).toBe('D2');
    // Station 1 has nothing before it, so there is no recall.
    expect(recallLesson(model, stationByN(1))).toBeNull();
  });
});

describe('JourneyScenario — a story, not a screen tour', () => {
  const renderScenario = (props = {}) => render(
    <MemoryRouter>
      <JourneyScenario
        journey={model}
        station={stationByN(3)}
        role={model.path}
        onOpenLesson={() => {}}
        {...props}
      />
    </MemoryRouter>,
  );

  it('frames the current station as a scene with a mission and real minutes', () => {
    renderScenario();
    const card = screen.getByTestId('journey-scenario-card');
    expect(card).toHaveTextContent('Camp 3 of 4');
    expect(screen.getByTestId('journey-mission')).toHaveTextContent('Bring many rows');
    expect(screen.getByTestId('journey-mission')).toHaveTextContent('Drop one file up to 10 MB.');
    expect(screen.getByTestId('journey-mission-minutes')).toHaveTextContent('About 4 min');
  });

  it('starts the lesson reader instead of jumping to a host page', () => {
    const onOpenLesson = vi.fn();
    renderScenario({ onOpenLesson });
    fireEvent.click(screen.getByTestId('journey-mission-open'));
    expect(onOpenLesson).toHaveBeenCalledWith('D7');
  });

  it('never shows a lock word and shows an honest no-mission line', () => {
    render(
      <MemoryRouter>
        <JourneyScenario journey={model} station={stationByN(4)} role={model.path} onOpenLesson={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('journey-no-mission')).toBeInTheDocument();
    expect(screen.queryByText(/^locked$/i)).not.toBeInTheDocument();
  });

  it('compacts for the drawer without the description paragraph', () => {
    renderScenario({ compact: true });
    const card = screen.getByTestId('journey-scenario-card');
    expect(card).toHaveAttribute('data-compact', 'true');
    expect(card).not.toHaveTextContent('Enter rows in Campus intake.');
  });

  it('offers a one-time seat prompt that reports the chosen track', () => {
    const onRoleChange = vi.fn();
    renderScenario({ showRolePrompt: true, onRoleChange });
    expect(screen.getByTestId('journey-role-prompt')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('journey-role-D'));
    expect(onRoleChange).toHaveBeenCalledWith('D');
  });

  it('hides the seat prompt once a seat is stored', () => {
    renderScenario({ showRolePrompt: false });
    expect(screen.queryByTestId('journey-role-prompt')).not.toBeInTheDocument();
  });

  it('renders a mixed-language glossary term as isolated LTR text in RTL', () => {
    renderRtl(
      <MemoryRouter>
        <JourneyScenario journey={model} station={stationByN(3)} role={model.path} onOpenLesson={() => {}} />
      </MemoryRouter>,
    );
    const card = screen.getByTestId('journey-scenario-card');
    const terms = within(card).getAllByText('Campus intake');
    expect(terms.some((node) => node.tagName.toLowerCase() === 'bdi' && node.getAttribute('dir') === 'ltr')).toBe(true);
  });
});

describe('useJourneyRole — personalization persists without touching the view store', () => {
  it('starts empty, stores the chosen seat, and clears on null', () => {
    const { result } = renderHook(() => useJourneyRole('u1', 'carbon'));
    expect(result.current[0]).toBeNull();
    act(() => result.current[1]('D'));
    expect(readJourneyRole('u1', 'carbon')).toBe('D');
    // Its own key, never the shared station/lesson store.
    expect(localStorage.getItem('carbon-journey-view:u1:carbon')).toBeNull();
    act(() => result.current[1](null));
    expect(readJourneyRole('u1', 'carbon')).toBeNull();
  });

  it('ignores an unknown stored track', () => {
    localStorage.setItem('carbon-journey-role:u2:carbon', 'X');
    const { result } = renderHook(() => useJourneyRole('u2', 'carbon'));
    expect(result.current[0]).toBeNull();
  });
});

describe('useJourneyCelebration — a real transition, never a first-visit guess', () => {
  const fresh = deriveJourney({ ...LISTING, lessons: [] }, 'D');
  const oneDone = deriveJourney(
    { ...LISTING, lessons: [lesson('D1', 'done', { title: 'What I owe' })] },
    'D',
  );

  it('records a baseline on the first visit and celebrates nothing', () => {
    const { result } = renderHook(() => useJourneyCelebration(oneDone, 'u', 'carbon'));
    expect(result.current.justDone).toBeNull();
  });

  it('celebrates only the station that turned done since the last visit', () => {
    const { result, rerender } = renderHook(
      ({ journey }) => useJourneyCelebration(journey, 'u', 'carbon'),
      { initialProps: { journey: fresh } },
    );
    expect(result.current.justDone).toBeNull();
    rerender({ journey: oneDone });
    expect(result.current.justDone?.key).toBe('setup');
  });
});

describe('JourneyCelebration — warm, specific, non-blocking', () => {
  const doneModel = deriveJourney(
    { ...LISTING, lessons: [lesson('D1', 'done', { title: 'What I owe' }), lesson('D2', 'done', { title: 'Enter one row' })] },
    'D',
  );

  it('names the station and the outcome the app actually proved', () => {
    sessionStorage.setItem('carbon-journey-seen:u:carbon', JSON.stringify(['setup']));
    render(<JourneyCelebration journey={doneModel} userKey="u" appId="carbon" />);
    const banner = screen.getByTestId('journey-celebration');
    expect(banner).toHaveTextContent('Coverage targets is done');
    expect(banner).toHaveTextContent('The app proved it: Cover or exclude.');
    expect(banner).toHaveAttribute('role', 'status');
  });

  it('dismisses on request and opts out of motion when asked', () => {
    mockReducedMotion(true);
    sessionStorage.setItem('carbon-journey-seen:u:carbon', JSON.stringify(['setup']));
    render(<JourneyCelebration journey={doneModel} userKey="u" appId="carbon" />);
    expect(screen.getByTestId('journey-celebration')).toHaveAttribute('data-motion', 'reduced');
    fireEvent.click(screen.getByTestId('journey-celebration-dismiss'));
    expect(screen.queryByTestId('journey-celebration')).not.toBeInTheDocument();
  });
});

describe('JourneyRecall — a read-only spaced check-in', () => {
  const DETAIL = {
    question: { kind: 'static', options: 3, params: {} },
    copy: {
      question: 'Which page lists the data you own for this period?',
      options: ['Data Entry', 'Chairman Overview', 'Emission Factors'],
      explain: 'Data Entry is scoped to your org units. Chairman shows the whole picture.',
    },
  };

  it('is skipped entirely when no finished choice-graded lesson maps to it', () => {
    render(<JourneyRecall appId="carbon" lesson={null} glossary={[]} />);
    expect(screen.queryByTestId('journey-recall')).not.toBeInTheDocument();
  });

  it('reveals the pack reasoning and never posts an answer', async () => {
    guideApi.fetchGuideLesson.mockResolvedValue(DETAIL);
    render(<JourneyRecall appId="carbon" lesson={{ id: 'D2', title: 'Enter one activity row' }} glossary={[]} />);
    fireEvent.click(screen.getByTestId('journey-recall-start'));
    expect(await screen.findByText('Which page lists the data you own for this period?')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('journey-recall-option-0'));
    fireEvent.click(screen.getByTestId('journey-recall-reveal'));
    expect(screen.getByTestId('journey-recall-reasoning')).toHaveTextContent('Data Entry is scoped to your org units.');
    expect(screen.getByText('Review only — your progress is unchanged.')).toBeInTheDocument();
    expect(guideApi.postGuideEvent).not.toHaveBeenCalled();
    // Read-only: the one call was a lesson GET with the lesson id.
    expect(guideApi.fetchGuideLesson).toHaveBeenCalledWith('carbon', 'D2', expect.any(Object));
  });

  it('stays quiet and honest when the check cannot be loaded', async () => {
    guideApi.fetchGuideLesson.mockRejectedValue(new Error('offline'));
    render(<JourneyRecall appId="carbon" lesson={{ id: 'D2', title: 'Enter one activity row' }} glossary={[]} />);
    fireEvent.click(screen.getByTestId('journey-recall-start'));
    expect(await screen.findByText('Could not load this check.')).toBeInTheDocument();
    expect(guideApi.postGuideEvent).not.toHaveBeenCalled();
  });
});
