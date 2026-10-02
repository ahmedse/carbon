import { describe, it, expect } from 'vitest';

import {
  appIdFromPath,
  closedPeriods,
  defaultTrack,
  deriveJourney,
  findLessonContext,
  journeyContextFromPath,
  onboardingViewFromSearch,
  pathForTrack,
  periodState,
} from '../journeyStages';

const lesson = (id, track, state, extra = {}) => ({
  id,
  track,
  state,
  title: extra.title || id,
  minutes: 2,
  is_next: false,
  blocker: null,
  route: '/carbon/my-data',
  steps: [],
  completion: 'answer',
  ...extra,
});

// Mirrors the engine payload shape returned by backend/guide for any pack.
const JOURNEY = {
  title: 'Your carbon onboarding journey',
  intro: 'This journey teaches the whole carbon inventory job.',
  glossary: ['emission factor', 'boundary'],
  stages: [
    {
      n: 1, key: 'setup', title: 'Setup and policy', what: 'Set the period and factors.',
      lessons: ['L2', 'L3', 'C2', 'C3'], competencies: ['open_period', 'sources_factors', 'period_status', 'tiers'],
      lead: ['L2', 'L3', 'C2', 'C3'], owner: ['C2', 'C3'], pending: false,
    },
    {
      n: 2, key: 'coverage', title: 'Coverage targets', what: 'Cover or exclude with a reason.',
      lessons: ['L5', 'D6'], competencies: ['cover_exclude', 'handoff'],
      lead: ['L5'], owner: ['D6'], pending: false,
    },
    {
      n: 3, key: 'data_products', title: 'Data products', what: 'Not wired to the app yet.',
      lessons: [], competencies: [], lead: [], owner: [], pending: true,
    },
    {
      n: 4, key: 'data_entry', title: 'Data entry', what: 'Save activity rows.',
      lessons: ['D1', 'D2', 'D7'], competencies: ['what_owed', 'one_row', 'data_product'],
      lead: [], owner: ['D1', 'D2', 'D7'], pending: false,
    },
    {
      n: 5, key: 'calculation', title: 'Calculation and quality', what: 'Run a calculation.',
      lessons: ['L4', 'D3', 'D4'], competencies: ['calculation', 'restate', 'quality'],
      lead: ['L4'], owner: ['D3', 'D4'], pending: false,
    },
    {
      n: 6, key: 'lock', title: 'Lock and close', what: 'Boundary then lock.',
      lessons: ['L1', 'L6', 'D5'], competencies: ['boundary', 'legal_transition', 'lock_read'],
      lead: ['L1', 'L6'], owner: ['D5'], pending: false,
    },
    {
      n: 7, key: 'report', title: 'Report and disclosure', what: 'State the scope of a number.',
      lessons: ['L7'], competencies: ['quote_scope'], lead: ['L7'], owner: [], pending: false,
    },
  ],
  competencies: [
    { key: 'open_period', title: 'Keep one period open', good: 'One open row.', kind: 'host', probe: 'one_open_period', lesson: 'L2' },
    { key: 'sources_factors', title: 'Declare sources', good: 'An active factor.', kind: 'host', probe: 'source_has_factor', lesson: 'L3' },
    { key: 'period_status', title: 'Read a period status', good: 'Name what is allowed.', kind: 'answer', probe: '', lesson: 'C2' },
    { key: 'tiers', title: 'Read a quality tier', good: 'Explain not assured.', kind: 'answer', probe: '', lesson: 'C3' },
    { key: 'cover_exclude', title: 'Cover or exclude', good: 'A stated reason.', kind: 'host', probe: 'status_decided', lesson: 'L5' },
    { key: 'handoff', title: 'Hand off rows', good: 'Tell the lead.', kind: 'answer', probe: '', lesson: 'D6' },
    { key: 'what_owed', title: 'Name what is owed', good: 'Point at the thinnest source.', kind: 'answer', probe: '', lesson: 'D1' },
    { key: 'one_row', title: 'Save one row', good: 'A saved row exists.', kind: 'host', probe: 'row_created', lesson: 'D2' },
    { key: 'data_product', title: 'Use a data product', good: 'Upload, map, validate.', kind: 'answer', probe: '', lesson: 'D7' },
    { key: 'calculation', title: 'Run a calculation', good: 'A run under your user.', kind: 'host', probe: 'calculation_run_by_me', lesson: 'L4' },
    { key: 'restate', title: 'Restate a row', good: 'No double count.', kind: 'answer', probe: '', lesson: 'D3' },
    { key: 'quality', title: 'Read the quality status', good: 'Fix failing first.', kind: 'answer', probe: '', lesson: 'D4' },
    { key: 'boundary', title: 'Set the boundary', good: 'A consolidation approach.', kind: 'host', probe: 'boundary_set', lesson: 'L1' },
    { key: 'legal_transition', title: 'Name the transition', good: 'Open goes to locked.', kind: 'answer', probe: '', lesson: 'L6' },
    { key: 'lock_read', title: 'Read a locked period', good: 'Read the note.', kind: 'answer', probe: '', lesson: 'D5' },
    { key: 'quote_scope', title: 'State the scope', good: 'Say what it sums.', kind: 'answer', probe: '', lesson: 'L7' },
  ],
};

