import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { apiFetch } from '../../../../api/api';
import ExcellenceLadderPage from '../ExcellenceLadderPage';
import ExcellenceSubjectPage from '../ExcellenceSubjectPage';

const LEVELS = ['Unmanaged', 'Declared', 'Specified', 'Built', 'Proven', 'Operated', 'Excellent'];

const ladder = {
  head: 'abc1234def',
  latest_event_id: 3,
  problems: [],
  tiers: [
    { id: 'platform', title: 'Platform core', owner: 'owner', level_names: LEVELS, tracks: [] },
    {
      id: 'pulse', title: 'Pulse', owner: 'pulse-master', level_names: LEVELS,
      tracks: [{ id: 'chat', title: 'Chat' }, { id: 'agent', title: 'Agent' }],
    },
  ],
  subjects: [
    {
      subject_id: 'platform.module.accounts', title: 'accounts', tier: 'platform', track: '', kind: 'module',
      level: 3, level_name: 'Built', dimensions: { correct: 3, governed: 4 }, next: ['PLAT-COR-02'], counts: {},
    },
    {
      subject_id: 'pulse.chat.turn', title: 'Chat turn', tier: 'pulse', track: 'chat', kind: 'process',
      level: 2, level_name: 'Specified', dimensions: { correct: 2 }, next: [], counts: {},
    },
    {
      subject_id: 'pulse.agent.planner', title: 'planner', tier: 'pulse', track: 'agent', kind: 'module',
      level: 3, level_name: 'Built', dimensions: { correct: 3 }, next: ['PLAT-COR-02'], counts: {},
    },
  ],
};

const subject = {
  subject_id: 'platform.module.accounts', title: 'accounts', tier: 'platform', track: '', kind: 'module',
  owner: 'owner', level: 3, level_name: 'Built', head: 'abc1234def', dimensions: { correct: 3 },
  next: ['PLAT-COR-02'], paths: ['backend/accounts'], tests: [], spec: [], adr: [],
  checks: [
    { check_id: 'PLAT-GOV-01', title: 'Subject has a named owner', rank: 1, dimension: 'governed', state: 'passed', evidence_class: 'executed', source: 'manifest:owner', solution: 'Set owner.' },
    { check_id: 'PLAT-COR-02', title: 'Module test suite executed green on HEAD', rank: 4, dimension: 'correct', state: 'unmeasured', evidence_class: 'configured', source: '', solution: 'python -m excellence.gauge --run pytest:<app>' },
  ],
  events: [{ id: 1, check_id: 'PLAT-GOV-01', result: 'passed', commit: 'abc1234def', source: 'manifest:owner', at: '2026-09-24T12:00:00Z' }],
  exemptions: [],
  trend: [{ date: '2026-09-24', level: 3, commit: 'abc1234def', dimensions: {} }],
};

vi.mock('../../../../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'staff-token' }),
}));

vi.mock('../../../../api/api', () => ({
  apiFetch: vi.fn(),
  apiFetchStream: vi.fn(async () => ({ ok: false, body: null })),
}));

function defaultFetch(url, opts = {}) {
  if (url === 'excellence/runs/' && opts.method === 'POST') {
    return Promise.resolve({ id: 9, status: 'succeeded', event_count: 12, ladder });
  }
  if (url.startsWith('excellence/subjects/')) return Promise.resolve(subject);
  if (url.startsWith('assurance/')) {
    return Promise.resolve({
      commit: 'x', blocking_not_passed: 0, rows: [
        { rule_id: 'PL-SSE-01', pack: 'platform', journey: 'Live', meaning: 'stream', label: 'configured', reason: 'none', residual: 'n', blocks_release: false },
      ],
    });
  }
  return Promise.resolve(ladder);
}

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockImplementation(defaultFetch);
});

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/excellence" element={<ExcellenceLadderPage />} />
        <Route path="/admin/excellence/rules" element={<ExcellenceLadderPage />} />
        <Route path="/admin/excellence/subjects/:subjectId" element={<ExcellenceSubjectPage />} />
        <Route path="/admin/excellence/:tier" element={<ExcellenceLadderPage />} />
        <Route path="/admin/excellence/:tier/:track" element={<ExcellenceLadderPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ExcellenceLadderPage', () => {
  it('defaults to the platform tier and shows level and next step', async () => {
    renderAt('/admin/excellence');
    expect(await screen.findByText('accounts')).toBeTruthy();
    expect(screen.getByText('L3 Built')).toBeTruthy();
    expect(screen.getByText('PLAT-COR-02')).toBeTruthy();
    expect(screen.queryByText('Chat turn')).toBeNull();
  });

  it('filters a tier by track', async () => {
    renderAt('/admin/excellence/pulse');
    expect(await screen.findByText('Chat turn')).toBeTruthy();
    expect(screen.getByText('planner')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Chat' }));
    expect(await screen.findByText('Chat turn')).toBeTruthy();
    expect(screen.queryByText('planner')).toBeNull();
  });

  it('shows the rules board under Excellence', async () => {
    renderAt('/admin/excellence/rules');
    expect(await screen.findByText('PL-SSE-01')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Rules' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('measures with the selected collector', async () => {
    renderAt('/admin/excellence');
    expect(await screen.findByText('accounts')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Measure' }));
    expect(await screen.findByText(/Run #9/)).toBeTruthy();
  });
});

describe('ExcellenceSubjectPage', () => {
  it('shows checks with their state and how to earn the next level', async () => {
    renderAt('/admin/excellence/subjects/platform.module.accounts');
    expect(await screen.findByText('Subject has a named owner')).toBeTruthy();
    expect(screen.getByText('unmeasured')).toBeTruthy();
    expect(screen.getByText('python -m excellence.gauge --run pytest:<app>')).toBeTruthy();
    expect(screen.getByText('2026-09-24 · L3')).toBeTruthy();
  });
});
