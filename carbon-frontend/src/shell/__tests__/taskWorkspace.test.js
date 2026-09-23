import { describe, it, expect } from 'vitest';
import {
  groupTaskBoard,
  hasTaskOutcome,
  humanTaskTitle,
  taskBoardCoworkerLine,
  taskCoworkerLine,
} from '../taskWorkspace';

describe('humanTaskTitle', () => {
  it('rewrites a GOSI / payroll engine brief', () => {
    expect(humanTaskTitle({
      brief: 'Plan gosi_wps.sif.lifecycle on a committed payroll run using generate_gosi_wps_sif, validate_gosi_wps_sif, submit_gosi_wps_sif. Never submit_my_leave.',
    })).toBe('Send the GOSI file for this payroll');
  });

  it('keeps a human brief', () => {
    expect(humanTaskTitle({
      brief: 'Create a professional Word report analyzing salary distribution at GOFSCO.',
    })).toMatch(/salary distribution/i);
  });
});

describe('hasTaskOutcome', () => {
  it('is true only after a real outcome', () => {
    expect(hasTaskOutcome('running', 'working')).toBe(false);
    expect(hasTaskOutcome('pending_approval', 'idle')).toBe(false);
    expect(hasTaskOutcome('completed', 'finished')).toBe(true);
    expect(hasTaskOutcome('failed', 'error')).toBe(true);
    expect(hasTaskOutcome('approved', 'finished')).toBe(false);
  });
});

describe('taskCoworkerLine', () => {
  const t = (key) => key;

  it('uses waiting copy when a step needs the employee', () => {
    expect(taskCoworkerLine({ t, awaiting: true })).toBe('coworkerWaiting');
  });

  it('keeps the paused count line', () => {
    expect(taskCoworkerLine({
      t,
      phase: 'paused',
      effective: 'paused',
      pausedCounts: { done: 1, pending: 2 },
    })).toBe('Paused — 1 step completed, 2 to go');
  });
});

describe('groupTaskBoard', () => {
  it('splits needs-you, working, and done', () => {
    const groups = groupTaskBoard([
      { id: 'a', status: 'pending_approval', created_at: '2026-09-23T10:00:00Z' },
      { id: 'b', status: 'running', created_at: '2026-09-22T10:00:00Z' },
      { id: 'c', status: 'completed', created_at: '2026-09-21T10:00:00Z' },
      { id: 'd', status: 'paused', created_at: '2026-09-20T10:00:00Z' },
    ]);
    expect(groups.attention.map((p) => p.id)).toEqual(['a', 'd']);
    expect(groups.working.map((p) => p.id)).toEqual(['b']);
    expect(groups.done.map((p) => p.id)).toEqual(['c']);
  });
});

describe('taskBoardCoworkerLine', () => {
  const t = (key, vars) => (vars?.count != null ? `${key}:${vars.count}` : key);

  it('counts what needs the employee', () => {
    expect(taskBoardCoworkerLine({ attention: [{}], working: [], done: [] }, t))
      .toBe('boardCoworkerNeedsOne');
    expect(taskBoardCoworkerLine({ attention: [{}, {}], working: [], done: [] }, t))
      .toBe('boardCoworkerNeedsMany:2');
    expect(taskBoardCoworkerLine({ attention: [], working: [{}], done: [] }, t))
      .toBe('boardCoworkerWorking');
    expect(taskBoardCoworkerLine({ attention: [], working: [], done: [] }, t))
      .toBe('boardCoworkerEmpty');
  });
});