const LISTING = {
  recommended_track: 'D',
  next_id: 'D2',
  journey: JOURNEY,
  lessons: [
    lesson('C2', 'C', 'offered', { title: "Read a period's status" }),
    lesson('C3', 'C', 'offered', { title: 'Tiers and not assured' }),
    lesson('L2', 'L', 'offered', { title: 'One open period' }),
    lesson('L3', 'L', 'offered', { title: 'Declare sources' }),
    lesson('D1', 'D', 'done', { title: 'What I owe this period' }),
    lesson('D2', 'D', 'started', { title: 'Enter one activity row', is_next: true }),
    lesson('D7', 'D', 'offered', { title: 'Bring many rows' }),
    lesson('D3', 'D', 'offered', { title: "Why my total didn't move" }),
    lesson('D4', 'D', 'offered', { title: 'Read my quality status' }),
    lesson('D5', 'D', 'offered', { title: 'Locked or rejected' }),
    lesson('D6', 'D', 'offered', { title: 'Hand-off to the lead' }),
  ],
};

describe('Journey model (engine payload)', () => {
  it('reads stages, titles and glossary from the pack payload', () => {
    const model = deriveJourney(LISTING, 'D');
    expect(model.stages).toHaveLength(7);
    expect(model.stages[0].title).toBe('Setup and policy');
    expect(model.glossary).toEqual(['emission factor', 'boundary']);
    expect(model.intro).toMatch(/whole carbon inventory/);
  });

  it('maps tracks to the pack role buckets', () => {
    expect(pathForTrack('L')).toBe('lead');
    expect(pathForTrack('D')).toBe('owner');
    expect(pathForTrack('C')).toBe('observer');
    expect(defaultTrack(LISTING)).toBe('D');
    expect(defaultTrack({ lessons: [lesson('L2', 'L', 'offered')] })).toBe('L');
  });

  it('derives the current station from the engine next lesson', () => {
    const model = deriveJourney(LISTING, 'D');
    expect(model.currentStage.n).toBe(4);
    expect(model.stages.find((station) => station.n === 4).state).toBe('current');
  });

  it('never exposes a lock state — every station is done, current or open', () => {
    const model = deriveJourney(LISTING, 'D');
    const states = new Set(model.stages.map((station) => station.state));
    expect([...states].every((state) => ['done', 'current', 'open'].includes(state))).toBe(true);
    expect(model.stages.some((station) => station.state === 'locked')).toBe(false);
    expect(model.stages.some((station) => station.state === 'available')).toBe(false);
  });

  it('shows a lead outcome on the lead path and not on the owner path', () => {
    const owner = deriveJourney(LISTING, 'D');
    const lead = deriveJourney(LISTING, 'L');
    const ownerKeys = owner.stages.flatMap((station) => station.competencies.map((row) => row.key));
    const leadKeys = lead.stages.flatMap((station) => station.competencies.map((row) => row.key));
    expect(ownerKeys).not.toContain('open_period');
    expect(ownerKeys).toContain('period_status');
    expect(leadKeys).toContain('open_period');
  });

  it('reads every track for a wildcard caller instead of one role split', () => {
    const su = { ...LISTING, all_tracks: true, recommended_track: null };
    const model = deriveJourney(su, 'D');
    expect(model.allTracks).toBe(true);
    expect(model.hasWork).toBe(true);
    const stage1 = model.stages.find((station) => station.n === 1);
    // The union of the lead and owner splits, not the owner slice alone.
    expect(stage1.lessons.map((lesson) => lesson.id).sort())
      .toEqual(['C2', 'C3', 'L2', 'L3']);
    expect(stage1.competencies.map((row) => row.key).sort())
      .toEqual(['open_period', 'period_status', 'sources_factors', 'tiers']);
  });

  it('keeps one path for a normal caller and reports no work honestly', () => {
    const owner = deriveJourney(LISTING, 'D');
    expect(owner.allTracks).toBe(false);
    expect(owner.hasWork).toBe(true);
    expect(owner.stages.find((station) => station.n === 1).lessons.map((lesson) => lesson.id))
      .toEqual(['C2', 'C3']);

    const none = deriveJourney({ recommended_track: null, journey: JOURNEY, lessons: [] }, 'D');
    expect(none.hasWork).toBe(false);
    expect(none.stages.every((station) => (
      station.lessons.length === 0 && station.competencies.length === 0
    ))).toBe(true);
  });

  it('marks a station done only when its outcomes are proven', () => {
    const listing = {
      ...LISTING,
      journey: JOURNEY,
      lessons: LISTING.lessons.map((row) => (
        ['C2', 'C3'].includes(row.id) ? { ...row, state: 'done' } : row
      )),
    };
    const model = deriveJourney(listing, 'D');
    expect(model.stages.find((station) => station.n === 1).state).toBe('done');
    expect(model.stages.find((station) => station.n === 4).state).toBe('current');
  });

  it('carries a pending station honestly without locking it', () => {
    const model = deriveJourney(LISTING, 'D');
    const pending = model.stages.find((station) => station.n === 3);
    expect(pending.pending).toBe(true);
    expect(pending.done).toBe(false);
    expect(pending.state).toBe('open');
  });

  it('derives the same spine for a fake non-carbon pack', () => {
    const fake = {
      recommended_track: 'C',
      journey: {
        title: 'Fake journey',
        intro: 'No domain words here.',
        glossary: ['flux capacitor'],
        stages: [
          { n: 1, key: 'begin', title: 'Begin', what: 'The first station.', lessons: ['F1'], competencies: ['first_step'], lead: [], owner: [], pending: false },
        ],
        competencies: [{ key: 'first_step', title: 'Take the first step', good: 'One route.', kind: 'answer', probe: '', lesson: 'F1' }],
      },
      lessons: [lesson('F1', 'C', 'offered', { title: 'The first lesson', route: '/fake/one' })],
    };
    const model = deriveJourney(fake, 'C');
    expect(model.stages[0].title).toBe('Begin');
    expect(model.stages[0].competencies[0].title).toBe('Take the first step');
  });
});

