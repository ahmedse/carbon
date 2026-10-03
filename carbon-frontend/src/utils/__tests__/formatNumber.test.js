import { describe, it, expect } from 'vitest';
import { formatNumber, formatPercent } from '../formatNumber';

// ADR-0018 §6: numbers are formatted with Intl, never by concatenating the raw
// API string. The API returns 4-decimal strings ("80.0000", "500000.0000");
// the UI must trim them and group thousands.
describe('formatNumber / formatPercent', () => {
  it('trims trailing zeros from percent values', () => {
    expect(formatPercent('80.0000')).toBe('80%');
    expect(formatPercent('100.0000')).toBe('100%');
    expect(formatPercent('0.00')).toBe('0%');
  });

  it('keeps meaningful percent precision', () => {
    expect(formatPercent('44.44')).toBe('44.44%');
    expect(formatPercent(12.3456)).toBe('12.35%');
  });

  it('groups thousands and trims absolute values', () => {
    expect(formatNumber('500000.0000')).toBe('500,000');
    expect(formatNumber(1234.5678)).toBe('1,234.57');
    expect(formatNumber(50)).toBe('50');
  });

  it('renders an honest dash for an absent value — never 0', () => {
    expect(formatNumber(null)).toBe('—');
    expect(formatNumber(undefined)).toBe('—');
    expect(formatNumber('')).toBe('—');
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent('not-a-number')).toBe('—');
  });

  it('uses Latin digits for Arabic (ar-EG-u-nu-latn)', () => {
    expect(formatNumber('500000.0000', { lang: 'ar' })).toBe('500,000');
    expect(formatPercent('80.0000', { lang: 'ar' })).toBe('80%');
  });
});
