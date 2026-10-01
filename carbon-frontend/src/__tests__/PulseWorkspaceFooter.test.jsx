import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PulsePrefsProvider } from '../shell/pulsePrefs';
import PulseWorkspaceFooter from '../shell/PulseWorkspaceFooter';
import { pulseReleaseLabel, releaseTooltip } from '../shell/releaseTooltip';

const setLanguage = vi.hoisted(() => vi.fn());

vi.mock('../i18n/useLanguage', () => ({
  useLanguage: () => ({ lang: 'en', isRtl: false, setLanguage, ready: true }),
}));

vi.mock('../shell/AIModelSelect', () => ({
  default: () => <div data-testid="model-select" />,
  AI_MODEL_STORAGE_KEY: 'ai.selectedModel',
}));

vi.mock('../shell/PulsePresence', () => ({ default: () => null }));

function healthResponse(release) {
  return {
    ok: true,
    json: async () => ({ release }),
  };
}

describe('PulseWorkspaceFooter', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => null }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

  it('switches the app to Arabic, which flips the page to RTL', () => {
    render(
      <PulsePrefsProvider>
        <PulseWorkspaceFooter variant="ready" label="Ready" />
      </PulsePrefsProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'العربية' }));
    expect(setLanguage).toHaveBeenCalledWith('ar');
  });

  it('shows pack identity from health when the release tag is absent', async () => {
    const release = {
      tag: '',
      pack: 'nibras',
      pack_version: '17',
      image_built_at: null,
      process_started_at: '2026-10-01T10:27:40.718869+00:00',
    };
    fetch.mockResolvedValue(healthResponse(release));
    render(
      <PulsePrefsProvider>
        <PulseWorkspaceFooter variant="ready" label="Ready" />
      </PulsePrefsProvider>,
    );
    const chip = await screen.findByTestId('pulse-release');
    expect(chip).toHaveTextContent('nibras 17');
    expect(chip).toHaveAttribute(
      'aria-label',
      'nibras 17\nstarted 2026-10-01T10:27:40.718869+00:00',
    );
    expect(releaseTooltip(release)).toBe(chip.getAttribute('aria-label'));
  });

  it('shows the release tag as the build and keeps pack version on a separate line', async () => {
    const release = {
      tag: 'nibras-v0.1.55',
      pack: 'nibras',
      pack_version: '16',
      image_built_at: '2026-10-01T10:24:22Z',
      process_started_at: '2026-10-01T10:28:09.247199+00:00',
    };
    fetch.mockResolvedValue(healthResponse(release));
    render(
      <PulsePrefsProvider>
        <PulseWorkspaceFooter variant="ready" label="Ready" />
      </PulsePrefsProvider>,
    );
    const chip = await screen.findByTestId('pulse-release');
    expect(chip).toHaveTextContent('v0.1.55');
    expect(pulseReleaseLabel(release)).toBe('v0.1.55');
    expect(chip).toHaveAttribute(
      'aria-label',
      'nibras-v0.1.55\nnibras 16\nbuilt 2026-10-01T10:24:22Z\nstarted 2026-10-01T10:28:09.247199+00:00',
    );
  });
});
