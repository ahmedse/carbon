// src/__tests__/journey.viewPersistence.test.jsx
// Regression suite for the 2 Oct 2026 defect: "preserve the station selected and
// opened lesson". Covers the six reported transitions plus the storage contract:
//   * main Journey page selection persists across reload (it had local-only state),
//   * main page and drawer Journey tab share ONE persisted view and stay in sync,
//   * a STABLE station id (not just the numeric index) drives restore,
//   * stored station/lesson that no longer exists falls back gracefully,
//   * deep links win for the load, then persist,
//   * per user + per app key isolation, and anonymous → resolved-user migration.
import React from 'react';
import {
  describe, it, expect, vi, beforeEach, afterEach,
} from 'vitest';
import {
  render, screen, fireEvent, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { NotesProvider } from '../notes/NotesContext';
import { NotesDrawer } from '../notes/NotesDrawer';
import { JourneyInspectorTabRegistrar, JourneyTabBody } from '../inspector/tabs/journeyTabs';
import { _resetInspectorTabRegistry } from '../inspector/InspectorTabRegistry';
import { JourneyStationSurface, JourneyReaderSurface } from '../pages/carbon/JourneyPage';
import { useDrawerJourneyView } from '../inspector/useDrawerJourneyView';
import { deriveJourney } from '../components/journey/journeyStages';

const hoisted = vi.hoisted(() => ({ journey: null, user: null, mobile: false }));

vi.mock('../components/journey/useJourney', () => ({
  default: () => ({
    phase: 'loaded',
    journey: hoisted.journey,
    reload: vi.fn(),
    period: { status: 'open', period: { name: 'FY 2026' } },
    closed: [],
    effectiveTrack: 'D',
  }),
}));

vi.mock('../hooks/useIsMobile', () => ({
  useIsMobile: () => hoisted.mobile,
  usePulseFullscreen: () => false,
}));

vi.mock('../auth/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useAuth: () => ({ user: hoisted.user, token: 'test-token' }) };
});

vi.mock('../notes/notesApi', () => ({
  fetchNotes: vi.fn(),
  createNote: vi.fn(),
  updateNote: vi.fn(),
  deleteNote: vi.fn(),
  toggleNoteReaction: vi.fn(),
  fetchComments: vi.fn(),
  addComment: vi.fn(),
  updateComment: vi.fn(),
  deleteComment: vi.fn(),
  toggleCommentReaction: vi.fn(),
}));

import * as notesApi from '../notes/notesApi';