describe('Open and closed periods', () => {
  it('reads exactly one open period, none, or many', () => {
    expect(periodState([{ id: 17, status: 'open', name: 'Calendar year 2026' }]))
      .toMatchObject({ status: 'open', openCount: 1 });
    expect(periodState([{ id: 17, status: 'closed' }])).toMatchObject({ status: 'none', openCount: 0 });
    expect(periodState([{ id: 1, status: 'open' }, { id: 2, status: 'open' }]))
      .toMatchObject({ status: 'many', openCount: 2 });
  });

  it('keeps closed periods read-only and separate from the open one', () => {
    const closed = closedPeriods([
      { id: 17, status: 'open' },
      { id: 15, status: 'closed' },
      { id: 16, status: 'closed' },
    ]);
    expect(closed.map((row) => row.id)).toEqual([15, 16]);
  });
});

describe('Routing helpers', () => {
  it('defaults to Journey and keeps the readiness query working', () => {
    expect(onboardingViewFromSearch('')).toBe('journey');
    expect(onboardingViewFromSearch('view=readiness')).toBe('readiness');
  });

  it('resolves the app id for generic and carbon routes', () => {
    expect(appIdFromPath('/journey/carbon')).toBe('carbon');
    expect(appIdFromPath('/journey/nibras')).toBe('nibras');
    expect(appIdFromPath('/carbon/onboarding')).toBe('carbon');
    expect(appIdFromPath('/settings')).toBe(null);
  });

  it('resolves the open lesson id from a reader URL, and null elsewhere', () => {
    expect(journeyContextFromPath('/journey/carbon/D2')).toEqual({ appId: 'carbon', lessonId: 'D2' });
    expect(journeyContextFromPath('/journey/carbon')).toEqual({ appId: 'carbon', lessonId: null });
    expect(journeyContextFromPath('/carbon/onboarding')).toEqual({ appId: 'carbon', lessonId: null });
    expect(journeyContextFromPath('/settings')).toBe(null);
  });
});

describe('Lesson context (master-detail reader)', () => {
  const model = deriveJourney(LISTING, 'D');

  it('resolves a lesson to its station, position and neighbours', () => {
    const context = findLessonContext(model, 'D2');
    expect(context.station.n).toBe(4);
    expect(context.lesson.id).toBe('D2');
    expect(context.index).toBe(1);
    expect(context.total).toBe(3);
    expect(context.prev.id).toBe('D1');
    expect(context.next.id).toBe('D7');
  });

  it('has no Prev at the first lesson and no Next at the last', () => {
    expect(findLessonContext(model, 'D1').prev).toBe(null);
    expect(findLessonContext(model, 'D7').next).toBe(null);
  });

  it('returns null for a lesson that is not on this path', () => {
    expect(findLessonContext(model, 'L5')).toBe(null);
    expect(findLessonContext(null, 'D2')).toBe(null);
    expect(findLessonContext(model, null)).toBe(null);
  });
});
