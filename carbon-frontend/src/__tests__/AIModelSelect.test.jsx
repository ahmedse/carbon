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
    id: 'deepseek-flash',
    label: 'DeepSeek Flash',
    description: 'Cheapest default.',
    input_cost_per_1m: 0.3,
    output_cost_per_1m: 1.2,
    is_default: true,
    tier: 'fast',
    context_window: 1000000,
    deprecated: false,
    superseded_by: null,
  },
  {
    id: 'gpt-4o',
    label: 'GPT-4o',
    description: 'High-quality general-purpose model.',
    input_cost_per_1m: 2.5,
    output_cost_per_1m: 10.0,
    is_default: false,
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
    id: 'claude-haiku-4.5',
    label: 'Claude Haiku 4.5',
    description: 'Low-latency Claude model.',
    input_cost_per_1m: 1.0,
    output_cost_per_1m: 5.0,
    is_default: false,
    tier: 'fast',
    context_window: 200000,
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

    expect(await screen.findByText('DeepSeek Flash')).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('deepseek-flash'));
    expect(localStorage.getItem(AI_MODEL_STORAGE_KEY)).toBe('deepseek-flash');
  });

  it('persists a new selection and notifies the parent', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);
    await screen.findByText('DeepSeek Flash');

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
    await screen.findByText('DeepSeek Flash');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    expect(await screen.findByText(/Cheapest default/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.30 in · \$1\.20 out \/ 1M tokens/)).toBeInTheDocument();
    expect(screen.queryByText(/High-quality general-purpose model/)).not.toBeInTheDocument();
  });

  // ── Phase 20-B — tier grouping + deprecated filtering ────────────────

  it('groups options by tier with Fast / Balanced / Brain headers in order', async () => {
    const user = userEvent.setup();
    render(<AIModelSelect onChange={vi.fn()} />);
    await screen.findByText('DeepSeek Flash');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).getByText('⚡ Fast')).toBeInTheDocument();
    expect(within(listbox).queryByText('⚖ Balanced')).not.toBeInTheDocument();
    expect(within(listbox).queryByText('🧠 Brain')).not.toBeInTheDocument();
    expect(within(listbox).getByText(/DeepSeek Flash/)).toBeInTheDocument();
    expect(within(listbox).getByText('GPT-4o mini')).toBeInTheDocument();
    expect(within(listbox).getByText('Claude Haiku 4.5')).toBeInTheDocument();
    expect(within(listbox).queryByText('GPT-4o')).not.toBeInTheDocument();
    expect(within(listbox).queryByText('Claude Sonnet 4.5')).not.toBeInTheDocument();
  });

  it('hides deprecated models from the picker', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);
    await screen.findByText('DeepSeek Flash');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    expect(within(listbox).queryByText('Claude 3.5 Sonnet')).not.toBeInTheDocument();
    // The deprecated model is also not selectable as the resolved default.
    expect(onChange).toHaveBeenCalledWith('deepseek-flash');
  });

  it('resolves a stored deprecated model id back to the active default', async () => {
    localStorage.setItem(AI_MODEL_STORAGE_KEY, 'claude-3-5-sonnet');
    const onChange = vi.fn();
    render(<AIModelSelect onChange={onChange} />);

    expect(await screen.findByText('DeepSeek Flash')).toBeInTheDocument();
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('deepseek-flash'));
    expect(localStorage.getItem(AI_MODEL_STORAGE_KEY)).toBe('deepseek-flash');
  });

  it('shows the context-window hint from catalog fields', async () => {
    const user = userEvent.setup();
    render(<AIModelSelect onChange={vi.fn()} />);
    await screen.findByText('DeepSeek Flash');

    await user.click(screen.getByRole('combobox', { name: 'Select AI model' }));

    const listbox = await screen.findByRole('listbox');
    // Two active models share the 128K window; only the balanced one has 200K.
    expect(within(listbox).getAllByText(/128K context/).length).toBeGreaterThan(0);
    expect(within(listbox).getByText(/200K context/)).toBeInTheDocument();
  });
});
