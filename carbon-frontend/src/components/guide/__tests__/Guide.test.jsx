import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GuideHub, { pickEntryLesson } from '../GuideHub';
import GuideNudge from '../GuideNudge';
import LiveCard from '../LiveCard';
import enGuide from '../../../i18n/locales/en/guide.json';
import arGuide from '../../../i18n/locales/ar/guide.json';

vi.mock('../../../auth/AuthContext', () => ({ useAuth: () => ({ token: 't' }) }));

const fetchGuide = vi.fn();
const fetchGuideLesson = vi.fn();
const postGuideEvent = vi.fn();
vi.mock('../../../api/guide', () => ({
  fetchGuide: (...a) => fetchGuide(...a),
  fetchGuideLesson: (...a) => fetchGuideLesson(...a),
  postGuideEvent: (...a) => postGuideEvent(...a),
}));

const LISTING = {
  app_id: 'carbon',
  next_id: 'D1',
  recommended_track: 'D',
  tracks: [
    { id: 'C', total: 1, done: 1, title: 'Start here' },
    { id: 'D', total: 2, done: 0, title: 'Enter and gather data', blurb: 'Your sources.' },
  ],
  lessons: [
    { id: 'C1', track: 'C', phase: 'gather', title: 'Where you are', state: 'done', minutes: 1, blocker: null, is_next: false },
    { id: 'D1', track: 'D', phase: 'gather', title: 'What I owe', state: 'offered', minutes: 2, blocker: null, is_next: true },
    { id: 'D2', track: 'D', phase: 'gather', title: 'Enter one row', state: 'offered', minutes: 3, is_next: false, blocker: { code: 'no_open_period', title: 'No open period', path: null } },
  ],
};

const DETAIL = {
  id: 'D1', state: 'started', minutes: 2, route: '/carbon/my-data', host_required: false, blocker: null,
  live: { kind: 'sources', items: [] },
  question: { options: 3, params: {} },
  copy: {
    title: 'What I owe', know: 'Know text', do: 'Do text', dont: 'Dont text',
    question: 'Which page?', options: ['Data Entry', 'Chairman', 'Factors'], explain: 'Because scoped.',
  },
};

function renderHub(props = {}) {
  return render(
    <MemoryRouter>
      <GuideHub appId="carbon" onOpen={() => {}} onClose={() => {}} {...props} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchGuide.mockReset().mockResolvedValue(LISTING);
  fetchGuideLesson.mockReset().mockResolvedValue(DETAIL);
  postGuideEvent.mockReset().mockResolvedValue({ correct: null, state: 'started', waiting: null });
});

describe('Guide hub', () => {
  it('shows tracks, groups by phase, marks next and blocked (GUIDE-USE-HUB)', async () => {
    renderHub();
    expect(await screen.findByTestId('guide-track-D')).toBeInTheDocument();
    expect(screen.getByText('Enter and gather data', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByTestId('guide-lesson-D1')).toHaveTextContent('Next');
    expect(screen.getByTestId('guide-lesson-D2')).toHaveTextContent('Blocked');
    expect(screen.getByTestId('guide-lesson-C1')).toHaveTextContent('Done');
    expect(screen.getAllByText(/Gathering data/).length).toBeGreaterThan(0);
  });

  it('shows an empty state when the server offers no lessons', async () => {
    fetchGuide.mockResolvedValue({ tracks: [], lessons: [], next_id: null });
    renderHub();
    expect(await screen.findByText('No lessons for you yet')).toBeInTheDocument();
  });

  it('shows an error with retry when the guide cannot load', async () => {
    fetchGuide.mockRejectedValue(new Error('boom'));
    renderHub();
    expect(await screen.findByText('Could not load your guide.')).toBeInTheDocument();
  });

  it('reopens the lesson the person last left (GUIDE-USE-RESUME)', async () => {
    const onOpen = vi.fn();
    fetchGuide.mockResolvedValue({ ...LISTING, resume: { id: 'D1', step: 2 } });
    renderHub({ onOpen });
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('D1', { replace: true }));
  });

  it('stays on the hub when the caller asked for the list', async () => {
    const onOpen = vi.fn();
    fetchGuide.mockResolvedValue({ ...LISTING, resume: { id: 'D1', step: 2 } });
    render(
      <MemoryRouter initialEntries={['/guide/carbon?list=1']}>
        <GuideHub appId="carbon" onOpen={onOpen} onClose={() => {}} />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('guide-lesson-D1')).toBeInTheDocument();
    expect(onOpen).not.toHaveBeenCalled();
  });
});

