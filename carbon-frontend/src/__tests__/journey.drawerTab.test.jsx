// src/__tests__/journey.drawerTab.test.jsx
// Journey is ONE TAB inside the standard system-wide drawer (Notes/Annotations),
// not a second docked panel. These tests cover: the tab exists next to Notes;
// the station list and the compact lesson reader render inside the tab; tab
// switches preserve journey state and notes; no separate Journey dock renders;
// the mobile drawer carries the Journey tab; and the drawer tab is route-gated.
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

// The reader now fetches the lesson detail (briefing / hazard / check). Resolve
// nothing here so this suite keeps exercising the waypoint reader unchanged.
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

function renderDrawer(entry = '/journey/carbon/D2') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <NotesProvider>
        <JourneyInspectorTabRegistrar />
        <NotesDrawer />
      </NotesProvider>
    </MemoryRouter>,
  );
}

function openDrawer() {
  fireEvent.click(screen.getByRole('button', { name: /^notes$/i }));
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

describe('Journey tab in the standard drawer', () => {
  it('lists Journey as a tab in the standard drawer, right after Notes', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();
    const panel = await screen.findByRole('complementary');

    // Notes is the fixed first tab; Journey is the first contextual tab.
    const tabs = within(panel).getAllByRole('tab').map((el) => el.textContent.trim());
    expect(tabs).toEqual(['Notes', 'Journey']);
    expect(screen.queryByTestId('journey-launcher-dock')).not.toBeInTheDocument();
    expect(screen.queryByTestId('journey-launcher-rail')).not.toBeInTheDocument();
  });

  it('opens the compact lesson reader with the station and Prev/Next', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));

    const reader = await screen.findByTestId('lesson-reader');
    expect(reader).toHaveAttribute('data-compact', 'true');
    expect(screen.getByTestId('lesson-reader-station')).toHaveTextContent('Data entry');
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
    expect(screen.getByTestId('lesson-reader-stepcount')).toHaveTextContent('Step 1 of 2');
    expect(screen.getByTestId('lesson-reader-prev')).toBeEnabled();
    expect(screen.getByTestId('lesson-reader-next')).toHaveTextContent('Next lesson');
    // The reader body is the shared step timeline.
    expect(screen.getByTestId('lesson-steps')).toBeInTheDocument();
  });

  it('walks to the next lesson inside the tab without changing the route', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    await screen.findByTestId('lesson-reader');

    fireEvent.click(screen.getByTestId('lesson-reader-next'));
    expect(await screen.findByText('Bring many rows')).toBeInTheDocument();
    // Last lesson in the station: Next becomes the station summary.
    expect(screen.getByTestId('lesson-reader-next')).toHaveTextContent('Station summary');
  });

  it('shows the station list when the route is not a lesson', async () => {
    renderDrawer('/journey/carbon');
    openDrawer();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));

    expect(await screen.findByTestId('journey-rail')).toBeInTheDocument();
    expect(screen.getByTestId('journey-tab')).toHaveTextContent('Enter one activity row');
    expect(screen.queryByTestId('lesson-reader')).not.toBeInTheDocument();
  });

  it('switches between Journey and Notes without losing either', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();

    // Notes tab first: its standard body is present.
    expect(await screen.findByText(/open a record to attach a note/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    expect(await screen.findByTestId('lesson-reader')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /^notes$/i }));
    expect(await screen.findByText(/open a record to attach a note/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    expect(await screen.findByTestId('lesson-reader')).toBeInTheDocument();
    expect(screen.getByText('Enter one activity row')).toBeInTheDocument();
  });

  it('persists the active tab so the drawer reopens on Journey', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    await screen.findByTestId('lesson-reader');
    expect(localStorage.getItem('carbon-notes-tab')).toBe('journey');
  });

  it('does not carry a parallel notes store inside the Journey tab', async () => {
    renderDrawer('/journey/carbon/D2');
    openDrawer();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    await screen.findByTestId('lesson-reader');
    expect(screen.queryByTestId('journey-notes-input')).not.toBeInTheDocument();
    expect(screen.queryByText(/Your notes/i)).not.toBeInTheDocument();
  });

  it('omits the Journey tab on a route with no app journey', async () => {
    renderDrawer('/settings');
    openDrawer();
    await screen.findByRole('complementary');
    expect(screen.queryByRole('tab', { name: /^journey$/i })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /^notes$/i })).toBeInTheDocument();
  });

  it('keeps the /guide/* alias out of the journey drawer tab', async () => {
    renderDrawer('/guide/carbon/D2');
    openDrawer();
    await screen.findByRole('complementary');
    // The guide hub owns /guide/*; the Journey drawer tab is route-gated to
    // /journey/<appId> or an app studio route.
    expect(screen.queryByRole('tab', { name: /^journey$/i })).not.toBeInTheDocument();
  });
});

describe('Journey tab on mobile', () => {
  it('appears inside the fullscreen drawer with one FAB only', async () => {
    hoisted.mobile = true;
    render(
      <MemoryRouter initialEntries={['/journey/carbon/D2']}>
        <NotesProvider>
          <JourneyInspectorTabRegistrar />
          <NotesDrawer mobileFullscreen />
        </NotesProvider>
      </MemoryRouter>,
    );

    // No second Journey sheet: the only mobile launcher is the standard FAB.
    expect(screen.queryByTestId('journey-launcher-fab')).not.toBeInTheDocument();
    const fab = screen.getByRole('button', { name: /notes/i });
    fireEvent.click(fab);

    expect(await screen.findByRole('tab', { name: /^journey$/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: /^journey$/i }));
    expect(await screen.findByTestId('lesson-reader')).toHaveAttribute('data-compact', 'true');
  });
});
