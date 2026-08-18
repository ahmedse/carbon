// src/__tests__/AIMemoryTabs.test.jsx
// Phase 23-B — Memory & learnt facts tabs:
//   AIMemoryTab   (episodes — event list + filter + empty state)
//   AILearntTab   (facts — confidence/provenance + Forget confirm flow)
//   AIRelationshipTab (empathy surface — every claim paired with why +
//                      forget affordance; explicit empty state)
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

vi.mock('../api/aiWorkspace', () => ({
  listFacts: vi.fn(),
  listEpisodes: vi.fn(),
  getRelationship: vi.fn(),
  forgetFact: vi.fn(),
}));

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

const { notify, notifyFromError } = vi.hoisted(() => ({
  notify: vi.fn(),
  notifyFromError: vi.fn(),
}));

vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify, notifyFromError }),
}));

import AIMemoryTab from '../shell/AIMemoryTab';
import AILearntTab from '../shell/AILearntTab';
import AIRelationshipTab from '../shell/AIRelationshipTab';
import { listFacts, listEpisodes, getRelationship, forgetFact } from '../api/aiWorkspace';

const facts = {
  count: 2,
  results: [
    {
      id: 'fact-1',
      category: 'preference',
      content: 'Prefers CSV exports',
      confidence: 0.9,
      provenance: { source: 'user_feedback:msg-1', created_at: '2026-08-10T09:00:00Z', last_used: '2026-08-12T10:00:00Z' },
      use_count: 3,
      visibility: 'private',
      valid_from: null,
      valid_to: null,
    },
    {
      id: 'fact-2',
      category: 'learned',
      content: 'Budget reviews happen monthly',
      confidence: 0.55,
      provenance: { source: 'conversation:conv-9', created_at: '2026-08-14T12:00:00Z', last_used: null },
      use_count: 0,
      visibility: 'private',
      valid_from: null,
      valid_to: null,
    },
  ],
};

const episodes = {
  count: 2,
  results: [
    {
      id: 'ep-1',
      event_type: 'milestone',
      summary: 'Schema change shipped',
      details: { scope: 'mdm', tables: 3 },
      caused_by_episode_id: null,
      relevance_score: 0.8,
      occurred_at: '2026-08-15T08:30:00Z',
      learned_at: '2026-08-15T08:31:00Z',
      visibility: 'private',
    },
    {
      id: 'ep-2',
      event_type: 'error',
      summary: 'DQ rule failed once',
      details: null,
      caused_by_episode_id: null,
      relevance_score: 0.4,
      occurred_at: '2026-08-16T14:00:00Z',
      learned_at: '2026-08-16T14:01:00Z',
      visibility: 'private',
    },
  ],
};

const relationship = {
  memory_enabled: true,
  memory: {
    fact_count: 2,
    episode_count: 2,
    top_categories: [
      { category: 'preference', count: 1 },
      { category: 'learned', count: 1 },
    ],
    avg_confidence: 0.725,
    total_uses: 3,
  },
  usage: {
    period_days: 30,
    total_tokens: 2500000,
    total_generations: 40,
    total_cost: '3.500000',
    by_model: {},
    quota: { used: 2500000, limit: 5000000 },
  },
  profile: { memory_enabled: true, temperature: 0.3 },
  computed_at: '2026-08-18T10:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
  listFacts.mockResolvedValue(facts);
  listEpisodes.mockResolvedValue(episodes);
  getRelationship.mockResolvedValue(relationship);
  forgetFact.mockResolvedValue('');
});

// ── AIMemoryTab (episodes) ──────────────────────────────────────────────

