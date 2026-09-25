import { describe, it, expect, beforeEach } from 'vitest';
import { readContentZoom, readDenseThinking } from '../shell/pulsePrefs';

describe('pulsePrefs helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('reads stored zoom and Think', () => {
    localStorage.setItem('ai.contentZoom', '1.2');
    localStorage.setItem('pulse.denseThinking', '1');
    expect(readContentZoom()).toBe(1.2);
    expect(readDenseThinking()).toBe(true);
  });
});
