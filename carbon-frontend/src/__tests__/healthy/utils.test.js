// src/__tests__/healthy/utils.test.js
// Pure helper unit tests (no rendering, no mocks).

import { describe, it, expect } from 'vitest';
import {
  churnRiskLevel,
  arRiskLevel,
  slowMoverSeverity,
  formatCurrency,
  formatPercent,
  buildLoadoutCsv,
} from '../../apps/healthy/utils';

describe('healthy utils', () => {
  it('churnRiskLevel buckets probabilities', () => {
    expect(churnRiskLevel(null)).toEqual({ label: 'No data', color: 'default' });
    expect(churnRiskLevel(0.1)).toEqual({ label: 'Low risk', color: 'success' });
    expect(churnRiskLevel(0.45)).toEqual({ label: 'At risk', color: 'warning' });
    expect(churnRiskLevel(0.8)).toEqual({ label: 'High risk', color: 'error' });
  });

  it('arRiskLevel buckets scores', () => {
    expect(arRiskLevel(0.2)).toEqual({ label: 'Low', color: 'success' });
    expect(arRiskLevel(0.5)).toEqual({ label: 'Medium', color: 'warning' });
    expect(arRiskLevel(0.9)).toEqual({ label: 'High', color: 'error' });
    expect(arRiskLevel(undefined)).toEqual({ label: 'Unknown', color: 'default' });
  });

  it('slowMoverSeverity classifies forecasts', () => {
    expect(slowMoverSeverity(0)).toBe('dead');
    expect(slowMoverSeverity(-3)).toBe('dead');
    expect(slowMoverSeverity(5)).toBe('slow');
    expect(slowMoverSeverity(25)).toBe('moving');
    expect(slowMoverSeverity(null)).toBe('unknown');
  });

  it('formats currency and percent defensively', () => {
    expect(formatCurrency(1250)).toBe('$1,250');
    expect(formatCurrency(null)).toBe('—');
    expect(formatPercent(0.42)).toBe('42%');
    expect(formatPercent(null)).toBe('—');
  });

  it('buildLoadoutCsv emits header and item rows with escaping', () => {
    const csv = buildLoadoutCsv([
      {
        week_start: '2026-01-05',
        rep_code: 'R1',
        rep_name: 'Ana',
        line_items: [
          { item_code: 'A1', item_name: 'Milk, 2L', qty_forecast: 10, qty_actual: 9, return_rate_forecast: 0.1 },
        ],
      },
    ]);
    expect(csv.split('\n')[0]).toBe(
      'week_start,rep_code,rep_name,item_code,item_name,qty_forecast,qty_actual,return_rate_forecast',
    );
    expect(csv).toContain('2026-01-05,R1,Ana,A1,"Milk, 2L",10,9,0.1');
  });

  it('buildLoadoutCsv emits a row for sheets with no line items', () => {
    const csv = buildLoadoutCsv([{ week_start: '2026-01-05', rep_code: 'R9', rep_name: 'Zed', line_items: [] }]);
    const lines = csv.split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[1].split(',')).toHaveLength(8);
    expect(lines[1]).toContain('2026-01-05,R9,Zed');
  });
});
