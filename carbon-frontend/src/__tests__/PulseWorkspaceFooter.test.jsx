import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PulsePrefsProvider } from '../shell/pulsePrefs';
import PulseWorkspaceFooter from '../shell/PulseWorkspaceFooter';

vi.mock('../shell/AIModelSelect', () => ({
  default: () => <div data-testid="model-select" />,
  AI_MODEL_STORAGE_KEY: 'ai.selectedModel',
}));

vi.mock('../shell/PulsePresence', () => ({ default: () => null }));

describe('PulseWorkspaceFooter', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('is the same bar for Chat and Tasks: Ready, Think, fonts, model', () => {
    render(
      <PulsePrefsProvider>
        <PulseWorkspaceFooter variant="ready" label="Ready" />
      </PulsePrefsProvider>,
    );
    expect(screen.getByTestId('pulse-workspace-footer')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Think/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /decrease text size/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /increase text size/i })).toBeInTheDocument();
    expect(screen.getByTestId('model-select')).toBeInTheDocument();
  });

  it('Think writes the shared key so Tasks keep the same choice', () => {
    render(
      <PulsePrefsProvider>
        <PulseWorkspaceFooter variant="ready" label="Ready" />
      </PulsePrefsProvider>,
    );
    fireEvent.click(screen.getByRole('checkbox', { name: /Think/i }));
    expect(localStorage.getItem('pulse.denseThinking')).toBe('1');
  });
});