describe('AIMemoryTab (Phase 23-B)', () => {
  it('renders episode summaries with event type chips', async () => {
    render(<AIMemoryTab />);

    expect(await screen.findByText('Schema change shipped')).toBeInTheDocument();
    expect(screen.getByText('DQ rule failed once')).toBeInTheDocument();
    expect(screen.getByText('milestone')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
    expect(listEpisodes).toHaveBeenCalledWith('test-token', { limit: 100 });
  });

  it('shows an explicit empty state when nothing is recorded', async () => {
    listEpisodes.mockResolvedValue({ count: 0, results: [] });
    render(<AIMemoryTab />);

    expect(await screen.findByText('No events recorded yet.')).toBeInTheDocument();
  });

  it('shows an error with Retry that recovers', async () => {
    listEpisodes.mockRejectedValueOnce(new Error('boom'));
    render(<AIMemoryTab />);

    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(notifyFromError).toHaveBeenCalled();

    listEpisodes.mockResolvedValue(episodes);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Schema change shipped')).toBeInTheDocument();
  });

  it('refetches with the selected event type', async () => {
    render(<AIMemoryTab />);
    await screen.findByText('Schema change shipped');

    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Event type' }));
    const option = await screen.findByRole('option', { name: 'error' });
    fireEvent.click(option);

    await waitFor(() => {
      expect(listEpisodes).toHaveBeenLastCalledWith('test-token', {
        event_type: 'error',
        limit: 100,
      });
    });
  });
});

// ── AILearntTab (facts + forget) ────────────────────────────────────────

describe('AILearntTab (Phase 23-B)', () => {
  it('renders facts with confidence and provenance copy', async () => {
    render(<AILearntTab />);

    expect(await screen.findByText('Prefers CSV exports')).toBeInTheDocument();
    expect(screen.getByText('Budget reviews happen monthly')).toBeInTheDocument();
    expect(screen.getByText(/90% confident/)).toBeInTheDocument();
    expect(screen.getByText(/from your feedback/)).toBeInTheDocument();
    expect(screen.getByText(/used 3×/)).toBeInTheDocument();
    expect(listFacts).toHaveBeenCalledWith('test-token', { limit: 100 });
  });

  it('shows an explicit empty state when nothing is learnt', async () => {
    listFacts.mockResolvedValue({ count: 0, results: [] });
    render(<AILearntTab />);

    expect(await screen.findByText('Nothing learnt yet.')).toBeInTheDocument();
  });

  it('shows an error with Retry that recovers', async () => {
    listFacts.mockRejectedValueOnce(new Error('boom'));
    render(<AILearntTab />);

    expect(await screen.findByText('boom')).toBeInTheDocument();

    listFacts.mockResolvedValue(facts);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Prefers CSV exports')).toBeInTheDocument();
  });

  it('forgets a fact only after explicit confirmation', async () => {
    render(<AILearntTab />);
    await screen.findByText('Prefers CSV exports');

    // Row action opens the confirm dialog.
    fireEvent.click(screen.getAllByRole('button', { name: 'Forget this fact' })[0]);
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Forget this fact?')).toBeInTheDocument();

    // Cancel does nothing.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(forgetFact).not.toHaveBeenCalled();
    expect(screen.getByText('Prefers CSV exports')).toBeInTheDocument();

    // Confirm deletes + removes the row + notifies.
    fireEvent.click(screen.getAllByRole('button', { name: 'Forget this fact' })[0]);
    const dialog2 = await screen.findByRole('dialog');
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Forget' }));

    await waitFor(() => {
      expect(forgetFact).toHaveBeenCalledWith('test-token', 'fact-1');
    });
    await waitFor(() => {
      expect(screen.queryByText('Prefers CSV exports')).not.toBeInTheDocument();
    });
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }));
  });

  it('surfaces a forget failure without removing the fact', async () => {
    forgetFact.mockRejectedValueOnce(new Error('not allowed'));
    render(<AILearntTab />);
    await screen.findByText('Prefers CSV exports');

    fireEvent.click(screen.getAllByRole('button', { name: 'Forget this fact' })[0]);
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Forget' }));

    await waitFor(() => {
      expect(notifyFromError).toHaveBeenCalledWith(expect.any(Error), 'Could not forget this fact');
    });
    expect(screen.getByText('Prefers CSV exports')).toBeInTheDocument();
  });

  it('refetches with the selected category', async () => {
    render(<AILearntTab />);
    await screen.findByText('Prefers CSV exports');

    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Category' }));
    const option = await screen.findByRole('option', { name: 'learned' });
    fireEvent.click(option);

    await waitFor(() => {
      expect(listFacts).toHaveBeenLastCalledWith('test-token', {
        category: 'learned',
        limit: 100,
      });
    });
  });
});

