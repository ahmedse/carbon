import { describe, expect, it } from 'vitest';
import { humanizeStepError } from '../humanizeStepError';

describe('humanizeStepError', () => {
  it('summarizes sandbox file-write PermissionError', () => {
    const raw = [
      'Traceback (most recent call last):',
      '  File "<string>", line 12, in <module>',
      "PermissionError: file write blocked in sandbox (mode='w+')",
    ].join('\n');
    const { summary, detail } = humanizeStepError(raw);
    expect(summary).toMatch(/Chart code tried to save a file/i);
    expect(detail).toContain('PermissionError');
  });

  it('keeps short plain errors as-is', () => {
    const { summary, detail } = humanizeStepError('Entity not found');
    expect(summary).toBe('Entity not found');
    expect(detail).toBe('');
  });
});
