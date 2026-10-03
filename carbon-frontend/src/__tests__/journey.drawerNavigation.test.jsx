// src/__tests__/journey.drawerNavigation.test.jsx
// Defect 2 + 3 regressions for the Journey drawer tab:
//   * interaction inside the tab stays in the tab (main route/pathname unchanged),
//   * the labelled "Go to <page>" step button is the one deliberate main-area
//     navigation,
//   * the tab's station/lesson/scroll view state persists per user + app across
//     navigation and reload, and survives the mobile fullscreen drawer.
import React from 'react';
import {
  describe, it, expect, vi, beforeEach, afterEach,
} from 'vitest';
import {
  render, screen, fireEvent, within,
} from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';

import { NotesProvider } from '../notes/NotesContext';
import { NotesDrawer } from '../notes/NotesDrawer';
import { JourneyInspectorTabRegistrar } from '../inspector/tabs/journeyTabs';
import { _resetInspectorTabRegistry } from '../inspector/InspectorTabRegistry';
import { deriveJourney } from '../components/journey/journeyStages';

const hoisted = vi.hoisted(() => ({ journey: null, mobile: false }));

vi.mock('../components/journey/useJourney', () => ({
  default: () => ({ phase: 'loaded', journey: hoisted.journey, reload: vi.fn() }),
}));

vi.mock('../hooks/useIsMobile', () => ({
  useIsMobile: () => hoisted.mobile,
  usePulseFullscreen: () => false,
}));

// The reader now fetches the lesson detail (briefing / hazard / check); this
// suite stays on the waypoint reader, so resolve nothing.
const guideApi = vi.hoisted(() => ({ fetchGuide: vi.fn(), fetchGuideLesson: vi.fn(), postGuideEvent: vi.fn() }));
vi.mock('../api/guide', () => ({
  fetchGuide: (...args) => guideApi.fetchGuide(...args),
  fetchGuideLesson: (...args) => guideApi.fetchGuideLesson(...args),
  postGuideEvent: (...args) => guideApi.postGuideEvent(...args),
}));

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
  recommended_track: 'D',
  journey: {
    title: 'Your journey',
    intro: 'A journey that is always open.',
    glossary: [],
    stages: [
      { n: 4, key: 'data_entry', title: 'Data entry', what: 'Save rows.', lessons: ['D1', 'D2', 'D7'], competencies: ['one_row', 'data_product'], lead: [], owner: ['D1', 'D2', 'D7'], pending: false },
    ],
    competencies: [
      { key: 'one_row', title: 'Save one row', good: 'A row.', kind: 'host', probe: 'row_created', lesson: 'D2' },
      { key: 'data_product', title: 'Use a data product', good: 'Upload.', kind: 'answer', probe: '', lesson: 'D7' },
    ],
  },
  lessons: [
    { id: 'D1', track: 'D', state: 'done', title: 'What I owe', route: '/carbon/my-data', steps: [{ title: 'Open My Data', do: 'Open it.', route: '/carbon/my-data' }], completion: 'answer', blocker: null, is_next: false },
    {
      id: 'D2',
      track: 'D',
      state: 'started',
      title: 'Enter one activity row',
      route: '/carbon/my-data',
      steps: [
        { title: 'Open My Data', do: 'Open it.', route: '/carbon/my-data' },
        { title: 'Save the row', do: 'Press Save.', route: '/carbon/my-data' },
      ],
      completion: 'answer',
      blocker: null,
      is_next: true,
    },
    { id: 'D7', track: 'D', state: 'offered', title: 'Bring many rows', route: '/carbon/my-data', steps: [], completion: 'answer', blocker: null, is_next: false },
  ],
};

function LocationProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <span data-testid="location">{location.pathname}</span>
      <button type="button" onClick={() => navigate('/carbon/console')}>go-console</button>
      <button type="button" onClick={() => navigate('/settings')}>go-settings</button>
      <button type="button" onClick={() => navigate('/carbon/dashboard')}>go-dashboard</button>
    </div>
  );
}

function renderApp(entry = '/carbon/dashboard', { mobileFullscreen = false } = {}) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <NotesProvider>
        <LocationProbe />
        <JourneyInspectorTabRegistrar />
        <NotesDrawer mobileFullscreen={mobileFullscreen} />
      </NotesProvider>
    </MemoryRouter>,
  );
}

function openDrawer() {
  fireEvent.click(screen.getByRole('button', { name: /^notes$/i }));
}

async function openJourneyTab() {
  openDrawer();
  fireEvent.click(await screen.findByRole('tab', { name: /^journey$/i }));
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  _resetInspectorTabRegistry();
  hoisted.mobile = false;
  hoisted.journey = deriveJourney(LISTING, 'D');
  notesApi.fetchNotes.mockResolvedValue({ count: 0, next: null, results: [] });
  notesApi.fetchComments.mockResolvedValue({ count: 0, next: null, results: [] });
  guideApi.fetchGuideLesson.mockResolvedValue(null);
  guideApi.postGuideEvent.mockResolvedValue({});
});