// ── AIRelationshipTab (empathy surface) ─────────────────────────────────

describe('AIRelationshipTab (Phase 23-B)', () => {
  it('shows an explicit, non-creepy empty state when nothing is stored', async () => {
    getRelationship.mockResolvedValue({
      memory_enabled: true,
      memory: { fact_count: 0, episode_count: 0, top_categories: [], avg_confidence: null, total_uses: 0 },
      usage: { total_tokens: 0, total_generations: 0 },
      profile: { memory_enabled: true },
      computed_at: '2026-08-18T10:00:00Z',
    });
    render(<AIRelationshipTab />);

    expect(await screen.findByText('Nothing stored yet.')).toBeInTheDocument();
    // No claims rendered — just the explicit, reassuring empty state.
    expect(screen.queryByText(/facts I've learned about how you work/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/events I remember from our work/i)).not.toBeInTheDocument();
  });

  it('pairs every claim with a why and a forget affordance', async () => {
    const onShowFacts = vi.fn();
    const onShowEpisodes = vi.fn();
    const onShowUsage = vi.fn();
    render(
      <AIRelationshipTab
        onShowFacts={onShowFacts}
        onShowEpisodes={onShowEpisodes}
        onShowUsage={onShowUsage}
      />,
    );

    // Facts claim + why + affordance.
    expect(await screen.findByText(/2 facts I've learned about how you work/)).toBeInTheDocument();
    expect(screen.getByText(/Each one comes from a past conversation/)).toBeInTheDocument();
    const reviewButtons = screen.getAllByRole('button', { name: 'Review & forget' });
    expect(reviewButtons).toHaveLength(2);
    fireEvent.click(reviewButtons[0]); // facts claim affordance
    expect(onShowFacts).toHaveBeenCalled();

    // Episodes claim + why + affordance.
    expect(screen.getByText(/2 events I remember from our work/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(onShowEpisodes).toHaveBeenCalled();

    // Confidence claim + why + affordance.
    expect(screen.getByText(/about 73% sure/)).toBeInTheDocument();
    expect(screen.getByText(/Confidence grows when/)).toBeInTheDocument();

    // Topics claim + why + forget affordance.
    expect(screen.getByText('Topics I keep in mind')).toBeInTheDocument();
    expect(screen.getByText('preference · 1')).toBeInTheDocument();
    expect(screen.getByText('learned · 1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Forget any' }));
    expect(onShowFacts).toHaveBeenCalledTimes(2);

    // Usage claim — why, no forget (usage is not memory).
    expect(screen.getByText(/2\.5M tokens across 40 generations/)).toBeInTheDocument();
    expect(screen.getByText(/never what I remember/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open usage' }));
    expect(onShowUsage).toHaveBeenCalled();

    expect(getRelationship).toHaveBeenCalledWith('test-token');
  });

  it('surfaces a memory-off notice while keeping data visible', async () => {
    getRelationship.mockResolvedValue({
      ...relationship,
      memory_enabled: false,
      profile: { memory_enabled: false, temperature: 0.3 },
    });
    render(<AIRelationshipTab />);

    expect(await screen.findByText('Memory off')).toBeInTheDocument();
    expect(screen.getByText(/nothing new will be stored/)).toBeInTheDocument();
    // Existing data still visible (reads are never gated).
    expect(screen.getByText(/2 facts I've learned/)).toBeInTheDocument();
  });

  it('shows an error with Retry that recovers', async () => {
    getRelationship.mockRejectedValueOnce(new Error('boom'));
    render(<AIRelationshipTab />);

    expect(await screen.findByText('boom')).toBeInTheDocument();

    getRelationship.mockResolvedValue(relationship);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText(/2 facts I've learned about how you work/)).toBeInTheDocument();
  });
});
