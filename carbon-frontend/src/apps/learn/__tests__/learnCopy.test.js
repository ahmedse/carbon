// src/apps/learn/__tests__/learnCopy.test.js
import { describe, it, expect } from 'vitest';
import {
  criterionLabel,
  pickLatestCoaching,
  resolveRoleAwareHome,
  resolveSubmissionRunId,
  stageLabel,
  statusLabel,
} from '../learnCopy';

describe('learnCopy — labels', () => {
  it('maps known criterion ids to student language', () => {
    expect(criterionLabel('task_achievement')).toBe('Task achievement');
    expect(criterionLabel('coherence_cohesion')).toBe('Coherence & cohesion');
  });

  it('title-cases unknown snake_case keys', () => {
    expect(criterionLabel('custom_criterion')).toBe('Custom Criterion');
  });

  it('maps reflective stages', () => {
    expect(stageLabel('so_what')).toBe('So what');
    expect(stageLabel('NOW_WHAT')).toBe('Now what');
  });

  it('aligns status vocabulary', () => {
    expect(statusLabel('draft')).toBe('Drafted');
    expect(statusLabel('drafted')).toBe('Drafted');
    expect(statusLabel('open')).toBe('Open');
    expect(statusLabel('published')).toBe('Open');
  });
});

describe('learnCopy — role-aware home', () => {
  it('sends learn-only students to /learn from Platform Home', () => {
    expect(resolveRoleAwareHome('/', {
      capabilities: ['learn:access', 'gradevance:submit'],
    })).toBe('/learn');
  });

  it('sends teach-only markers to /teach', () => {
    expect(resolveRoleAwareHome('/', {
      capabilities: ['teach:access', 'gradevance:mark'],
    })).toBe('/teach');
  });

  it('preserves admin home and remembered non-home paths', () => {
    expect(resolveRoleAwareHome('/', {
      capabilities: ['learn:access'],
      isAdmin: true,
    })).toBe('/');
    expect(resolveRoleAwareHome('/learn/assignments', {
      capabilities: ['learn:access'],
    })).toBe('/learn/assignments');
  });

  it('does not override dual learn+teach users on home', () => {
    expect(resolveRoleAwareHome('/', {
      capabilities: ['learn:access', 'teach:access'],
    })).toBe('/');
  });
});

describe('learnCopy — hydrate + coaching pick', () => {
  it('resolves run id from latest_run object', () => {
    expect(resolveSubmissionRunId({
      latest_run: { id: 'run-1', coaching: {} },
    })).toBe('run-1');
  });

  it('falls back to legacy latest_run_id / run', () => {
    expect(resolveSubmissionRunId({ latest_run_id: 'run-2' })).toBe('run-2');
    expect(resolveSubmissionRunId({ run: { id: 'run-3' } })).toBe('run-3');
  });

  it('picks most recent formative with strengths when available', () => {
    const picked = pickLatestCoaching([
      {
        assignment: 'a1',
        assignment_title: 'Old article',
        created_at: '2026-09-01T00:00:00Z',
        latest_run: {
          id: 'r1',
          created_at: '2026-09-01T00:00:00Z',
          coaching: { diagnosis_actions: [{ diagnosis: 'x', action: 'y' }] },
        },
      },
      {
        assignment: 'a2',
        assignment_title: 'NAA Cycle 1',
        created_at: '2026-09-20T00:00:00Z',
        latest_run: {
          id: 'r2',
          created_at: '2026-09-20T12:00:00Z',
          coaching: { strengths: ['Clear WHAT move'] },
        },
      },
    ]);
    expect(picked.assignmentId).toBe('a2');
    expect(picked.coaching.strengths[0]).toBe('Clear WHAT move');
  });
});