afterEach(() => {
  _resetInspectorTabRegistry();
});

describe('Defect 2 — interaction inside the Journey tab stays inside the tab', () => {
  it('opens the lesson reader in the drawer on a row click without touching the main route', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();

    expect(await screen.findByTestId('journey-rail')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('journey-lesson-D2'));

    expect(await screen.findByTestId('lesson-reader')).toHaveAttribute('data-compact', 'true');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    // The page the user was working on is still the main route.
    expect(screen.getByTestId('location')).toHaveTextContent('/carbon/dashboard');
  });

  it('walks Prev/Next inside the drawer without changing the main route', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();
    fireEvent.click(await screen.findByTestId('journey-lesson-D2'));

    fireEvent.click(await screen.findByTestId('lesson-reader-next'));
    expect(await screen.findByText('Bring many rows')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/carbon/dashboard');
  });

  it('navigates the main area ONLY from the labelled "Go to <page>" step button', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();
    fireEvent.click(await screen.findByTestId('journey-lesson-D2'));
    await screen.findByTestId('lesson-reader');

    fireEvent.click(screen.getAllByRole('button', { name: /go to my data/i })[0]);
    expect(screen.getByTestId('location')).toHaveTextContent('/carbon/my-data');
  });

  it('still renders the reader on the main journey route (deep link is not hijacked)', async () => {
    renderApp('/journey/carbon/D2');
    await openJourneyTab();

    expect(await screen.findByTestId('lesson-reader')).toHaveAttribute('data-compact', 'true');
    expect(screen.getByTestId('location')).toHaveTextContent('/journey/carbon/D2');
  });
});

describe('Defect 3 — drawer tab state survives navigation and reload', () => {
  it('restores station + lesson after leaving the app and coming back', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();
    fireEvent.click(await screen.findByTestId('journey-lesson-D2'));
    await screen.findByTestId('lesson-reader');

    // Leave the app: the Journey tab unregisters and its body unmounts.
    fireEvent.click(screen.getByText('go-settings'));
    expect(screen.getByTestId('location')).toHaveTextContent('/settings');
    await screen.findByRole('tab', { name: /^notes$/i });
    expect(screen.queryByTestId('lesson-reader')).not.toBeInTheDocument();

    // Come back: the drawer reopens on Journey with the same lesson.
    fireEvent.click(screen.getByText('go-dashboard'));
    expect(await screen.findByTestId('lesson-reader')).toBeInTheDocument();
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(localStorage.getItem('carbon-notes-tab')).toBe('journey');
  });

  it('restores the drawer open state, active tab, station and lesson across a reload', async () => {
    const first = renderApp('/carbon/dashboard');
    await openJourneyTab();
    fireEvent.click(await screen.findByTestId('journey-lesson-D2'));
    await screen.findByTestId('lesson-reader');
    first.unmount();

    // Fresh mount == browser reload: everything must come back from localStorage.
    renderApp('/carbon/dashboard');
    const reader = await screen.findByTestId('lesson-reader');
    expect(reader).toHaveAttribute('data-compact', 'true');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /^journey$/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('location')).toHaveTextContent('/carbon/dashboard');
  });

  it('keeps the same tab + lesson state in the mobile fullscreen drawer', async () => {
    localStorage.setItem('carbon-notes-open', 'true');
    localStorage.setItem('carbon-notes-tab', 'journey');
    localStorage.setItem(
      'carbon-journey-view:anonymous:carbon',
      JSON.stringify({ stationN: 4, lessonId: 'D2', scrollTop: 0 }),
    );
    hoisted.mobile = true;

    renderApp('/carbon/dashboard', { mobileFullscreen: true });

    const reader = await screen.findByTestId('lesson-reader');
    expect(reader).toHaveAttribute('data-compact', 'true');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /^journey$/i })).toHaveAttribute('aria-selected', 'true');
  });
});

describe('Defect 2/3 — persisted view state is per user + app', () => {
  it('writes the drawer view state under a carbon-journey-view key', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();
    fireEvent.click(await screen.findByTestId('journey-lesson-D2'));
    await screen.findByTestId('lesson-reader');

    const raw = localStorage.getItem('carbon-journey-view:anonymous:carbon');
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw)).toMatchObject({ stationN: 4, lessonId: 'D2' });
  });

  it('has no separate Journey store — only the drawer persistence keys are used', async () => {
    renderApp('/carbon/dashboard');
    await openJourneyTab();
    await screen.findByTestId('journey-rail');
    const keys = Object.keys(localStorage);
    // The Journey tab carries no parallel notes/state store beyond the drawer
    // view-state key and the drawer's own open/tab preferences.
    expect(keys.every((k) => k.startsWith('carbon-'))).toBe(true);
    expect(within(screen.getByTestId('journey-tab')).queryByTestId('journey-notes-input')).toBeNull();
  });
});
