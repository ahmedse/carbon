// src/__tests__/AIModelSelect.test.jsx
// Phase 18 — AI Workspace chat-model picker.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
  },
  {
    id: 'gpt-4o-mini',
    label: 'GPT-4o mini',
    description: 'Fast and economical.',
    input_cost_per_1m: 0.15,
    output_cost_per_1m: 0.6,
    is_default: false,
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
});