const LISTING = {
  all_tracks: true,
  recommended_track: 'D',
  journey: {
    title: 'Your journey',
    intro: '',
    glossary: [],
    stages: [
      { n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the period.', lessons: ['L1'], competencies: [], lead: [], owner: ['L1'], pending: false },
      { n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover sources.', lessons: ['L2'], competencies: [], lead: [], owner: ['L2'], pending: false },
      { n: 4, key: 'data_entry', title: 'Data entry', what: 'Save rows.', lessons: ['D2'], competencies: [], lead: [], owner: ['D2'], pending: false },
    ],
    competencies: [],
  },
  lessons: [
    { id: 'L1', track: 'D', state: 'done', title: 'Lesson one', route: '/carbon/a', steps: [], completion: 'answer', blocker: null, is_next: false },
    { id: 'L2', track: 'D', state: 'done', title: 'Lesson two', route: '/carbon/b', steps: [], completion: 'answer', blocker: null, is_next: false },
    {
      id: 'D2',
      track: 'D',
      state: 'started',
      title: 'Enter one activity row',
      route: '/carbon/my-data',
      steps: [{ title: 'Open My Data', do: 'Open it.', route: '/carbon/my-data' }],
      completion: 'answer',
      blocker: null,
      is_next: true,
    },
  ],
};

const KEY = 'carbon-journey-view:anonymous:carbon';
const stored = (key = KEY) => JSON.parse(localStorage.getItem(key) || '{}');

function seed(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function renderAt(ui, entry = '/journey/carbon') {
  return render(<MemoryRouter initialEntries={[entry]}>{ui}</MemoryRouter>);
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  _resetInspectorTabRegistry();
  hoisted.user = null;
  hoisted.mobile = false;
  hoisted.journey = deriveJourney(LISTING, 'D');
  notesApi.fetchNotes.mockResolvedValue({ count: 0, next: null, results: [] });
  notesApi.fetchComments.mockResolvedValue({ count: 0, next: null, results: [] });
});

afterEach(() => {
  _resetInspectorTabRegistry();
});

describe('stable station id storage shape', () => {
  it('stores the stable station key (with the index) when a station is picked', () => {
    renderAt(<JourneyStationSurface appId="carbon" />);
    fireEvent.click(screen.getByTestId('journey-station-2'));

    expect(stored()).toMatchObject({ stationKey: 'coverage', stationN: 2, lessonId: null });
  });

  it('resolves the stored station by KEY even when the index points elsewhere', () => {
    seed(KEY, { stationKey: 'coverage', stationN: 99 });
    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-2')).toHaveAttribute('aria-selected', 'true');
  });

  it('keeps the SAME station across a pack reorder (key survives, index moves)', () => {
    seed(KEY, { stationKey: 'coverage' });
    // Reorder: coverage is now the last station, with a new index.
    const reordered = {
      ...LISTING,
      journey: {
        ...LISTING.journey,
        stages: [
          { ...LISTING.journey.stages[0], n: 6 },
          { ...LISTING.journey.stages[2], n: 7 },
          { ...LISTING.journey.stages[1], n: 9 },
        ],
      },
    };
    hoisted.journey = deriveJourney(reordered, 'D');
    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-9')).toHaveAttribute('aria-selected', 'true');
  });

  it('falls back to the current stage when the stored station no longer exists', () => {
    seed(KEY, { stationKey: 'ghost', stationN: 99 });
    renderAt(<JourneyStationSurface appId="carbon" />);
    // data_entry is the current stage and still renders — no crash, no blank.
    expect(screen.getByTestId('journey-station-4')).toHaveAttribute('aria-selected', 'true');
  });

  it('reads a legacy numeric-only value (backward compatibility)', () => {
    seed(KEY, { stationN: 2, lessonId: 'L2' });
    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-2')).toHaveAttribute('aria-selected', 'true');
  });
});

describe('main Journey page persistence (reload + deep link)', () => {
  it('restores the picked station after a full remount (browser reload)', () => {
    const first = renderAt(<JourneyStationSurface appId="carbon" />);
    fireEvent.click(screen.getByTestId('journey-station-2'));
    expect(stored().stationKey).toBe('coverage');
    first.unmount();

    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-2')).toHaveAttribute('aria-selected', 'true');
  });

  it('lets a ?station deep link win for the load, then persists it', () => {
    renderAt(<JourneyStationSurface appId="carbon" />, '/journey/carbon?station=1');
    expect(screen.getByTestId('journey-station-1')).toHaveAttribute('aria-selected', 'true');
    expect(stored()).toMatchObject({ stationKey: 'setup', stationN: 1 });
  });
});

describe('main page and drawer share ONE view', () => {
  it('a station picked on the main page updates the drawer surface', () => {
    renderAt(
      <>
        <JourneyStationSurface appId="carbon" />
        <JourneyTabBody />
      </>,
    );
    // Main rail renders first, the drawer rail second.
    fireEvent.click(screen.getAllByTestId('journey-station-1')[0]);

    const rails = screen.getAllByTestId('journey-rail');
    for (const rail of rails) {
      expect(within(rail).getByTestId('journey-station-1')).toHaveAttribute('aria-selected', 'true');
    }
    expect(stored().stationKey).toBe('setup');
  });

  it('a lesson opened in the drawer lands on the station the main page shows', () => {
    const drawer = renderAt(<JourneyTabBody />, '/carbon/dashboard');
    // Open the lesson that belongs to data_entry.
    fireEvent.click(screen.getByTestId('journey-lesson-D2'));
    expect(stored()).toMatchObject({ stationKey: 'data_entry', stationN: 4, lessonId: 'D2' });
    drawer.unmount();

    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-4')).toHaveAttribute('aria-selected', 'true');
  });

  it('selecting a station in the drawer clears the open lesson for the main page too', () => {
    seed(KEY, { stationKey: 'data_entry', stationN: 4, lessonId: 'D2' });
    renderAt(<JourneyTabBody />, '/carbon/dashboard');

    // Back to the station, then pick another one.
    fireEvent.click(screen.getByTestId('lesson-reader-station'));
    expect(stored().lessonId).toBeNull();

    fireEvent.click(screen.getByTestId('journey-station-1'));
    expect(stored()).toMatchObject({ stationKey: 'setup', lessonId: null });
  });
});

describe('deep links and graceful fallback', () => {
  it('persists a deep-linked lesson (route) as the selection', () => {
    renderAt(<JourneyReaderSurface appId="carbon" lessonId="D2" />);
    expect(stored()).toMatchObject({ lessonId: 'D2', stationKey: 'data_entry', stationN: 4 });
  });

  it('ignores a persisted lesson that no longer exists and shows the station', () => {
    seed(KEY, { stationKey: 'setup', stationN: 1, lessonId: 'GONE' });
    renderAt(<JourneyTabBody />, '/carbon/dashboard');
    expect(screen.getByTestId('journey-rail')).toBeInTheDocument();
    expect(screen.queryByTestId('lesson-reader')).not.toBeInTheDocument();
    expect(screen.getByTestId('journey-station-1')).toHaveAttribute('aria-selected', 'true');
  });

  it('still explains a deep link to a lesson that does not exist', () => {
    renderAt(<JourneyTabBody />, '/journey/carbon/GONE');
    expect(screen.getByText(/no longer available|missing|not found/i)).toBeInTheDocument();
  });
});

describe('per user + per app isolation and migration', () => {
  it('keeps each user’s selection separate', () => {
    hoisted.user = { id: 7, username: 'ahmed' };
    const first = renderAt(<JourneyStationSurface appId="carbon" />);
    fireEvent.click(screen.getByTestId('journey-station-2'));
    expect(stored('carbon-journey-view:7:carbon').stationKey).toBe('coverage');
    first.unmount();

    // Different user: the previous selection must not leak in.
    hoisted.user = { id: 8, username: 'sara' };
    renderAt(<JourneyStationSurface appId="carbon" />);
    expect(screen.getByTestId('journey-station-4')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('journey-station-2')).toHaveAttribute('aria-selected', 'false');
  });

  it('migrates an early anonymous selection to the resolved user key', () => {
    seed(KEY, { stationKey: 'coverage', stationN: 2 });
    // The auth user starts unresolved (anonymous) and resolves a frame later,
    // exactly like AuthProvider restores the session after mount.
    const view = renderAt(<JourneyStationSurface appId="carbon" />);
    hoisted.user = { id: 7, username: 'ahmed' };
    view.rerender(
      <MemoryRouter initialEntries={['/journey/carbon']}>
        <JourneyStationSurface appId="carbon" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('journey-station-2')).toHaveAttribute('aria-selected', 'true');
    expect(stored('carbon-journey-view:7:carbon').stationKey).toBe('coverage');
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  it('does not copy a selection across apps', () => {
    hoisted.user = { id: 7, username: 'ahmed' };
    seed('carbon-journey-view:7:carbon', { stationKey: 'coverage', stationN: 2 });
    // Rendering the drawer on a non-carbon route must not migrate carbon view.
    renderAt(<JourneyTabBody />, '/settings');
    expect(localStorage.getItem('carbon-journey-view:7:none')).toBeNull();
  });
});

describe('mobile fullscreen drawer keeps the shared view', () => {
  it('restores station + lesson from the store in the mobile drawer', async () => {
    seed('carbon-journey-view:anonymous:carbon', { stationKey: 'data_entry', stationN: 4, lessonId: 'D2' });
    localStorage.setItem('carbon-notes-open', 'true');
    localStorage.setItem('carbon-notes-tab', 'journey');
    hoisted.mobile = true;

    render(
      <MemoryRouter initialEntries={['/carbon/dashboard']}>
        <NotesProvider>
          <JourneyInspectorTabRegistrar />
          <NotesDrawer mobileFullscreen />
        </NotesProvider>
      </MemoryRouter>,
    );

    const reader = await screen.findByTestId('lesson-reader');
    expect(reader).toHaveAttribute('data-compact', 'true');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
  });
});

describe('RTL render keeps the same behavior', () => {
  it('picks and persists a station inside an RTL document', () => {
    const wrapper = renderAt(
      <div dir="rtl">
        <JourneyStationSurface appId="carbon" />
      </div>,
    );
    fireEvent.click(screen.getByTestId('journey-station-1'));
    expect(stored().stationKey).toBe('setup');
    wrapper.unmount();
    renderAt(
      <div dir="rtl">
        <JourneyStationSurface appId="carbon" />
      </div>,
    );
    expect(screen.getByTestId('journey-station-1')).toHaveAttribute('aria-selected', 'true');
  });
});

describe('shared store hook', () => {
  function Probe({ label }) {
    const [view, update] = useDrawerJourneyView('u1', 'carbon');
    return (
      <button type="button" onClick={() => update({ stationKey: label })} data-testid={`probe-${label}`}>
        {JSON.stringify(view)}
      </button>
    );
  }

  it('notifies every mounted consumer of the same key', () => {
    render(
      <>
        <Probe label="a" />
        <Probe label="b" />
      </>,
    );
    fireEvent.click(screen.getByTestId('probe-a'));
    expect(screen.getByTestId('probe-b')).toHaveTextContent('"stationKey":"a"');
  });
});
