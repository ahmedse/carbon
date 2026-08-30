// src/__tests__/SkillLearningPanel.test.jsx
// Wave B, task B3 — Skill Learning progression view (Pulse 0.2 #3).
// Backed by GET /ai/pulse/skills/ (getPulseSkills) returning a top-level array.
// Verifies the drafted → promoted → reused arc is legible, all counts derive
// from the API array (never UI-invented), and the four grounded states render
// honestly (loading / offline / empty / zero-reused).
//
// This panel does NOT use CarbonDataGrid, so no ResizeObserver /
// getBoundingClientRect stubs are required.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import SkillLearningPanel from '../pages/admin/ai/SkillLearningPanel';

let mockAuth = { token: 'test-token', userCapabilities: [] };

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const getPulseSkills = vi.fn();

vi.mock('../api/aiPulse', () => ({
  getPulseSkills: (...args) => getPulseSkills(...args),
}));

/** Minimal skill factory matching the backend contract. */
function skill(overrides = {}) {
  return {
    name: 'Skill',
    kind: 'prompt',
    status: 'draft',
    usage_count: 0,
    success_rate: 0.9,
    avg_latency_ms: 120,
    last_executed_at: '2026-08-30T00:00:00Z',
    promoted_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth = { token: 'test-token', userCapabilities: [] };
  getPulseSkills.mockResolvedValue([]);
});

describe('SkillLearningPanel — progression view', () => {
  it('renders the three stages and the reused skills after load', async () => {
    getPulseSkills.mockResolvedValue([
      skill({ name: 'DraftSkill', status: 'draft', usage_count: 0 }),
      skill({ name: 'PromotedIdle', status: 'instance_promoted', usage_count: 0 }),
      skill({ name: 'HotPathSkill', status: 'instance_promoted', usage_count: 3 }),
    ]);

    render(<SkillLearningPanel />);

    expect(await screen.findByText('Drafted')).toBeInTheDocument();
    expect(screen.getByText('Promoted')).toBeInTheDocument();
    expect(screen.getByText('Reused')).toBeInTheDocument();

    expect(await screen.findByText('HotPathSkill')).toBeInTheDocument();
    expect(screen.getByText('3 uses')).toBeInTheDocument();
  });

  it('shows an honest empty state and never invents zero counts', async () => {
    getPulseSkills.mockResolvedValue([]);

    render(<SkillLearningPanel />);

    expect(
      await screen.findByText(
        /No skills yet — draft a skill from the AI workspace to start the learning flywheel/,
      ),
    ).toBeInTheDocument();

    // The empty branch renders no stepper at all (no fake zero stage cards).
    expect(screen.queryByText('Drafted')).not.toBeInTheDocument();
    expect(screen.queryByText('Promoted')).not.toBeInTheDocument();
    expect(screen.queryByText('Reused')).not.toBeInTheDocument();
  });

  it('shows an honest zero-reused message without fabricated usage numbers', async () => {
    getPulseSkills.mockResolvedValue([
      skill({ name: 'DraftSkill', status: 'draft', usage_count: 0 }),
      skill({ name: 'PromotedIdle', status: 'instance_promoted', usage_count: 0 }),
    ]);

    render(<SkillLearningPanel />);

    expect(
      await screen.findByText(/No skills have been reused yet — promote a skill/),
    ).toBeInTheDocument();

    // The stepper still renders real drafted/promoted counts…
    expect(screen.getByText('Drafted')).toBeInTheDocument();
    expect(screen.getByText('Promoted')).toBeInTheDocument();
    expect(screen.getByText('Reused')).toBeInTheDocument();

    // …but no skill is listed as reused (no fabricated usage count entries).
    expect(screen.queryByText('DraftSkill')).not.toBeInTheDocument();
    expect(screen.queryByText('PromotedIdle')).not.toBeInTheDocument();
  });

  it('shows the offline paper when the API rejects', async () => {
    getPulseSkills.mockRejectedValue(new Error('offline'));

    render(<SkillLearningPanel />);

    expect(await screen.findByText('Data unavailable')).toBeInTheDocument();
    expect(screen.getByText(/the skill learning API is offline/)).toBeInTheDocument();
  });

  it('formats success_rate and null timestamps defensively', async () => {
    getPulseSkills.mockResolvedValue([
      skill({
        name: 'LuckySkill',
        status: 'instance_promoted',
        usage_count: 1,
        success_rate: 0.85,
        last_executed_at: null,
      }),
    ]);

    render(<SkillLearningPanel />);

    expect(await screen.findByText('LuckySkill')).toBeInTheDocument();
    expect(screen.getByText('85% success')).toBeInTheDocument();
    expect(screen.getByText('Last run: —')).toBeInTheDocument();
  });
});
