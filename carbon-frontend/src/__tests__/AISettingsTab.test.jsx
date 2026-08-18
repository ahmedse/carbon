// src/__tests__/AISettingsTab.test.jsx
// Phase 22-B — Preferences tab: loads /ai/profile/ + model catalog, edits via
// optimistic PATCH, error + Retry, and clear-default-model semantics.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../api/aiWorkspace', () => ({
  getProfile: vi.fn(),
  patchProfile: vi.fn(),
  listModels: vi.fn(),
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

import AISettingsTab from '../shell/AISettingsTab';
import { getProfile, listModels, patchProfile } from '../api/aiWorkspace';

const profile = {
  default_model_id: 'gpt-4o',
  resolved_model_id: 'gpt-4o',
  temperature: 0.7,
  auto_title: true,
  memory_enabled: false,
  usage_alert_threshold: 50,
};

const modelData = {
  models: [
    { id: 'gpt-4o', label: 'GPT-4o', tier: 'brain', is_default: true, deprecated: false },
    { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash', tier: 'fast', deprecated: false },
    { id: 'retired-model', label: 'Retired', tier: 'fast', deprecated: true },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  getProfile.mockResolvedValue(profile);
  listModels.mockResolvedValue(modelData);
  patchProfile.mockResolvedValue(profile);
});

describe('AISettingsTab loading + error states', () => {
  it('renders stored preferences once loaded', async () => {
    render(<AISettingsTab />);

    expect(await screen.findByRole('combobox', { name: 'Default model' })).toHaveTextContent('GPT-4o');
    expect(screen.getByRole('slider', { name: 'Temperature' })).toHaveAttribute('aria-valuenow', '0.7');
    expect(screen.getByRole('checkbox', { name: 'Auto-title conversations' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Long-term memory' })).not.toBeChecked();
    expect(screen.getByRole('slider', { name: 'Usage alert threshold' })).toHaveAttribute('aria-valuenow', '50');
    expect(getProfile).toHaveBeenCalledWith('test-token');
    expect(listModels).toHaveBeenCalledWith('test-token');
  });

  it('shows an error with Retry when loading fails, then recovers', async () => {
    getProfile.mockRejectedValueOnce(new Error('boom'));
    render(<AISettingsTab />);

    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(notifyFromError).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('combobox', { name: 'Default model' })).toHaveTextContent('GPT-4o');
  });
});

describe('AISettingsTab model dropdown', () => {
  it('lists System default + active catalog models grouped by tier, excluding deprecated', async () => {
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Default model' }));

    expect(await screen.findByRole('option', { name: 'System default' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /GPT-4o/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /DeepSeek V4 Flash/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Retired/ })).not.toBeInTheDocument();
  });
});

describe('AISettingsTab saving', () => {
  it('is disabled until a change is made, then PATCHes the form and notifies', async () => {
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    const save = screen.getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-title conversations' }));
    expect(save).toBeEnabled();

    fireEvent.click(save);

    await waitFor(() => {
      expect(patchProfile).toHaveBeenCalledWith('test-token', {
        default_model_id: 'gpt-4o',
        temperature: 0.7,
        auto_title: false,
        memory_enabled: false,
        usage_alert_threshold: 50,
      });
    });
    expect(notify).toHaveBeenCalledWith({ message: 'Preferences saved', type: 'success' });
  });

  it('clears the model override when System default is chosen (PATCH null)', async () => {
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Default model' }));
    fireEvent.click(await screen.findByRole('option', { name: 'System default' }));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(patchProfile).toHaveBeenCalledWith('test-token', expect.objectContaining({ default_model_id: null }));
    });
  });

  it('syncs the form to the server response after save (optimistic round-trip)', async () => {
    patchProfile.mockResolvedValue({ ...profile, temperature: 1.0 });
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    const slider = screen.getByRole('slider', { name: 'Temperature' });
    fireEvent.keyDown(slider, { key: 'ArrowRight' }); // +0.1 → 0.8
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByRole('slider', { name: 'Temperature' })).toHaveAttribute('aria-valuenow', '1');
    });
  });

  it('Reset restores the loaded profile and disables Save again', async () => {
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-title conversations' }));
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: 'Auto-title conversations' })).toBeChecked();
  });

  it('notifies from error when the PATCH fails', async () => {
    patchProfile.mockRejectedValueOnce(new Error('nope'));
    render(<AISettingsTab />);
    await screen.findByRole('combobox', { name: 'Default model' });

    fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-title conversations' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(notifyFromError).toHaveBeenCalledWith(expect.any(Error), 'Could not save preferences');
    });
  });
});
