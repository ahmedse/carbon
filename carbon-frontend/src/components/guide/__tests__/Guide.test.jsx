import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GuideHub from '../GuideHub';
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
  });

  it('waits for the host check and offers to check again', async () => {
    fetchGuideLesson.mockResolvedValue({ ...DETAIL, id: 'D2', host_required: true });
    postGuideEvent.mockResolvedValue({ correct: true, state: 'started', waiting: 'host' });
    renderHub({ lessonId: 'D2' });
    await screen.findByTestId('guide-coach');
    fireEvent.click(screen.getByText('Continue'));
    fireEvent.click(screen.getByText('Continue'));
    fireEvent.click(screen.getByLabelText('Data Entry'));
    fireEvent.click(screen.getByText('Check my answer'));
    expect(await screen.findByText(/finishes when the app shows/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Check again'));
    await waitFor(() => expect(postGuideEvent).toHaveBeenCalledWith('carbon', 'D2', { event: 'check' }, 't'));
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
