import { describe, it, expect, beforeEach } from 'vitest';
import {
  AUTONOMY_KEY,
  autonomyDefaultListOpen,
  readAutonomyMode,
  writeAutonomyMode,
} from '../autonomyMode';

describe('autonomyMode', () => {
  beforeEach(() => {
    localStorage.removeItem(AUTONOMY_KEY);
  });

  it('defaults to balanced', () => {
    expect(readAutonomyMode()).toBe('balanced');
  });

  it('persists a valid mode', () => {
    expect(writeAutonomyMode('careful')).toBe('careful');
    expect(readAutonomyMode()).toBe('careful');
  });

  it('rejects unknown modes', () => {
    expect(writeAutonomyMode('yolo')).toBe('balanced');
  });

  it('careful opens the list; awaiting never auto-opens Analyst wall', () => {
    expect(autonomyDefaultListOpen('careful', { finished: true })).toBe(true);
    expect(autonomyDefaultListOpen('fast', { finished: true })).toBe(false);
    expect(autonomyDefaultListOpen('balanced', { finished: true })).toBe(false);
    expect(autonomyDefaultListOpen('balanced', { awaiting: true })).toBe(false);
    expect(autonomyDefaultListOpen('careful', { awaiting: true })).toBe(false);
  });
});
