// src/__tests__/AIContextPanel.test.jsx
// Phase 3B — context panel renders scope/mentions/budget and calls summarize.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AIContextPanel from '../shell/AIContextPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../components/NotificationProvider', () => ({
  useNotification: () => ({ notify: vi.fn(), notifyFromError: vi.fn() }),
}));
vi.mock('../api/aiWorkspace', () => ({
  summarizeConversation: vi.fn(),
}));

import { summarizeConversation } from '../api/aiWorkspace';

const baseConversation = {
  id: 'conv-1',
  conversation_type: 'dq_validate',
  app_identifier: 'platform',
  scope_json: { org_unit_ids: ['1', '2'] },
  // Backend budget keys (see backend/ai/context_assembler.py) + retrieved KG entities.
  context_snapshot_json: {
    T2_history: 420,
    T2b_summary: 120,
    T3_retrieval: 340,
    T4_memory: 0,
    kg_entities: [
      { name: 'monthly_electricity', node_type: 'ENTITY', confidence: 1.0, attributes: ['month', 'total_kwh'] },
    ],
  },
  summary: '',
};

function renderPanel(props = {}) {
  return render(
    <AIContextPanel conversation={baseConversation} mentions={[]} {...props} />,
  );
}

describe('AIContextPanel', () => {
  beforeEach(() => summarizeConversation.mockReset());

  it('shows toggle button and is collapsed by default', () => {
    renderPanel();
    expect(screen.getByLabelText('Show context panel')).toBeInTheDocument();
  });

  it('expands and shows scope chips on toggle', () => {
    renderPanel();
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText('dq_validate')).toBeInTheDocument();
    expect(screen.getByText('platform')).toBeInTheDocument();
  });

  it('renders resolved mentions when panel is open', () => {
    const mentions = [{ kind: 'table', id: '35', name: 'Electricity' }];
    renderPanel({ mentions });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText('Electricity')).toBeInTheDocument();
  });

  it('renders token budget bars for non-zero tiers', () => {
    renderPanel();
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(screen.getByText('Summary')).toBeInTheDocument();
    expect(screen.getByText('KG Retrieval')).toBeInTheDocument();
  });

  it('renders retrieved knowledge-graph entities with attributes', () => {
    renderPanel();
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('monthly_electricity')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('month, total_kwh')).toBeInTheDocument();
  });

  it('shows "None retrieved" when no kg entities present', () => {
    renderPanel({ conversation: { ...baseConversation, context_snapshot_json: {} } });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText(/none retrieved/i)).toBeInTheDocument();
  });

  it('shows placeholder when no context snapshot', () => {
    renderPanel({ conversation: { ...baseConversation, context_snapshot_json: {} } });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText(/available after first message/i)).toBeInTheDocument();
  });

  it('calls summarizeConversation and invokes onSummarized', async () => {
    const updated = { ...baseConversation, summary: 'Rolling summary text.' };
    summarizeConversation.mockResolvedValue(updated);
    const onSummarized = vi.fn();
    renderPanel({ onSummarized });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    fireEvent.click(screen.getByRole('button', { name: /summarize now/i }));

    await waitFor(() => expect(summarizeConversation).toHaveBeenCalledWith('test-token', 'conv-1', false));
    await waitFor(() => expect(onSummarized).toHaveBeenCalledWith(updated));
  });

  it('shows existing summary text when present', () => {
    const convWithSummary = { ...baseConversation, summary: 'This is a rolling summary of the conversation.' };
    renderPanel({ conversation: convWithSummary });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText(/rolling summary/i)).toBeInTheDocument();
  });

  it('"No matches" hint shown when mentions empty', () => {
    renderPanel({ mentions: [] });
    fireEvent.click(screen.getByLabelText('Show context panel'));
    expect(screen.getByText(/type # to mention/i)).toBeInTheDocument();
  });
});