describe('Lesson coach', () => {
  async function openCheck() {
    renderHub({ lessonId: 'D1' });
    await screen.findByTestId('guide-coach');
    fireEvent.click(screen.getByText('Continue'));
    fireEvent.click(screen.getByText('Continue'));
  }

  it('opens on the saved coach step', async () => {
    fetchGuideLesson.mockResolvedValue({ ...DETAIL, step: 2 });
    renderHub({ lessonId: 'D1' });
    expect(await screen.findByText('Which page?')).toBeInTheDocument();
  });

  it('walks Know, Do, Check and starts the lesson once (GUIDE-USE-COACH)', async () => {
    fetchGuideLesson.mockResolvedValue({ ...DETAIL, state: 'offered' });
    renderHub({ lessonId: 'D1' });
    expect(await screen.findByText('Know text')).toBeInTheDocument();
    await waitFor(() => expect(postGuideEvent).toHaveBeenCalledWith('carbon', 'D1', { event: 'started' }, 't'));
    fireEvent.click(screen.getByText('Continue'));
    expect(screen.getByText('Do text')).toBeInTheDocument();
    expect(screen.getByText(/Dont text/)).toBeInTheDocument();
    expect(screen.queryByTestId('guide-live')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Continue'));
    expect(screen.getByText('Which page?')).toBeInTheDocument();
  });

  it('sends the chosen option and shows the explanation when right', async () => {
    postGuideEvent.mockResolvedValue({ correct: true, state: 'done', waiting: null });
    await openCheck();
    const submit = screen.getByText('Check my answer');
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Data Entry'));
    fireEvent.click(submit);
    await waitFor(() => expect(postGuideEvent).toHaveBeenCalledWith('carbon', 'D1', { event: 'answered', choice: 0 }, 't'));
    expect(await screen.findByText('Because scoped.')).toBeInTheDocument();
  });

  it('says so on a wrong answer and does not reveal the explanation', async () => {
    postGuideEvent.mockResolvedValue({ correct: false, state: 'started', waiting: null });
    await openCheck();
    fireEvent.click(screen.getByLabelText('Factors'));
    fireEvent.click(screen.getByText('Check my answer'));
    expect(await screen.findByText(/Not quite/)).toBeInTheDocument();
    expect(screen.queryByText('Because scoped.')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('Data Entry')).toBeEnabled());
    fireEvent.click(screen.getByLabelText('Data Entry'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Check my answer' })).toBeEnabled());
    fireEvent.click(screen.getByText('Check my answer'));
    await waitFor(() => expect(postGuideEvent.mock.calls.filter((call) => call[2]?.event === 'answered')).toHaveLength(2));
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Check my answer' })).toBeEnabled();
  });

  it('shows only the wrong alert when a failed check also comes back as waiting', async () => {
    postGuideEvent.mockResolvedValue({ correct: false, state: 'started', waiting: 'host' });
    await openCheck();
    fireEvent.click(screen.getByLabelText('Factors'));
    fireEvent.click(screen.getByText('Check my answer'));
    expect(await screen.findByText(/Not quite/)).toBeInTheDocument();
    expect(screen.queryByText(/Your answer is right/)).not.toBeInTheDocument();
    expect(screen.queryByText(/finishes when the app shows/)).not.toBeInTheDocument();
    expect(screen.queryByText('Because scoped.')).not.toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });

  it('shows only the waiting line when the answer is right and the app has not caught up', async () => {
    fetchGuideLesson.mockResolvedValue({ ...DETAIL, id: 'D2', host_required: true });
    postGuideEvent.mockResolvedValue({ correct: true, state: 'started', waiting: 'host' });
    renderHub({ lessonId: 'D2' });
    await screen.findByTestId('guide-coach');
    fireEvent.click(screen.getByText('Continue'));
    fireEvent.click(screen.getByText('Continue'));
    fireEvent.click(screen.getByLabelText('Data Entry'));
    fireEvent.click(screen.getByText('Check my answer'));
    expect(await screen.findByText(/finishes when the app shows/)).toBeInTheDocument();
    expect(screen.queryByText(/Not quite/)).not.toBeInTheDocument();
    expect(screen.queryByText('Because scoped.')).not.toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    await waitFor(() => expect(screen.getByLabelText('Factors')).toBeEnabled());
    fireEvent.click(screen.getByLabelText('Factors'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Check my answer' })).toBeEnabled());
    fireEvent.click(screen.getByText('Check my answer'));
    await waitFor(() => expect(postGuideEvent.mock.calls.filter((call) => call[2]?.event === 'answered')).toHaveLength(2));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Check again' })).toBeEnabled());
    fireEvent.click(screen.getByText('Check again'));
    await waitFor(() => expect(postGuideEvent.mock.calls.filter((call) => call[2]?.event === 'check')).toHaveLength(1));
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Check again' })).toBeEnabled();
  });

  it('shows the blocker text and no fix button when the user cannot fix it', async () => {
    fetchGuideLesson.mockResolvedValue({
      ...DETAIL, blocker: { code: 'no_open_period', title: 'No open period', body: 'A lead opens one.', path: null },
    });
    renderHub({ lessonId: 'D1' });
    expect(await screen.findByText('No open period')).toBeInTheDocument();
    expect(screen.queryByText('Fix it')).not.toBeInTheDocument();
  });
});

const STAGE = {
  app_id: 'carbon',
  next_id: 'D2',
  recommended_track: 'D',
  resume: { id: 'D3', step: 2 },
  tracks: [
    { id: 'C', total: 1, done: 0, title: 'The period and the figure' },
    { id: 'D', total: 4, done: 1, title: 'Enter and gather data' },
  ],
  lessons: [
    { id: 'D1', track: 'D', phase: 'gather', title: 'What I owe', state: 'done', minutes: 2, stage: 'entry', target: 'my-data.list', is_next: false, blocker: null },
    { id: 'D2', track: 'D', phase: 'gather', title: 'Enter one activity row', state: 'started', minutes: 3, stage: 'entry', target: 'my-data.add-row', is_next: true, blocker: null },
    { id: 'D3', track: 'D', phase: 'gather', title: "Why my total didn't move", state: 'started', minutes: 2, stage: '', is_next: false, blocker: null },
    { id: 'D7', track: 'D', phase: 'gather', title: 'Bring many rows', state: 'offered', minutes: 3, stage: 'entry', target: 'my-data.bulk-import', is_next: false, blocker: null },
    { id: 'C2', track: 'C', phase: 'gather', title: "Read a period's status", state: 'offered', minutes: 2, stage: '', is_next: false, blocker: null },
  ],
};

describe('Data-entry stage', () => {
  it('opens the first unfinished data-entry lesson', () => {
    expect(pickEntryLesson(STAGE.lessons.filter((lesson) => lesson.stage))).toBe('D2');
    expect(pickEntryLesson([
      { id: 'D1', state: 'offered' },
      { id: 'D2', state: 'started', target: 'my-data.add-row' },
    ])).toBe('D1');
    expect(pickEntryLesson([
      { id: 'D2', state: 'done', target: 'my-data.add-row' },
      { id: 'D7', state: 'offered', target: 'my-data.bulk-import' },
    ])).toBe('D7');
  });

  it('does not resume a calculation quiz when data entry is unfinished', async () => {
    const onOpen = vi.fn();
    fetchGuide.mockResolvedValue(STAGE);
    renderHub({ onOpen });
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('D2', { replace: true }));
    expect(onOpen).not.toHaveBeenCalledWith('D3', expect.anything());
  });

  it('teaches the row and keeps the other lessons quiet', async () => {
    fetchGuide.mockResolvedValue(STAGE);
    fetchGuideLesson.mockResolvedValue({
      ...DETAIL,
      id: 'D2',
      route: '/carbon/my-data',
      copy: {
        ...DETAIL.copy,
        title: 'Enter one activity row',
        know: 'A row is one activity.',
        do: 'Open Data Entry and save one row.',
        dont: 'Do not round.',
      },
    });
    renderHub({ lessonId: 'D2' });
    expect(await screen.findByText('A row is one activity.')).toBeInTheDocument();
    expect(screen.getByText('Open Data Entry and save one row.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open Data Entry' })).toBeInTheDocument();
    expect(screen.queryByText('Know')).not.toBeInTheDocument();
    const entry = screen.getByTestId('guide-entry');
    expect(entry).toHaveTextContent('1 of 3 done');
    expect(entry).toHaveTextContent('What I owe');
    expect(entry).toHaveTextContent('Enter one activity row');
    expect(entry).toHaveTextContent('Bring many rows');
    expect(entry).not.toHaveTextContent("Why my total didn't move");
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
    const later = screen.getByTestId('guide-later');
    expect(later).not.toHaveClass('Mui-expanded');
    fireEvent.click(screen.getByText('Later'));
    expect(later).toHaveTextContent("Why my total didn't move");
    expect(later).toHaveTextContent("Read a period's status");
    expect(later).not.toHaveTextContent('Enter one activity row');
    expect(later).not.toHaveTextContent('What I owe');
    expect(screen.getByTestId('guide-lesson-D1')).toHaveTextContent('Done');
    expect(screen.getByTestId('guide-lesson-D3')).not.toHaveTextContent('Next');
  });

  it('checks a saved row with one sentence and no scope quiz', async () => {
    const rowCopy = {
      title: 'Enter one activity row',
      know: 'A row is one activity.',
      do: 'Open Data Entry and save one row.',
      dont: 'Do not round.',
      question: 'This lesson finishes when Data Entry shows a row you saved.',
      options: [],
      explain: 'Because scoped.',
    };
    fetchGuide.mockResolvedValue(STAGE);
    fetchGuideLesson.mockResolvedValue({
      ...DETAIL,
      id: 'D2',
      state: 'started',
      host_required: true,
      route: '/carbon/my-data',
      question: { kind: 'host', options: 0, params: {} },
      copy: rowCopy,
    });
    postGuideEvent.mockResolvedValue({ correct: null, state: 'started', waiting: 'host' });
    renderHub({ lessonId: 'D2' });
    expect(await screen.findByText('A row is one activity.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Check'));
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.queryByText(/GHG scope/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check for a saved row' }));
    expect(await screen.findByText('No saved row yet.')).toBeInTheDocument();
    expect(screen.queryByText(/Your answer is right/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Not quite/)).not.toBeInTheDocument();
    expect(screen.queryByText('Because scoped.')).not.toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    const again = await screen.findByRole('button', { name: 'Check again' });
    await waitFor(() => expect(again).toBeEnabled());
    fireEvent.click(again);
    await waitFor(() => expect(postGuideEvent.mock.calls.filter((call) => call[2]?.event === 'check')).toHaveLength(2));
    expect(screen.getAllByText('No saved row yet.')).toHaveLength(1);
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Check again' })).toBeEnabled();
  });

  it('shows only the done state once the row is in the app', async () => {
    fetchGuide.mockResolvedValue(STAGE);
    fetchGuideLesson.mockResolvedValue({
      ...DETAIL,
      id: 'D2',
      state: 'done',
      host_required: true,
      question: { kind: 'host', options: 0, params: {} },
      copy: {
        title: 'Enter one activity row',
        know: 'A row is one activity.',
        do: 'Open Data Entry and save one row.',
        dont: 'Do not round.',
        question: 'This lesson finishes when Data Entry shows a row you saved.',
        options: [],
        explain: 'Because scoped.',
      },
    });
    renderHub({ lessonId: 'D2' });
    expect(await screen.findByText('Lesson complete.')).toBeInTheDocument();
    expect(screen.queryByText('Because scoped.')).not.toBeInTheDocument();
    expect(screen.queryByText('No saved row yet.')).not.toBeInTheDocument();
    expect(screen.queryByText(/Your answer is right/)).not.toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });
});

describe('Guide nudge', () => {
  const renderNudge = () => render(<MemoryRouter><GuideNudge appId="carbon" /></MemoryRouter>);

  it('offers the next lesson and snoozes on Later (GUIDE-USE-NUDGE)', async () => {
    renderNudge();
    expect(await screen.findByTestId('guide-nudge')).toHaveTextContent('What I owe');
    fireEvent.click(screen.getByText('Later'));
    await waitFor(() => expect(postGuideEvent).toHaveBeenCalledWith('carbon', 'D1', { event: 'snooze' }, 't'));
    expect(screen.queryByTestId('guide-nudge')).not.toBeInTheDocument();
  });

  it('stays silent when the guide is unavailable', async () => {
    fetchGuide.mockRejectedValue(new Error('403'));
    renderNudge();
    await waitFor(() => expect(fetchGuide).toHaveBeenCalled());
    expect(screen.queryByTestId('guide-nudge')).not.toBeInTheDocument();
  });

  it('stays silent when there is nothing next', async () => {
    fetchGuide.mockResolvedValue({ ...LISTING, next_id: null });
    renderNudge();
    await waitFor(() => expect(fetchGuide).toHaveBeenCalled());
    expect(screen.queryByTestId('guide-nudge')).not.toBeInTheDocument();
  });

  it('outlines the lesson target when it is on the page', async () => {
    fetchGuide.mockResolvedValue({
      ...LISTING,
      lessons: LISTING.lessons.map((l) => (l.id === 'D1' ? { ...l, target: 'my-data.list' } : l)),
    });
    const { container } = render(
      <MemoryRouter><div data-guide="my-data.list" /><GuideNudge appId="carbon" /></MemoryRouter>,
    );
    await screen.findByTestId('guide-nudge');
    await waitFor(() => expect(container.querySelector('[data-guide="my-data.list"]').style.outline).toContain('solid'));
  });
});

describe('Live card', () => {
  it('renders nothing for an unknown kind', () => {
    const { container } = render(<LiveCard live={{ kind: 'nope' }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the carbon period and sources cards without any emission figure', async () => {
    render(<LiveCard live={{ kind: 'period', open_count: 1, current: { name: 'FY26', status: 'open', start_date: '2026-01-01', end_date: '2026-12-31' } }} />);
    expect(await screen.findByText('FY26')).toBeInTheDocument();
    render(<LiveCard live={{ kind: 'sources', items: [{ id: 1, name: 'Generators', scope: 1, status: 'declared', row_count: 3 }] }} />);
    expect(await screen.findByText('3 rows')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\bkg\b|tonne|co2e/i);
  });
});

describe('Guide i18n (GUIDE-I18N)', () => {
  const flat = (obj, prefix = '') => Object.entries(obj).flatMap(([k, v]) => (
    v && typeof v === 'object' ? flat(v, `${prefix}${k}.`) : [`${prefix}${k}`]
  ));

  it('has the same keys in English and Arabic', () => {
    expect(flat(arGuide).sort()).toEqual(flat(enGuide).sort());
  });

  it('does not describe the guide as only the data-entry lessons', () => {
    expect(enGuide.hub.entry.description).toMatch(/Later/);
    expect(enGuide.hub.entry.description).not.toMatch(/type one row/i);
    expect(arGuide.hub.entry.description).toMatch(/لاحق/);
    expect(enGuide.coach.waitingRow).not.toMatch(/answer is right/i);
    expect(arGuide.coach.waitingRow).not.toMatch(/صحيحة/);
  });

  it('has no empty strings', () => {
    [enGuide, arGuide].forEach((catalog) => flat(catalog).forEach((key) => {
      const value = key.split('.').reduce((node, part) => node[part], catalog);
      expect(String(value).trim().length, key).toBeGreaterThan(0);
    }));
  });
});

describe('Guide RTL (GUIDE-USE-RTL)', () => {
  it('uses logical layout only, so the coach flips with the language', async () => {
    const { readdirSync, readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const dir = join(process.cwd(), 'src', 'components', 'guide');
    const files = readdirSync(dir).filter((f) => f.endsWith('.jsx'));
    expect(files.length).toBeGreaterThan(3);
    files.forEach((file) => {
      const text = readFileSync(join(dir, file), 'utf8');
      expect(text, file).not.toMatch(/margin(Left|Right)|padding(Left|Right)|ml:|mr:|pl:|pr:|textAlign:\s*'(left|right)'|\b(left|right):\s/);
    });
  });
});
