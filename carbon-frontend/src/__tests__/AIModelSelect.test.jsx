// src/__tests__/AIModelSelect.test.jsx
// Phase 18 — AI Workspace chat-model picker.
// Phase 20-B — tier grouping (⚡ Fast / ⚖ Balanced / 🧠 Brain), deprecated
// models hidden from the picker, cost + context hints from the catalog.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));
vi.mock('../api/aiWorkspace', () => ({
  listModels: vi.fn(),
}));

import { listModels } from '../api/aiWorkspace';
import AIModelSelect, { AI_MODEL_STORAGE_KEY } from '../shell/AIModelSelect';

const MODELS = [
  {
    id: 'gpt-4o',
    label: 'GPT-4o',
    description: 'High-quality general-purpose model.',
    input_cost_per_1m: 2.5,
    output_cost_per_1m: 10.0,
    is_default: true,
    tier: 'brain',
    context_window: 128000,
    deprecated: false,
    superseded_by: null,
  },
  {
    id: 'gpt-4o-mini',
    label: 'GPT-4o mini',
    description: 'Fast and economical.',
    input_cost_per_1m: 0.15,
    output_cost_per_1m: 0.6,
    is_default: false,
    tier: 'fast',
    context_window: 128000,
    deprecated: false,
    superseded_by: null,
  },
  {
    id: 'claude-sonnet-4.5',
    label: 'Claude Sonnet 4.5',
    description: 'Balanced model for analysis and multi-step reasoning.',
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    is_default: false,
    tier: 'balanced',
    context_window: 200000,
    deprecated: false,
    superseded_by: null,
  },
  {
    id: 'claude-3-5-sonnet',
    label: 'Claude 3.5 Sonnet',
    description: 'Previous-generation Sonnet, retired in favor of Sonnet 4.5.',
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    is_default: false,
    tier: 'balanced',
    context_window: 200000,
    deprecated: true,
    superseded_by: 'claude-sonnet-4.5',
  },
];

beforeEach(() => {
  localStorage.clear();
  listModels.mockResolvedValue({ models: MODELS });
});

afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('AIModelSelect', () => {
  it('renders the default model and notifies the parent', async () => {
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);

    expect(await screen.findByText('GPT-4o')).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('gpt-4o'));
    expect(localStorage.getItem(AI_MODEL_STORAGE_KEY)).toBe('gpt-4o');
  });

  it('persists a new selection and notifies the parent', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);
    await screen.findByText('GPT-4o');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));
    await user.click(await screen.findByRole('option', { name: /GPT-4o mini/ }));

    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith('gpt-4o-mini'));
    expect(localStorage.getItem(AI_MODEL_STORAGE_KEY)).toBe('gpt-4o-mini');
  });

  it('restores the stored model and reports it to the parent', async () => {
    localStorage.setItem(AI_MODEL_STORAGE_KEY, 'gpt-4o-mini');
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);

    expect(await screen.findByText('GPT-4o mini')).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('gpt-4o-mini'));
  });

  it('shows cost details in the menu options', async () => {
    const user = userEvent.setup();
    render(<AIModelSelect onChange={vi.fn()} />);
    await screen.findByText('GPT-4o');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    expect(await screen.findByText(/High-quality general-purpose model/)).toBeInTheDocument();
    expect(screen.getByText(/\$2\.50 in · \$10\.00 out \/ 1M tokens/)).toBeInTheDocument();
  });

  // ── Phase 20-B — tier grouping + deprecated filtering ────────────────

  it('groups options by tier with Fast / Balanced / Brain headers in order', async () => {
    const user = userEvent.setup();
    render(<AIModelSelect onChange={vi.fn()} />);
    await screen.findByText('GPT-4o');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('⚡ Fast')).toBeInTheDocument();
    expect(within(listbox).getByText('⚖ Balanced')).toBeInTheDocument();
    expect(within(listbox).getByText('🧠 Brain')).toBeInTheDocument();

    // Headers render in tier order, each followed by its own models.
    const text = listbox.textContent;
    expect(text.indexOf('⚡ Fast')).toBeLessThan(text.indexOf('⚖ Balanced'));
    expect(text.indexOf('⚖ Balanced')).toBeLessThan(text.indexOf('🧠 Brain'));
    expect(text.indexOf('⚡ Fast')).toBeLessThan(text.indexOf('Fast and economical.'));
    expect(text.indexOf('⚖ Balanced')).toBeLessThan(
      text.indexOf('Balanced model for analysis and multi-step reasoning.'),
    );
    expect(text.indexOf('🧠 Brain')).toBeLessThan(
      text.indexOf('High-quality general-purpose model.'),
    );
  });

  it('hides deprecated models from the picker', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);
    await screen.findByText('GPT-4o');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).queryByText('Claude 3.5 Sonnet')).not.toBeInTheDocument();
    // The deprecated model is also not selectable as the resolved default.
    expect(onChange).toHaveBeenCalledWith('gpt-4o');
  });

  it('resolves a stored deprecated model id back to the active default', async () => {
    localStorage.setItem(AI_MODEL_STORAGE_KEY, 'claude-3-5-sonnet');
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);

    expect(await screen.findByText('GPT-4o')).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('gpt-4o'));
    expect(localStorage.getItem(AI_MODEL_STORAGE_KEY)).toBe('gpt-4o');
  });

  it('shows the context-window hint from catalog fields', async () => {
    const user = userEvent.setup();
    render(<AIModelSelect onChange={vi.fn()} />);
    await screen.findByText('GPT-4o');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    // Two active models share the 128K window; only the balanced one has 200K.
    expect(within(listbox).getAllByText(/128K context/).length).toBeGreaterThan(0);
    expect(within(listbox).getByText(/200K context/)).toBeInTheDocument();
  });
});
