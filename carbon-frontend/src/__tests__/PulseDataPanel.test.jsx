// src/__tests__/PulseDataPanel.test.jsx — drill-down helper unit tests.
// Covers the pure formatters powering the Pulse read-only console's row
// detail drawer: defensive cell formatting, scope label collapse, and the
// thin-grid deepen helpers (type filter, evidence href, column presets).
import { describe, it, expect } from 'vitest';
import {
  formatCellValue,
  buildScopeLabel,
  buildDetailFields,
  listRowTypes,
  buildEvidenceHref,
  resolveColumnFields,
} from '../pages/admin/ai/pulseFormat';

describe('formatCellValue', () => {
  it('renders null/undefined/empty as em-dash', () => {
    expect(formatCellValue(null)).toBe('—');
    expect(formatCellValue(undefined)).toBe('—');
    expect(formatCellValue('')).toBe('—');
  });

  it('stringifies arrays and objects as JSON', () => {
    expect(formatCellValue([1, 2, 3])).toBe('[1,2,3]');
    expect(formatCellValue({ a: 1 })).toBe('{"a":1}');
  });

  it('truncates long JSON to 80 chars with ellipsis', () => {
    const long = { key: 'x'.repeat(120) };
    const out = formatCellValue(long);
    expect(out.length).toBe(80 + 1); // 80 chars + ellipsis
    expect(out.endsWith('…')).toBe(true);
  });

  it('passes through scalars as strings', () => {
    expect(formatCellValue(42)).toBe('42');
    expect(formatCellValue('hello')).toBe('hello');
    expect(formatCellValue(false)).toBe('false');
  });
});

describe('buildScopeLabel', () => {
  it('joins app/org/user/visibility into one line', () => {
    const label = buildScopeLabel({
      app_identifier: 'carbon',
      org_unit_id: 7,
      host_user_id: 'u-1',
      visibility: 'private',
    });
    expect(label).toBe('carbon · org:7 · user:u-1 · private');
  });

  it('returns em-dash when no scope fields present', () => {
    expect(buildScopeLabel({})).toBe('—');
  });
});

describe('buildDetailFields', () => {
  it('excludes _type and scope helper columns', () => {
    const fields = buildDetailFields({
      _type: 'conversation',
      id: 'conv-1',
      app_identifier: 'carbon',
      org_unit_id: 7,
      host_user_id: 'u-1',
      visibility: 'private',
      title: 'Session',
    });
    const keys = fields.map((f) => f.key);
    expect(keys).not.toContain('_type');
    expect(keys).not.toContain('app_identifier');
    expect(keys).not.toContain('org_unit_id');
    expect(keys).not.toContain('host_user_id');
    expect(keys).not.toContain('visibility');
    expect(keys).toContain('id');
    expect(keys).toContain('title');
  });

  it('formats values through formatCellValue', () => {
    const fields = buildDetailFields({ _type: 'x', name: null, count: 5 });
    expect(fields).toEqual([
      { key: 'name', value: '—' },
      { key: 'count', value: '5' },
    ]);
  });
});

describe('listRowTypes', () => {
  it('returns sorted distinct _type values', () => {
    expect(
      listRowTypes([
        { _type: 'ToolExecution' },
        { _type: 'TaskExecution' },
        { _type: 'ToolExecution' },
        {},
      ]),
    ).toEqual(['TaskExecution', 'ToolExecution']);
  });

  it('returns empty for empty input', () => {
    expect(listRowTypes([])).toEqual([]);
    expect(listRowTypes(null)).toEqual([]);
  });
});

describe('buildEvidenceHref', () => {
  it('prefers run_id then conversation_id', () => {
    expect(buildEvidenceHref({ run_id: 'r1' })).toBe(
      '/admin/ai/evidence?tab=explorer&run_id=r1',
    );
    expect(buildEvidenceHref({ plan_id: 'p1' })).toBe(
      '/admin/ai/evidence?tab=explorer&run_id=p1',
    );
    expect(buildEvidenceHref({ conversation_id: 'c1' })).toBe(
      '/admin/ai/evidence?tab=explorer&conversation_id=c1',
    );
  });

  it('returns null when no reconstructable id', () => {
    expect(buildEvidenceHref({})).toBeNull();
    expect(buildEvidenceHref(null)).toBeNull();
  });
});

describe('resolveColumnFields', () => {
  it('orders preset fields first for tools', () => {
    const fields = resolveColumnFields('tools', [
      { status: 'ok', run_id: 'r1', noise: 1, tool_name: 'x' },
    ]);
    expect(fields[0]).toBe('tool_name');
    expect(fields).toContain('status');
    expect(fields).toContain('run_id');
    expect(fields).toContain('noise');
  });

  it('falls back to dynamic keys when no preset match', () => {
    const fields = resolveColumnFields('unknown', [{ foo: 1, bar: 2 }]);
    expect(fields).toEqual(['bar', 'foo']);
  });
});
