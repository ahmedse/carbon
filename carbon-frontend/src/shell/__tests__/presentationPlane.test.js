// presentationPlane — Operator / Proof / Analyst view gate (RULE_23).
import { describe, it, expect } from 'vitest';
import {
  presentToolLabel,
  presentSource,
  presentSources,
  presentCaveat,
  presentCaveats,
  presentConsentExpandLabel,
  hasEngineLeakage,
} from '../presentationPlane';

describe('presentationPlane', () => {
  it('maps call_host_api to a business label; never leaks the tool id on operator', () => {
    expect(presentToolLabel('call_host_api', { audience: 'operator' })).toBe('System check');
    expect(
      presentToolLabel('call_host_api', {
        audience: 'operator',
        apiName: 'people.self.leave_balance',
      }),
    ).toBe('Leave balance');
    expect(
      presentToolLabel('call_host_api', {
        audience: 'operator',
        apiName: 'submit_my_leave',
      }),
    ).toBe('Submit leave request');
    expect(
      presentToolLabel('call_host_api', {
        audience: 'operator',
        apiName: 'submit_my_leave',
      }),
    ).not.toMatch(/system check|leave records/i);
    expect(hasEngineLeakage(presentToolLabel('call_host_api', { audience: 'operator' }))).toBe(false);
  });

  it('keeps raw tool id only for analyst audience', () => {
    expect(presentToolLabel('call_host_api', { audience: 'analyst' })).toBe('call_host_api');
  });

  it('omits zero-row noise on operator source chips', () => {
    const chip = presentSource(
      { tool: 'call_host_api', rows_returned: 0, api_name: 'leave/balance' },
      'operator',
    );
    expect(chip.label).toBe('Leave balance');
    expect(chip.label).not.toMatch(/0/);
    expect(hasEngineLeakage(chip.label)).toBe(false);
  });

  it('soft-falls back when sources exist but none map on operator', () => {
    const { chips, softFallback } = presentSources(
      [{ tool: 'totally_unknown_plugin_xyz', rows_returned: 0 }],
      'operator',
    );
    expect(chips).toHaveLength(0);
    expect(softFallback).toBe(true);
  });

  it('rewrites ADR-0046 / host-mutation caveats on operator', () => {
    const presented = presentCaveat(
      { level: 'info', text: 'Chat cannot stage host mutations (ADR-0046 / G2).' },
      'operator',
    );
    expect(presented.text).toMatch(/can’t be submitted in Chat/i);
    expect(presented.text).not.toMatch(/ADR-0046|host mutations|G2/i);
    expect(hasEngineLeakage(presented.text)).toBe(false);
  });

  it('drops engine-only caveats that cannot be rewritten', () => {
    expect(
      presentCaveats(
        [{ level: 'warning', text: 'call_host_api returned status_code=403' }],
        'operator',
      ),
    ).toHaveLength(0);
  });

  it('consent expand uses preparation language, not Details & JSON', () => {
    expect(presentConsentExpandLabel({ open: false })).toBe('How this was prepared');
    expect(presentConsentExpandLabel({ open: true })).toBe('Hide preparation details');
    expect(presentConsentExpandLabel({ open: false })).not.toMatch(/JSON/i);
  });
});
